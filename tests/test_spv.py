import unittest
import hashlib
from core.engines.spv.spv_core import (
    hash256,
    parse_header,
    bits_to_target,
    verify_pow,
    calculate_next_work_required
)

GENESIS_BLOCK_HEX = "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c"
GENESIS_EXPECTED_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_BITS = 0x1d00ffff
GENESIS_TIMESTAMP = 1231006505
GENESIS_MERKLE_ROOT = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"

class TestSPVMathCryptography(unittest.TestCase):
    def test_hash256_double_sha(self):
        mock_payload = b'alea_entropy'
        
        expected = hashlib.sha256(hashlib.sha256(mock_payload).digest()).digest()
        result = hash256(mock_payload)
        
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 32)

    def test_parse_header_valid_mainnet_block(self):
        parsed = parse_header(GENESIS_BLOCK_HEX)
        
        self.assertEqual(parsed['version'], 1)
        self.assertEqual(parsed['prev_hash'], "0000000000000000000000000000000000000000000000000000000000000000")
        self.assertEqual(parsed['merkle_root'], GENESIS_MERKLE_ROOT)
        self.assertEqual(parsed['timestamp'], GENESIS_TIMESTAMP)
        self.assertEqual(parsed['bits'], GENESIS_BITS)
        self.assertEqual(parsed['nonce'], 2083236893)
        self.assertEqual(parsed['hash'], GENESIS_EXPECTED_HASH)

    def test_parse_header_invalid_length(self):
        invalid_hex = "01000000" * 15
        with self.assertRaises(ValueError):
            parse_header(invalid_hex)


class TestDifficultyTargets(unittest.TestCase):
    def test_bits_to_target_unpacking(self):
        target = bits_to_target(GENESIS_BITS)
        expected_target_hex = "00000000ffff0000000000000000000000000000000000000000000000000000"
        self.assertEqual(hex(target), "0x" + expected_target_hex.lstrip("0"))

    def test_verify_pow_valid_block(self):
        is_valid = verify_pow(GENESIS_BLOCK_HEX)
        self.assertTrue(is_valid)

    def test_verify_pow_invalid_block(self):
        mutated_hex = GENESIS_BLOCK_HEX[:-1] + "a"
        is_valid = verify_pow(mutated_hex)
        self.assertFalse(is_valid)


class TestRetargetingEpochs(unittest.TestCase):
    def setUp(self):
        self.expected_time = 2016 * 10 * 60
        self.base_target = bits_to_target(GENESIS_BITS)

    def test_calculate_next_work_required_exact_time(self):
        first_time = 1000000000
        last_time = first_time + self.expected_time
        new_target = calculate_next_work_required(first_time, last_time, GENESIS_BITS)

        self.assertEqual(new_target, self.base_target)

    def test_calculate_next_work_required_fast_blocks(self):
        first_time = 1000000000
        last_time = first_time + (self.expected_time // 2)
        new_target = calculate_next_work_required(first_time, last_time, GENESIS_BITS)

        self.assertEqual(new_target, self.base_target // 2)

    def test_calculate_next_work_required_absolute_ceiling(self):
        first_time = 1000000000
        last_time = first_time + (self.expected_time * 10)
        new_target = calculate_next_work_required(first_time, last_time, GENESIS_BITS)
        
        self.assertEqual(new_target, self.base_target)

    def test_calculate_next_work_required_relative_x4_limit(self):
        first_time = 1000000000
        last_time = first_time + (self.expected_time * 10)

        harder_bits = 0x181bc330 
        harder_target = bits_to_target(harder_bits)
        new_target = calculate_next_work_required(first_time, last_time, harder_bits)
        
        self.assertEqual(new_target, harder_target * 4)

if __name__ == '__main__':
    unittest.main()