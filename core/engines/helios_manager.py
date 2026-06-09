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

_active_processes = []
_open_log_files = []

def _get_rpc_list(env_var: str) -> list:
    raw_val = os.getenv(env_var, "")

    if not raw_val:
        return []
    return [url.strip() for url in raw_val.split(",") if url.strip()]

def start_helios_node(network: str, el_rpc_list: list, cl_rpc_list: list, rpc_port: int, el_idx: int = 0, cl_idx: int = 0) -> subprocess.Popen:
    if not HELIOS_BIN.exists():
        raise FileNotFoundError(f"[FATAL] helios_manager: Binary not found at {HELIOS_BIN}")
    
    if not el_rpc_list:
        raise ValueError(f"[FATAL] helios_manager: Missing Execution RPC for {network}")
    
    current_el = el_rpc_list[el_idx % len(el_rpc_list)]
    current_cl = cl_rpc_list[cl_idx % len(cl_rpc_list)] if cl_rpc_list else None

    if network == "ethereum":
        command = [
            str(HELIOS_BIN),
            "ethereum",
            "--execution-rpc", current_el,
            "--rpc-port", str(rpc_port)
        ]
        if current_cl:
            command.extend(["--consensus-rpc", current_cl])

    elif network == "base":
        command = [
            str(HELIOS_BIN),
            "opstack",
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
    print(f"[ LOG ] helios_manager: Target EL -> {current_el[:45]}")

    if current_cl:
        print(f"[ LOG ] helios_manager: Target CL/L1 -> {current_cl[:45]}")
    print(f"[ LOG ] helios_manager: Tailing logs to -> {log_path}")

    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

    _active_processes.append(process)

    failed_health_check = False
    for _ in range(12):
        time.sleep(1)

        if process.poll() is not None:
            failed_health_check = True
            break

        try:
            with open(log_path, "r") as f:
                live_log = f.read().lower()
                if "429" in live_log or "404" in live_log or "too many requests" in live_log:
                    print(f"[ WARN ] helios_manager: Rate limit (429) or 404 detected. Assassinating zombie process...")
                    process.terminate()
                    process.wait()
                    failed_health_check = True
                    break
        except FileNotFoundError:
            pass

    if failed_health_check:
        print(f"[ ALERT ] helios_manager: {network.capitalize()} client failed health check. Executing failover sequence...")

        if process in _active_processes:
            _active_processes.remove(process)
        if log_file in _open_log_files:
            _open_log_files.remove(log_file)
        log_file.close()

        with open(log_path, "r") as f:
            error_content = f.read()

        rpc_errors = ["503", "rpc error", "failed to advance", "error decoding", "status:", "429", "404"]

        if any(err in error_content.lower() for err in rpc_errors):
            next_el_idx = el_idx
            next_cl_idx = cl_idx

            if network == "ethereum" and len(cl_rpc_list) > 1 and (cl_idx + 1) < len(cl_rpc_list):
                print("[ LOG ] helios_manager: Consensus endpoint failed or throttled. Rotating to backup pool...")
                next_cl_idx += 1
            elif len(el_rpc_list) > 1 and (el_idx + 1) < len(el_rpc_list):
                print(f"[ LOG ] helios_manager: {network.capitalize()} Execution endpoint failed. Rotating to backup pool...")
                next_el_idx += 1
            else:
                print(f"[FATAL] helios_manager: Network endpoints exhausted for {network}. No backups remain.")
                return None
            
            return start_helios_node(network, el_rpc_list, cl_rpc_list, rpc_port, next_el_idx, next_cl_idx)
        
        else:
            print(f"[FATAL] helios_manager: Network endpoints exhausted for {network}. No backups remain.")
            return None
        
    return process

def boot_engines():
    eth_el_pool = _get_rpc_list("ETH_EXECUTION_RPC")
    eth_cl_pool = _get_rpc_list("ETH_CONSENSUS_RPC")
    start_helios_node("ethereum", eth_el_pool, eth_cl_pool, 8545)

    base_el_pool = _get_rpc_list("BASE_EXECUTION_RPC")
    base_cl_pool = _get_rpc_list("BASE_CONSENSUS_RPC")
    start_helios_node("base", base_el_pool, base_cl_pool, 8546)

def _cleanup_zombies():
    for proc in _active_processes:
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

    for log_file in _open_log_files:
        if not log_file.closed:
            log_file.close()

    if _active_processes:
        print("[ LOG ] helios_manager: All active Helios nodes successfully terminated and logs saved.")

atexit.register(_cleanup_zombies)

if __name__ == "__main__":
    try:
        boot_engines()
        print("[ LOG ] helios_manager: Engines running. Press Ctrl+C to gracefully exit.")

        while True:
            time.sleep(1)

    except Exception as e:
        print(f"[FATAL] helios_manager: An error occurred - {e}")