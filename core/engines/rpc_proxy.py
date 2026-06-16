import os
import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Alea.Proxy")
logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

class ProxyRouter:
    def __init__(self, name: str, port: int, urls: list[str], node_type: str):
        self.name = name
        self.port = port
        self.node_type = node_type

        self.active_pool: list[str] = []
        self.dead_pool: list[str] = []

        self.dead_pool = [url.rstrip('/') for url in urls if url.strip()]
        self.session: ClientSession = None

    async def _test_endpoint(self, url: str) -> bool:
        try:
            if self.node_type == "EL":
                payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
                async with self.session.post(url, json=payload, timeout=ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return 'result' in data
            else:
                target = f"{url}/eth/v1/beacon/headers/finalized"
                async with self.session.get(target, timeout=ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return bool(data.get('data', {}).get('root'))
        
        except Exception:
            return False
        
        return False
    
    async def _revival_task(self, url: str, initial_delay: int):
        logger.warning(f"[{self.name}] {url[:35]}... assigned to Dead Pool. Recovery check in {initial_delay}s.")
        await asyncio.sleep(initial_delay)

        while url in self.dead_pool:
            is_healthy = await self._test_endpoint(url)

            if is_healthy:
                self.dead_pool.remove(url)
                self.active_pool.append(url)
                logger.info(f"[{self.name}] {url[:35]}... RECOVERED. Graduated to Active Pool.")
                break
            else:
                await asyncio.sleep(60)

    async def _sweep_initial(self):
        logger.info(f"[{self.name}] Initiating boot sweep of {len(self.dead_pool)} endpoints...")
        
        endpoints_to_test = list(self.dead_pool)
        for url in endpoints_to_test:
            is_healthy = await self._test_endpoint(url)
            if is_healthy:
                self.dead_pool.remove(url)
                self.active_pool.append(url)

        logger.info(f"[{self.name}] Boot Sweep Complete. Active: {len(self.active_pool)} | Dead: {len(self.dead_pool)}")

        for idx, url in enumerate(list(self.dead_pool)):
            staggered_delay = 15 * (idx + 1)
            asyncio.create_task(self._revival_task(url, staggered_delay))

    def _mark_dead_and_retry(self, url: str):
        if url in self.active_pool:
            self.active_pool.remove(url)
            self.dead_pool.append(url)
            asyncio.create_task(self._revival_task(url, 60))

    async def handle_request(self, request: web.Request):
        if not self.active_pool:
            logger.error(f"[{self.name}] FATAL: Active pool is completely empty. Returning 503.")
            return web.Response(status=503, text="No upstream endpoints available.")

        if self.node_type == "CL":
            await asyncio.sleep(0.1)

        body = await request.read()
        path = request.rel_url.path_qs

        for _ in range(len(self.active_pool) + len(self.dead_pool)):
            if not self.active_pool:
                break

            target_url = self.active_pool[0]
            full_target = f"{target_url}{path}" if path != "/" else target_url

            try:
                async with self.session.request(
                    method=request.method,
                    url=full_target,
                    headers={'Content-Type': 'application/json'},
                    data=body,
                    timeout=ClientTimeout(total=8)
                ) as resp:
                    if resp.status in (429, 403, 502, 503):
                        logger.warning(f"[{self.name}] Endpoint {target_url[:35]}... threw {resp.status}. Banish to Dead Pool.")
                        self._mark_dead_and_retry(target_url)
                        continue

                    response_data = await resp.read()
                    return web.Response(
                        status=resp.status,
                        body=response_data,
                        content_type=resp.content_type
                    )

            except asyncio.TimeoutError:
                logger.warning(f"[{self.name}] Endpoint {target_url[:35]}... timed out. Banish to Dead Pool.")
                self._mark_dead_and_retry(target_url)
            except Exception as e:
                logger.warning(f"[{self.name}] Endpoint {target_url[:35]}... failed: {e}. Banish to Dead Pool.")
                self._mark_dead_and_retry(target_url)

        return web.Response(status=503, text="All upstream endpoints exhausted during retry.")
    
    async def start_server(self):
        self.session = ClientSession()
        await self._sweep_initial()

        app = web.Application()
        app.router.add_route('*', '/{tail:.*}', self.handle_request)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', self.port)
        await site.start()
        logger.info(f"[{self.name}] Proxy listening on http://127.0.0.1:{self.port}")

async def main():
    def get_rpcs(env_var: str) -> list[str]:
        return [url.strip() for url in os.getenv(env_var, "").split(",") if url.strip()]

    routers = [
        ProxyRouter("ETH_EL", 43200, get_rpcs("ETH_EXECUTION_RPC"), "EL"),
        ProxyRouter("ETH_CL", 43201, get_rpcs("ETH_CONSENSUS_RPC"), "CL"),
        ProxyRouter("BASE_EL", 43202, get_rpcs("BASE_EXECUTION_RPC"), "EL")
    ]

    await asyncio.gather(*(router.start_server() for router in routers))

    logger.info("[ SYSTEM ] Web3 Proxy Multiplexer Active. Awaiting Helios traffic...")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        for router in routers:
            if router.session:
                await router.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] Proxy cleanly terminated.")