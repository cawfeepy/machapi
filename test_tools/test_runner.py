"""
Test Runner Module for Test Management Tool.

This module provides functionality to generate and execute test commands
for both Django's test runner and pytest.

Key Features:
- Generate Django test commands for APITestCase tests
- Generate pytest commands for pytest tests
- Execute tests and capture output
- Detect pytest availability

Example Usage:
    >>> from machtms.test_tools.test_runner import TestRunner
    >>>
    >>> runner = TestRunner()
    >>>
    >>> # Generate a Django test command
    >>> cmd = runner.get_django_test_command({
    ...     'type': 'class',
    ...     'module_path': 'machtms.backend.loads.tests',
    ...     'class_name': 'LoadWriteSerializerTestCase',
    ... })
    >>> print(cmd)
    'python manage.py test machtms.backend.loads.tests.LoadWriteSerializerTestCase'
    >>>
    >>> # Execute a test
    >>> result = runner.run_test(cmd)
    >>> print(result.exit_code)
    0
"""

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class TestResult:
    """
    Represents the result of a test execution.

    Attributes:
        command: The command that was executed.
        exit_code: The exit code from the test process.
        stdout: Standard output from the test.
        stderr: Standard error from the test.
        success: Whether the test passed (exit_code == 0).
    """
    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Return True if the test passed."""
        return self.exit_code == 0


class TestRunner:
    """
    Generates and executes test commands for Django and pytest.

    This class provides methods to:
    - Generate appropriate test commands based on test type and framework
    - Execute test commands and capture results
    - Detect pytest availability

    Attributes:
        project_root: Path to the Django project root (where manage.py is).
        django_settings: The Django settings module to use.
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        django_settings: Optional[str] = None
    ):
        """
        Initialize the TestRunner.

        Args:
            project_root: Path to the project root. If None, searches for manage.py.
            django_settings: Django settings module. If None, uses environment or default.
        """
        self.project_root = Path(project_root) if project_root else self._find_project_root()
        self.django_settings = django_settings or self._get_django_settings()

    def _find_project_root(self) -> Path:
        """Find the project root by looking for manage.py."""
        current = Path.cwd()
        while current != current.parent:
            if (current / 'manage.py').exists():
                return current
            current = current.parent
        return Path.cwd()

    def _get_django_settings(self) -> str:
        """Get the Django settings module from environment or default."""
        return os.environ.get('DJANGO_SETTINGS_MODULE', 'api.settings')

    def is_pytest_available(self) -> bool:
        """
        Check if pytest is installed.

        Returns:
            True if pytest is available, False otherwise.
        """
        return importlib.util.find_spec('pytest') is not None

    def is_pytest_django_available(self) -> bool:
        """
        Check if pytest-django is installed.

        Returns:
            True if pytest-django is available, False otherwise.
        """
        return importlib.util.find_spec('pytest_django') is not None

    def get_pytest_install_message(self) -> str:
        """Return a helpful message for installing pytest."""
        return "pytest not found. Install with: uv add pytest pytest-django"

    def get_django_test_command(
        self,
        test_info: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Generate a Django test runner command.

        Args:
            test_info: Dictionary with test metadata from TestDiscovery.
            verbose: Whether to add verbose flag.

        Returns:
            The test command string.

        Examples:
            For a class:
                'python manage.py test machtms.backend.loads.tests.LoadTestCase'

            For a specific method:
                'python manage.py test machtms.backend.loads.tests.LoadTestCase.test_create'
        """
        module_path = test_info['module_path']
        class_name = test_info.get('class_name')
        function_name = test_info.get('function_name')
        test_type = test_info.get('type', 'function')

        # Build the test path
        if test_type == 'class':
            test_path = f"{module_path}.{class_name}"
        else:
            # Function test (method within a class)
            if class_name:
                test_path = f"{module_path}.{class_name}.{function_name}"
            else:
                # Standalone function - Django test runner doesn't support this well
                test_path = f"{module_path}.{function_name}"

        parts = ['python', 'manage.py', 'test', test_path]

        if verbose:
            parts.append('-v')
            parts.append('2')

        return ' '.join(parts)

    def get_django_all_tests_command(
        self,
        pattern: str = "*test*.py",
        verbose: bool = False
    ) -> str:
        """
        Generate command to run all Django tests.

        Args:
            pattern: File pattern for test discovery.
            verbose: Whether to add verbose flag.

        Returns:
            The test command string.
        """
        parts = ['python', 'manage.py', 'test', f'--pattern="{pattern}"']

        if verbose:
            parts.extend(['-v', '2'])

        return ' '.join(parts)

    def get_pytest_command(
        self,
        test_info: Dict[str, Any],
        verbose: bool = False,
        reuse_db: bool = False
    ) -> str:
        """
        Generate a pytest command.

        Args:
            test_info: Dictionary with test metadata from TestDiscovery.
            verbose: Whether to add verbose flag.
            reuse_db: Whether to reuse the database between tests.

        Returns:
            The pytest command string.

        Examples:
            For a class:
                'pytest path/to/tests.py::TestClassName'

            For a method in a class:
                'pytest path/to/tests.py::TestClassName::test_method'

            For a standalone function:
                'pytest path/to/tests.py::test_function'
        """
        file_path = test_info['file_path']
        class_name = test_info.get('class_name')
        function_name = test_info.get('function_name')
        test_type = test_info.get('type', 'function')

        # Make path relative to project root if absolute
        path = Path(file_path)
        if path.is_absolute():
            try:
                path = path.relative_to(self.project_root)
            except ValueError:
                pass

        # Build the pytest node ID
        if test_type == 'class':
            node_id = f"{path}::{class_name}"
        else:
            if class_name:
                # Method in a class
                node_id = f"{path}::{class_name}::{function_name}"
            else:
                # Standalone function
                node_id = f"{path}::{function_name}"

        parts = ['pytest', str(node_id)]

        # Add Django settings if not set in environment
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            parts.extend(['--ds', self.django_settings])

        if verbose:
            parts.append('-v')

        if reuse_db:
            parts.append('--reuse-db')

        return ' '.join(parts)

    def get_pytest_all_tests_command(
        self,
        verbose: bool = False,
        reuse_db: bool = False
    ) -> str:
        """
        Generate command to run all pytest tests.

        Args:
            verbose: Whether to add verbose flag.
            reuse_db: Whether to reuse the database between tests.

        Returns:
            The pytest command string.
        """
        parts = ['pytest', str(self.project_root)]

        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            parts.extend(['--ds', self.django_settings])

        if verbose:
            parts.append('-v')

        if reuse_db:
            parts.append('--reuse-db')

        return ' '.join(parts)

    def get_test_command(
        self,
        test_info: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Generate the appropriate test command based on framework.

        Automatically selects Django test runner or pytest based on
        the test's framework.

        Args:
            test_info: Dictionary with test metadata from TestDiscovery.
            verbose: Whether to add verbose flag.

        Returns:
            The test command string.
        """
        framework = test_info.get('framework', 'apitestcase')

        if framework in ('apitestcase', 'django'):
            return self.get_django_test_command(test_info, verbose)
        else:
            return self.get_pytest_command(test_info, verbose)

    def run_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        capture_output: bool = True
    ) -> TestResult:
        """
        Execute a test command.

        Args:
            command: The command to execute.
            timeout: Optional timeout in seconds.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            TestResult with command output and exit code.
        """
        try:
            # Change to project root for execution
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )

            return TestResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout if capture_output else '',
                stderr=result.stderr if capture_output else ''
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                command=command,
                exit_code=-1,
                stdout='',
                stderr=f'Test timed out after {timeout} seconds'
            )
        except Exception as e:
            return TestResult(
                command=command,
                exit_code=-1,
                stdout='',
                stderr=str(e)
            )

    def run_test_interactive(
        self,
        command: str,
        timeout: Optional[int] = None
    ) -> int:
        """
        Execute a test command with live output.

        Runs the test and streams output directly to the terminal,
        useful for interactive test running.

        Args:
            command: The command to execute.
            timeout: Optional timeout in seconds.

        Returns:
            The exit code from the test process.
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                timeout=timeout,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )
            return result.returncode

        except subprocess.TimeoutExpired:
            print(f"\nTest timed out after {timeout} seconds")
            return -1
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
            return -2
        except Exception as e:
            print(f"\nError running test: {e}")
            return -1

    def run_test(
        self,
        test_info: Dict[str, Any],
        verbose: bool = False,
        interactive: bool = True,
        timeout: Optional[int] = None
    ) -> Tuple[str, int]:
        """
        Run a test given its metadata.

        This is the main entry point for running tests. It generates
        the appropriate command and executes it.

        Args:
            test_info: Dictionary with test metadata from TestDiscovery.
            verbose: Whether to run in verbose mode.
            interactive: Whether to run interactively with live output.
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (command, exit_code).
        """
        command = self.get_test_command(test_info, verbose)

        if interactive:
            exit_code = self.run_test_interactive(command, timeout)
            return command, exit_code
        else:
            result = self.run_command(command, timeout)
            return command, result.exit_code

    def run_all_tests(
        self,
        framework: str,
        verbose: bool = False,
        interactive: bool = True,
        timeout: Optional[int] = None
    ) -> Tuple[str, int]:
        """
        Run all tests of a given framework.

        Args:
            framework: 'apitestcase' or 'pytest'.
            verbose: Whether to run in verbose mode.
            interactive: Whether to run interactively with live output.
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (command, exit_code).
        """
        if framework in ('apitestcase', 'django'):
            command = self.get_django_all_tests_command(verbose=verbose)
        else:
            if not self.is_pytest_available():
                print(self.get_pytest_install_message())
                return '', -1
            command = self.get_pytest_all_tests_command(verbose=verbose)

        if interactive:
            exit_code = self.run_test_interactive(command, timeout)
            return command, exit_code
        else:
            result = self.run_command(command, timeout)
            return command, result.exit_code
