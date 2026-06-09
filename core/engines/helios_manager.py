import os
import atexit
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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

def start_nodes(network: str, el_rpc_list: list, cl_rpc_list: list, rpc_port: int, el_idx: int = 0, cl_idx: int = 0) -> dict:
    if not HELIOS_BIN.exists():
        raise FileNotFoundError(f"[FATAL] helios_manager: Binary not found at {HELIOS_BIN}")
    if not el_rpc_list:
        raise ValueError(f"[FATAL] helios_manager: Missing Execution RPC for {network}")
    
    current_el = el_rpc_list[el_idx % len(el_rpc_list)]
    current_cl = cl_rpc_list[cl_idx % len(cl_rpc_list)] if cl_rpc_list else None

    if network == "ethereum":
        command = [
            str(HELIOS_BIN), "ethereum",
            "--execution-rpc", current_el,
            "--rpc-port", str(rpc_port),
            "--fallback", "https://sync-mainnet.beaconcha.in"
        ]
        if current_cl: 
            command.extend(["--consensus-rpc", current_cl])

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
    log_path = LOG_DIR / f"helios_{network}_{rpc_port}.log"

    log_file = open(log_path, "w")
    _open_log_files.append(log_file)

    print(f"[ LOG ] helios_manager: Booting {network.capitalize()} Light Client on port {rpc_port}")
    print(f"[ LOG ] helios_manager: Target EL -> {current_el[:45]}...")

    if current_cl: 
        print(f"[ LOG ] helios_manager: Target CL/L1 -> {current_cl[:45]}...")

    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)

    return {
        "network": network, "process": process, "log_path": log_path,
        "el_list": el_rpc_list, "cl_list": cl_rpc_list, "port": rpc_port,
        "el_idx": el_idx, "cl_idx": cl_idx, "log_file": log_file, "failed": False
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
                error_content = ""

                if not is_dead:
                    try:
                        with open(node["log_path"], "r") as f:
                            f.seek(0, os.SEEK_END)
                            file_size = f.tell()
                            f.seek(max(file_size - 2000, 0), os.SEEK_SET)
                            error_content = f.read().lower()

                            if "429" in error_content or "too many requests" in error_content or "404" in error_content:
                                is_zombie = True
                    
                    except Exception:
                        pass

                if is_dead or is_zombie:
                    net = node["network"].capitalize()

                    if is_zombie:
                        print(f"[ WARN ] helios_manager: {net} hit a Rate Limit (429/404). Assassinating zombie process...")
                        proc.terminate()
                        proc.wait()
                    else:
                        print(f"[ WARN ] helios_manager: {net} crashed natively. Analyzing telemetry...")
                    
                    node["failed"] = True
                    node["log_file"].close()
                    if node["log_file"] in _open_log_files:
                        _open_log_files.remove(node["log_file"])

                    next_el, next_cl = node["el_idx"], node["cl_idx"]
                    cl_pool, el_pool = node["cl_list"], node["el_list"]
                    rpc_errors = ["503", "rpc error", "failed to advance", "error decoding", "status:", "429", "404", "too many requests"]

                    if any(err in error_content for err in rpc_errors) or is_zombie:

                        if node["network"] == "ethereum" and len(cl_pool) > 1 and (next_cl + 1) < len(cl_pool):
                            print(f"[ LOG ] helios_manager: {net} Consensus endpoint throttled. Rotating CL backup pool...")
                            next_cl += 1
                        elif len(el_pool) > 1 and (next_el + 1) < len(el_pool):
                            print(f"[ LOG ] helios_manager: {net} Execution endpoint throttled. Rotating EL backup pool...")
                            next_el += 1
                        else:
                            print(f"[FATAL] helios_manager: {net} endpoints exhausted. No backups remain.")
                            continue

                        _active_nodes[i] = start_nodes(node["network"], el_pool, cl_pool, node["port"], next_el, next_cl)

                    else:
                        print(f"[FATAL] helios_manager: Core crash detected. Review error logs natively at: {node['log_path']}")

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[FATAL] helios_manager: Supervisor engine failure - {e}")