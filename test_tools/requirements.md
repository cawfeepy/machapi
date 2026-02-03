# Test Management Tool - Requirements Specification

## Project Overview

This tool provides a streamlined interface for running Django REST Framework tests with minimal keystrokes. Developers can quickly discover, navigate, and execute tests through an intuitive keyboard-driven interface.

## Goals

1. Reduce friction in running individual tests or test classes
2. Provide visual organization of test structure
3. Support both Django's APITestCase and pytest patterns (including pytest-django)
4. Enable quick navigation via unique keyboard shortcuts

## Architecture

The tool consists of three main components:

### 1. Key Sequence Generator (Developer 1)
Generates unique keyboard shortcuts for test navigation.

### 2. Test Discovery & Runner (Developer 2)
Discovers tests in the codebase and organizes them for display.

### 3. Management Command
Django management command that ties everything together.

---

## Component 1: Key Sequence Generator

**Purpose:** Generate unique, ergonomic keyboard shortcuts for test selection.

### Requirements

#### 1.1 Key Character Set
- **Allowed characters:** `a`, `s`, `d`, `f`, `h`, `j`, `k`, `l`
- **Rationale:** Home row keys for ergonomic typing without hand movement
- **Character count:** 8 unique characters

#### 1.2 Sequence Types

##### 1.2.1 Four-Letter Sequences (Class-level shortcuts)
- **Length:** Exactly 4 characters
- **Repetition:** Allowed (e.g., "aaaa", "jkkl", "asdf")
- **Capacity:** Generate up to 100 unique sequences
- **Use case:** Selecting entire test classes

##### 1.2.2 Three-Letter Sequences (Function-level shortcuts)
- **Length:** Exactly 3 characters
- **Repetition:** Allowed (e.g., "aaa", "jkl", "hfd")
- **Capacity:** Generate up to 100 unique sequences (or more if needed)
- **Use case:** Selecting individual test functions

#### 1.3 Uniqueness Guarantee
- No two sequences of the same length should ever be identical
- Track used sequences to prevent duplicates
- Provide mechanism to reset/clear used sequences if needed

#### 1.4 Interface Requirements

The generator must provide:

```python
class KeySequenceGenerator:
    def get_next_class_key() -> str:
        """Returns next available 4-letter sequence."""
        pass
    
    def get_next_function_key() -> str:
        """Returns next available 3-letter sequence."""
        pass
    
    def reset():
        """Clear all used sequences."""
        pass
    
    def get_stats() -> dict:
        """Return usage statistics (e.g., keys used, keys remaining)."""
        pass
```

#### 1.5 Algorithm Suggestions
- Simple counter-based approach (convert number to base-8)
- Random generation with collision detection
- Pre-computed lookup tables
- *Developer 1 has freedom to choose implementation*

#### 1.6 Performance
- Key generation must be O(1) or O(log n)
- Support generating all 100 keys in under 1ms

---

## Component 2: Test Discovery & Runner

**Purpose:** Find and organize tests in the Django project.

### Requirements

#### 2.1 Test File Discovery

##### 2.1.1 APITestCase Discovery
- **Pattern:** Files containing classes that inherit from `rest_framework.test.APITestCase`
- **Example:**
  ```python
  from rest_framework.test import APITestCase
  
  class LoadWriteSerializerTestCase(APITestCase):
      def test_create_load_without_legs(self):
          pass
  ```

##### 2.1.2 Pytest Discovery (including pytest-django)
- **Pattern:** Files containing:
  - Functions starting with `test_` 
  - OR functions decorated with `@pytest.mark.*` (including `@pytest.mark.django_db`)
  - OR classes starting with `Test` containing test methods
- **pytest-django markers:**
  - `@pytest.mark.django_db` - Test requires database access
  - `@pytest.mark.django_db(transaction=True)` - Test needs transaction support
  - Fixtures like `client`, `admin_client`, `django_user_model`, `rf` (RequestFactory)
- **Example:**
  ```python
  import pytest
  from django.contrib.auth import get_user_model
  
  def test_example():
      pass
  
  @pytest.mark.django_db
  def test_with_database():
      User = get_user_model()
      user = User.objects.create(username='test')
      assert user.username == 'test'
  
  @pytest.mark.django_db(transaction=True)
  def test_with_transaction():
      pass
  
  class TestUserModel:
      @pytest.mark.django_db
      def test_user_creation(self):
          pass
  ```

