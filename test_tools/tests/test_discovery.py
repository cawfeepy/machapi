"""
Unit tests for the Test Discovery module.

These tests verify that the test discovery module correctly:
- Finds test files in the project
- Parses APITestCase classes and methods
- Parses pytest test functions and classes
- Detects pytest-django markers
- Assigns keyboard shortcuts
- Formats output correctly
"""

import ast
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from machtms.test_tools.test_discovery import (
    TestDiscovery,
    TestModule,
    TestClass,
    TestFunction,
    ASTTestVisitor,
)


class ASTTestVisitorTestCase(TestCase):
    """Tests for the ASTTestVisitor class."""

    def test_finds_apitestcase_class(self):
        """Test that APITestCase classes are correctly identified."""
        source = '''
from rest_framework.test import APITestCase

class LoadTestCase(APITestCase):
    def test_create_load(self):
        pass

    def test_update_load(self):
        pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.classes), 1)
        self.assertEqual(visitor.classes[0].name, 'LoadTestCase')
        self.assertEqual(visitor.classes[0].framework, 'apitestcase')
        self.assertEqual(len(visitor.classes[0].methods), 2)

    def test_finds_django_testcase_class(self):
        """Test that Django TestCase classes are correctly identified."""
        source = '''
from django.test import TestCase

class MyTestCase(TestCase):
    def test_something(self):
        pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.classes), 1)
        self.assertEqual(visitor.classes[0].name, 'MyTestCase')
        self.assertEqual(visitor.classes[0].framework, 'django')

    def test_finds_pytest_class(self):
        """Test that pytest-style classes are correctly identified."""
        source = '''
class TestUserModel:
    def test_user_creation(self):
        pass

    def test_user_validation(self):
        pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.classes), 1)
        self.assertEqual(visitor.classes[0].name, 'TestUserModel')
        self.assertEqual(visitor.classes[0].framework, 'pytest')
        self.assertEqual(len(visitor.classes[0].methods), 2)

    def test_finds_standalone_functions(self):
        """Test that standalone test functions are correctly identified."""
        source = '''
def test_helper_function():
    pass

def test_another_function():
    pass

def not_a_test():
    pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.standalone_functions), 2)
        function_names = [f.name for f in visitor.standalone_functions]
        self.assertIn('test_helper_function', function_names)
        self.assertIn('test_another_function', function_names)
        self.assertNotIn('not_a_test', function_names)

    def test_detects_pytest_django_db_marker(self):
        """Test that @pytest.mark.django_db decorator is detected."""
        source = '''
import pytest

@pytest.mark.django_db
def test_with_database():
    pass

@pytest.mark.django_db(transaction=True)
def test_with_transaction():
    pass

def test_without_db():
    pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.standalone_functions), 3)

        db_tests = [f for f in visitor.standalone_functions if f.has_django_db_marker]
        non_db_tests = [f for f in visitor.standalone_functions if not f.has_django_db_marker]

        self.assertEqual(len(db_tests), 2)
        self.assertEqual(len(non_db_tests), 1)

    def test_ignores_non_test_methods(self):
        """Test that non-test methods in classes are ignored."""
        source = '''
from rest_framework.test import APITestCase

class LoadTestCase(APITestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def helper_method(self):
        pass

    def test_actual_test(self):
        pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.classes), 1)
        self.assertEqual(len(visitor.classes[0].methods), 1)
        self.assertEqual(visitor.classes[0].methods[0].name, 'test_actual_test')

    def test_extracts_decorators(self):
        """Test that decorators are correctly extracted."""
        source = '''
import pytest

@pytest.mark.parametrize("value", [1, 2, 3])
@pytest.mark.django_db
def test_with_decorators():
    pass
'''
        tree = ast.parse(source)
        visitor = ASTTestVisitor()
        visitor.visit(tree)

        self.assertEqual(len(visitor.standalone_functions), 1)
        decorators = visitor.standalone_functions[0].decorators
        self.assertIn('pytest.mark.parametrize', decorators)
        self.assertIn('pytest.mark.django_db', decorators)


