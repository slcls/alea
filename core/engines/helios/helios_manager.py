import os
import asyncio
import json
import urllib.request
import logging
from enum import Enum
from typing import Optional
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HELIOS_BIN = PROJECT_ROOT / "bin" / "helios"

logger = logging.getLogger("Alea.Supervisor")
logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

class NodeState(Enum):
    BOOTING = "BOOTING"
    SYNCING = "SYNCING"
    HEALTHY = "HEALTHY"
    DEAD = "DEAD"

class HeliosNode:
    def __init__(self, network: str, el_rpc: str, cl_rpc: str, port: int):
        self.network = network
        self.el_rpc = el_rpc
        self.cl_rpc = cl_rpc
        self.port = port

        self.state = NodeState.BOOTING
        self.process: Optional[asyncio.subprocess.Process] = None
        self.stream_task: Optional[asyncio.Task] = None
        self.checkpoint_root: Optional[str] = None

    async def fetch_checkpoint(self) -> bool:
        logger.info(f"[{self.network.upper()}] Requesting dynamic checkpoint from local proxy...")

        def fetch():
            req = urllib.request.Request(
                f"{self.cl_rpc.rstrip('/')}/eth/v1/beacon/headers/finalized", 
                headers={'User-Agent': 'Alea-Supervisor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode())
            
        try:
            cl_res = await asyncio.to_thread(fetch)
            root = cl_res.get('data', {}).get('root')
            if not root:
                return False
            
            self.checkpoint_root = root
            logger.info(f"[{self.network.upper()}] Checkpoint acquired: {root[:10]}...")
            return True
        except Exception as e:
            logger.error(f"[{self.network.upper()}] Failed to fetch checkpoint from proxy: {e}")
            return False
        
    async def start(self):
        if self.network == "ethereum" and self.cl_rpc:
            success = await self.fetch_checkpoint()
            if not success:
                logger.error(f"[{self.network.upper()}] Boot aborted. Cannot reach CL proxy.")
                self.state = NodeState.DEAD
                return
            
        cmd = [str(HELIOS_BIN)]

        if self.network == "ethereum":
            cmd.extend(["ethereum", "--execution-rpc", self.el_rpc, "--rpc-port", str(self.port)])
            if self.cl_rpc:
                cmd.extend(["--consensus-rpc", self.cl_rpc])
            if self.checkpoint_root:
                cmd.extend(["--checkpoint", self.checkpoint_root])
            else:
                cmd.extend(["--fallback", "https://sync-mainnet.beaconcha.in"])
        
        elif self.network == "base":
            cmd.extend(["opstack", "--network", "base", "--execution-rpc", self.el_rpc, "--rpc-port", str(self.port)])

        logger.info(f"[{self.network.upper()}] Booting Light Client on port {self.port}...")
        self.state = NodeState.BOOTING

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        self.stream_task = asyncio.create_task(self.consume_stream())

    async def consume_stream(self):
        if not self.process or not self.process.stdout:
            return
        
        while not self.process.stdout.at_eof():
            line_bytes = await self.process.stdout.readline()
            if not line_bytes:
                break

            line = line_bytes.decode('utf-8', errors='ignore').strip()
            line_lower = line.lower()

            if any(x in line_lower for x in ["latest block", "saved checkpoint", "synced"]):
                if self.state != NodeState.HEALTHY:
                    logger.info(f"[{self.network.upper()}] Node successfully synced and healthy.")
                    self.state = NodeState.HEALTHY

            elif any(x in line_lower for x in ["status: 429", "too many requests"]):
                logger.warning(f"[{self.network.upper()}] Helios detected a rate limit leaking through the proxy.")

        if self.process.returncode is not None:
            logger.error(f"[{self.network.upper()}] Process crashed natively.")
            self.state = NodeState.DEAD

    async def terminate(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
        if self.stream_task:
            self.stream_task.cancel()

async def main_supervisor():
    eth_node = HeliosNode("ethereum", el_rpc="http://127.0.0.1:43200", cl_rpc="http://127.0.0.1:43201", port=43210)
    base_node = HeliosNode("base", el_rpc="http://127.0.0.1:43202", cl_rpc="", port=43211)

    nodes = [eth_node, base_node]

    for node in nodes:
        await node.start()
        await asyncio.sleep(2)
    
    logger.info("[ SYSTEM ] Async Supervisor Active. Press Ctrl+C to exit.")

    try:
        while True:
            await asyncio.sleep(5)

            for node in nodes:
                if node.state == NodeState.DEAD:
                    logger.warning(f"[{node.network.upper()}] Process is DEAD. Restarting...")
                    await node.terminate()
                    await asyncio.sleep(2)
                    await node.start()

    except asyncio.CancelledError:
        logger.info("[ SYSTEM ] Shutdown signal received. Terminating nodes...")
    finally:
        for node in nodes:
            await node.terminate()

if __name__ == "__main__":
    if not HELIOS_BIN.exists():
        logger.error(f"FATAL: Helios binary not found at {HELIOS_BIN}")
        exit(1)

    try:
        asyncio.run(main_supervisor())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] Gracefully exited.")