##### 2.1.3 Important pytest-django Considerations
- **pytest.ini or pyproject.toml:** May contain `DJANGO_SETTINGS_MODULE` configuration
- **Fixtures:** pytest-django provides built-in fixtures that tests may use
- **Class-based tests:** pytest supports class-based tests (unlike pure pytest functions)
- **Discovery:** Use pytest's collection mechanism or AST parsing

#### 2.2 Search Scope
- **Starting directory:** Project root (where `manage.py` exists)
- **File pattern:** `**/test*.py` and `**/*test.py`
- **Exclusions:** 
  - `__pycache__`
  - `.git`
  - `node_modules`
  - Virtual environment directories

#### 2.3 Organizational Structure

##### 2.3.1 For APITestCase
Group tests hierarchically:
```
Module
└── TestClass
    ├── test_function_1
    ├── test_function_2
    └── test_function_3
```

##### 2.3.2 For pytest (including pytest-django)
Group tests by module, with optional class grouping:
```
Module
├── TestClass (if present)
│   ├── test_method_1
│   └── test_method_2
├── test_function_1
├── test_function_2
└── test_function_3
```

**Note:** Some pytest tests use classes (`class TestSomething:`), others are standalone functions.

#### 2.4 Display Format

##### 2.4.1 APITestCase Display
```
backend/loads/tests.py:
[afda] LoadWriteSerializerTestCase
    <jkla> test_create_load_without_legs
    <ljla> test_create_load_with_single_leg_no_stops
    <hksa> test_create_load_with_nested_legs_and_stops

[skdj] LegSerializerRefactoredTestCase
    <asd> test_create_leg_with_stops
    <fgh> test_update_leg_modify_stops
```

**Format rules:**
- Module path shows max 2 folders (e.g., `backend/loads/tests.py` not `machtms/backend/loads/tests.py`)
- Class-level keys use `[]` brackets
- Function-level keys use `<>` brackets
- Indentation: 4 spaces for test functions under class

##### 2.4.2 Pytest Display (with class grouping support)
```
backend/utils/test_helpers.py:
[jfkd] TestUserModel
    <jkla> test_user_creation
    <asdf> test_user_validation
    <hkls> test_standalone_helper_function
    <dfgh> test_another_helper
```

**Format rules:**
- Module path shows max 2 folders
- If pytest test is in a class, show class with `[]` and indent methods
- Standalone functions have no indentation and use `<>` brackets
- Mixed format is allowed (classes + standalone functions in same file)

##### 2.4.3 pytest-django Indicator (Optional Enhancement)
Consider marking tests that require database access:
```
backend/utils/test_helpers.py:
[jfkd] TestUserModel
    <jkla> test_user_creation [db]
    <asdf> test_user_validation [db]
```

#### 2.5 Test Execution

Must support running:

##### 2.5.1 All APITestCase tests
- **Command:** `python manage.py test --pattern="*test*.py"`
- **Scope:** All discovered APITestCase files

##### 2.5.2 All pytest tests (including pytest-django)
- **Command:** `pytest <project_root>`
- **Alternative:** `pytest --ds=machtms.settings` (if DJANGO_SETTINGS_MODULE not set)
- **Scope:** All discovered pytest files

##### 2.5.3 Specific test class
- **For APITestCase:** `python manage.py test <module_path>.<ClassName>`
- **For pytest class:** `pytest <file_path>::<ClassName>`
- **Examples:**
  - APITestCase: `python manage.py test machtms.backend.loads.tests.LoadWriteSerializerTestCase`
  - pytest: `pytest machtms/backend/loads/tests.py::TestUserModel`

##### 2.5.4 Specific test function
- **For APITestCase:** `python manage.py test <module_path>.<ClassName>.<test_name>`
- **For pytest (in class):** `pytest <file_path>::<ClassName>::<test_name>`
- **For pytest (standalone):** `pytest <file_path>::<test_name>`
- **Examples:**
  - APITestCase: `python manage.py test machtms.backend.loads.tests.LoadWriteSerializerTestCase.test_create_load_without_legs`
  - pytest class method: `pytest machtms/backend/loads/tests.py::TestUserModel::test_user_creation`
  - pytest function: `pytest machtms/backend/loads/tests.py::test_standalone_function`

##### 2.5.5 pytest-django Execution Notes
- Ensure `DJANGO_SETTINGS_MODULE` is set (check environment or pass `--ds` flag)
- May need to use `pytest --reuse-db` or `--create-db` flags for database tests
- Consider supporting verbose output: `pytest -v`

#### 2.6 Integration with Key Sequence Generator

