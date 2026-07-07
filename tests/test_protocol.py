import json
import unittest
from unittest.mock import patch, MagicMock

from core.crypto.canonicalization import build_payload
from core.crypto.hashing import generate_sha3_256
from core.crypto.signatures import EphemeralSigner, verify_signature
from core.crypto.rejection_sampling import sample_from_bytes, ModuloBiasRejection

class TestEdgeVerificationSecurity(unittest.TestCase):
    def setUp(self):
        self.signer = EphemeralSigner()
        self.pubkey = self.signer.get_public_key_b64()
        
        self.valid_height = 956621
        self.valid_hash = "0000000000000000000198a77958aac346f84307c3aa53a6afcef53f7161a90b"
        
        self.canonical_bytes = build_payload(self.valid_hash)
        self.valid_signature = self.signer.sign_payload(self.canonical_bytes)

    def test_flawless_client_verification_path(self):
        reconstructed_bytes = build_payload(self.valid_hash)
        is_authentic = verify_signature(self.pubkey, self.valid_signature, reconstructed_bytes)
        
        self.assertTrue(is_authentic)

    def test_host_tampered_payload_detection(self):
        tampered_hash = "0000000000000000000198a77958aac346f84307c3aa53a6afcef53f7161a90c"
        client_bytes = build_payload(tampered_hash)
        
        is_authentic = verify_signature(self.pubkey, self.valid_signature, client_bytes)
        self.assertFalse(is_authentic)

    def test_host_signature_forgery_rejection(self):
        reconstructed_bytes = build_payload(self.valid_hash)
        
        invalid_signature = self.valid_signature[:-3] + "AAA"
        
        is_authentic = verify_signature(self.pubkey, invalid_signature, reconstructed_bytes)
        self.assertFalse(is_authentic)

    def test_rogue_public_key_injection(self):
        attacker_signer = EphemeralSigner()
        attacker_pubkey = attacker_signer.get_public_key_b64()
        
        reconstructed_bytes = build_payload(self.valid_hash)
        
        is_authentic = verify_signature(attacker_pubkey, self.valid_signature, reconstructed_bytes)
        self.assertFalse(is_authentic)

class TestEdgeClientIntegrationFrames(unittest.TestCase):
    def setUp(self):
        self.signer = EphemeralSigner()
        self.pubkey = self.signer.get_public_key_b64()

    def test_parse_and_verify_production_json_frame(self):
        mock_height = 956622
        mock_hash = "00000000000000000000e32a02a699bc1a522da63c4d54564f5f9ea8d112a497"
        
        canonical_bytes = build_payload(mock_hash)
        signature = self.signer.sign_payload(canonical_bytes)
        
        incoming_json_frame = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {
                "result": {
                    "number": hex(mock_height),  
                    "hash": mock_hash,
                    "network": "bitcoin",
                    "signature": signature
                }
            }
        })

        data = json.loads(incoming_json_frame)
        result = data["params"]["result"]
        
        extracted_hash = result["hash"]
        extracted_sig = result["signature"]
        
        client_canonical = build_payload(extracted_hash)
        is_valid = verify_signature(self.pubkey, extracted_sig, client_canonical)
        
        self.assertTrue(is_valid)
        self.assertEqual(extracted_hash, mock_hash)