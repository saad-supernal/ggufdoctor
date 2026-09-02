# Task 1 Report: Project Scaffolding and Shared Value Types

## Summary

Task 1 completed successfully. All project scaffolding and shared dataclasses have been implemented and tested.

## Files Created

- `pyproject.toml` — Build configuration with Hatchling, project metadata, pytest settings, and CLI entry point
- `src/ggufdoctor/__init__.py` — Package initialization with version string
- `src/ggufdoctor/models.py` — All shared dataclasses: `Severity`, `Finding`, `GgufModel`, `RenderResult`, `Coverage`, `Fixture`, `CheckContext`, and `SEVERITY_ORDER`
- `tests/test_models.py` — Test suite with 4 test cases covering Severity enum, Finding mutable defaults, RenderResult.ok property, and Coverage dataclass
- `tests/__init__.py` — Empty package marker (additional requirement to prevent pytest sys.path pollution)

## Test Results

Command: `.venv/bin/python -m pytest tests/test_models.py -v`

Output:
```
============================== test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 4 items

tests/test_models.py::test_severity_is_string_valued PASSED              [ 25%]
tests/test_models.py::test_finding_defaults_are_independent PASSED       [ 50%]
tests/test_models.py::test_render_result_ok_reflects_error PASSED        [ 75%]
tests/test_models.py::test_coverage_records_families_run PASSED          [100%]

============================== 4 passed in 0.01s =======================================
```

All 4 tests pass consistently.

## Commit

Commit SHA: `013b7df`
Message: `feat: project scaffolding and shared value types`
Files: 5 (pyproject.toml, src/ggufdoctor/__init__.py, src/ggufdoctor/models.py, tests/__init__.py, tests/test_models.py)

## Implementation Details

### Severity Enum
- Implements `str` + `Enum` to be string-valued
- Three values: `ERROR="error"`, `WARN="warn"`, `INFO="info"`
- Includes `SEVERITY_ORDER` dict for sorting (INFO=0, WARN=1, ERROR=2)

### Dataclasses
All dataclasses implemented with proper type hints and default factories to prevent mutable default leakage:
- `Finding`: id, severity, message, optional fixture, and evidence dict with field(default_factory=dict)
- `GgufModel`: source_id, optional architecture/chat_template, tokens list, optional token IDs/add_bos, metadata dict
- `RenderResult`: text and error fields with computed `ok` property (True iff error is None)
- `Coverage`: upstream string and families_run list
- `Fixture`: immutable (frozen=True) with name and context dict
- `CheckContext`: model, engines list, fixtures list, optional upstream_template/metadata

### Installation
Package installed via `uv pip install --python .venv/bin/python -e .` which correctly installed:
- ggufdoctor==0.1.0 (editable)
- jinja2==3.1.6 (runtime dependency)
- markupsafe==3.0.3 (transitive)

## Deviations from Brief

Only one intentional deviation:
- **Added `tests/__init__.py`** (empty file) — This was explicitly required as an additional requirement beyond the brief to prevent pytest from adding `tests/` to `sys.path`, which would break later tasks' imports of `from tests.helpers...`. The brief omitted this file but it was marked as a requirement.

No deviations in code, test names, dataclass signatures, or enum values. All used verbatim from the brief.

## Notes for Later Tasks

1. All dataclasses use `field(default_factory=dict)` for mutable defaults, ensuring independence between instances
2. `Severity` is a string-valued enum and can be used in string contexts (JSON serialization, etc.)
3. `RenderResult.ok` is a read-only property — check it for success/failure rather than inspecting error directly
4. `Fixture` is frozen (immutable) — important for use as dict keys or in sets if needed
5. `CheckContext` will be the primary input type for checker functions in later tasks
6. The `SEVERITY_ORDER` constant is available for sorting findings by severity (higher number = higher severity)
7. The package is properly installable and discoverable — `ggufdoctor` module imports work from any location
