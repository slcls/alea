import hashlib
import struct

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

    MAX_TARGET = 0x00000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    if new_target > MAX_TARGET:
        new_target = MAX_TARGET

    return new_target