"""
Key Sequence Generator for Test Management Tool.

This module provides the KeySequenceGenerator class that generates unique,
ergonomic keyboard shortcuts using home row keys for test navigation.

Example Usage:
    from machtms.test_tools.key_generator import KeySequenceGenerator
    # Create a new generator instance
    gen = KeySequenceGenerator()
    # Generate class-level keys (4 characters)
    class_key1 = gen.get_next_class_key()  # Returns 'aaaa'
    class_key2 = gen.get_next_class_key()  # Returns 'aaas'
    # Generate function-level keys (3 characters)
    func_key1 = gen.get_next_function_key()  # Returns 'aaa'
    func_key2 = gen.get_next_function_key()  # Returns 'aas'
    # Check usage statistics
    stats = gen.get_stats()
    print(stats)
    {
        'class_keys_used': 2,
        'class_keys_remaining': 4094,
        'function_keys_used': 2,
        'function_keys_remaining': 510
    }
    # Reset to start fresh
    gen.reset()
    gen.get_next_class_key()  # Returns 'aaaa' again

Character Set:
    The generator uses only home row keys for ergonomic typing:
    a, s, d, f, h, j, k, l (8 characters)

Capacity:
    - 4-letter sequences (class keys): 8^4 = 4,096 possible combinations
    - 3-letter sequences (function keys): 8^3 = 512 possible combinations
"""

from typing import Dict


class KeysExhaustedError(Exception):
    """
    Exception raised when all available key sequences have been used.

    This exception is raised when attempting to generate a new key sequence
    but all possible combinations for that key type have already been used.

    Attributes:
        key_type: The type of key that was exhausted ('class' or 'function')
        message: Explanation of the error
    """

    def __init__(self, key_type: str, max_keys: int):
        self.key_type = key_type
        self.max_keys = max_keys
        self.message = (
            f"All {max_keys} {key_type} keys have been exhausted. "
            f"Call reset() to clear used keys and start over."
        )
        super().__init__(self.message)


