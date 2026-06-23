import os
import ssl
import json
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Alea.BTC_Proxy")
logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

class BtcStratumProxy:
    def __init__(self):
        self.active_pool: list[str] = []
        self.dead_pool: list[str] = []
        self.http_reserve_pool: list[str] = []
        
        self.output_queue = asyncio.Queue()
        self._active_tasks = {}
        self._strike_counts = {}

        self._parse_env_endpoints()

    def _parse_env_endpoints(self):
        raw_endpoints = [url.strip() for url in os.getenv("BTC_NETWORK_RPC", "").split(",") if url.strip()]
        for ep in raw_endpoints:
            if ep.startswith("http"):
                self.http_reserve_pool.append(ep)
            else:
                self.dead_pool.append(ep)

    async def _test_stratum_endpoint(self, endpoint: str) -> bool:
        host, port = endpoint.split(":")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port), ssl=ssl_ctx),
                timeout=5.0
            )

            req = json.dumps({"id": 1, "method": "server.version", "params": ["Alea_Proxy", "1.4"]}) + "\n"
            writer.write(req.encode('utf-8'))
            await writer.drain()

            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            writer.close()
            await writer.wait_closed()
            
            return bool(response)
        
        except Exception:
            return False

    async def _revival_task(self, endpoint: str, initial_delay: int):
        logger.warning(f"[BTC_Proxy] {endpoint} in Dead Pool. Recovery check in {initial_delay}s.")
        await asyncio.sleep(initial_delay)

        while endpoint in self.dead_pool:
            is_healthy = await self._test_stratum_endpoint(endpoint)

            if is_healthy:
                self.dead_pool.remove(endpoint)
                self.active_pool.append(endpoint)
                logger.info(f"[BTC_Proxy] {endpoint} RECOVERED. Graduated to Active Pool.")
                self._spawn_listener(endpoint)
                break

            else:
                await asyncio.sleep(60)

    async def _sweep_initial(self):
        logger.info(f"[BTC_Proxy] Boot Sweep of {len(self.dead_pool)} Stratum endpoints...")
        
        endpoints_to_test = list(self.dead_pool)
        for endpoint in endpoints_to_test:
            is_healthy = await self._test_stratum_endpoint(endpoint)
            if is_healthy:
                self.dead_pool.remove(endpoint)
                self.active_pool.append(endpoint)

        logger.info(f"[BTC_Proxy] Boot Sweep Complete. Active: {len(self.active_pool)} | Dead: {len(self.dead_pool)} | HTTP Reserves: {len(self.http_reserve_pool)}")

        for idx, endpoint in enumerate(list(self.dead_pool)):
            staggered_delay = 15 * (idx + 1)
            asyncio.create_task(self._revival_task(endpoint, staggered_delay))

    def _banish_endpoint(self, endpoint: str, reason: str):
        strikes = self._strike_counts.get(endpoint, 0) + 1
        self._strike_counts[endpoint] = strikes

        if strikes >= 3:
            logger.error(f"[BTC_Proxy] Endpoint {endpoint} failed ({reason}). STRIKE {strikes}/3. PERMANENTLY BANISHED.")
            if endpoint in self.active_pool:
                self.active_pool.remove(endpoint)
            if endpoint in self.dead_pool:
                self.dead_pool.remove(endpoint)
        else:
            logger.warning(f"[BTC_Proxy] Endpoint {endpoint} failed ({reason}). Strike {strikes}/3. Banish to Dead Pool.")
            if endpoint in self.active_pool:
                self.active_pool.remove(endpoint)
                self.dead_pool.append(endpoint)
            
            asyncio.create_task(self._revival_task(endpoint, 60))

        if endpoint in self._active_tasks:
            task = self._active_tasks[endpoint]
            if not task.done():
                task.cancel()
            del self._active_tasks[endpoint]

    async def _listen_to_node(self, endpoint: str):
        host, port = endpoint.split(":")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_ctx)
            
            req = json.dumps({"id": 1, "method": "blockchain.headers.subscribe", "params": []}) + "\n"
            writer.write(req.encode('utf-8'))
            await writer.drain()

            while True:
                response = await reader.readline()
                if not response:
                    raise ConnectionError("Socket closed by remote host.")

                data = json.loads(response.decode('utf-8'))
                
                if 'method' in data and data['method'] == 'blockchain.headers.subscribe':
                    header_data = data['params'][0]
                elif 'result' in data:
                    header_data = data['result']
                else:
                    continue

                if 'hex' in header_data and 'height' in header_data:
                    self._strike_counts[endpoint] = 0

                    await self.output_queue.put({
                        "source": endpoint,
                        "height": header_data['height'],
                        "raw_hex": header_data['hex']
                    })

        except asyncio.CancelledError:
            if 'writer' in locals():
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            self._banish_endpoint(endpoint, str(e))

    def _spawn_listener(self, endpoint: str):
        task = asyncio.create_task(self._listen_to_node(endpoint))
        self._active_tasks[endpoint] = task

    async def start_multiplexer(self):
        await self._sweep_initial()
        
        if not self.active_pool:
            logger.error("[BTC_Proxy] FATAL: All Stratum endpoints are dead on arrival.")
            
        for endpoint in self.active_pool:
            self._spawn_listener(endpoint)
            
        logger.info("[BTC_Proxy] Shotgun Multiplexer Active. Awaiting Stratum push notifications...")

    async def shutdown(self):
        logger.info("[BTC_Proxy] Initiating graceful shutdown...")

        for endpoint, task in self._active_tasks.items():
            if not task.done():
                task.cancel()
        
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        logger.info("[BTC_Proxy] All active Stratum sockets closed.")

if __name__ == "__main__":
    proxy = BtcStratumProxy()

    async def run_test():
        await proxy.start_multiplexer()
        try:
            while True:
                payload = await proxy.output_queue.get()
                logger.info(f"[RACE WINNER] Height: {payload['height']} | Source: {payload['source']}")

        except asyncio.CancelledError:
            pass
        finally:
            await proxy.shutdown()

    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] BTC Proxy cleanly terminated.")