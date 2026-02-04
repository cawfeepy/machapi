"""
Unit tests for the Test Runner module.

These tests verify that the test runner module correctly:
- Generates Django test commands
- Generates pytest commands
- Executes commands and captures output
- Detects pytest availability
"""

import os
import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from test_tools.test_runner import TestRunner, TestResult


class TestResultTestCase(TestCase):
    """Tests for the TestResult dataclass."""

    def test_success_property_true_for_zero_exit(self):
        """Test that success is True when exit_code is 0."""
        result = TestResult(
            command='python manage.py test',
            exit_code=0,
            stdout='OK',
            stderr=''
        )
        self.assertTrue(result.success)

    def test_success_property_false_for_nonzero_exit(self):
        """Test that success is False when exit_code is non-zero."""
        result = TestResult(
            command='python manage.py test',
            exit_code=1,
            stdout='',
            stderr='FAILED'
        )
        self.assertFalse(result.success)


class TestRunnerDjangoCommandTestCase(TestCase):
    """Tests for Django test command generation."""

    def setUp(self):
        """Create a TestRunner instance with a mock project root."""
        self.runner = TestRunner(project_root='/mock/project')

    def test_generates_class_test_command(self):
        """Test command generation for a test class."""
        test_info = {
            'type': 'class',
            'module_path': 'machtms.backend.loads.tests',
            'class_name': 'LoadWriteSerializerTestCase',
            'framework': 'apitestcase',
        }

        command = self.runner.get_django_test_command(test_info)

        expected = 'python manage.py test machtms.backend.loads.tests.LoadWriteSerializerTestCase'
        self.assertEqual(command, expected)

    def test_generates_method_test_command(self):
        """Test command generation for a specific test method."""
        test_info = {
            'type': 'function',
            'module_path': 'machtms.backend.loads.tests',
            'class_name': 'LoadWriteSerializerTestCase',
            'function_name': 'test_create_load',
            'framework': 'apitestcase',
        }

        command = self.runner.get_django_test_command(test_info)

        expected = 'python manage.py test machtms.backend.loads.tests.LoadWriteSerializerTestCase.test_create_load'
        self.assertEqual(command, expected)

    def test_generates_verbose_command(self):
        """Test that verbose flag is added correctly."""
        test_info = {
            'type': 'class',
            'module_path': 'myapp.tests',
            'class_name': 'MyTestCase',
            'framework': 'django',
        }

        command = self.runner.get_django_test_command(test_info, verbose=True)

        self.assertIn('-v', command)
        self.assertIn('2', command)

    def test_generates_all_tests_command(self):
        """Test command generation for running all tests."""
        command = self.runner.get_django_all_tests_command()

        self.assertIn('python manage.py test', command)
        self.assertIn('--pattern', command)


