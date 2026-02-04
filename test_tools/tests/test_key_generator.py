"""
Unit tests for the KeySequenceGenerator class.

This module contains comprehensive tests for the key sequence generator,
including uniqueness verification, format validation, performance tests,
and edge case handling.

Test Categories:
    - Uniqueness Tests: Verify no duplicate keys are generated
    - Format Validation Tests: Verify key length and character constraints
    - Performance Tests: Verify generation speed meets requirements
    - Edge Case Tests: Verify error handling and reset functionality
"""

import time
import unittest

from test_tools.key_generator import KeySequenceGenerator, KeysExhaustedError


class TestKeySequenceGeneratorUniqueness(unittest.TestCase):
    """Tests to verify that generated keys are unique."""

    def setUp(self):
        """Create a fresh generator for each test."""
        self.generator = KeySequenceGenerator()

    def test_generate_100_unique_class_keys(self):
        """
        Test that 100 class keys can be generated without duplicates.

        This verifies the core requirement that at least 100 unique
        4-letter class keys can be generated.
        """
        keys = set()
        for i in range(100):
            key = self.generator.get_next_class_key()
            self.assertNotIn(key, keys, f"Duplicate class key found at index {i}: {key}")
            keys.add(key)

        self.assertEqual(len(keys), 100, "Expected exactly 100 unique class keys")

    def test_generate_100_unique_function_keys(self):
        """
        Test that 100 function keys can be generated without duplicates.

        This verifies the core requirement that at least 100 unique
        3-letter function keys can be generated.
        """
        keys = set()
        for i in range(100):
            key = self.generator.get_next_function_key()
            self.assertNotIn(key, keys, f"Duplicate function key found at index {i}: {key}")
            keys.add(key)

        self.assertEqual(len(keys), 100, "Expected exactly 100 unique function keys")

    def test_generate_all_possible_function_keys_unique(self):
        """
        Test that all 512 possible function keys are unique.

        This exhaustive test verifies that every possible 3-letter
        combination is generated exactly once.
        """
        keys = set()
        for i in range(512):
            key = self.generator.get_next_function_key()
            self.assertNotIn(key, keys, f"Duplicate function key found at index {i}: {key}")
            keys.add(key)

        self.assertEqual(len(keys), 512, "Expected exactly 512 unique function keys")

    def test_class_and_function_keys_independent(self):
        """
        Test that class and function key generation are independent.

        Generating class keys should not affect function key generation
        and vice versa.
        """
        # Generate some class keys
        for _ in range(50):
            self.generator.get_next_class_key()

        # First function key should still be 'aaa'
        func_key = self.generator.get_next_function_key()
        self.assertEqual(func_key, 'aaa', "Function key generation should be independent of class keys")

        # Check stats
        stats = self.generator.get_stats()
        self.assertEqual(stats['class_keys_used'], 50)
        self.assertEqual(stats['function_keys_used'], 1)


