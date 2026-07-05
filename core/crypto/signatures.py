import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class EphemeralSigner:
    def __init__(self):
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        
    def get_public_key_b64(self) -> str:
        raw_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw_bytes).decode('utf-8')

    def sign_payload(self, data: bytes) -> str:
        signature = self._private_key.sign(data)
        return base64.b64encode(signature).decode('utf-8')

def verify_signature(public_key_b64: str, signature_b64: str, data: bytes) -> bool:
    try:
        public_bytes = base64.b64decode(public_key_b64)
        sig_bytes = base64.b64decode(signature_b64)
        
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
        public_key.verify(sig_bytes, data)
        return True
    except Exception:
        return False