**Requirement:** Developer 2 must collaborate with Developer 1 to:
- Import the KeySequenceGenerator
- Assign class-level keys to test classes (both APITestCase and pytest classes)
- Assign function-level keys to test functions
- Maintain mapping between keys and test paths

**Data structure suggestion:**
```python
{
    'afda': {
        'type': 'class',
        'test_framework': 'apitestcase',  # or 'pytest'
        'path': 'machtms.backend.loads.tests.LoadWriteSerializerTestCase',
        'file_path': 'machtms/backend/loads/tests.py',  # for pytest
        'display': 'LoadWriteSerializerTestCase'
    },
    'jkla': {
        'type': 'function',
        'test_framework': 'apitestcase',  # or 'pytest'
        'path': 'machtms.backend.loads.tests.LoadWriteSerializerTestCase.test_create_load_without_legs',
        'file_path': 'machtms/backend/loads/tests.py',
        'display': 'test_create_load_without_legs',
        'parent_class': 'LoadWriteSerializerTestCase',  # optional, if in a class
        'parent_key': 'afda'  # reference to class key if applicable
    }
}
```

#### 2.7 Interface Requirements

```python
class TestDiscovery:
    def discover_apitestcase_tests() -> list:
        """Find all APITestCase classes and methods."""
        pass
    
    def discover_pytest_tests() -> list:
        """
        Find all pytest test functions and classes.
        Handles both standalone functions and class-based tests.
        Detects pytest-django markers.
        """
        pass
    
    def format_display(test_list, test_type) -> str:
        """Format tests for terminal display with key shortcuts."""
        pass
    
    def get_test_command(key: str) -> str:
        """
        Return shell command to run test associated with key.
        Handles both Django test runner and pytest command formats.
        """
        pass
```

---

## Component 3: Django Management Command

**Purpose:** User-facing CLI tool for test management.

**Location:** `/Users/work/mshared/mtms/backend/tms/machtms/machtms/management/commands/runtests.py`

### Requirements

#### 3.1 Command Structure

```bash
python manage.py runtests
```

#### 3.2 User Flow

**Step 1:** Test type selection
```
Select test type:
1. APITestCase (Django REST Framework)
2. pytest (including pytest-django)
3. All tests (APITestCase + pytest)

Enter choice (1/2/3):
```

**Step 2:** Display test list with shortcuts
```
Available tests:

backend/loads/tests.py:
[afda] LoadWriteSerializerTestCase
    <jkla> test_create_load_without_legs
    <ljla> test_create_load_with_single_leg_no_stops

backend/legs/tests.py:
[skdj] TestLegModel
    <asd> test_create_leg
    <fgh> test_update_leg
    <hjk> test_standalone_pytest_function
    
Enter key to run test (or 'q' to quit, 'a' to run all):
```

**Step 3:** Execute selected test
- If class key entered: Run entire test class
- If function key entered: Run specific test
- If 'a' entered: Run all tests of selected type
- If 'q' entered: Exit

**Step 4:** Display results and loop back
```
Running: pytest machtms/backend/loads/tests.py::TestUserModel::test_user_creation

[Test output appears here]

Press Enter to continue...
```

#### 3.3 Error Handling

- Invalid key entered → "Invalid key. Please try again."
- No tests found → "No tests discovered. Ensure test files exist."
- Test execution failure → Display full error output
- pytest not installed → "pytest not found. Install with: uv add pytest pytest-django"
- pytest-django not configured → Helpful message about DJANGO_SETTINGS_MODULE

#### 3.4 UX Enhancements

- Clear screen between operations for clean UI
- Color coding (optional):
  - Green for passed tests
  - Red for failed tests
  - Yellow for warnings
- Show test count: "Found 15 test classes (8 APITestCase, 7 pytest), 87 test functions"
- Show pytest-django marker count: "23 tests require database access"

---

## Technical Constraints

### Python Version
- Must support Python 3.8+

### Dependencies
- **Required:**
  - Django (already installed)
  - django-rest-framework (already installed)
- **Optional:**
  - pytest (detect if available)
  - pytest-django (detect if available)
- **Package manager:** Use `uv` (not pip) for any additional dependencies
- No additional external dependencies beyond pytest ecosystem

### pytest-django Configuration
- Check for `pytest.ini`, `pyproject.toml`, or `setup.cfg` for Django settings
- Default to `DJANGO_SETTINGS_MODULE=machtms.settings` if not configured
- Gracefully handle missing pytest or pytest-django

### Performance
- Test discovery should complete in < 2 seconds for 100 test files
- Key generation should be negligible (< 10ms total)
- AST parsing (if used) should not significantly impact performance

