import unittest
import hashlib
from unittest.mock import patch, MagicMock

from core.crypto.canonicalization import build_payload
from core.crypto.hashing import generate_sha3_256
from core.crypto.rejection_sampling import (
    sample_from_bytes,
    generate_zero_bias_winner,
    ModuloBiasRejection,
    SHA3_256_MAX
)

class TestHashing(unittest.TestCase):
    def test_valid_byte_hashing(self): # Valid input test.
        mock_payload = b'\x00\x00\x00\x04test'
        result = generate_sha3_256(mock_payload)

        expected = hashlib.sha3_256(mock_payload).digest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 32)

    def test_invalid_type_rejection(self): # Invalid type test.
        with self.assertRaises(TypeError):
            generate_sha3_256("this_is_a_string")

class TestCanonicalization(unittest.TestCase):
    def test_eth_hex_parsing(self): # ETH/Base Hex Test.
        payload = build_payload("0x1a2b")
        expected = b'\x00\x00\x00\x02\x1a\x2b'
        self.assertEqual(payload, expected)

    def test_btc_hash_parsing(self): # BTC Hash Test.
        btc_hash = "0000000000000000000000000000000000000000000000000000000000001a2b"
        payload = build_payload(btc_hash)
        self.assertEqual(len(payload), 4 + 32)

    def test_utf8_string_parsing(self): # Normal Str Test.
        payload = build_payload("lottery")
        expected = b'\x00\x00\x00\x07lottery'
        self.assertEqual(payload, expected)

    def test_integer_parsing(self): # Integer Test.
        payload_255 = build_payload(255)
        self.assertEqual(payload_255, b'\x00\x00\x00\x02\x00\xff') # Allocates 2 bytes when signed=True.

        payload_0 = build_payload(0)
        self.assertEqual(payload_0, b'\x00\x00\x00\x01\x00')

        payload_neg = build_payload(-1)
        self.assertEqual(payload_neg, b'\x00\x00\x00\x01\xff')

    def test_direct_bytes_parsing(self): # Bytes input test.
        payload = build_payload(b'\x99\x88')
        expected = b'\x00\x00\x00\x02\x99\x88'
        self.assertEqual(payload, expected)

    def test_multi_argument_payload(self): # Multi-argument Payload Test.
        payload = build_payload("0xaa", 255)
        expected = b'\x00\x00\x00\x01\xaa' + b'\x00\x00\x00\x02\x00\xff' # Updated 2 bytes header.
        self.assertEqual(payload, expected)

    def test_unsupported_type_rejection(self): # Unsupported type test.
        with self.assertRaises(TypeError):
            build_payload(["block_1", "block_2"])

    def test_empty_payload_rejection(self): # Empty payload test.
        with self.assertRaises(ValueError):
            build_payload()

class TestRejectionSampling(unittest.TestCase):
    def test_valid_sample(self): # Valid input, expected result.
        safe_hash = b'\x01' * 32
        total_tickets = 1000

        result = sample_from_bytes(safe_hash, total_tickets)

        expected_int = int.from_bytes(safe_hash, 'big')
        self.assertEqual(result, expected_int % total_tickets)

    def test_rejection_zone(self): # Rejection zone tests.
        total_tickets = 1000

        limit = SHA3_256_MAX - (SHA3_256_MAX % total_tickets)
        
        rejection_hash = limit.to_bytes(32, byteorder='big')

        with self.assertRaises(ModuloBiasRejection):
            sample_from_bytes(rejection_hash, total_tickets)

    def test_invalid_hash_length(self): # Invalid length test.
        invalid_hash = b'\x01' * 16

        with self.assertRaises(ValueError):
            sample_from_bytes(invalid_hash, 100)

    def test_invalid_ticket_count(self): # Zero & negative ticket tests.
        safe_hash = b'\x01' * 32

        with self.assertRaises(ValueError):
            sample_from_bytes(safe_hash, 0)

        with self.assertRaises(ValueError):
            sample_from_bytes(safe_hash, -10)
    
    def test_grinding_loop_good_path(self): # First try success test.
        dummy_builder = lambda *args: b'dummy_payload'
        base_args = ("block_100", "lottery_commit")
        
        with patch('core.crypto.rejection_sampling.generate_sha3_256') as mock_hash:
            mock_hash.return_value = b'\x01' * 32
            
            winning_ticket, nonce = generate_zero_bias_winner(dummy_builder, base_args, 1000)
            
            self.assertEqual(nonce, 0)
            self.assertEqual(mock_hash.call_count, 1)

    def test_grinding_loop_rejection_recovery(self): # Rejection & recovery test.
        dummy_builder = lambda *args: b'dummy_payload'
        base_args = ("block_100", "lottery_commit")
        total_tickets = 1000

        limit = SHA3_256_MAX - (SHA3_256_MAX % total_tickets)
        safe_hash = b'\x01' * 32
        rejection_hash = limit.to_bytes(32, byteorder='big')

        with patch('core.crypto.rejection_sampling.generate_sha3_256') as mock_hash:
            mock_hash.side_effect = [rejection_hash, safe_hash]

            winning_ticket, nonce = generate_zero_bias_winner(dummy_builder, base_args, total_tickets)

            self.assertEqual(nonce, 1)
            self.assertEqual(mock_hash.call_count, 2)

    def test_payload_passthrough_arguments(self): # Payload Integrity test.
        mock_builder = MagicMock(return_value=b'dummy_payload')
        base_args = ("block_100", "lottery_commit")

        with patch('core.crypto.rejection_sampling.generate_sha3_256') as mock_hash:
            mock_hash.return_value = b'\x01' * 32
            generate_zero_bias_winner(mock_builder, base_args, 1000)
            mock_builder.assert_called_once_with("block_100", "lottery_commit", 0)

if __name__ == '__main__':
    unittest.main()