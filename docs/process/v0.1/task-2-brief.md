### Task 2: Byte sources and GGUF primitive readers

**Files:**
- Create: `src/ggufdoctor/bytesource.py`
- Create: `tests/helpers/__init__.py`
- Create: `tests/helpers/gguf_builder.py`
- Test: `tests/test_bytesource.py`

**Interfaces:**
- Consumes: nothing
- Produces: `ByteSource` protocol with `read(offset: int, length: int) -> bytes`; `LocalByteSource(path)`; `Cursor(source)` with `.u32()`, `.u64()`, `.i32()`, `.f32()`, `.b()`, `.string()`, `.offset`. Test helper `build_gguf(kvs: dict[str, tuple[str, Any]]) -> bytes` where the tuple is `(type_name, value)` and `type_name` ∈ `{"string","u32","u64","bool","array_string","f32"}`.

GGUF layout: magic `GGUF`, `version:u32`, `tensor_count:u64`, `kv_count:u64`, then `kv_count` pairs of `key:string`, `value_type:u32`, `value`. Strings are `len:u64` + UTF-8 bytes. Arrays are `elem_type:u32`, `count:u64`, then elements. Type enum: `4=UINT32`, `6=FLOAT32`, `7=BOOL`, `8=STRING`, `9=ARRAY`, `10=UINT64`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bytesource.py
import struct
from ggufdoctor.bytesource import LocalByteSource, Cursor


def test_local_source_reads_slice(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"0123456789")
    src = LocalByteSource(str(p))
    assert src.read(2, 4) == b"2345"


def test_cursor_reads_primitives(tmp_path):
    blob = struct.pack("<I", 7) + struct.pack("<Q", 1 << 40) + b"\x01"
    blob += struct.pack("<Q", 3) + b"abc"
    p = tmp_path / "f.bin"
    p.write_bytes(blob)
    c = Cursor(LocalByteSource(str(p)))
    assert c.u32() == 7
    assert c.u64() == 1 << 40
    assert c.b() is True
    assert c.string() == "abc"
    assert c.offset == len(blob)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bytesource.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.bytesource'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/bytesource.py
from __future__ import annotations

import struct
from typing import Protocol


class ByteSource(Protocol):
    def read(self, offset: int, length: int) -> bytes: ...


class LocalByteSource:
    def __init__(self, path: str) -> None:
        self.path = path

    def read(self, offset: int, length: int) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(offset)
            return f.read(length)


class TruncatedError(Exception):
    """Raised when the source ends before the requested bytes."""


class Cursor:
    """Sequential reader over a ByteSource with a small read-ahead buffer."""

    CHUNK = 1 << 20

    def __init__(self, source: ByteSource, offset: int = 0) -> None:
        self.source = source
        self.offset = offset
        self._buf = b""
        self._buf_start = offset

    def _ensure(self, n: int) -> bytes:
        rel = self.offset - self._buf_start
        if rel < 0 or rel + n > len(self._buf):
            want = max(n, self.CHUNK)
            self._buf = self.source.read(self.offset, want)
            self._buf_start = self.offset
            rel = 0
            if len(self._buf) < n:
                raise TruncatedError(f"needed {n} bytes at {self.offset}")
        return self._buf[rel:rel + n]

    def take(self, n: int) -> bytes:
        data = self._ensure(n)
        self.offset += n
        return data

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def b(self) -> bool:
        return self.take(1)[0] != 0

    def string(self) -> str:
        n = self.u64()
        return self.take(n).decode("utf-8", "replace")
```

```python
# tests/helpers/__init__.py
```

```python
# tests/helpers/gguf_builder.py
"""Build synthetic GGUF byte blobs for tests."""
from __future__ import annotations

import struct
from typing import Any

T_UINT32, T_FLOAT32, T_BOOL, T_STRING, T_ARRAY, T_UINT64 = 4, 6, 7, 8, 9, 10


def _s(v: str) -> bytes:
    e = v.encode("utf-8")
    return struct.pack("<Q", len(e)) + e


def _value(kind: str, v: Any) -> bytes:
    if kind == "string":
        return struct.pack("<I", T_STRING) + _s(v)
    if kind == "u32":
        return struct.pack("<I", T_UINT32) + struct.pack("<I", v)
    if kind == "u64":
        return struct.pack("<I", T_UINT64) + struct.pack("<Q", v)
    if kind == "bool":
        return struct.pack("<I", T_BOOL) + (b"\x01" if v else b"\x00")
    if kind == "f32":
        return struct.pack("<I", T_FLOAT32) + struct.pack("<f", v)
    if kind == "array_string":
        out = struct.pack("<I", T_ARRAY) + struct.pack("<I", T_STRING)
        out += struct.pack("<Q", len(v))
        for item in v:
            out += _s(item)
        return out
    raise ValueError(f"unsupported kind {kind}")


def build_gguf(kvs: dict[str, tuple[str, Any]], version: int = 3,
               tensor_count: int = 0) -> bytes:
    out = b"GGUF" + struct.pack("<I", version)
    out += struct.pack("<Q", tensor_count) + struct.pack("<Q", len(kvs))
    for key, (kind, val) in kvs.items():
        out += _s(key) + _value(kind, val)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bytesource.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/bytesource.py tests/helpers tests/test_bytesource.py
git commit -m "feat: byte sources and GGUF primitive readers"
```

---

