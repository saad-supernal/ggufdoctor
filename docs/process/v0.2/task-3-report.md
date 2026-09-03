# Task 3: Engine semantics table — Report

## Summary

Created `tests/test_engine_semantics.py` with 20 test cases pinning both engines' behaviour on known divergences and agreement rows. All tests pass on the first run.

## What Was Done

1. Created `/Users/saad/Silvergrain/Agent Tools/ggufdoctor/tests/test_engine_semantics.py` with:
   - 20 parametrized test rows covering divergences and agreement cases
   - Test fixture for engine initialization with availability check
   - Outcome classifier mapping test results to "ok", "render", or "compile" status
   - Coverage check ensuring all documented divergence classes are present

2. Verified all 20 semantic test rows pass individually with verbose output

3. Ran full test suite: all 200 tests pass (180 existing + 20 new)

4. Committed to `feat/v0.2` branch:
   - SHA: `1aa4da3`
   - Message: "test: pin jinja2 vs llama.cpp semantics table from the engine spike"

## Test Execution Results

### Engine Semantics Suite
```
tests/test_engine_semantics.py::test_semantics_row[print None] PASSED
tests/test_engine_semantics.py::test_semantics_row[print list] PASSED
tests/test_engine_semantics.py::test_semantics_row[print dict] PASSED
tests/test_engine_semantics.py::test_semantics_row[str + None] PASSED
tests/test_engine_semantics.py::test_semantics_row[str + list] PASSED
tests/test_engine_semantics.py::test_semantics_row[default on None] PASSED
tests/test_engine_semantics.py::test_semantics_row[floor division] PASSED
tests/test_engine_semantics.py::test_semantics_row[length of None] PASSED
tests/test_engine_semantics.py::test_semantics_row[str ~ list] PASSED
tests/test_engine_semantics.py::test_semantics_row[undefined var] PASSED
tests/test_engine_semantics.py::test_semantics_row[tojson non-ascii] PASSED
tests/test_engine_semantics.py::test_semantics_row[tojson indent] PASSED
tests/test_engine_semantics.py::test_semantics_row[namespace] PASSED
tests/test_engine_semantics.py::test_semantics_row[generation tag] PASSED
tests/test_engine_semantics.py::test_semantics_row[dictsort] PASSED
tests/test_engine_semantics.py::test_semantics_row[negative slice] PASSED
tests/test_engine_semantics.py::test_semantics_row[is mapping/iterable] PASSED
tests/test_engine_semantics.py::test_semantics_row[loop.index] PASSED
tests/test_engine_semantics.py::test_semantics_row[break] PASSED
tests/test_engine_semantics.py::test_table_covers_every_divergence_class_named_in_the_spike PASSED

20 passed in 0.12s
```

### Full Suite
```
============================= 200 passed in 2.95s ==============================
```

## Test Coverage

The 20 test rows cover:

**Known Divergences (8 rows)**
- `print None`: Jinja2 renders "None", llama.cpp renders empty
- `print list`: Jinja2 uses Python repr, llama.cpp converts to string
- `print dict`: Jinja2 uses Python repr, llama.cpp renders empty
- `str + None`: Jinja2 raises error, llama.cpp coerces None to "x"
- `str + list`: Jinja2 raises error, llama.cpp coerces and concatenates
- `default on None`: Jinja2 treats None as truthy, llama.cpp uses default
- `floor division`: Jinja2 supports `//`, llama.cpp has no operator (compile error)
- `length of None`: Both engines error on length of None (agreement on error)

**Agreement Rows (12 rows)**
- String concatenation with `~` operator
- Undefined variable handling
- JSON serialization with tojson filter
- JSON indentation support
- Namespace objects
- Generation tag support
- Dictionary sorting
- Negative string slicing
- Type checking (`is iterable`, `is mapping`)
- Loop controls (loop.index)
- Break statement

## Files Modified

- **Created**: `/Users/saad/Silvergrain/Agent Tools/ggufdoctor/tests/test_engine_semantics.py` (71 lines)

## Concerns

None. All test rows passed on first run against the committed module, confirming that measured values match both engines' current behavior as of 2026-09-03.

## Next Steps

This test file now serves as a tripwire: any future engine bump that changes semantics will cause a test failure, forcing a review of the change against the spike research at `docs/research/2026-09-03-engine-spike.md §3` before any row expectation is updated.
