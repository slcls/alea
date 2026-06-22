import unittest
import sqlite3
import hashlib
from unittest.mock import patch, MagicMock
from core.engines.spv.spv_core import SPVState
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

# SPV State Management Tests

class TestSPVStateManagement(unittest.TestCase):
    def setUp(self):
        self.spv = SPVState(":memory:")
        self.spv.retention_limit = 10 

    def tearDown(self):
        self.spv.conn.close()

    @patch('core.engines.spv.spv_core.verify_pow', return_value=True)
    @patch('core.engines.spv.spv_core.parse_header')
    def test_genesis_block_insertion(self, mock_parse, mock_verify):
        mock_parse.return_value = {
            "hash": "block_0_hash", "prev_hash": "000000", 
            "timestamp": 1000, "bits": 0x1d00ffff
        }
        
        success = self.spv.process_new_header(0, "dummy_hex")
        self.assertTrue(success)
        
        tip = self.spv.get_tip()
        self.assertEqual(tip['height'], 0)
        self.assertEqual(tip['hash'], "block_0_hash")

    @patch('core.engines.spv.spv_core.verify_pow', return_value=False)
    def test_invalid_pow_rejection(self, mock_verify):
        success = self.spv.process_new_header(1, "invalid_hex")
        self.assertFalse(success)
        self.assertIsNone(self.spv.get_tip())

    @patch('core.engines.spv.spv_core.verify_pow', return_value=True)
    @patch('core.engines.spv.spv_core.parse_header')
    def test_sequential_chaining_and_stale_rejection(self, mock_parse, mock_verify):
        mock_parse.return_value = {"hash": "hash_1", "prev_hash": "hash_0", "timestamp": 1000, "bits": 0x1d00ffff}
        self.spv._insert_header(1, mock_parse.return_value, "hex_1")

        mock_parse.return_value = {"hash": "stale_hash", "prev_hash": "hash_0", "timestamp": 1000, "bits": 0x1d00ffff}
        success_stale = self.spv.process_new_header(1, "stale_hex")
        self.assertFalse(success_stale)
        
        success_gap = self.spv.process_new_header(3, "gap_hex")
        self.assertFalse(success_gap)

        mock_parse.return_value = {"hash": "hash_2", "prev_hash": "hash_1", "timestamp": 1010, "bits": 0x1d00ffff}
        success_valid = self.spv.process_new_header(2, "hex_2")
        self.assertTrue(success_valid)
        self.assertEqual(self.spv.get_tip()['height'], 2)


class TestSPVStateReorganizations(unittest.TestCase):
    def setUp(self):
        self.spv = SPVState(":memory:")

    @patch('core.engines.spv.spv_core.verify_pow', return_value=True)
    @patch('core.engines.spv.spv_core.parse_header')
    def test_chain_split_rollback(self, mock_parse, mock_verify):
        base_block = {"hash": "hash_10", "prev_hash": "hash_9", "timestamp": 1000, "bits": 0x1d00ffff}
        self.spv._insert_header(10, base_block, "hex_10")

        orphan_block = {"hash": "orphan_11", "prev_hash": "hash_10", "timestamp": 1010, "bits": 0x1d00ffff}
        self.spv._insert_header(11, orphan_block, "orphan_hex")

        mock_parse.return_value = {"hash": "heavy_11", "prev_hash": "hash_10", "timestamp": 1015, "bits": 0x1d00ffff}
        success = self.spv.process_new_header(11, "heavy_hex")

        self.assertTrue(success)
        tip = self.spv.get_tip()
        
        self.assertEqual(tip['hash'], "heavy_11")
        self.assertEqual(tip['prev_hash'], "hash_10")

class TestSPVStateRetargetingAndPruning(unittest.TestCase):
    def setUp(self):
        self.spv = SPVState(":memory:")
        self.spv.retention_limit = 50 

    def test_automated_pruning_execution(self):
        for i in range(100):
            block = {"hash": f"h_{i}", "prev_hash": f"h_{i-1}", "timestamp": 1000+i, "bits": 0x1d00ffff}
            self.spv._insert_header(i, block, f"hex_{i}")

        self.spv.prune_ancient_blocks(100)

        cursor = self.spv.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM headers")
        total_rows = cursor.fetchone()[0]

        self.assertEqual(total_rows, 50)
        self.assertIsNone(self.spv.get_block_by_height(49))
        self.assertIsNotNone(self.spv.get_block_by_height(50))

    @patch('core.engines.spv.spv_core.calculate_next_work_required')
    @patch('core.engines.spv.spv_core.bits_to_target')
    def test_epoch_retarget_verification(self, mock_bits_to_target, mock_calc_work):
        tip_block = {"hash": "h_2015", "prev_hash": "h_2014", "timestamp": 2000000, "bits": 0x1d00ffff}
        self.spv._insert_header(2015, tip_block, "hex_2015")

        start_block = {"hash": "h_0", "prev_hash": "00", "timestamp": 1000000, "bits": 0x1d00ffff}
        self.spv._insert_header(0, start_block, "hex_0")

        expected_new_target = 500000
        mock_calc_work.return_value = expected_new_target
        
        new_bits = 0x1c00aaaa
        mock_bits_to_target.return_value = expected_new_target

        is_valid = self.spv.verify_retarget(2016, new_bits)
        
        self.assertTrue(is_valid)
        mock_calc_work.assert_called_once_with(1000000, 2000000, 0x1d00ffff)

if __name__ == '__main__':
    unittest.main()