class TestRunnerPytestCommandTestCase(TestCase):
    """Tests for pytest command generation."""

    def setUp(self):
        """Create a TestRunner instance with a mock project root."""
        self.runner = TestRunner(
            project_root='/mock/project',
            django_settings='api.settings'
        )

    def test_generates_class_test_command(self):
        """Test command generation for a pytest class."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests/test_utils.py',
            'class_name': 'TestUserModel',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info)

        self.assertIn('pytest', command)
        self.assertIn('tests/test_utils.py::TestUserModel', command)

    def test_generates_method_test_command(self):
        """Test command generation for a pytest class method."""
        test_info = {
            'type': 'function',
            'file_path': '/mock/project/tests/test_utils.py',
            'class_name': 'TestUserModel',
            'function_name': 'test_user_creation',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info)

        self.assertIn('pytest', command)
        self.assertIn('tests/test_utils.py::TestUserModel::test_user_creation', command)

    def test_generates_standalone_function_command(self):
        """Test command generation for a standalone pytest function."""
        test_info = {
            'type': 'function',
            'file_path': '/mock/project/tests/test_utils.py',
            'class_name': None,
            'function_name': 'test_helper_function',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info)

        self.assertIn('pytest', command)
        self.assertIn('tests/test_utils.py::test_helper_function', command)

    @patch.dict(os.environ, {}, clear=True)
    def test_adds_django_settings_when_not_in_env(self):
        """Test that Django settings are added when not in environment."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests.py',
            'class_name': 'TestClass',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info)

        self.assertIn('--ds', command)
        self.assertIn('api.settings', command)

    @patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'myproject.settings'})
    def test_skips_settings_when_in_env(self):
        """Test that Django settings are skipped when in environment."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests.py',
            'class_name': 'TestClass',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info)

        self.assertNotIn('--ds', command)

    def test_adds_verbose_flag(self):
        """Test that verbose flag is added correctly."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests.py',
            'class_name': 'TestClass',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info, verbose=True)

        self.assertIn('-v', command)

    def test_adds_reuse_db_flag(self):
        """Test that reuse-db flag is added correctly."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests.py',
            'class_name': 'TestClass',
            'framework': 'pytest',
        }

        command = self.runner.get_pytest_command(test_info, reuse_db=True)

        self.assertIn('--reuse-db', command)


class TestRunnerFrameworkSelectionTestCase(TestCase):
    """Tests for automatic framework selection."""

    def setUp(self):
        """Create a TestRunner instance."""
        self.runner = TestRunner(project_root='/mock/project')

    def test_selects_django_for_apitestcase(self):
        """Test that Django test runner is selected for APITestCase."""
        test_info = {
            'type': 'class',
            'module_path': 'myapp.tests',
            'class_name': 'MyAPITestCase',
            'framework': 'apitestcase',
        }

        command = self.runner.get_test_command(test_info)

        self.assertIn('python manage.py test', command)

    def test_selects_django_for_django_testcase(self):
        """Test that Django test runner is selected for Django TestCase."""
        test_info = {
            'type': 'class',
            'module_path': 'myapp.tests',
            'class_name': 'MyTestCase',
            'framework': 'django',
        }

        command = self.runner.get_test_command(test_info)

        self.assertIn('python manage.py test', command)

    def test_selects_pytest_for_pytest_tests(self):
        """Test that pytest is selected for pytest tests."""
        test_info = {
            'type': 'class',
            'file_path': '/mock/project/tests.py',
            'class_name': 'TestSomething',
            'framework': 'pytest',
        }

        command = self.runner.get_test_command(test_info)

        self.assertIn('pytest', command)


class TestRunnerPytestDetectionTestCase(TestCase):
    """Tests for pytest availability detection."""

    def setUp(self):
        """Create a TestRunner instance."""
        self.runner = TestRunner(project_root='/mock/project')

    @patch('importlib.util.find_spec')
    def test_detects_pytest_available(self, mock_find_spec):
        """Test that pytest is detected when installed."""
        mock_find_spec.return_value = MagicMock()

        self.assertTrue(self.runner.is_pytest_available())

    @patch('importlib.util.find_spec')
    def test_detects_pytest_unavailable(self, mock_find_spec):
        """Test that missing pytest is detected."""
        mock_find_spec.return_value = None

        self.assertFalse(self.runner.is_pytest_available())

    def test_install_message_includes_uv(self):
        """Test that install message uses uv."""
        message = self.runner.get_pytest_install_message()

        self.assertIn('uv add', message)
        self.assertIn('pytest', message)


class TestRunnerCommandExecutionTestCase(TestCase):
    """Tests for command execution."""

    def setUp(self):
        """Create a TestRunner instance."""
        self.runner = TestRunner(project_root='/tmp')

    @patch('subprocess.run')
    def test_captures_command_output(self, mock_run):
        """Test that command output is captured correctly."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Test passed',
            stderr=''
        )

        result = self.runner.run_command('echo test')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, 'Test passed')
        self.assertTrue(result.success)

    @patch('subprocess.run')
    def test_handles_command_failure(self, mock_run):
        """Test that command failures are handled correctly."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='Error occurred'
        )

        result = self.runner.run_command('false')

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stderr, 'Error occurred')
        self.assertFalse(result.success)

    @patch('subprocess.run')
    def test_handles_timeout(self, mock_run):
        """Test that timeouts are handled correctly."""
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)

        result = self.runner.run_command('sleep 100', timeout=5)

        self.assertEqual(result.exit_code, -1)
        self.assertIn('timeout', result.stderr.lower())

    @patch('subprocess.run')
    def test_runs_from_project_root(self, mock_run):
        """Test that commands run from project root."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',
            stderr=''
        )

        self.runner.run_command('echo test')

        # Check that cwd was set to project root
        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs['cwd'], '/tmp')
