import os
import json
import struct
import hashlib
import struct
import sqlite3
import asyncio
import aiohttp
import logging
import websockets
from pathlib import Path
from core.engines.spv.btc_proxy import BtcStratumProxy

logger = logging.getLogger("Alea.SPV_Orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

# Math and Crypto Utils

def hash256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def parse_header(raw_hex: str) -> dict:
    header_bytes = bytes.fromhex(raw_hex)
    if len(header_bytes) != 80:
        raise ValueError(f"Invalid header length: {len(header_bytes)} bytes. Must be exactly 80.")

    version = struct.unpack("<I", header_bytes[0:4])[0]
    prev_hash = header_bytes[4:36][::-1].hex()
    merkle_root = header_bytes[36:68][::-1].hex()
    
    timestamp = struct.unpack("<I", header_bytes[68:72])[0]
    bits = struct.unpack("<I", header_bytes[72:76])[0]
    nonce = struct.unpack("<I", header_bytes[76:80])[0]
    block_hash = hash256(header_bytes)[::-1].hex()

    return {
        "hash": block_hash,
        "version": version,
        "prev_hash": prev_hash,
        "merkle_root": merkle_root,
        "timestamp": timestamp,
        "bits": bits,
        "nonce": nonce
    }

def bits_to_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007fffff
    
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
        
    return target

def verify_pow(raw_hex: str) -> bool:
    try:
        header_bytes = bytes.fromhex(raw_hex)
        header_hash_bytes = hash256(header_bytes)
        hash_int = int.from_bytes(header_hash_bytes, byteorder='little')
        parsed = parse_header(raw_hex)
        target = bits_to_target(parsed['bits'])
        
        return hash_int <= target
    
    except Exception:
        return False

def calculate_next_work_required(first_timestamp: int, last_timestamp: int, old_bits: int) -> int:
    expected_time = 2016 * 10 * 60
    actual_time = last_timestamp - first_timestamp

    if actual_time < expected_time // 4:
        actual_time = expected_time // 4
    if actual_time > expected_time * 4:
        actual_time = expected_time * 4

    old_target = bits_to_target(old_bits)
    new_target = (old_target * actual_time) // expected_time

    MAX_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    
    if new_target > MAX_TARGET:
        new_target = MAX_TARGET

    return new_target

# SPV State Management

class SPVState:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self.retention_limit = 3000

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS headers (
                height INTEGER PRIMARY KEY,
                hash TEXT UNIQUE,
                prev_hash TEXT,
                timestamp INTEGER,
                bits INTEGER,
                raw_hex TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prev_hash ON headers(prev_hash);")
        self.conn.commit()

    def get_tip(self) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT height, hash, prev_hash, timestamp, bits FROM headers ORDER BY height DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            return {"height": row[0], "hash": row[1], "prev_hash": row[2], "timestamp": row[3], "bits": row[4]}
        
        return None
    
    def get_block_by_height(self, height: int) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT height, hash, prev_hash, timestamp, bits FROM headers WHERE height = ?", (height,))
        row = cursor.fetchone()

        if row:
             return {"height": row[0], "hash": row[1], "prev_hash": row[2], "timestamp": row[3], "bits": row[4]}
        
        return None
    
    def prune_ancient_blocks(self, current_height: int):
        prune_threshold = current_height - self.retention_limit
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM headers WHERE height < ?", (prune_threshold,))
        deleted = cursor.rowcount
        self.conn.commit()

        if deleted > 0:
            logger.debug(f"[SPV] Pruned {deleted} ancient blocks. State threshold: {prune_threshold}")

    def verify_retarget(self, new_height: int, new_bits: int) -> bool:
        if new_height % 2016 != 0:
            tip = self.get_tip()
            return new_bits == tip['bits']
        
        first_block_height = new_height - 2016
        first_block = self.get_block_by_height(first_block_height)

        if not first_block:
            logger.warning(f"[SPV] Cannot verify retarget: Missing block {first_block_height} for epoch calculation.")
            return True
        
        tip = self.get_tip()
        expected_target = calculate_next_work_required(first_block['timestamp'], tip['timestamp'], tip['bits'])
        new_target = bits_to_target(new_bits)

        difference = abs(expected_target - new_target)
        precision_margin = expected_target * 0.01

        return difference <= precision_margin
    
    def process_new_header(self, expected_height: int, raw_hex: str) -> bool:
        if not verify_pow(raw_hex):
            logger.error(f"[SPV] SECURITY ALERT: Invalid PoW for header at expected height {expected_height}!")
            return False

        parsed = parse_header(raw_hex)
        tip = self.get_tip()

        if not tip:
            self._insert_header(expected_height, parsed, raw_hex)
            return True

        if expected_height == tip['height'] + 1:
            if parsed['prev_hash'] == tip['hash']:
                if not self.verify_retarget(expected_height, parsed['bits']):
                    logger.error(f"[SPV] SECURITY ALERT: Invalid Difficulty Retarget at height {expected_height}!")
                    return False
                
                self._insert_header(expected_height, parsed, raw_hex)
                self.prune_ancient_blocks(expected_height)
                return True
            
            else:
                logger.warning(f"[SPV] DEEP FORK DETECTED. Tip {tip['height']} is orphaned. Rolling back...")
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM headers WHERE height >= ?", (tip['height'],))
                self.conn.commit()
                return False 

        if expected_height == tip['height']:
            if parsed['hash'] == tip['hash']:
                return False
            else:
                return self._handle_reorg(expected_height, parsed, raw_hex)

        if expected_height < tip['height']:
            return False

        if expected_height > tip['height'] + 1:
            return False

    def _handle_reorg(self, height: int, parsed: dict, raw_hex: str) -> bool:
        logger.warning(f"[SPV] CHAIN SPLIT DETECTED at height {height}. Initiating localized rollback...")

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM headers WHERE height >= ?", (height,))
        self.conn.commit()

        logger.info(f"[SPV] Successfully rolled back orphaned chain. Appending new block {height}.")
        self._insert_header(height, parsed, raw_hex)
        return True
    
    def _insert_header(self, height: int, parsed: dict, raw_hex: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO headers (height, hash, prev_hash, timestamp, bits, raw_hex) VALUES (?, ?, ?, ?, ?, ?)",
            (height, parsed['hash'], parsed['prev_hash'], parsed['timestamp'], parsed['bits'], raw_hex)
        )

        self.conn.commit()
        logger.info(f"[SPV] VERIFIED NEW BLOCK: {height} | HASH: {parsed['hash']}")

# Pipeline Handler

class SpvOrchestrator:
    def __init__(self, db_path: Path, ws_port: int = 43212):
        self.state = SPVState(db_path)
        self.proxy = BtcStratumProxy()
        self.ws_port = ws_port
        self.ws_clients = set()

    async def _ws_handler(self, websocket):
        self.ws_clients.add(websocket)

        try:
            async for msg in websocket:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.ws_clients.remove(websocket)

    async def _broadcast_new_head(self, height: int, block_hash: str):
        if not self.ws_clients:
            return
        
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {
                "result": {
                    "number": hex(height),  
                    "hash": block_hash,
                    "network": "bitcoin"
                }
            }
        })
        
        await asyncio.gather(
            *[client.send(payload) for client in self.ws_clients],
            return_exceptions=True
        )

    async def _execute_catch_up(self):
        tip = self.state.get_tip()
        if not tip:
            logger.info("[SPV_Orchestrator] Database is empty. Awaiting first live Stratum block to anchor the chain...")
            return

        local_height = tip['height']
        http_pool = self.proxy.http_reserve_pool
        if not http_pool:
            logger.warning("[SPV_Orchestrator] No HTTP reserves mapped in .env. Skipping Catch-Up Sync.")
            return

        url = http_pool[0]
        tatum_key = os.getenv("TATUM_API_KEY", "")
        headers = {'Content-Type': 'application/json'}
        if "tatum.io" in url and tatum_key:
            headers['x-api-key'] = tatum_key

        async with aiohttp.ClientSession() as session:
            try:
                p1 = {"jsonrpc": "2.0", "method": "getbestblockhash", "params": [], "id": 1}
                async with session.post(url, json=p1, headers=headers, timeout=5) as resp:
                    best_hash = (await resp.json())['result']

                p2 = {"jsonrpc": "2.0", "method": "getblockheader", "params": [best_hash, True], "id": 2}
                async with session.post(url, json=p2, headers=headers, timeout=5) as resp:
                    latest_height = (await resp.json())['result']['height']

                gap = latest_height - local_height
                if gap <= 0:
                    logger.info("[SPV_Orchestrator] Local database is completely synced with the network.")
                    return

                logger.info(f"[SPV_Orchestrator] Catch-Up Sync Required: Missing {gap} blocks. Fetching via HTTP...")

                start_height = local_height + 1
                if gap > self.state.retention_limit:
                    logger.warning(f"[SPV_Orchestrator] Gap ({gap}) exceeds retention limit. Fast-forwarding to safe window.")
                    start_height = latest_height - self.state.retention_limit + 1
                    
                    cursor = self.state.conn.cursor()
                    cursor.execute("DELETE FROM headers")
                    self.state.conn.commit()

                for h in range(start_height, latest_height + 1):
                    p_hash = {"jsonrpc": "2.0", "method": "getblockhash", "params": [h], "id": h}
                    async with session.post(url, json=p_hash, headers=headers, timeout=5) as r:
                        block_hash = (await r.json())['result']
                    
                    p_hex = {"jsonrpc": "2.0", "method": "getblockheader", "params": [block_hash, False], "id": h}
                    async with session.post(url, json=p_hex, headers=headers, timeout=5) as r:
                        raw_hex = (await r.json())['result']

                    if not verify_pow(raw_hex):
                        logger.error(f"[SPV_Orchestrator] Catch-Up endpoint provided invalid PoW at height {h}! Aborting sync.")
                        break

                    self.state.process_new_header(h, raw_hex)

                    if h % 100 == 0:
                        logger.info(f"[SPV_Orchestrator] Catch-Up Progress: {h}/{latest_height}")

                logger.info("[SPV_Orchestrator] Catch-Up Sync completed.")

            except Exception as e:
                logger.error(f"[SPV_Orchestrator] Catch-Up Sync failed: {e}")

    async def start(self):
        logger.info("[ SYSTEM ] Booting Alea Bitcoin SPV Orchestrator...")
        
        ws_server = await websockets.serve(self._ws_handler, "127.0.0.1", self.ws_port)
        logger.info(f"[SPV_Orchestrator] Verified Block Stream hosted on ws://127.0.0.1:{self.ws_port}")

        await self.proxy.start_multiplexer()
        await self._execute_catch_up()

        logger.info("[SPV_Orchestrator] Pipeline glued. Awaiting multiplexer races...")

        try:
            while True:
                payload = await self.proxy.output_queue.get()
                height = payload['height']
                raw_hex = payload['raw_hex']
                source = payload['source']

                tip = self.state.get_tip()

                if not verify_pow(raw_hex):
                    logger.error(f"[SPV_Orchestrator] SECURITY ALERT: Malicious payload from {source}!")
                    self.proxy._banish_endpoint(source, "Failed PoW Cryptography")
                    continue

                if tip and height > tip['height'] + 1:
                    logger.warning(f"[SPV_Orchestrator] Live gap detected (Tip: {tip['height']}, Got: {height}). Pausing race for Catch-Up...")
                    await self._execute_catch_up()

                is_valid = self.state.process_new_header(height, raw_hex)

                if is_valid:
                    new_tip = self.state.get_tip()
                    if new_tip and new_tip['height'] == height:
                        logger.info(f"[SPV_Orchestrator] BROADCASTING VERIFIED TIP: {height} | Winner: {source}")
                        await self._broadcast_new_head(height, new_tip['hash'])
                        
        except asyncio.CancelledError:
            pass

        finally:
            await self.proxy.shutdown()
            ws_server.close()
            await ws_server.wait_closed()

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    DB_PATH = DATA_DIR / "spv_state.db"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    orchestrator = SpvOrchestrator(DB_PATH)

    try:
        asyncio.run(orchestrator.start())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] Bitcoin SPV Orchestrator cleanly terminated.")