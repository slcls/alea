import os
import asyncio
import json
import urllib.request
import logging
from enum import Enum
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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
    THROTTLED = "THROTTLED"
    DEAD = "DEAD"

class HeliosNode:
    def __init__(self, network: str, el_rpcs: list[str], cl_rpcs: list[str], port: int):
        self.network = network
        self.el_rpcs = el_rpcs
        self.cl_rpcs = cl_rpcs
        self.port = port

        self.state = NodeState.BOOTING
        self.process: Optional[asyncio.subprocess.Process] = None
        self.stream_task: Optional[asyncio.Task] = None

        self.el_idx = 0
        self.cl_idx = 0
        self.checkpoint_root: Optional[str] = None

    @property
    def current_el(self) -> str:
        return self.el_rpcs[self.el_idx % len(self.el_rpcs)] if self.el_rpcs else ""
    
    @property
    def current_cl(self) -> str:
        return self.cl_rpcs[self.cl_idx % len(self.cl_rpcs)] if self.cl_rpcs else ""

    def rotate_el(self):
        self.el_idx += 1
        logger.warning(f"[{self.network.upper()}] Rotating EL pool -> {self.current_el[:45]}...")

    def rotate_cl(self):
        self.cl_idx += 1
        logger.warning(f"[{self.network.upper()}] Rotating CL pool -> {self.current_cl[:45]}...")

    async def _async_http_post(self, url: str, payload: dict, timeout=5) -> dict:
        def fetch():
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Alea-Supervisor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
            
        return await asyncio.to_thread(fetch)

    async def _async_http_get(self, url: str, timeout=5) -> dict:
        def fetch():
            req = urllib.request.Request(url, headers={'User-Agent': 'Alea-Supervisor/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        
        return await asyncio.to_thread(fetch)

    async def validate_upstream_rpcs(self) -> bool:
        logger.info(f"[{self.network.upper()}] Running pre-flight checks...")

        try:
            el_payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
            el_res = await self._async_http_post(self.current_el, el_payload)

            if 'error' in el_res or 'result' not in el_res:
                return False

        except Exception as e:
            logger.error(f"[{self.network.upper()}] EL Pre-flight failed: {e}")
            return False

        if self.current_cl == "ethereum" and self.current_cl:
            try:
                cl_target = f"{self.current_cl.rstrip('/')}/eth/v1/beacon/headers/finalized"
                cl_res = await self._async_http_get(cl_target)

                root = cl_res.get('data', {}).get('root')
                if not root:
                    return False
                
                self.checkpoint_root = root
                logger.info(f"[{self.network.upper()}] Pre-flight passed. Checkpoint: {root[:10]}...")

            except Exception as e:
                logger.error(f"[{self.network.upper()}] CL Pre-flight failed (Likely no Altair support): {e}")
                return False
            
        return True

    async def start(self):
        if not await self.validate_upstream_rpcs():
            self.state = NodeState.DEAD
            return
        
        cmd = [str(HELIOS_BIN)]
        if self.network == "ethereum":
            cmd.extend(["ethereum", "--execution-rpc", self.current_el, "--rpc-port", str(self.port)])
            if self.current_cl:
                cmd.extend(["--consensus-rpc", self.current_cl])
            if self.checkpoint_root:
                cmd.extend(["--checkpoint", self.checkpoint_root])
            else:
                cmd.extend(["--fallback", "https://sync-mainnet.beaconcha.in"])
        
        elif self.network == "base":
            cmd.extend(["opstack", "--network", "base", "--execution-rpc", self.current_el, "--rpc-port", str(self.port)])

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

            elif any(x in line_lower for x in ["status: 429", "status: 404", "too many requests", "rate limit", "status: 503"]):
                logger.warning(f"[{self.network.upper()}] Detected HTTP Rate Limit / Friction.")
                self.state = NodeState.THROTTLED
                break

        if self.process.returncode is not None and self.state != NodeState.THROTTLED:
            logger.error(f"[{self.network.upper()}] Process crashed natively.")
            self.state = NodeState.DEAD

    async def terminate(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
        if self.stream_task:
            self.stream_task.cancel()

async def main_supervisor():
    def get_rpcs(env_var: str) -> list[str]:
        return [url.strip() for url in os.getenv(env_var, "").split(",") if url.strip()]
    
    eth_node = HeliosNode("ethereum", get_rpcs("ETH_EXECUTION_RPC"), get_rpcs("ETH_CONSENSUS_RPC"), 8545)
    base_node = HeliosNode("base", get_rpcs("BASE_EXECUTION_RPC"), get_rpcs("BASE_CONSENSUS_RPC"), 8546)

    nodes = [eth_node, base_node]

    for node in nodes:
        await node.start()
        await asyncio.sleep(2)

    logger.info("[ SYSTEM ] Async Supervisor Active. Press Ctrl+C to exit.")

    try:
        while True:
            await asyncio.sleep(3)

            for node in nodes:
                if node.state in (NodeState.THROTTLED, NodeState.DEAD):
                    logger.warning(f"[{node.network.upper()}] State is {node.state.name}. Executing failover sequence...")

                    await node.terminate()

                    if node.state == NodeState.THROTTLED:
                        logger.info(f"[{node.network.upper()}] Applying token bucket cooldown (15s) to respect limits...")
                        await asyncio.sleep(15)

                    node.rotate_el()

                    if node.network == "ethereum":
                        node.rotate_cl()

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