class TestDiscoveryTestCase(TestCase):
    """Tests for the TestDiscovery class."""

    def setUp(self):
        """Create a temporary directory with test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.discovery = TestDiscovery(self.temp_dir)

        # Create test file structure
        self._create_test_file(
            'tests.py',
            '''
from rest_framework.test import APITestCase

class LoadTestCase(APITestCase):
    def test_create(self):
        pass

    def test_update(self):
        pass
'''
        )

        self._create_test_file(
            'test_utils.py',
            '''
import pytest

@pytest.mark.django_db
def test_helper():
    pass

class TestHelperClass:
    def test_method(self):
        pass
'''
        )

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_file(self, filename: str, content: str):
        """Create a test file in the temporary directory."""
        file_path = Path(self.temp_dir) / filename
        file_path.write_text(content)

    def test_discovers_test_files(self):
        """Test that test files are correctly discovered."""
        files = self.discovery.discover_test_files()
        filenames = [f.name for f in files]

        self.assertIn('tests.py', filenames)
        self.assertIn('test_utils.py', filenames)

    def test_discovers_apitestcase_tests(self):
        """Test that APITestCase tests are correctly discovered."""
        modules = self.discovery.discover_apitestcase_tests()

        self.assertEqual(len(modules), 1)
        self.assertEqual(len(modules[0].classes), 1)
        self.assertEqual(modules[0].classes[0].name, 'LoadTestCase')
        self.assertEqual(len(modules[0].classes[0].methods), 2)

    def test_discovers_pytest_tests(self):
        """Test that pytest tests are correctly discovered."""
        modules = self.discovery.discover_pytest_tests()

        self.assertEqual(len(modules), 1)
        # Should have one class and one standalone function
        self.assertEqual(len(modules[0].classes), 1)
        self.assertEqual(len(modules[0].standalone_functions), 1)

    def test_assigns_keys_to_tests(self):
        """Test that keys are correctly assigned to tests."""
        modules = self.discovery.discover_apitestcase_tests()
        key_map = self.discovery.assign_keys(modules)

        # Should have keys for class + 2 methods
        self.assertEqual(len(key_map), 3)

        # Check key types
        class_keys = [k for k, v in key_map.items() if v['type'] == 'class']
        function_keys = [k for k, v in key_map.items() if v['type'] == 'function']

        self.assertEqual(len(class_keys), 1)
        self.assertEqual(len(function_keys), 2)

        # Class keys should be 4 chars, function keys 3 chars
        for key in class_keys:
            self.assertEqual(len(key), 4)
        for key in function_keys:
            self.assertEqual(len(key), 3)

    def test_truncates_display_path(self):
        """Test that display paths are correctly truncated."""
        result = self.discovery._truncate_display_path(
            'machtms/backend/loads/tests.py',
            max_levels=2
        )
        self.assertEqual(result, 'loads/tests.py')

    def test_format_display_output(self):
        """Test that display output is correctly formatted."""
        modules = self.discovery.discover_apitestcase_tests()
        self.discovery.assign_keys(modules)

        output = self.discovery.format_display(modules)

        # Should contain class name with brackets
        self.assertIn('LoadTestCase', output)
        self.assertIn('[', output)  # Class key brackets
        self.assertIn('<', output)  # Function key brackets

    def test_excludes_pycache_directories(self):
        """Test that __pycache__ directories are excluded."""
        # Create a __pycache__ directory with a test file
        pycache_dir = Path(self.temp_dir) / '__pycache__'
        pycache_dir.mkdir()
        (pycache_dir / 'test_cached.py').write_text('def test_foo(): pass')

        files = self.discovery.discover_test_files()
        filenames = [f.name for f in files]

        self.assertNotIn('test_cached.py', filenames)

    def test_handles_syntax_errors_gracefully(self):
        """Test that files with syntax errors are skipped."""
        self._create_test_file('test_broken.py', 'def test_broken( pass')

        # Should not raise an exception
        modules = self.discovery.discover_pytest_tests()

        # The broken file should be skipped
        file_paths = [m.file_path for m in modules]
        broken_file = str(Path(self.temp_dir) / 'test_broken.py')
        self.assertNotIn(broken_file, file_paths)

    def test_lookup_test_by_key(self):
        """Test that tests can be looked up by their assigned key."""
        modules = self.discovery.discover_apitestcase_tests()
        key_map = self.discovery.assign_keys(modules)

        # Get a key
        some_key = list(key_map.keys())[0]

        # Look it up
        result = self.discovery.lookup_test(some_key)

        self.assertIsNotNone(result)
        self.assertIn('type', result)
        self.assertIn('framework', result)

    def test_reset_clears_key_map(self):
        """Test that reset clears the key map and generator."""
        modules = self.discovery.discover_apitestcase_tests()
        self.discovery.assign_keys(modules)

        self.assertTrue(len(self.discovery.get_key_map()) > 0)

        self.discovery.reset()

        self.assertEqual(len(self.discovery.get_key_map()), 0)


class TestModuleDataclassTestCase(TestCase):
    """Tests for the TestModule dataclass."""

    def test_creates_test_module(self):
        """Test that TestModule can be created with all fields."""
        test_class = TestClass(
            name='MyTestCase',
            line_number=10,
            base_classes=['APITestCase'],
            methods=[
                TestFunction(name='test_one', line_number=15),
                TestFunction(name='test_two', line_number=20),
            ],
            framework='apitestcase'
        )

        module = TestModule(
            file_path='/path/to/tests.py',
            module_path='myapp.tests',
            display_path='myapp/tests.py',
            classes=[test_class],
            standalone_functions=[]
        )

        self.assertEqual(module.file_path, '/path/to/tests.py')
        self.assertEqual(len(module.classes), 1)
        self.assertEqual(len(module.classes[0].methods), 2)
