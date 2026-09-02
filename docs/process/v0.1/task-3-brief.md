### Task 3: GGUF metadata parser

**Files:**
- Create: `src/ggufdoctor/reader.py`
- Test: `tests/test_reader.py`

**Interfaces:**
- Consumes: `Cursor`, `LocalByteSource`, `TruncatedError` from Task 2; `GgufModel` from Task 1
- Produces: `read_gguf(source: ByteSource, source_id: str) -> GgufModel`; `read_gguf_file(path: str) -> GgufModel`; `NotGgufError`

Keys mapped onto `GgufModel`: `general.architecture` → `architecture`, `tokenizer.chat_template` → `chat_template`, `tokenizer.ggml.tokens` → `tokens`, `tokenizer.ggml.bos_token_id` → `bos_token_id`, `tokenizer.ggml.eos_token_id` → `eos_token_id`, `tokenizer.ggml.add_bos_token` → `add_bos_token`. All raw KVs land in `metadata`, except `tokenizer.ggml.tokens` which is omitted from `metadata` to keep it small.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader.py
import pytest
from ggufdoctor.reader import read_gguf, read_gguf_file, NotGgufError
from ggufdoctor.bytesource import LocalByteSource
from tests.helpers.gguf_builder import build_gguf


def _write(tmp_path, blob, name="m.gguf"):
    p = tmp_path / name
    p.write_bytes(blob)
    return str(p)


def test_parses_core_fields(tmp_path):
    blob = build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.chat_template": ("string", "{{ 'hi' }}"),
        "tokenizer.ggml.tokens": ("array_string", ["<s>", "a", "</s>"]),
        "tokenizer.ggml.bos_token_id": ("u32", 0),
        "tokenizer.ggml.eos_token_id": ("u32", 2),
        "tokenizer.ggml.add_bos_token": ("bool", True),
    })
    m = read_gguf_file(_write(tmp_path, blob))
    assert m.architecture == "llama"
    assert m.chat_template == "{{ 'hi' }}"
    assert m.tokens == ["<s>", "a", "</s>"]
    assert m.bos_token_id == 0
    assert m.eos_token_id == 2
    assert m.add_bos_token is True


def test_missing_template_is_none_not_error(tmp_path):
    blob = build_gguf({"general.architecture": ("string", "bert")})
    m = read_gguf_file(_write(tmp_path, blob))
    assert m.chat_template is None
    assert m.architecture == "bert"


def test_rejects_non_gguf(tmp_path):
    with pytest.raises(NotGgufError):
        read_gguf_file(_write(tmp_path, b"NOPE" + b"\x00" * 32))


def test_tokens_excluded_from_metadata_blob(tmp_path):
    blob = build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.ggml.tokens": ("array_string", ["a"] * 50),
    })
    m = read_gguf_file(_write(tmp_path, blob))
    assert "tokenizer.ggml.tokens" not in m.metadata
    assert len(m.tokens) == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.reader'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/reader.py
from __future__ import annotations

from typing import Any

from ggufdoctor.bytesource import ByteSource, Cursor, LocalByteSource
from ggufdoctor.models import GgufModel

T_UINT8, T_INT8, T_UINT16, T_INT16 = 0, 1, 2, 3
T_UINT32, T_INT32, T_FLOAT32, T_BOOL = 4, 5, 6, 7
T_STRING, T_ARRAY, T_UINT64, T_INT64, T_FLOAT64 = 8, 9, 10, 11, 12

_FIXED = {
    T_UINT8: (1, "B"), T_INT8: (1, "b"), T_UINT16: (2, "H"), T_INT16: (2, "h"),
    T_UINT32: (4, "I"), T_INT32: (4, "i"), T_FLOAT32: (4, "f"),
    T_UINT64: (8, "Q"), T_INT64: (8, "q"), T_FLOAT64: (8, "d"),
}

TOKENS_KEY = "tokenizer.ggml.tokens"


class NotGgufError(Exception):
    """Source does not begin with the GGUF magic."""


def _read_value(c: Cursor, vtype: int) -> Any:
    import struct
    if vtype == T_STRING:
        return c.string()
    if vtype == T_BOOL:
        return c.b()
    if vtype in _FIXED:
        size, fmt = _FIXED[vtype]
        return struct.unpack("<" + fmt, c.take(size))[0]
    if vtype == T_ARRAY:
        etype = c.u32()
        count = c.u64()
        return [_read_value(c, etype) for _ in range(count)]
    raise NotGgufError(f"unknown GGUF value type {vtype}")


def read_gguf(source: ByteSource, source_id: str) -> GgufModel:
    c = Cursor(source)
    if c.take(4) != b"GGUF":
        raise NotGgufError(f"{source_id}: missing GGUF magic")
    c.u32()   # version
    c.u64()   # tensor count
    kv_count = c.u64()

    model = GgufModel(source_id=source_id)
    for _ in range(kv_count):
        key = c.string()
        value = _read_value(c, c.u32())
        if key == TOKENS_KEY:
            model.tokens = [t for t in value if isinstance(t, str)]
            continue
        model.metadata[key] = value

    md = model.metadata
    model.architecture = md.get("general.architecture")
    model.chat_template = md.get("tokenizer.chat_template")
    model.bos_token_id = md.get("tokenizer.ggml.bos_token_id")
    model.eos_token_id = md.get("tokenizer.ggml.eos_token_id")
    model.add_bos_token = md.get("tokenizer.ggml.add_bos_token")
    return model


def read_gguf_file(path: str) -> GgufModel:
    return read_gguf(LocalByteSource(path), path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reader.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/reader.py tests/test_reader.py
git commit -m "feat: GGUF metadata parser"
```

---

