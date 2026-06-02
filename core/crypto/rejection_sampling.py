import hashlib
from typing import Callable, Tuple

SHA3_256_MAX = 1 << 256

def sample_from_bytes(hash_bytes: bytes, total_tickets: int) -> int:
    if len(hash_bytes) != 32:
        raise ValueError(f"[ERROR] Rejection Sampling: Input must be exactly 32 bytes, got {len(hash_bytes)}")
    if total_tickets <= 0:
        raise ValueError("[ERROR] Rejection Sampling: Total tickets must be greater than zero.")
    
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    limit = SHA3_256_MAX - (SHA3_256_MAX % total_tickets)

    if hash_int >= limit:
        raise ValueError("[REJECT] Hash fell into the modulo bias zone. Resampling required.")
    
    return hash_int % total_tickets

def generate_zero_bias_winner(
    payload_builder: Callable[..., bytes], 
    base_args: tuple, 
    total_tickets: int
) -> Tuple[int, int]:
    
    nonce = 0

    while True:
        current_payload = payload_builder(*base_args, nonce)
        hash_bytes = hashlib.sha3_256(current_payload).digest()

        try:
            winning_ticket = sample_from_bytes(hash_bytes, total_tickets)
            return winning_ticket, nonce
        
        except ValueError as e:
            if "[REJECT]" in str(e):
                nonce += 1
                continue
            raise e