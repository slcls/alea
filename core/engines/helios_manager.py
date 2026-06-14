import os
import atexit
import subprocess
import time
import json
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = time.strftime("%Y%m%d_%H%M%S")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
HELIOS_BIN = BIN_DIR / "helios"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

_active_nodes = []
_open_log_files = []

def _get_rpc_list(env_var: str) -> list:
    raw_val = os.getenv(env_var, "")
    if not raw_val:
        return []
    return [url.strip() for url in raw_val.split(",") if url.strip()]

def fetch_dynamic_checkpoint(cl_url: str) -> str:
    clean_url = cl_url.rstrip('/')
    target = f"{clean_url}/eth/v1/beacon/headers/finalized"

    try:
        req = urllib.request.Request(target, headers={'User-Agent': 'Alea-Supervisor/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            root = data.get('data', {}).get('root')

            if root:
                print(f"[ LOG ] helios_manager: Acquired dynamic L1 checkpoint {root[:10]}... from {clean_url}")
                return root
            
    except Exception:
        pass

    return None

def start_nodes(network: str, el_rpc_list: list, cl_rpc_list: list, rpc_port: int, el_idx: int = 0, cl_idx: int = 0) -> dict:
    if not HELIOS_BIN.exists():
        raise FileNotFoundError(f"[FATAL] helios_manager: Binary not found at {HELIOS_BIN}")
    if not el_rpc_list:
        raise ValueError(f"[FATAL] helios_manager: Missing Execution RPC for {network}")
    
    current_el = el_rpc_list[el_idx % len(el_rpc_list)]
    current_cl = cl_rpc_list[cl_idx % len(cl_rpc_list)] if cl_rpc_list else None
    checkpoint_root = None

    if network == "ethereum":
        command = [
            str(HELIOS_BIN), "ethereum",
            "--execution-rpc", current_el,
            "--rpc-port", str(rpc_port)
        ]
        
        if cl_rpc_list:
            for offset in range(len(cl_rpc_list)):
                candidate_idx = (cl_idx + offset) % len(cl_rpc_list)
                candidate_url = cl_rpc_list[candidate_idx]

                root = fetch_dynamic_checkpoint(candidate_url)

                if root:
                    checkpoint_root = root
                    current_cl = candidate_url
                    cl_idx = candidate_idx
                    break

            if current_cl:
                command.extend(["--consensus-rpc", current_cl])

        if checkpoint_root:
            command.extend(["--checkpoint", checkpoint_root])
        else:
            print("[ WARN ] helios_manager: All dynamic checkpoints failed or unavailable. Falling back to beaconcha.in")
            command.extend(["--fallback", "https://sync-mainnet.beaconcha.in"])

    elif network == "base":
        command = [
            str(HELIOS_BIN), "opstack",
            "--network", "base",
            "--execution-rpc", current_el,
            "--rpc-port", str(rpc_port)
        ]

    else:
        raise ValueError(f"[FATAL] helios_manager: Unsupported network '{network}'")
    
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"helios_{network}_{rpc_port}_{SESSION_ID}.log"

    initial_file_size = os.path.getsize(log_path) if log_path.exists() else 0

    log_file = open(log_path, "a")
    _open_log_files.append(log_file)

    print(f"[ LOG ] helios_manager: Booting {network.capitalize()} Light Client on port {rpc_port}")
    print(f"[ LOG ] helios_manager: Target EL -> {current_el[:45]}")

    if current_cl: 
        print(f"[ LOG ] helios_manager: Target CL/L1 -> {current_cl[:45]}")

    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)

    return {
        "network": network, "process": process, "log_path": log_path,
        "el_list": el_rpc_list, "cl_list": cl_rpc_list, "port": rpc_port,
        "el_idx": el_idx, "cl_idx": cl_idx, "log_file": log_file, "failed": False,
        "first_error_ts": None, "last_read_pos": initial_file_size
    }

def _cleanup():
    for node in _active_nodes:
        if not node["failed"] and node["process"].poll() is None:
            node["process"].terminate()
            node["process"].wait()
    
    for f in _open_log_files:
        if not f.closed: 
            f.close()

    if _active_nodes:
        print("\n[ LOG ] helios_manager: All active Helios nodes successfully terminated and logs saved.")

atexit.register(_cleanup)

if __name__ == "__main__":
    eth_el = _get_rpc_list("ETH_EXECUTION_RPC")
    eth_cl = _get_rpc_list("ETH_CONSENSUS_RPC")
    base_el = _get_rpc_list("BASE_EXECUTION_RPC")
    base_cl = _get_rpc_list("BASE_CONSENSUS_RPC")

    try:
        _active_nodes.append(start_nodes("ethereum", eth_el, eth_cl, 8545))

        print("[ LOG ] helios_manager: Allowing L1 peer handshake to settle (10s delay)...")
        time.sleep(10)

        _active_nodes.append(start_nodes("base", base_el, base_cl, 8546))
        print("\n[ SYSTEM ] helios_manager: Continuous Supervisor Active. Press Ctrl+C to exit.\n")

        while True:
            time.sleep(2)
            
            for i, node in enumerate(_active_nodes):
                if node["failed"]: 
                    continue

                proc = node["process"]
                is_dead = proc.poll() is not None
                is_zombie = False
                new_logs = ""

                if not is_dead:
                    try:
                        with open(node["log_path"], "r") as f:
                            f.seek(node["last_read_pos"])
                            new_logs = f.read().lower()
                            node["last_read_pos"] = f.tell()

                        has_rate_limit = any(x in new_logs for x in ["status: 429", "status: 404", "too many requests", "rate limit"])
                        has_recovery = any(x in new_logs for x in ["latest block", "saved checkpoint", "synced"])

                        if has_rate_limit and node["first_error_ts"] is None:
                            node["first_error_ts"] = time.time()

                        if has_recovery:
                            if node["first_error_ts"] is not None:
                                print(f"[ LOG ] helios_manager: {node['network'].capitalize()} successfully recovered. Resetting status trackers.")
                            node["first_error_ts"] = None
                
                    except Exception:
                        pass

                if node["first_error_ts"] is not None:
                    elapsed_errors = time.time() - node["first_error_ts"]
                    if elapsed_errors >= 45:
                        is_zombie = True
                    else:
                        print(f"[ ALERT ] helios_manager: {node['network'].capitalize()} experiencing transport friction ({int(elapsed_errors)}s/45s window). Sustaining node.")

                if is_dead or is_zombie:
                    net = node["network"].capitalize()

                    if is_zombie:
                        print(f"[ WARN ] helios_manager: {net} exceeded error state grace window. Executing tactical shutdown...")
                        proc.terminate()
                        proc.wait()
                    else:
                        print(f"[ WARN ] helios_manager: {net} crashed natively. Analyzing telemetry...")
                    
                    node["failed"] = True
                    node["log_file"].close()

                    if node["log_file"] in _open_log_files:
                        _open_log_files.remove(node["log_file"])

                    try:
                        with open(node["log_path"], "r") as f:
                            f.seek(0, os.SEEK_END)
                            file_size = f.tell()
                            f.seek(max(file_size - 5000, 0), os.SEEK_SET)
                            error_content = f.read().lower()
                    except Exception:
                        error_content = ""

                    next_el, next_cl = node["el_idx"], node["cl_idx"]
                    cl_pool, el_pool = node["cl_list"], node["el_list"]

                    is_execution_fault = "execution" in error_content or "el" in error_content
                    is_consensus_fault = "consensus" in error_content or "cl" in error_content

                    if not is_execution_fault and not is_consensus_fault:
                        is_execution_fault = True

                    if is_zombie or any(err in error_content for err in ["503", "rpc error", "failed to advance", "status:"]):
                        if node["network"] == "ethereum" and is_consensus_fault and len(cl_pool) > 1 and (next_cl + 1) < len(cl_pool):
                            print(f"[ LOG ] helios_manager: Identified Consensus layer failure. Rotating CL pool...")
                            next_cl += 1
                        elif len(el_pool) > 1 and (next_el + 1) < len(el_pool):
                            print(f"[ LOG ] helios_manager: Identified Execution layer failure. Rotating EL pool...")
                            next_el += 1
                        elif node["network"] == "ethereum" and len(cl_pool) > 1 and (next_cl + 1) < len(cl_pool):
                            print(f"[ LOG ] helios_manager: EL exhausted. Shifting fault domain to clear CL pool...")
                            next_cl += 1
                        else:
                            print(f"[FATAL] helios_manager: {net} pool configurations thoroughly exhausted.")
                            continue

                        _active_nodes[i] = start_nodes(node["network"], el_pool, cl_pool, node["port"], next_el, next_cl)

                    else:
                        print(f"[FATAL] helios_manager: Structural crash detected. Diagnostics saved at: {node['log_path']}")

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[FATAL] helios_manager: Supervisor engine failure - {e}")