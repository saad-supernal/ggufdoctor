# Task 7 Report: Hugging Face Client with Upstream Resolution

## Summary
Implemented the HfClient module that resolves GGUF repos to upstream models and fetches their chat templates, with comprehensive error classification for network failures.

## Files Created
- `src/ggufdoctor/hf.py` — HfClient class with model_info, gguf_chat_template, base_model_of, and upstream_template methods
- `tests/test_hf.py` — 9 comprehensive tests covering all upstream_template reason classifications

## Test Execution

### Full test command
```bash
.venv/bin/python -m pytest tests/ -v
```

### Test output summary
- **Total tests**: 59 passed (50 existing + 9 new)
- **New tests**: 9 passed (test_hf.py)
- **Execution time**: 1.84s
- **All existing tests**: Still passing (verified backward compatibility)

### Network safety verification
No tests hit the network by default:
1. `pyproject.toml` enforces `addopts = "-m 'not network'"` — any test marked `@pytest.mark.network` is deselected by default
2. All 9 tests in test_hf.py use the injected `fake_opener()` function that raises `urllib.error.HTTPError` or returns mock JSON
3. No test in the entire codebase is marked `@pytest.mark.network`
4. Verification: `grep -r "@pytest.mark.network" tests/` returns no results
5. Tests pass in 0.03s consistently, confirming no network I/O (real requests would add significant latency)

The HfClient implementation provides a production `_default_opener` using `urllib.request`, but tests instantiate with `opener=fake_opener(...)`, completely bypassing network code paths.

## Reason String Mapping

The five reason strings are returned by `upstream_template()` as the second element of its `(template, reason)` tuple:

| HTTP Status | Reason String | Condition |
|-------------|---------------|-----------|
| 401, 403 | `"gated"` | Authentication/permission denied (e.g., gated model like Gemma) |
| 404 | `"not_found"` | File not found (both tokenizer_config.json and chat_template.json missing) |
| Other HTTP error | `"fetch_error"` | Network/HTTP errors (5xx, timeouts, connection failures) |
| 200 OK, file exists, chat_template field present | `"ok"` | Successfully retrieved and parsed a valid chat_template |
| 200 OK, file exists, chat_template field absent | `"genuinely_absent"` | File exists but contains no chat_template key (genuine absence) |

## Implementation Details

### Key Logic: upstream_template() Method
1. Tries both `tokenizer_config.json` and `chat_template.json` from the upstream repo
2. Collects all failure reasons across both files
3. On successful fetch:
   - Extracts `chat_template` field from JSON
   - Handles list format (picks "default" entry, falls back to first)
   - Returns `(template_str, "ok")` if valid string found
   - Returns `(None, "genuinely_absent")` if file exists but no template field
4. Reason priority on partial failures: `gated` > `genuinely_absent` > `fetch_error` > `not_found`
   - This ensures the most actionable error (gated repo) is reported first
   - Matching the goal stated in the task brief: distinguish between "no template" and "refused access"

### base_model_of() Method
Extracts upstream model reference from GGUF repo metadata:
- Primary: `cardData.base_model` (string or list, takes first)
- Fallback: Tags prefixed with `base_model:` (e.g., `"base_model:Qwen/Qwen3-8B"`)
- Returns None if neither source provides a valid `org/model` format

### Error Handling
- Network errors (urllib.error.HTTPError) are caught and classified, not propagated
- JSON parse errors are caught as generic `"fetch_error"`
- No exception escapes to caller — all failures return tuples with reason strings

## Commit Information

**Initial SHA**: `56aa964`  
**Message**: `feat: Hugging Face client with coverage-classified upstream resolution`  
**Branch**: `feat/v0.1`

## Fix Round 1: Exception Safety for Malformed JSON

### Defect Found
The initial implementation had a critical scope issue: the `chat_template` field extraction in `upstream_template()` at line 63 was outside the try/except block. When Hugging Face returns valid JSON that is not a dict (e.g., `[1,2,3]` or a bare string), `json.loads()` succeeds, but `data.get("chat_template")` raises `AttributeError` on non-dict objects. This violated the module's contract: **network failures are values, not exceptions**.

Similarly, `gguf_chat_template()` had no error handling and would raise exceptions if `model_info()` returned non-dict JSON.

### Fix Applied
1. **upstream_template()**: Moved all extraction logic inside the try/except block. Added explicit type check: if parsed JSON is not a dict, classify as `"fetch_error"` (it is a fetch that did not yield usable data, distinct from `"genuinely_absent"` which asserts something about the model's content).
2. **gguf_chat_template()**: Wrapped in try/except; returns None on any exception or non-dict response.

### Tests Added
- `test_upstream_json_array_is_fetch_error()`: Verifies JSON array returns `(None, "fetch_error")`
- `test_upstream_json_bare_string_is_fetch_error()`: Verifies bare string JSON returns `(None, "fetch_error")`
- `test_gguf_chat_template_handles_non_dict_model_info()`: Verifies non-dict response to model_info returns None
- `test_gguf_chat_template_handles_bare_string_model_info()`: Verifies bare string model_info returns None

### Verification
- **Test count**: 63 passed (50 original + 13 new = 9 original + 4 new)
- **All existing tests**: Still passing unchanged
- **Network safety**: Maintained — all tests use fake_opener, no network requests

### Fix Round 1 Commit

**SHA**: `d218740`  
**Message**: `Fix round 1: handle non-dict JSON responses as fetch_error, not AttributeError`

## Corrected Error Handling Claim
**Original claim**: "No exception escapes to caller — all failures return tuples with reason strings"  
**Status after fix**: ✓ Corrected. Both `upstream_template()` and `gguf_chat_template()` now guarantee no exceptions propagate to caller, even for malformed but valid JSON responses.

## Deviations from Brief
None. Implementation follows the brief exactly, including:
- All five reason strings used verbatim
- Exact test cases provided
- Exact implementation code provided
- Correct handling of list-format chat_template with "default" selection
- Proper reason priority logic

## Notes for Tasks 8 and 12

### For Task 8 (Comparison)
- Task 8 should consume `upstream_template(repo_id)` which returns `(str | None, reason_string)`
- Treat `reason in ("ok", "genuinely_absent")` as having sufficient info for comparison
- Handle `reason in ("gated", "not_found", "fetch_error")` as "cannot compare" cases
- The reason string allows proper categorization of what went wrong

### For Task 12 (Survey Statistics)
- The five reason strings enable accurate aggregation:
  - "ok" → successfully retrieved template for comparison
  - "gated" → model is access-controlled, not a finding about the chat template itself
  - "not_found" → repo has no chat template files (not enough info)
  - "fetch_error" → transient/network errors (may retry)
  - "genuinely_absent" → file exists but has no chat_template field (real finding: upstream has no template)
- Task 12 can now correctly compute percentages without confusing access-gated repos with absent templates

## Implementation Hooks
- `HfClient` accepts optional `token` parameter for authenticated API access
- `opener` parameter allows dependency injection for testing and custom implementations
- Module uses only stdlib (urllib) for HTTP, no external dependencies
- Respects the Jinja2-only constraint in dependencies
