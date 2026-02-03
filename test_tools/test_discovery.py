"""
Test Discovery Module for Test Management Tool.

This module provides functionality to discover Django and pytest tests in a codebase
using AST (Abstract Syntax Tree) parsing, without importing the test code.

Key Features:
- Discovers APITestCase classes and their test methods
- Discovers pytest test functions and classes
- Detects pytest-django markers
- Groups tests by module for organized display
- Assigns keyboard shortcuts using KeySequenceGenerator

Example Usage:
    >>> from machtms.test_tools.test_discovery import TestDiscovery
    >>>
    >>> discovery = TestDiscovery('/path/to/project')
    >>> apitestcase_tests = discovery.discover_apitestcase_tests()
    >>> pytest_tests = discovery.discover_pytest_tests()
    >>> display = discovery.format_display(apitestcase_tests, 'apitestcase')
    >>> print(display)
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field

from .key_generator import KeySequenceGenerator


# Known Django/DRF test base classes
APITESTCASE_BASES = {'APITestCase', 'APITransactionTestCase', 'APISimpleTestCase'}
DJANGO_TESTCASE_BASES = {'TestCase', 'TransactionTestCase', 'SimpleTestCase', 'LiveServerTestCase'}
ALL_DJANGO_BASES = APITESTCASE_BASES | DJANGO_TESTCASE_BASES

# Pytest marker prefixes
PYTEST_MARKERS = {'pytest.mark.django_db', 'pytest.mark.parametrize', 'pytest.mark'}


@dataclass
class TestFunction:
    """Represents a single test function or method."""
    name: str
    line_number: int
    decorators: List[str] = field(default_factory=list)
    has_django_db_marker: bool = False
    key: str = ""


@dataclass
class TestClass:
    """Represents a test class with its methods."""
    name: str
    line_number: int
    base_classes: List[str] = field(default_factory=list)
    methods: List[TestFunction] = field(default_factory=list)
    framework: str = ""  # 'apitestcase', 'django', or 'pytest'
    key: str = ""


@dataclass
class TestModule:
    """Represents a test file/module."""
    file_path: str
    module_path: str
    display_path: str
    classes: List[TestClass] = field(default_factory=list)
    standalone_functions: List[TestFunction] = field(default_factory=list)


class ASTTestVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts test classes and functions from Python source.

    This visitor walks through the AST and identifies:
    - Classes inheriting from TestCase/APITestCase
    - Classes following pytest naming convention (Test*)
    - Standalone test functions (test_*)
    - Decorator information for pytest markers
    """

    def __init__(self):
        self.classes: List[TestClass] = []
        self.standalone_functions: List[TestFunction] = []
        self._current_class: Optional[TestClass] = None

    def _get_decorator_names(self, decorator_list: List[ast.expr]) -> List[str]:
        """Extract decorator names from a list of decorator nodes."""
        decorators = []
        for dec in decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                # Handle decorators like @pytest.mark.django_db
                parts = []
                node = dec
                while isinstance(node, ast.Attribute):
                    parts.append(node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    parts.append(node.id)
                decorators.append('.'.join(reversed(parts)))
            elif isinstance(dec, ast.Call):
                # Handle decorators with arguments like @pytest.mark.django_db(transaction=True)
                if isinstance(dec.func, ast.Attribute):
                    parts = []
                    node = dec.func
                    while isinstance(node, ast.Attribute):
                        parts.append(node.attr)
                        node = node.value
                    if isinstance(node, ast.Name):
                        parts.append(node.id)
                    decorators.append('.'.join(reversed(parts)))
                elif isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
        return decorators

    def _get_base_class_names(self, bases: List[ast.expr]) -> List[str]:
        """Extract base class names from class definition."""
        base_names = []
        for base in bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle qualified names like rest_framework.test.APITestCase
                base_names.append(base.attr)
        return base_names

    def _has_django_db_marker(self, decorators: List[str]) -> bool:
        """Check if decorators include pytest.mark.django_db."""
        return any('django_db' in dec for dec in decorators)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition node."""
        base_names = self._get_base_class_names(node.bases)

        # Check if this is a test class
        is_apitestcase = bool(set(base_names) & APITESTCASE_BASES)
        is_django_testcase = bool(set(base_names) & DJANGO_TESTCASE_BASES)
        is_pytest_class = node.name.startswith('Test') and not is_apitestcase and not is_django_testcase

        if is_apitestcase or is_django_testcase or is_pytest_class:
            if is_apitestcase:
                framework = 'apitestcase'
            elif is_django_testcase:
                framework = 'django'
            else:
                framework = 'pytest'

            test_class = TestClass(
                name=node.name,
                line_number=node.lineno,
                base_classes=base_names,
                framework=framework,
                methods=[]
            )

            # Find test methods within the class
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                    decorators = self._get_decorator_names(item.decorator_list)
                    test_method = TestFunction(
                        name=item.name,
                        line_number=item.lineno,
                        decorators=decorators,
                        has_django_db_marker=self._has_django_db_marker(decorators)
                    )
                    test_class.methods.append(test_method)

            self.classes.append(test_class)

        # Don't visit children - we handled methods above

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a function definition node (for standalone test functions)."""
        # Only capture top-level functions that look like tests
        if node.name.startswith('test_'):
            decorators = self._get_decorator_names(node.decorator_list)
            test_func = TestFunction(
                name=node.name,
                line_number=node.lineno,
                decorators=decorators,
                has_django_db_marker=self._has_django_db_marker(decorators)
            )
            self.standalone_functions.append(test_func)


class TestDiscovery:
    """
    Main class for discovering tests in a Django project.

    This class provides methods to:
    - Find test files in the project
    - Parse test files using AST to extract test classes and functions
    - Assign keyboard shortcuts to tests
    - Format tests for display

    Attributes:
        project_root: The root directory of the Django project.
        key_generator: Instance of KeySequenceGenerator for assigning shortcuts.
    """

    # Directories to exclude from search
    EXCLUDED_DIRS: Set[str] = {
        '__pycache__', '.git', '.hg', '.svn', 'node_modules',
        'venv', '.venv', 'env', '.env', 'virtualenv',
        '.tox', '.nox', '.pytest_cache', '.mypy_cache',
        'dist', 'build', 'eggs', '*.egg-info',
        'migrations', 'static', 'media', 'templates'
    }

    def __init__(self, project_root: Optional[str] = None, search_path: Optional[str] = None):
        """
        Initialize the TestDiscovery instance.

        Args:
            project_root: Path to the project root directory.
                          If None, uses the current working directory.
            search_path: Path to limit test discovery to. If None, searches
                         from project_root. Can be relative to project_root
                         or an absolute path.
        """
        if project_root is None:
            # Try to find manage.py to determine project root
            project_root = self._find_project_root()

        self.project_root = Path(project_root).resolve()

        # Set search path (defaults to project_root if not specified)
        if search_path is not None:
            search_path_obj = Path(search_path)
            if not search_path_obj.is_absolute():
                search_path_obj = self.project_root / search_path_obj
            self.search_path = search_path_obj.resolve()
        else:
            self.search_path = self.project_root

        self.key_generator = KeySequenceGenerator()
        self._key_map: Dict[str, Dict[str, Any]] = {}

    def _find_project_root(self) -> str:
        """
        Find the project root by looking for manage.py.

        Searches upward from the current directory for a directory
        containing manage.py.

        Returns:
            Path to the project root directory.
        """
        current = Path.cwd()
        while current != current.parent:
            if (current / 'manage.py').exists():
                return str(current)
            current = current.parent
        return str(Path.cwd())

    def _should_exclude_dir(self, dir_name: str) -> bool:
        """Check if a directory should be excluded from search."""
        return dir_name in self.EXCLUDED_DIRS or dir_name.startswith('.')

    def _is_test_file(self, file_path: Path) -> bool:
        """
        Check if a file is a test file based on naming convention.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file matches test file patterns.
        """
        name = file_path.name
        if not name.endswith('.py'):
            return False

        # Match patterns: test*.py, *test.py, *tests.py, *_test.py, test_*.py
        return (
            name.startswith('test') or
            name.endswith('test.py') or
            name.endswith('tests.py') or
            name.endswith('_test.py')
        )

    def discover_test_files(self) -> List[Path]:
        """
        Find all test files in the project.

        Recursively searches the search_path directory for Python files
        matching test file naming patterns, excluding certain directories.

        Returns:
            List of Path objects for discovered test files.
        """
        test_files = []

        for root, dirs, files in os.walk(self.search_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude_dir(d)]

            root_path = Path(root)
            for file_name in files:
                file_path = root_path / file_name
                if self._is_test_file(file_path):
                    test_files.append(file_path)

        return sorted(test_files)

    def _parse_test_file(self, file_path: Path) -> Optional[TestModule]:
        """
        Parse a single test file and extract test classes and functions.

        Uses AST parsing to analyze the file without importing it.

        Args:
            file_path: Path to the test file.

        Returns:
            TestModule containing discovered tests, or None if parsing fails.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))
            visitor = ASTTestVisitor()
            visitor.visit(tree)

            if not visitor.classes and not visitor.standalone_functions:
                return None

            # Calculate paths
            relative_path = file_path.relative_to(self.project_root)
            module_path = str(relative_path).replace('/', '.').replace('.py', '')
            display_path = self._truncate_display_path(str(relative_path))

            return TestModule(
                file_path=str(file_path),
                module_path=module_path,
                display_path=display_path,
                classes=visitor.classes,
                standalone_functions=visitor.standalone_functions
            )

        except SyntaxError as e:
            # Skip files with syntax errors
            print(f"Warning: Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            # Skip files that can't be read
            print(f"Warning: Could not parse {file_path}: {e}")
            return None

    def _truncate_display_path(self, file_path: str, max_levels: int = 2) -> str:
        """
        Truncate file path to show only the last N directory levels.

        Args:
            file_path: The full relative file path.
            max_levels: Maximum number of directory levels to show.

        Returns:
            Truncated path showing at most max_levels directories.

        Example:
            >>> _truncate_display_path('machtms/backend/loads/tests.py', 2)
            'loads/tests.py'
        """
        parts = Path(file_path).parts
        if len(parts) <= max_levels + 1:  # +1 for filename
            return str(Path(*parts))
        return str(Path(*parts[-(max_levels + 1):]))

    def _file_to_module_path(self, file_path: str) -> str:
        """
        Convert a file path to a Python module path.

        Args:
            file_path: Absolute or relative file path.

        Returns:
            Python module path (dot-separated).
        """
        path = Path(file_path)
        if path.is_absolute():
            try:
                path = path.relative_to(self.project_root)
            except ValueError:
                pass

        return str(path).replace('/', '.').replace('.py', '')

    def discover_apitestcase_tests(self) -> List[TestModule]:
        """
        Discover all APITestCase and Django TestCase classes.

        Scans the project for test files and extracts classes that inherit
        from APITestCase, TestCase, or related Django test classes.

        Returns:
            List of TestModule objects containing discovered tests.
        """
        test_files = self.discover_test_files()
        modules = []

        for file_path in test_files:
            module = self._parse_test_file(file_path)
            if module:
                # Filter to only include APITestCase/Django TestCase classes
                apitestcase_classes = [
                    cls for cls in module.classes
                    if cls.framework in ('apitestcase', 'django')
                ]

                if apitestcase_classes:
                    module.classes = apitestcase_classes
                    module.standalone_functions = []  # Not relevant for APITestCase
                    modules.append(module)

        return modules

    def discover_pytest_tests(self) -> List[TestModule]:
        """
        Discover all pytest test classes and functions.

        Scans the project for test files and extracts:
        - Classes following pytest naming convention (Test*)
        - Standalone test functions (test_*)
        - Functions with pytest markers

        Returns:
            List of TestModule objects containing discovered tests.
        """
        test_files = self.discover_test_files()
        modules = []

        for file_path in test_files:
            module = self._parse_test_file(file_path)
            if module:
                # Filter to only include pytest classes
                pytest_classes = [
                    cls for cls in module.classes
                    if cls.framework == 'pytest'
                ]

                if pytest_classes or module.standalone_functions:
                    module.classes = pytest_classes
                    modules.append(module)

        return modules

    def discover_all_tests(self) -> Tuple[List[TestModule], List[TestModule]]:
        """
        Discover both APITestCase and pytest tests.

        Returns:
            Tuple of (apitestcase_modules, pytest_modules).
        """
        test_files = self.discover_test_files()
        apitestcase_modules = []
        pytest_modules = []

        for file_path in test_files:
            module = self._parse_test_file(file_path)
            if not module:
                continue

            # Split classes by framework
            apitestcase_classes = [
                cls for cls in module.classes
                if cls.framework in ('apitestcase', 'django')
            ]
            pytest_classes = [
                cls for cls in module.classes
                if cls.framework == 'pytest'
            ]

            if apitestcase_classes:
                api_module = TestModule(
                    file_path=module.file_path,
                    module_path=module.module_path,
                    display_path=module.display_path,
                    classes=apitestcase_classes,
                    standalone_functions=[]
                )
                apitestcase_modules.append(api_module)

            if pytest_classes or module.standalone_functions:
                pytest_module = TestModule(
                    file_path=module.file_path,
                    module_path=module.module_path,
                    display_path=module.display_path,
                    classes=pytest_classes,
                    standalone_functions=module.standalone_functions
                )
                pytest_modules.append(pytest_module)

        return apitestcase_modules, pytest_modules

    def assign_keys(self, modules: List[TestModule]) -> Dict[str, Dict[str, Any]]:
        """
        Assign keyboard shortcuts to all tests in the given modules.

        Assigns 4-letter keys to test classes and 3-letter keys to
        test methods/functions.

        Args:
            modules: List of TestModule objects to assign keys to.

        Returns:
            Dictionary mapping keys to test metadata.
        """
        key_map = {}

        for module in modules:
            # Assign keys to classes
            for test_class in module.classes:
                class_key = self.key_generator.get_next_class_key()
                test_class.key = class_key

                key_map[class_key] = {
                    'type': 'class',
                    'framework': test_class.framework,
                    'module_path': module.module_path,
                    'class_name': test_class.name,
                    'file_path': module.file_path,
                    'display_path': module.display_path,
                }

                # Assign keys to methods
                for method in test_class.methods:
                    method_key = self.key_generator.get_next_function_key()
                    method.key = method_key

                    key_map[method_key] = {
                        'type': 'function',
                        'framework': test_class.framework,
                        'module_path': module.module_path,
                        'class_name': test_class.name,
                        'function_name': method.name,
                        'file_path': module.file_path,
                        'display_path': module.display_path,
                        'parent_key': class_key,
                        'has_django_db': method.has_django_db_marker,
                    }

            # Assign keys to standalone functions
            for func in module.standalone_functions:
                func_key = self.key_generator.get_next_function_key()
                func.key = func_key

                key_map[func_key] = {
                    'type': 'function',
                    'framework': 'pytest',
                    'module_path': module.module_path,
                    'class_name': None,
                    'function_name': func.name,
                    'file_path': module.file_path,
                    'display_path': module.display_path,
                    'parent_key': None,
                    'has_django_db': func.has_django_db_marker,
                }

        self._key_map = key_map
        return key_map

    def get_key_map(self) -> Dict[str, Dict[str, Any]]:
        """Return the current key-to-test mapping."""
        return self._key_map

    def format_display(
        self,
        modules: List[TestModule],
        test_type: str = 'all',
        show_db_markers: bool = False
    ) -> str:
        """
        Format the test list for terminal display.

        Formats tests in a hierarchical structure with keyboard shortcuts:
        - Module paths as headers
        - Classes with [key] notation
        - Methods/functions with <key> notation

        Args:
            modules: List of TestModule objects to display.
            test_type: Type of tests ('apitestcase', 'pytest', or 'all').
            show_db_markers: Whether to show [db] markers for pytest-django tests.

        Returns:
            Formatted string for terminal output.
        """
        if not modules:
            return "No tests found."

        lines = []

        for module in modules:
            # Module header
            lines.append(f"\n{module.display_path}:")

            # Classes
            for test_class in module.classes:
                lines.append(f"[{test_class.key}] {test_class.name}")

                # Methods (indented)
                for method in test_class.methods:
                    db_marker = " [db]" if show_db_markers and method.has_django_db_marker else ""
                    lines.append(f"    <{method.key}> {method.name}{db_marker}")

            # Standalone functions (not indented)
            for func in module.standalone_functions:
                db_marker = " [db]" if show_db_markers and func.has_django_db_marker else ""
                lines.append(f"<{func.key}> {func.name}{db_marker}")

        return '\n'.join(lines)

    def get_test_summary(
        self,
        apitestcase_modules: List[TestModule],
        pytest_modules: List[TestModule]
    ) -> str:
        """
        Generate a summary of discovered tests.

        Args:
            apitestcase_modules: List of modules with APITestCase tests.
            pytest_modules: List of modules with pytest tests.

        Returns:
            Summary string with test counts.
        """
        api_classes = sum(len(m.classes) for m in apitestcase_modules)
        api_methods = sum(
            sum(len(c.methods) for c in m.classes)
            for m in apitestcase_modules
        )

        pytest_classes = sum(len(m.classes) for m in pytest_modules)
        pytest_methods = sum(
            sum(len(c.methods) for c in m.classes)
            for m in pytest_modules
        )
        pytest_functions = sum(len(m.standalone_functions) for m in pytest_modules)

        db_tests = sum(
            sum(1 for c in m.classes for method in c.methods if method.has_django_db_marker)
            + sum(1 for f in m.standalone_functions if f.has_django_db_marker)
            for m in pytest_modules
        )

        total_classes = api_classes + pytest_classes
        total_functions = api_methods + pytest_methods + pytest_functions

        parts = [
            f"Found {total_classes} test classes",
            f"({api_classes} APITestCase, {pytest_classes} pytest)",
            f", {total_functions} test functions"
        ]

        if db_tests > 0:
            parts.append(f" ({db_tests} require database)")

        return ''.join(parts)

    def lookup_test(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Look up test metadata by key.

        Args:
            key: The keyboard shortcut key.

        Returns:
            Dictionary with test metadata, or None if key not found.
        """
        return self._key_map.get(key)

    def reset(self) -> None:
        """Reset the key generator and clear the key map."""
        self.key_generator.reset()
        self._key_map.clear()
