# Task 3 Report: GGUF Metadata Parser

## Summary

Implemented the GGUF metadata parser module (`src/ggufdoctor/reader.py`) with full test coverage. All 5 new tests pass, and all 6 existing tests remain passing.

**Commit SHA:** `ed9a3e1`

## What Was Created

### `src/ggufdoctor/reader.py`
The GGUF metadata parser implementation with:
- **`NotGgufError`** — exception raised when a file does not begin with the GGUF magic bytes
- **`read_gguf(source: ByteSource, source_id: str) -> GgufModel`** — reads a GGUF model from any ByteSource
- **`read_gguf_file(path: str) -> GgufModel`** — convenience wrapper that creates a LocalByteSource and calls read_gguf
- **Internal helpers:**
  - `_FIXED` — dict mapping GGUF fixed-size type IDs to (byte_size, struct format)
  - `_read_value(c: Cursor, vtype: int)` — recursively reads a GGUF value of any type using struct unpacking and the Cursor interface

#### Key Behavior
- Parses GGUF header: magic, version, tensor count, KV count
- Iterates KV blocks, mapping keys to fields per the specification:
  - `general.architecture` → `model.architecture`
  - `tokenizer.chat_template` → `model.chat_template`
  - `tokenizer.ggml.tokens` → `model.tokens` (array_string)
  - `tokenizer.ggml.bos_token_id` → `model.bos_token_id`
  - `tokenizer.ggml.eos_token_id` → `model.eos_token_id`
  - `tokenizer.ggml.add_bos_token` → `model.add_bos_token`
  - All other KVs → `model.metadata` dict
- `tokenizer.ggml.tokens` is explicitly excluded from metadata to keep it small

### `tests/test_reader.py`
Five tests verifying parser behavior:

1. **`test_parses_core_fields`** — validates all six special-case keys map correctly onto GgufModel fields
2. **`test_missing_template_is_none_not_error`** — confirms missing optional fields default to None
3. **`test_rejects_non_gguf`** — ensures a file without GGUF magic raises NotGgufError
4. **`test_tokens_excluded_from_metadata_blob`** — validates tokens are extracted to the tokens field and excluded from metadata
5. **`test_round_trips_every_builder_type`** — (extra test, as requested) confirms all six supported builder types survive the round-trip:
   - `string` (mapped to special fields and metadata)
   - `u32` (u32 values parsed correctly)
   - `u64` (u64 values parsed correctly)
   - `bool` (bool values parsed correctly)
   - `f32` (f32 values parsed correctly)
   - `array_string` (array_string values parsed correctly)

## Test Results

### test_reader.py execution
```
tests/test_reader.py::test_parses_core_fields PASSED                     [ 20%]
tests/test_reader.py::test_missing_template_is_none_not_error PASSED     [ 40%]
tests/test_reader.py::test_rejects_non_gguf PASSED                       [ 60%]
tests/test_reader.py::test_tokens_excluded_from_metadata_blob PASSED     [ 80%]
tests/test_reader.py::test_round_trips_every_builder_type PASSED         [100%]

5 passed in 0.04s
```

### Full test suite
```
tests/test_bytesource.py::test_local_source_reads_slice PASSED           [  9%]
tests/test_bytesource.py::test_cursor_reads_primitives PASSED            [ 18%]
tests/test_models.py::test_severity_is_string_valued PASSED              [ 27%]
tests/test_models.py::test_finding_defaults_are_independent PASSED       [ 36%]
tests/test_models.py::test_render_result_ok_reflects_error PASSED        [ 45%]
tests/test_models.py::test_coverage_records_families_run PASSED          [ 54%]
tests/test_reader.py::test_parses_core_fields PASSED                     [ 63%]
tests/test_reader.py::test_missing_template_is_none_not_error PASSED     [ 72%]
tests/test_reader.py::test_rejects_non_gguf PASSED                       [ 81%]
tests/test_reader.py::test_tokens_excluded_from_metadata_blob PASSED     [ 90%]
tests/test_reader.py::test_round_trips_every_builder_type PASSED         [100%]

11 passed in 0.02s
```

## Extra Test: `test_round_trips_every_builder_type`

This test validates that all six builder types supported by `build_gguf()` are correctly parsed:

- **string**: Tested via `general.architecture`, `tokenizer.chat_template`, and arbitrary metadata keys
- **u32**: Tested via `bos_token_id`, `eos_token_id`, and arbitrary metadata keys
- **u64**: Tested via arbitrary metadata key `test.u64`
- **bool**: Tested via `add_bos_token`
- **f32**: Tested via arbitrary metadata key `test.f32` with pytest.approx comparison
- **array_string**: Tested via `tokenizer.ggml.tokens`

All values survive the round-trip unchanged, confirming the parser correctly handles every supported GGUF type.

## Deviations from Brief

None. The implementation matches the brief verbatim, including:
- Type constant definitions and _FIXED mapping
- TOKENS_KEY constant
- NotGgufError exception
- _read_value recursion for arrays and all primitive types
- read_gguf main parsing loop with proper KV mapping
- read_gguf_file convenience wrapper

The extra `test_round_trips_every_builder_type` test was added as requested in the instructions and provides comprehensive coverage of all supported GGUF types.

## Notes for Later Tasks

- The reader depends only on ByteSource protocol, Cursor, and GgufModel — no direct file I/O except through these abstractions, enabling Task 4 (HTTP range-request source) to work seamlessly
- All GGUF integers are little-endian via Cursor methods (u32, u64, etc.)
- The tokens field filtering (`[t for t in value if isinstance(t, str)]`) is defensive but important: it ensures only strings are stored even if array parsing were to produce mixed types
- NotGgufError is the single exception type for all parser errors (unknown type, missing magic, etc.)
