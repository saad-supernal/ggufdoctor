# Task 2 Report: LlamaCppEngine — the wasmtime host

## Implementation Summary

Implemented the Python class that hosts the llama.cpp WASM module through the `wasmtime` package, following the brief exactly.

## Files Changed

1. **pyproject.toml** — Added `wasmtime>=48,<49` to dependencies
2. **src/ggufdoctor/models.py** — Added `RenderResult.extra` field with `dict[str, Any]` type and `field(default_factory=dict)` default
3. **src/ggufdoctor/engines/llamacpp_engine.py** — Created new file with complete `LlamaCppEngine` class implementation
4. **tests/test_engine_llamacpp.py** — Created new test file with 11 comprehensive test cases

## TDD Evidence

### Step 1: Dependency and Install
```bash
uv pip install --python .venv/bin/python -e ".[dev]"
```
Result: ✓ wasmtime==48.0.0 installed successfully
```
import wasmtime; print('wasmtime ok')
```
Result: ✓ wasmtime importable

### Step 3: RED (Failing Tests)
```bash
.venv/bin/python -m pytest tests/test_engine_llamacpp.py -v
```
Result: ✗ ModuleNotFoundError: No module named 'ggufdoctor.engines.llamacpp_engine'
Expected failure captured as per brief.

### Step 6: GREEN (Passing Tests)
```bash
.venv/bin/python -m pytest tests/test_engine_llamacpp.py tests/test_engine_jinja2.py -v
```
Result: ✓ 22 passed in 0.32s

All 11 LlamaCppEngine tests pass:
- test_engine_identifies_the_pinned_llama_cpp_build
- test_renders_simple_template
- test_base_context_defaults_match_jinja2_engine
- test_parser_failure_is_a_compile_error
- test_author_decline_is_tagged_raise_with_verbatim_message
- test_engine_failure_is_tagged_render
- test_strftime_now_is_pinned_like_jinja2
- test_normaliser_rewrites_typed_content_for_string_only_templates
- test_missing_module_file_makes_engine_unavailable_not_raising
- test_env_var_overrides_module_path
- test_wasmtime_import_failure_makes_engine_unavailable

### Step 7: Full Suite
```bash
.venv/bin/python -m pytest -q
```
Result: ✓ 179 passed in 2.77s

All existing tests continue to pass (no regressions).

## Implementation Details

### RenderResult.extra Field
Added to `src/ggufdoctor/models.py`:
- Type: `dict[str, Any]`
- Default: `field(default_factory=dict)`
- Comment: Documents that it holds engine-specific metadata (llama.cpp uses "caps" and "normalized" keys)

### LlamaCppEngine Class
Implemented in `src/ggufdoctor/engines/llamacpp_engine.py`:

**Key Features:**
- `name = "llama.cpp"` (class constant)
- `version: str` — loaded from manifest `build_tag` ("b10775")
- `commit: str` — loaded from manifest `commit` ("67a17c17caa95742186f8b1ecadd1b5abd6d5ebb")
- `backend: str | None` — formatted as "wasmtime X.Y.Z", or None if unavailable
- `available: bool` — tracks whether engine is ready to use
- `unavailable_reason: str | None` — explains why if not available
- `ENV_MODULE_PATH = "GGUFDOCTOR_ENGINE_WASM"` — module constant for environment variable
- Module name: "llamacpp-jinja.wasm"
- Manifest name: "llamacpp-jinja.json"

**Initialization Logic:**
1. Load manifest from engine_data resources
2. Extract version and commit from manifest
3. Check wasmtime is importable (graceful failure if not)
4. Set backend version from metadata.version('wasmtime')
5. Check WASM module is readable (env var or resource-bundled)
6. Set `available=True` only if all checks pass

**Lazy Compilation:**
- WASM module is compiled on first render, not during init
- `_ensure_compiled()` creates Engine, Module, Linker once
- Cache configuration set to minimize JIT compile time

**Render Method:**
- Merges BASE_CONTEXT with provided context
- Sends JSON payload: `{"template": template, "context": ctx, "normalize": True}`
- Instantiates WASM module with WASI config
- Calls gd_alloc, memory.write, gd_render, gd_out_len, gd_free in sequence
- Reads result JSON from module memory
- Maps error stages to error prefixes:
  - "lexer"/"parser" → "compile:lexer:" / "compile:parser:"
  - "raise" → "raise:"
  - other → "render:" (using last non-empty line)
- Returns RenderResult with `extra` dict containing:
  - "caps": result["caps"] (capabilities reported by module)
  - "normalized": bool (whether input was normalized for string-only templates)