class KeySequenceGenerator:
    """
    Generates unique keyboard shortcuts using home row keys.

    This class provides deterministic, counter-based generation of unique
    keyboard shortcuts for test navigation. Keys are generated using a
    base-8 conversion algorithm where each position maps to one of the
    8 allowed home row characters.

    The generator maintains separate counters for class-level (4-letter)
    and function-level (3-letter) keys, ensuring uniqueness within each
    category.

    Attributes:
        ALLOWED_CHARS: List of 8 home row characters used for key generation.
        MAX_CLASS_KEYS: Maximum number of 4-letter combinations (4096).
        MAX_FUNCTION_KEYS: Maximum number of 3-letter combinations (512).

    Example:
        >>> gen = KeySequenceGenerator()
        >>> gen.get_next_class_key()
        'aaaa'
        >>> gen.get_next_class_key()
        'aaas'
        >>> gen.get_next_function_key()
        'aaa'
        >>> gen.get_stats()
        {
            'class_keys_used': 2,
            'class_keys_remaining': 4094,
            'function_keys_used': 1,
            'function_keys_remaining': 511
        }
    """

    ALLOWED_CHARS = ['a', 's', 'd', 'f', 'h', 'j', 'k', 'l']
    MAX_CLASS_KEYS = 4096  # 8^4
    MAX_FUNCTION_KEYS = 512  # 8^3

    def __init__(self) -> None:
        """
        Initialize the KeySequenceGenerator with fresh counters and tracking sets.

        Creates new instances of counters and sets for tracking used keys.
        Both class and function key counters start at 0.
        """
        self._class_key_counter: int = 0
        self._function_key_counter: int = 0
        self._used_class_keys: set = set()
        self._used_function_keys: set = set()

    def _generate_sequence(self, counter: int, length: int) -> str:
        """
        Convert a counter value to a base-8 sequence of specified length.

        Uses the ALLOWED_CHARS list as digits in a base-8 number system.
        The counter is converted to base-8 and each digit is mapped to
        the corresponding character.

        Args:
            counter: The numeric value to convert (0 to 8^length - 1).
            length: The desired length of the output sequence.

        Returns:
            A string of exactly length characters from ALLOWED_CHARS.

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen._generate_sequence(0, 4)
            'aaaa'
            >>> gen._generate_sequence(1, 4)
            'aaas'
            >>> gen._generate_sequence(8, 4)
            'aada'
        """
        result = []
        value = counter
        for _ in range(length):
            result.append(self.ALLOWED_CHARS[value % 8])
            value //= 8
        return ''.join(reversed(result))

    def get_next_class_key(self) -> str:
        """
        Return the next available 4-letter sequence for class-level shortcuts.

        Generates a unique 4-character key using the base-8 counter approach.
        Each call increments the internal counter and returns a new unique key.

        Returns:
            A 4-character string using only characters from ALLOWED_CHARS.

        Raises:
            KeysExhaustedError: If all 4096 possible class keys have been used.

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen.get_next_class_key()
            'aaaa'
            >>> gen.get_next_class_key()
            'aaas'
        """
        if self._class_key_counter >= self.MAX_CLASS_KEYS:
            raise KeysExhaustedError('class', self.MAX_CLASS_KEYS)

        key = self._generate_sequence(self._class_key_counter, 4)
        self._used_class_keys.add(key)
        self._class_key_counter += 1
        return key

    def get_next_function_key(self) -> str:
        """
        Return the next available 3-letter sequence for function-level shortcuts.

        Generates a unique 3-character key using the base-8 counter approach.
        Each call increments the internal counter and returns a new unique key.

        Returns:
            A 3-character string using only characters from ALLOWED_CHARS.

        Raises:
            KeysExhaustedError: If all 512 possible function keys have been used.

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen.get_next_function_key()
            'aaa'
            >>> gen.get_next_function_key()
            'aas'
        """
        if self._function_key_counter >= self.MAX_FUNCTION_KEYS:
            raise KeysExhaustedError('function', self.MAX_FUNCTION_KEYS)

        key = self._generate_sequence(self._function_key_counter, 3)
        self._used_function_keys.add(key)
        self._function_key_counter += 1
        return key

    def reset(self) -> None:
        """
        Clear all used sequences and reset counters to their initial state.

        After calling reset(), the generator will start producing keys from
        the beginning again ('aaaa' for class keys, 'aaa' for function keys).

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen.get_next_class_key()
            'aaaa'
            >>> gen.get_next_class_key()
            'aaas'
            >>> gen.reset()
            >>> gen.get_next_class_key()
            'aaaa'
        """
        self._class_key_counter = 0
        self._function_key_counter = 0
        self._used_class_keys.clear()
        self._used_function_keys.clear()

    def get_stats(self) -> Dict[str, int]:
        """
        Return usage statistics for both key types.

        Provides information about how many keys have been used and how many
        remain available for both class-level and function-level keys.

        Returns:
            A dictionary containing:
                - class_keys_used: Number of 4-letter keys generated
                - class_keys_remaining: Number of 4-letter keys still available
                - function_keys_used: Number of 3-letter keys generated
                - function_keys_remaining: Number of 3-letter keys still available

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen.get_next_class_key()
            'aaaa'
            >>> gen.get_next_function_key()
            'aaa'
            >>> gen.get_stats()
            {
                'class_keys_used': 1,
                'class_keys_remaining': 4095,
                'function_keys_used': 1,
                'function_keys_remaining': 511
            }
        """
        return {
            'class_keys_used': self._class_key_counter,
            'class_keys_remaining': self.MAX_CLASS_KEYS - self._class_key_counter,
            'function_keys_used': self._function_key_counter,
            'function_keys_remaining': self.MAX_FUNCTION_KEYS - self._function_key_counter,
        }

    def is_valid_key(self, key: str) -> bool:
        """
        Check if a key string contains only allowed characters.

        Validates that a given key sequence uses only the allowed home row
        characters. This is useful for validating user input or testing.

        Args:
            key: The key string to validate.

        Returns:
            True if all characters in the key are in ALLOWED_CHARS, False otherwise.

        Example:
            >>> gen = KeySequenceGenerator()
            >>> gen.is_valid_key('asdf')
            True
            >>> gen.is_valid_key('abcd')
            False
        """
        return all(char in self.ALLOWED_CHARS for char in key)
