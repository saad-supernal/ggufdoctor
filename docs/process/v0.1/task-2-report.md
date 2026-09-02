# Task 2: Byte Sources and GGUF Primitive Readers — Report

## What was created

- `src/ggufdoctor/bytesource.py`: Core byte-reading layer including:
  - `ByteSource` protocol with `read(offset: int, length: int) -> bytes` signature
  - `LocalByteSource` implementation reading from local files
  - `Cursor` class with sequential reader semantics, 1MB read-ahead buffer, and methods for GGUF primitives
  - `TruncatedError` exception for underrun conditions
  - Primitive readers: `u32()`, `i32()`, `u64()`, `f32()`, `b()`, `string()`
  - All integer formats use explicit little-endian byte order (`<I`, `<i`, `<Q`)

- `tests/helpers/__init__.py`: Empty module file for test helpers package

- `tests/helpers/gguf_builder.py`: GGUF synthesis helper for tests:
  - `build_gguf(kvs, version=3, tensor_count=0) -> bytes` function
  - Constructs valid GGUF blobs with metadata key-value pairs
  - Supports types: string, u32, u64, bool, f32, array_string
  - Type enums: T_UINT32=4, T_FLOAT32=6, T_BOOL=7, T_STRING=8, T_ARRAY=9, T_UINT64=10
  - Internal helpers `_s()` for string encoding and `_value()` for type dispatch

- `tests/test_bytesource.py`: Test suite with two cases:
  - `test_local_source_reads_slice`: Verifies LocalByteSource slice reads
  - `test_cursor_reads_primitives`: Verifies Cursor primitive parsing and offset tracking

## Test execution

**Command:** `.venv/bin/python -m pytest tests/test_bytesource.py -v`

**Output summary:**
```
tests/test_bytesource.py::test_local_source_reads_slice PASSED           [ 50%]
tests/test_bytesource.py::test_cursor_reads_primitives PASSED            [100%]
============================== 2 passed in 0.04s ===============================
```

## Commit

**SHA:** 7b85f65  
**Message:** feat: byte sources and GGUF primitive readers

## Deviations from brief

None. All code follows the brief verbatim.

## Notes for Tasks 3/4

### Shape contracts for downstream consumers

- **ByteSource protocol**: Minimal, read-only interface suitable for HTTP range-request implementation in Task 4
- **Cursor class**:
  - Constructor signature: `Cursor(source: ByteSource, offset: int = 0)` — allows starting mid-stream
  - Public `.offset` attribute tracks current position; incremented by each `take()` call
  - Exception type: `TruncatedError` raised on underrun; carries helpful message with needed bytes and position
  - Read-ahead buffer (`_buf`, `_buf_start`) is internal; not part of the stable interface
  - `_ensure()` and `take()` methods are internal (leading underscore)

- **GGUF builder**:
  - Returns raw bytes; caller is responsible for I/O
  - Key order in output follows insertion order (Python 3.7+ dicts are ordered)
  - Version defaults to 3, tensor_count defaults to 0; both overridable
  - No validation of key names or value ranges

- **Little-endian commitment**: All struct format strings use `<` prefix. Task 3 (GGUF reader) must also use explicit `<` in struct calls when parsing values read via Cursor primitives.

### No dependencies added

All modules use only `struct` from stdlib and `typing` for protocol support. No new runtime dependencies beyond Jinja2 (already required by Task 1).
