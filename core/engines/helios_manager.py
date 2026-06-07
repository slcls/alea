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

def start_helios_node(network: str, el_rpc: str, cl_rpc: str, rpc_port: int) -> subprocess.Popen:
    if not HELIOS_BIN.exists():
        raise FileNotFoundError(f"[FATAL] helios_manager: Binary not found at {HELIOS_BIN}")
    
    if not el_rpc:
        raise ValueError(f"[FATAL] helios_manager: Missing Execution RPC for {network}")
    
    if network == "ethereum" and not cl_rpc:
        raise ValueError(f"[FATAL] helios_manager: Missing Consensus RPC for {network}. Light client cannot verify state.")
    
    command = [
        str(HELIOS_BIN),
        "--network", network,
        "--execution-rpc", el_rpc,
        "--rpc-port", str(rpc_port)
    ]

    if cl_rpc:
        command.extend(["--consensus-rpc", cl_rpc])

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"helios_{network}_{rpc_port}.log"

    log_file = open(log_path, "a")
    _open_log_files.append(log_file)

    print(f"[ LOG ] helios_manager: Booting {network.capitalize()} Light Client on port {rpc_port}...")
    print(f"[ LOG ] helios_manager: Tailing logs to -> {log_path}")

    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

    _active_processes.append(process)
    return process

def boot_engines():
    eth_el = os.getenv("ETH_EXECUTION_RPC")
    eth_cl = os.getenv("ETH_CONSENSUS_RPC")
    start_helios_node("ethereum", eth_el, eth_cl, 8545)

    base_el = os.getenv("BASE_EXECUTION_RPC")
    base_cl = os.getenv("BASE_CONSENSUS_RPC")
    start_helios_node("base", base_el, base_cl, 8546)

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