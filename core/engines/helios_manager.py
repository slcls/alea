import os
import atexit
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
HELIOS_BIN = BIN_DIR / "helios"

_active_processes = []

def start_helios_node(network: str, el_rpc: str, cl_rpc: str, rpc_port: int) -> subprocess.Popen:
    if not HELIOS_BIN.exists():
        raise FileNotFoundError(f"[ERROR] helios_manager: Binary not found at {HELIOS_BIN}")
    
    if not el_rpc:
        raise ValueError(f"[ERROR] helios_manager: Missing Execution RPC for {network}")
    
    command = [
        str(HELIOS_BIN),
        "--network", network,
        "--execution-rpc", el_rpc,
        "--consensus-rpc", cl_rpc,
        "--rpc-port", str(rpc_port)
    ]

    print(f"[ LOG ] helios_manager: Starting Helios ({network}) on port {rpc_port}...")

    