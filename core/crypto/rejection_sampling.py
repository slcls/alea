from typing import Callable, Tuple
from core.crypto.hashing import generate_sha3_256

class ModuloBiasRejection(Exception):
    pass

SHA3_256_MAX = 1 << 256 # Max value, which equates to 2^256.

def sample_from_bytes(hash_bytes: bytes, total_tickets: int) -> int:
    if len(hash_bytes) != 32: # 256 / 8 = 32 bytes :)
        raise ValueError(f"[ERROR] rejection_sampling.py: Input must be exactly 32 bytes, got {len(hash_bytes)}")
    if total_tickets <= 0:
        raise ValueError("[ERROR] rejection_sampling.py: Total tickets must be greater than zero.")
    
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    limit = SHA3_256_MAX - (SHA3_256_MAX % total_tickets)

    if hash_int >= limit:
        raise ModuloBiasRejection("[REJECT] rejection_sampling.py: Hash fell into the modulo bias zone. Resampling applied.")
    
    return hash_int % total_tickets

def generate_zero_bias_winner(
    payload_builder: Callable[..., bytes], 
    base_args: tuple, 
    total_tickets: int
) -> Tuple[int, int]:
    
    nonce = 0

    while True:
        current_payload = payload_builder(*base_args, nonce)
        hash_bytes = generate_sha3_256(current_payload)

        try:
            winning_ticket = sample_from_bytes(hash_bytes, total_tickets)
            return winning_ticket, nonce
        
        except ModuloBiasRejection:
            nonce += 1
            continue