# Test Management Tool - Project Guide

## Quick Start

This folder contains the planning documents for building a Django/pytest test management tool.

### For Developer 1 (Key Sequence Generator)
**Start here:** Read `TODO_developer1.md`

**Your job:** Create a key generator that produces unique 3-letter and 4-letter sequences using only home row keys (a,s,d,f,h,j,k,l).

**Time estimate:** 4-6 hours

**Deliverable:** `/Users/work/mshared/mtms/backend/tms/machtms/test_tools/key_generator.py`

### For Developer 2 (Test Discovery & Runner)
**Start here:** Read `TODO_developer2.md`

**Your job:** Build test discovery (find APITestCase and pytest tests), integrate with key generator, and create the management command.

**Time estimate:** 18-23 hours

**Deliverables:**
- `/Users/work/mshared/mtms/backend/tms/machtms/test_tools/test_discovery.py`
- `/Users/work/mshared/mtms/backend/tms/machtms/test_tools/test_runner.py`
- `/Users/work/mshared/mtms/backend/tms/machtms/machtms/management/commands/runtests.py`

### For Everyone
**Full requirements:** Read `requirements.md` for complete technical specifications.

## File Structure

```
machtms/test_tools/
├── __init__.py                 # Package initialization (created)
├── README.md                   # This file
├── requirements.md             # Complete technical requirements
├── TODO_developer1.md          # Developer 1 task list
├── TODO_developer2.md          # Developer 2 task list
├── key_generator.py            # Developer 1 creates this
├── test_discovery.py           # Developer 2 creates this
└── test_runner.py              # Developer 2 creates this

machtms/management/commands/
└── runtests.py                 # Developer 2 creates this
```

## Development Workflow

1. **Developer 1** starts first on key generator
2. **Developer 2** can start on test discovery in parallel
3. After Developer 1 completes Phase 1 (core generator), Developer 2 integrates it
4. Both developers write tests for their components
5. Developer 2 completes the management command integration
6. Both developers perform integration testing

## Key Features

### What This Tool Does
- Discovers Django APITestCase classes and pytest tests
- Assigns keyboard shortcuts to each test
- Provides interactive CLI for running tests quickly
- Supports both `python manage.py test` and `pytest` commands

### Example User Experience

```bash
$ python manage.py runtests

Select test type:
1. APITestCase (Django REST Framework)
2. pytest (including pytest-django)
3. All tests

Enter choice (1/2/3): 1

Available tests:

backend/loads/tests.py:
[afda] LoadWriteSerializerTestCase
    <jkla> test_create_load_without_legs
    <ljla> test_create_load_with_single_leg_no_stops

backend/legs/tests.py:
[skdj] LegSerializerTestCase
    <asd> test_create_leg

Found 2 test classes, 3 test functions

Enter key to run test (or 'q' to quit, 'a' to run all): jkla

Running: machtms.backend.loads.tests.LoadWriteSerializerTestCase.test_create_load_without_legs

[Test output...]

Press Enter to continue...
```

## Technical Stack

- **Python:** 3.8+
- **Django:** Already installed
- **DRF:** django-rest-framework (already installed)
- **pytest:** Optional, gracefully handle if not installed
- **pytest-django:** Optional, for Django integration with pytest
- **Package manager:** Use `uv` (not pip)

## Important Notes

### pytest-django Awareness
This tool must handle pytest tests that use Django-specific features:
- `@pytest.mark.django_db` decorator
- pytest-django fixtures (client, rf, etc.)
- Proper Django settings configuration

### Performance Requirements
- Test discovery: < 2 seconds for 100 test files
- Key generation: < 10ms total for 100 keys
- Overall responsiveness: Tool should feel instant

### Code Quality
- All code must have docstrings
- All components need unit tests
- Follow PEP 8 style guidelines
- Use type hints where appropriate

## Getting Help

### Questions About Requirements?
Refer back to `requirements.md` - it has detailed specifications.

### Questions About Your Tasks?
- Developer 1: See `TODO_developer1.md`
- Developer 2: See `TODO_developer2.md`

### Integration Questions?
Both developers should coordinate after Developer 1 completes the key generator interface.

## Testing Your Work

### Developer 1
```bash
cd /Users/work/mshared/mtms/backend/tms/machtms
pytest test_tools/tests/test_key_generator.py
```

### Developer 2
```bash
cd /Users/work/mshared/mtms/backend/tms/machtms
pytest test_tools/tests/test_discovery.py
pytest test_tools/tests/test_runner.py

# Integration test
python manage.py runtests
```

## Success Criteria

The project is complete when:

1. Developer 1's key generator passes all tests
2. Developer 2's test discovery finds all tests accurately
3. The management command works end-to-end
4. A developer can run any test with just 3-4 keystrokes
5. Both Django and pytest tests are supported
6. Tool is faster than manually typing test commands

## Project Timeline

- **Developer 1:** 1 day (4-6 hours)
- **Developer 2:** 2-3 days (18-23 hours)
- **Total project:** 3-4 days with parallel work

Good luck! This will be a very useful tool for the team.
