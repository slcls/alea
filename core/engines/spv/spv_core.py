import hashlib
import struct
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("Alea.SPVState")

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
                return self._handle_reorg(expected_height, parsed, raw_hex)
            
        if expected_height <= tip['height']:
            logger.debug(f"[SPV] Ignored stale block at height {expected_height}. Current tip is {tip['height']}.")
            return False
        
        if expected_height > tip['height'] + 1:
            logger.warning(f"[SPV] Gap detected. Tip is {tip['height']}, received {expected_height}. Requires Catch-Up Sync.")
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