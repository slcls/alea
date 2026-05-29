import re # Imported this so that no hex string from SPV ever gets passed as utf-8.

DELIMITER = b'\x76'
HEX_0X_PATTERN = re.compile(r'^0[xX][0-9a-fA-F]+$')
BTC_HASH_PATTERN = re.compile(r'^[0-9a-fA-F]{64}$')

def _to_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    
    elif isinstance(value, str):
        if HEX_0X_PATTERN.match(value): # Standard Ox usually from ETH/BASE
            val = value[2:]

            if len(val) % 2 != 0:
                val = '0' + val
            return bytes.fromhex(val)
        
        elif BTC_HASH_PATTERN.match(value): # Weird ass 00001a.. hash from SPV
            return bytes.fromhex(value)
        
        return value.encode('utf-8')
    
    elif isinstance(value, int):
        byte_length = (value.bit_length() + 7) // 8 or 1 # Allocation for bytes, "or 1" for empty values
        return value.to_bytes(byte_length, byteorder='big', signed=True) # Signedd just in case it goes negative.
    
    else:
        raise TypeError(f"[ERROR] canonicalization.py: Unsupported valuetype -> {type(value)}")
    
def build_payload(*args) -> bytes:
    if not args:
        raise ValueError("[ERROR] canonicalization.py: Payload must contain at least one element.")
    
    byte_args = [_to_bytes(arg) for arg in args]
    return DELIMITER.join(byte_args)