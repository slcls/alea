import unittest
from core.crypto.rejection_sampling import sample_from_bytes, ModuloBiasRejection, SHA3_256_MAX

class ZeroBiasTest(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()