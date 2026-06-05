import hashlib

def generate_sha3_256(payload: bytes) -> bytes:
    if not isinstance(payload, bytes):
        raise TypeError(f"[ERROR] hashing.py: Payload must be raw bytes, got {type(payload)}")
    
    return hashlib.sha3_256(payload).digest()