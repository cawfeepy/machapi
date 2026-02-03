"""
Test Tools Package

This package provides utilities for discovering and running Django and pytest tests
with keyboard shortcuts.

Components:
- key_generator: Generates unique keyboard shortcuts for test navigation
- test_discovery: Discovers APITestCase and pytest tests in the codebase
- test_runner: Executes tests based on user selection
- display: Terminal display utilities for colored output

Usage:
    python manage.py runtests

Example:
    >>> from machtms.test_tools import TestDiscovery, TestRunner
    >>>
    >>> discovery = TestDiscovery()
    >>> modules = discovery.discover_apitestcase_tests()
    >>> key_map = discovery.assign_keys(modules)
    >>>
    >>> runner = TestRunner()
    >>> command = runner.get_test_command(key_map['aaaa'])
"""

__version__ = '1.0.0'

# Import main classes for convenience
from .key_generator import KeySequenceGenerator, KeysExhaustedError
from .test_discovery import (
    TestDiscovery,
    TestModule,
    TestClass,
    TestFunction,
)
from .test_runner import TestRunner, TestResult
from .display import Display, Colors

__all__ = [
    'KeySequenceGenerator',
    'KeysExhaustedError',
    'TestDiscovery',
    'TestModule',
    'TestClass',
    'TestFunction',
    'TestRunner',
    'TestResult',
    'Display',
    'Colors',
]