### File Structure
```
machtms/test_tools/
├── __init__.py
├── key_generator.py       # Developer 1
├── test_discovery.py      # Developer 2
└── test_runner.py         # Developer 2

machtms/management/commands/
└── runtests.py            # Integrates components 1 & 2
```

---

## Testing Requirements

### Developer 1 (Key Generator)
- Unit tests for uniqueness guarantee
- Unit tests for key format validation
- Performance tests for 100 key generation
- Edge case: Exhausting all available keys

### Developer 2 (Test Discovery)
- Unit tests for APITestCase discovery accuracy
- Unit tests for pytest discovery (both functions and classes)
- Unit tests for pytest-django marker detection
- Integration tests with sample test files
- Test path truncation logic
- Test command generation for both APITestCase and pytest
- Test handling of mixed pytest classes and functions

---

## Acceptance Criteria

The project is complete when:

1. **Key Generator:**
   - ✓ Generates unique 4-letter and 3-letter sequences
   - ✓ Never produces duplicate keys
   - ✓ Uses only specified characters (a,s,d,f,h,j,k,l)
   - ✓ Has comprehensive unit tests

2. **Test Discovery:**
   - ✓ Finds all APITestCase classes and methods
   - ✓ Finds all pytest functions (standalone)
   - ✓ Finds all pytest classes and methods
   - ✓ Detects pytest-django markers (optional: display in UI)
   - ✓ Displays tests in specified format
   - ✓ Generates correct test execution commands for both frameworks
   - ✓ Integrates with key generator

3. **Management Command:**
   - ✓ Prompts user for test type
   - ✓ Displays organized test list with shortcuts
   - ✓ Executes selected tests correctly (both Django and pytest)
   - ✓ Handles errors gracefully
   - ✓ Detects pytest availability and warns if missing
   - ✓ Provides clean UX

4. **Integration:**
   - ✓ All components work together seamlessly
   - ✓ Supports both APITestCase and pytest-django patterns
   - ✓ Correctly handles pytest class-based and function-based tests
   - ✓ End-to-end manual testing passes
   - ✓ Tool reduces test running time compared to manual approach

---

## Open Questions

1. **pytest availability:** Should the tool auto-detect if pytest is installed and hide the option if not?
   - **Recommendation:** Yes, detect and show helpful install message if missing
2. **pytest-django configuration:** Should we auto-configure DJANGO_SETTINGS_MODULE if not set?
   - **Recommendation:** Yes, with fallback to project default
3. **Test filtering:** Should we support filtering tests by name/pattern?
   - **Recommendation:** Defer to v2
4. **Test history:** Should we track recently run tests for quick re-running?
   - **Recommendation:** Defer to v2
5. **Configuration:** Should key preferences be configurable via settings file?
   - **Recommendation:** Defer to v2

---

## Future Enhancements (Out of Scope)

- Watch mode (re-run tests on file changes)
- Test coverage integration
- Parallel test execution with pytest-xdist
- IDE integration
- Web UI for test management
- Support for pytest fixtures display
- Test dependency visualization

---

## Glossary

- **APITestCase:** Django REST Framework's base test class (extends Django's TestCase)
- **pytest:** Popular Python testing framework
- **pytest-django:** Plugin that provides Django integration for pytest
- **@pytest.mark.django_db:** Decorator that enables database access in pytest tests
- **Management Command:** Django's CLI extension mechanism
- **Home row keys:** The middle row of keyboard keys where fingers rest
- **AST parsing:** Abstract Syntax Tree parsing for analyzing Python code structure
- **RequestFactory (rf):** pytest-django fixture for creating request objects

---

## pytest-django Quick Reference for Developers

### Common Markers
```python
@pytest.mark.django_db  # Enable database access
@pytest.mark.django_db(transaction=True)  # Use transactions
@pytest.mark.django_db(reset_sequences=True)  # Reset DB sequences
```

### Common Fixtures
- `client` - Django test client
- `admin_client` - Client logged in as admin
- `django_user_model` - User model
- `rf` - RequestFactory
- `settings` - Django settings

### Execution Examples
```bash
# Run all pytest tests
pytest

# Run specific file
pytest path/to/test_file.py

# Run specific class
pytest path/to/test_file.py::TestClassName

# Run specific test
pytest path/to/test_file.py::TestClassName::test_method
pytest path/to/test_file.py::test_function

# With Django settings
pytest --ds=machtms.settings

# Verbose output
pytest -v

# Reuse database
pytest --reuse-db
```
