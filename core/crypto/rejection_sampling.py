import hashlib
from typing import Callable, Tuple

SHA3_256_MAX = 1 << 256

def sample_from_bytes(hash_bytes: bytes, total_tickets: int) -> int:
    