class TestKeySequenceGeneratorFormat(unittest.TestCase):
    """Tests to verify the format of generated keys."""

    def setUp(self):
        """Create a fresh generator for each test."""
        self.generator = KeySequenceGenerator()
        self.allowed_chars = set(['a', 's', 'd', 'f', 'h', 'j', 'k', 'l'])

    def test_class_keys_are_exactly_4_characters(self):
        """Test that all class keys have exactly 4 characters."""
        for i in range(100):
            key = self.generator.get_next_class_key()
            self.assertEqual(
                len(key), 4,
                f"Class key at index {i} has {len(key)} characters, expected 4: {key}"
            )

    def test_function_keys_are_exactly_3_characters(self):
        """Test that all function keys have exactly 3 characters."""
        for i in range(100):
            key = self.generator.get_next_function_key()
            self.assertEqual(
                len(key), 3,
                f"Function key at index {i} has {len(key)} characters, expected 3: {key}"
            )

    def test_class_keys_use_only_allowed_characters(self):
        """Test that class keys only use the 8 allowed home row characters."""
        for i in range(100):
            key = self.generator.get_next_class_key()
            for char in key:
                self.assertIn(
                    char, self.allowed_chars,
                    f"Class key at index {i} contains invalid character '{char}': {key}"
                )

    def test_function_keys_use_only_allowed_characters(self):
        """Test that function keys only use the 8 allowed home row characters."""
        for i in range(100):
            key = self.generator.get_next_function_key()
            for char in key:
                self.assertIn(
                    char, self.allowed_chars,
                    f"Function key at index {i} contains invalid character '{char}': {key}"
                )

    def test_first_class_key_is_aaaa(self):
        """Test that the first class key is 'aaaa' (counter starts at 0)."""
        key = self.generator.get_next_class_key()
        self.assertEqual(key, 'aaaa', "First class key should be 'aaaa'")

    def test_first_function_key_is_aaa(self):
        """Test that the first function key is 'aaa' (counter starts at 0)."""
        key = self.generator.get_next_function_key()
        self.assertEqual(key, 'aaa', "First function key should be 'aaa'")

    def test_class_key_sequence_pattern(self):
        """Test the expected sequence pattern for class keys."""
        expected_sequence = ['aaaa', 'aaas', 'aaad', 'aaaf', 'aaah', 'aaaj', 'aaak', 'aaal']
        for expected in expected_sequence:
            key = self.generator.get_next_class_key()
            self.assertEqual(key, expected, f"Expected {expected}, got {key}")

    def test_function_key_sequence_pattern(self):
        """Test the expected sequence pattern for function keys."""
        expected_sequence = ['aaa', 'aas', 'aad', 'aaf', 'aah', 'aaj', 'aak', 'aal']
        for expected in expected_sequence:
            key = self.generator.get_next_function_key()
            self.assertEqual(key, expected, f"Expected {expected}, got {key}")


class TestKeySequenceGeneratorPerformance(unittest.TestCase):
    """
    Tests to verify the performance of key generation.

    Performance requirement: Generate 100 keys in under 10ms total.
    """

    def setUp(self):
        """Create a fresh generator for each test."""
        self.generator = KeySequenceGenerator()

    def test_generate_100_class_keys_under_10ms(self):
        """
        Test that 100 class keys can be generated in under 10ms.

        The algorithm uses O(1) counter-based generation, so this
        should easily meet the performance requirement.
        """
        start_time = time.perf_counter()
        for _ in range(100):
            self.generator.get_next_class_key()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self.assertLess(
            elapsed_ms, 10,
            f"Generating 100 class keys took {elapsed_ms:.2f}ms, expected < 10ms"
        )

    def test_generate_100_function_keys_under_10ms(self):
        """
        Test that 100 function keys can be generated in under 10ms.

        The algorithm uses O(1) counter-based generation, so this
        should easily meet the performance requirement.
        """
        start_time = time.perf_counter()
        for _ in range(100):
            self.generator.get_next_function_key()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self.assertLess(
            elapsed_ms, 10,
            f"Generating 100 function keys took {elapsed_ms:.2f}ms, expected < 10ms"
        )

    def test_generate_all_function_keys_reasonable_time(self):
        """
        Test that all 512 function keys can be generated in reasonable time.

        Even generating all possible 3-letter combinations should
        complete quickly with O(1) generation.
        """
        start_time = time.perf_counter()
        for _ in range(512):
            self.generator.get_next_function_key()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self.assertLess(
            elapsed_ms, 100,
            f"Generating all 512 function keys took {elapsed_ms:.2f}ms, expected < 100ms"
        )


class TestKeySequenceGeneratorEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""

    def setUp(self):
        """Create a fresh generator for each test."""
        self.generator = KeySequenceGenerator()

    def test_reset_clears_counters(self):
        """Test that reset() properly clears all counters and tracking."""
        # Generate some keys
        for _ in range(10):
            self.generator.get_next_class_key()
            self.generator.get_next_function_key()

        # Reset
        self.generator.reset()

        # Verify counters are reset
        stats = self.generator.get_stats()
        self.assertEqual(stats['class_keys_used'], 0)
        self.assertEqual(stats['function_keys_used'], 0)
        self.assertEqual(stats['class_keys_remaining'], 4096)
        self.assertEqual(stats['function_keys_remaining'], 512)

    def test_reset_allows_regenerating_same_keys(self):
        """Test that after reset, the same sequence of keys is generated."""
        # Generate first 5 keys
        original_class_keys = [self.generator.get_next_class_key() for _ in range(5)]
        original_function_keys = [self.generator.get_next_function_key() for _ in range(5)]

        # Reset
        self.generator.reset()

        # Generate again
        new_class_keys = [self.generator.get_next_class_key() for _ in range(5)]
        new_function_keys = [self.generator.get_next_function_key() for _ in range(5)]

        self.assertEqual(original_class_keys, new_class_keys)
        self.assertEqual(original_function_keys, new_function_keys)

    def test_function_keys_exhaustion_raises_error(self):
        """Test that exhausting all function keys raises KeysExhaustedError."""
        # Generate all 512 function keys
        for _ in range(512):
            self.generator.get_next_function_key()

        # The next call should raise an error
        with self.assertRaises(KeysExhaustedError) as context:
            self.generator.get_next_function_key()

        self.assertEqual(context.exception.key_type, 'function')
        self.assertEqual(context.exception.max_keys, 512)

    def test_class_keys_exhaustion_raises_error(self):
        """Test that exhausting all class keys raises KeysExhaustedError."""
        # Generate all 4096 class keys
        for _ in range(4096):
            self.generator.get_next_class_key()

        # The next call should raise an error
        with self.assertRaises(KeysExhaustedError) as context:
            self.generator.get_next_class_key()

        self.assertEqual(context.exception.key_type, 'class')
        self.assertEqual(context.exception.max_keys, 4096)

    def test_get_stats_returns_accurate_data(self):
        """Test that get_stats() returns accurate usage information."""
        # Generate some keys
        for _ in range(25):
            self.generator.get_next_class_key()
        for _ in range(10):
            self.generator.get_next_function_key()

        stats = self.generator.get_stats()

        self.assertEqual(stats['class_keys_used'], 25)
        self.assertEqual(stats['class_keys_remaining'], 4096 - 25)
        self.assertEqual(stats['function_keys_used'], 10)
        self.assertEqual(stats['function_keys_remaining'], 512 - 10)

    def test_get_stats_initial_state(self):
        """Test that get_stats() returns correct initial values."""
        stats = self.generator.get_stats()

        self.assertEqual(stats['class_keys_used'], 0)
        self.assertEqual(stats['class_keys_remaining'], 4096)
        self.assertEqual(stats['function_keys_used'], 0)
        self.assertEqual(stats['function_keys_remaining'], 512)

    def test_is_valid_key_with_valid_keys(self):
        """Test that is_valid_key() returns True for valid keys."""
        valid_keys = ['aaaa', 'asdf', 'hjkl', 'llll', 'aaa', 'jkl', 'fds']
        for key in valid_keys:
            self.assertTrue(
                self.generator.is_valid_key(key),
                f"Key '{key}' should be valid"
            )

    def test_is_valid_key_with_invalid_keys(self):
        """Test that is_valid_key() returns False for invalid keys."""
        invalid_keys = ['abcd', 'asdfg', 'xyz', 'test', '1234', 'AS DF']
        for key in invalid_keys:
            self.assertFalse(
                self.generator.is_valid_key(key),
                f"Key '{key}' should be invalid"
            )

    def test_is_valid_key_empty_string(self):
        """Test that is_valid_key() handles empty string."""
        # Empty string should return True (vacuously true - all zero characters are valid)
        self.assertTrue(self.generator.is_valid_key(''))

    def test_multiple_generators_are_independent(self):
        """Test that multiple generator instances are independent."""
        gen1 = KeySequenceGenerator()
        gen2 = KeySequenceGenerator()

        # Generate keys from gen1
        for _ in range(10):
            gen1.get_next_class_key()

        # gen2 should still start from the beginning
        key = gen2.get_next_class_key()
        self.assertEqual(key, 'aaaa', "Independent generator should start from 'aaaa'")


class TestKeysExhaustedError(unittest.TestCase):
    """Tests for the KeysExhaustedError exception class."""

    def test_error_message_format(self):
        """Test that the error message is properly formatted."""
        error = KeysExhaustedError('test', 100)

        self.assertEqual(error.key_type, 'test')
        self.assertEqual(error.max_keys, 100)
        self.assertIn('100', str(error))
        self.assertIn('test', str(error))
        self.assertIn('reset()', str(error))

    def test_error_is_exception_subclass(self):
        """Test that KeysExhaustedError is an Exception subclass."""
        error = KeysExhaustedError('class', 4096)
        self.assertIsInstance(error, Exception)


if __name__ == '__main__':
    unittest.main()
