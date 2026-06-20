import os
import ssl
import json
import asyncio
import hashlib
import sqlite3
import logging
from pathlib import Path
from dotenv import load_dotenv
import aiohttp

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "spv_state.db"

logger = logging.getLogger("Alea.BTC_SPV")

logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS headers (
            height INTEGER PRIMARY KEY,
            hash TEXT UNIQUE,
            raw_header TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    return conn

def verify_pow(raw_hex: str, expected_hash: str) -> bool:
    try:
        header_bytes = bytes.fromhex(raw_hex)

        if len(header_bytes) != 80:
            return False
            
        hash1 = hashlib.sha256(header_bytes).digest()
        hash2 = hashlib.sha256(hash1).digest()
        calculated_hash = hash2[::-1].hex()
        
        return calculated_hash == expected_hash
    
    except Exception:
        return False

class BtcSpvManager:
    def __init__(self):
        self.db_conn = init_db()
        self.tatum_key = os.getenv("TATUM_API_KEY", "")
        
        raw_endpoints = [url.strip() for url in os.getenv("BTC_NETWORK_RPC", "").split(",") if url.strip()]
        self.active_pool = raw_endpoints
        self.dead_pool = []
        self.current_height = self._load_last_height()

    def _load_last_height(self) -> int:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT MAX(height) FROM headers")
        result = cursor.fetchone()[0]
        return result if result else 0

    def _save_header(self, height: int, block_hash: str, raw_hex: str):
        cursor = self.db_conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO headers (height, hash, raw_header) VALUES (?, ?, ?)",
            (height, block_hash, raw_hex)
        )
        self.db_conn.commit()

    async def _fetch_from_http(self, url: str, session: aiohttp.ClientSession) -> dict:
        headers = {'Content-Type': 'application/json'}
        if "tatum.io" in url and self.tatum_key:
            headers['x-api-key'] = self.tatum_key

        payload1 = {"jsonrpc": "2.0", "method": "getbestblockhash", "params": [], "id": 1}
        async with session.post(url, json=payload1, headers=headers, timeout=5) as resp:
            best_hash = (await resp.json())['result']

        payload2 = {"jsonrpc": "2.0", "method": "getblockheader", "params": [best_hash, True], "id": 2}
        async with session.post(url, json=payload2, headers=headers, timeout=5) as resp:
            data = (await resp.json())['result']
            
        payload3 = {"jsonrpc": "2.0", "method": "getblockheader", "params": [best_hash, False], "id": 3}
        async with session.post(url, json=payload3, headers=headers, timeout=5) as resp:
            raw_hex = (await resp.json())['result']

        return {"height": data['height'], "hash": best_hash, "hex": raw_hex}

    async def _fetch_from_electrum(self, endpoint: str) -> dict:
        host, port = endpoint.split(":")
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.open_connection(host, int(port), ssl=ssl_ctx)
        
        try:
            req = json.dumps({"id": 1, "method": "blockchain.headers.subscribe", "params": []}) + "\n"
            writer.write(req.encode('utf-8'))
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            data = json.loads(response.decode('utf-8'))['result']
            
            raw_hex = data['hex']
            calculated_hash = hashlib.sha256(hashlib.sha256(bytes.fromhex(raw_hex)).digest()).digest()[::-1].hex()
            
            return {"height": data['height'], "hash": calculated_hash, "hex": raw_hex}
        
        finally:
            writer.close()
            await writer.wait_closed()

    async def _fetch_latest_header(self, session: aiohttp.ClientSession) -> dict:
        for endpoint in list(self.active_pool):
            try:
                if endpoint.startswith("http"):
                    result = await self._fetch_from_http(endpoint, session)
                else:
                    result = await self._fetch_from_electrum(endpoint)
                
                return result
                
            except Exception as e:
                logger.warning(f"[BTC] Endpoint {endpoint} failed: {e}. Banishing to Dead Pool.")
                self.active_pool.remove(endpoint)
                self.dead_pool.append(endpoint)
                
        raise Exception("All BTC endpoints exhausted.")

    async def sync_loop(self):
        logger.info(f"[ SYSTEM ] Bitcoin SPV Engine Booted. Current Height: {self.current_height}")
        
        async with aiohttp.ClientSession() as session:
            while True:
                if not self.active_pool:
                    logger.error("FATAL: No active BTC endpoints. Waiting 60s for revival sweep...")
                    self.active_pool, self.dead_pool = self.dead_pool, []
                    await asyncio.sleep(60)
                    continue

                try:
                    data = await self._fetch_latest_header(session)
                    
                    if data['height'] > self.current_height:
                        is_valid = verify_pow(data['hex'], data['hash'])
                        
                        if is_valid:
                            self._save_header(data['height'], data['hash'], data['hex'])
                            self.current_height = data['height']
                            logger.info(f"[BTC] VERIFIED NEW BLOCK: {self.current_height} | HASH: {data['hash']}")
                        else:
                            logger.error(f"[BTC] SECURITY ALERT: Invalid PoW detected for block {data['height']}!")
                    
                except Exception as e:
                    logger.error(f"[BTC] Sync cycle failed: {e}")
                
                await asyncio.sleep(60)

if __name__ == "__main__":
    spv = BtcSpvManager()
    try:
        asyncio.run(spv.sync_loop())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] Bitcoin SPV cleanly terminated.")
        spv.db_conn.close()