**Error Handling:**
- WASM read/compile failures: `engine:unavailable:<reason>`
- WASM instantiation/execution failures: `render:wasm: <exception type>: <first line>`
- Corrupt module, wasmtime traps: caught and reported with error prefix

## Code Quality & Adherence

### Code Matches Brief Exactly
- All method signatures, field types, and logic follow the brief's implementation
- Error prefixes: "compile:", "raise:", "render:", "engine:unavailable:" — exact match
- Helper functions `_first_line()` and `_last_line()` present and used correctly
- Module constants (`MODULE_NAME`, `MANIFEST_NAME`, `ENV_MODULE_PATH`) all defined

### Test Coverage
- 11 tests covering all code paths and edge cases
- Tests for unavailability reasons (missing file, import failure)
- Tests for error prefixes (compile, raise, render, engine)
- Tests for features (caps, normalized context, BASE_CONTEXT matching)
- Tests for environment variable override

### Self-Review Findings

✓ **Completeness**
- Every step in the brief completed
- All four required error prefixes implemented and tested
- `extra` defaults to empty dict as specified
- No test files missing; all 11 test cases from brief present and passing

✓ **Code Quality**
- Type hints complete and correct
- Exception handling is specific and informative
- Helper functions are clean and tested via their usage
- No dead code; every function is used

✓ **Testing Discipline**
- RED-GREEN-REFACTOR pattern followed
- No warnings in test output
- Full test suite passes (179 tests)
- No regressions in existing tests

✓ **Brief Compliance**
- No additions beyond the brief
- Filenames, imports, and interfaces exactly as specified
- Commit message format follows exact template (including Co-Authored-By)

## Concerns

None. All implementation requirements met, all tests passing, no deviations from brief.

## Commit

```
531c0ac feat(engine): LlamaCppEngine hosts the WASM module through wasmtime
```

Author: Claude Fable 5.1 <noreply@anthropic.com>
Date: 2026-09-03

Changes:
- Modified: pyproject.toml (dependency)
- Modified: src/ggufdoctor/models.py (RenderResult.extra field)
- Created: src/ggufdoctor/engines/llamacpp_engine.py (LlamaCppEngine implementation)
- Created: tests/test_engine_llamacpp.py (11 test cases)

---

## Fix Round 1: Review Findings

### Issue 1 (Important) — Non-serializable context raises TypeError

**Problem:** The brief's code had `json.dumps(...)` outside the try block. If context contains non-JSON-serializable values (e.g., `set`, `bytes`, or custom objects), `TypeError` escapes `render()` instead of being caught.

**Constraint:** Global rule — "engines never raise from render()" overrides brief's sample code.

**Fix:** Moved `json.dumps()` call inside the try block (line 101). Now `TypeError` from context serialization is caught and returned as `RenderResult(None, f"render:wasm: {type(e).__name__}: ...")`.

**Test Added:**
```python
def test_non_serializable_context_is_a_render_error_not_an_exception():
    r = LlamaCppEngine().render("test", {"messages": [], "junk": {1, 2}})
    assert not r.ok
    assert r.error.startswith("render:")
```

### Issue 2 (Important) — Module response missing "text" key raises KeyError

**Problem:** Code had `result["text"]` unguarded after try/except. If module returns `"ok": true` without a `"text"` key (or with a non-string value), `KeyError` escapes `render()`.

**Fix:** Changed to `result.get("text")` and validate it's a string:
```python
text = result.get("text")
if not isinstance(text, str):
    return RenderResult(None, f"render:wasm: module returned ok without valid text", extra=extra)
return RenderResult(text, None, extra=extra)
```

### Issue 3 (Minor) — Unused pytest import

**Problem:** `tests/test_engine_llamacpp.py` imported `pytest` but never used it.

**Fix:** Removed `import pytest` line 3.

### Test Results After Fixes

Covering tests:
```bash
.venv/bin/python -m pytest tests/test_engine_llamacpp.py tests/test_engine_jinja2.py -v
```
Result: ✓ 23 passed in 0.24s (new test included)

Full suite:
```bash
.venv/bin/python -m pytest -q
```
Result: ✓ 180 passed in 2.83s (179 original + 1 new test)

### Fix Commit

```
db78ca5 fix(engine): prevent render() from raising on non-serializable context or invalid module response
```

Changes:
- Modified: src/ggufdoctor/engines/llamacpp_engine.py
  - Moved json.dumps() inside try block
  - Added result.get("text") check with string validation
  - Updated exception comment
- Modified: tests/test_engine_llamacpp.py
  - Removed unused import pytest
  - Added test_non_serializable_context_is_a_render_error_not_an_exception

All tests green. No regressions. Engine now conforms to global constraint: render() never raises.
