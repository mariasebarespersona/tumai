# 🧪 Tests

## Running Tests

### Run all tests
```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
.venv/bin/pytest tests/ -v
```

### Run specific test file
```bash
.venv/bin/pytest tests/test_numbers_flow.py -v
```

### Run with coverage
```bash
.venv/bin/pytest tests/ --cov=tools --cov-report=html
open htmlcov/index.html
```

## Test Files

### `test_numbers_flow.py`
Integration tests for Numbers Table:
- Formula evaluation (D5, E5, B10, B12, etc.)
- Dependency graph (cascading calculations)
- Auto-calculation flow
- Edge cases (missing dependencies, zeros, rounding)

### `test_verifier_numbers.py`
Tests for the verifier post-execution checks:
- Cell value verification
- Calculated cells verification

### `test_formula_cascade.py`
Tests for cascading formula calculations

## CI Integration

Tests run automatically on every PR via `.github/workflows/ci.yml`

## Writing New Tests

1. Create test file: `tests/test_<feature>.py`
2. Use pytest fixtures for common setup
3. Test happy path + edge cases
4. Run locally before pushing: `pytest tests/test_<feature>.py -v`

## Test Coverage Goals

- **Critical flows**: 90%+ coverage
  - Numbers Table operations
  - Document upload/email
  - Property management
  
- **Tools**: 80%+ coverage
  - All tools in `tools/registry.py`
  
- **Router**: 70%+ coverage
  - Intent classification
  - Agent routing

