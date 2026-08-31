# ggufdoctor v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a CLI that reads a GGUF file's embedded chat template, runs offline sanity checks against the file's own tokenizer, optionally compares rendered output against the upstream source model, and reproduces the ecosystem survey.

**Architecture:** Layered and I/O-free at the edges. `reader` parses GGUF metadata from a byte source (local file or HTTP range). `sources` resolves user input and upstream models, classifying every failure instead of dropping it. `engines` renders templates behind a uniform interface (v0.1 ships Jinja2 only; the interface is the seam for minja/Ollama later). `checks` are pure functions over already-loaded data. `report` formats. `survey` batches.

**Tech Stack:** Python 3.11+, Jinja2 3.1+, pytest. HTTP via stdlib `urllib` — no `requests` dependency.

**Spec:** `docs/superpowers/specs/2026-08-31-ggufdoctor-design.md`

## Global Constraints

- Python 3.11+ (uses `X | None` union syntax and `StrEnum`-style patterns).
- Runtime dependencies: **Jinja2 only**. HTTP uses stdlib `urllib.request`. No `requests`, no `huggingface_hub`.
- **Checks perform no I/O.** Every check is a pure function over a `CheckContext`. A check that opens a file or socket is a bug.
- **No network unless** the input is remote or `--compare-upstream` was passed. A local path with no flags must issue zero requests.
- Exit codes: `0` nothing at or above threshold, `1` findings at or above threshold, `2` tool or usage failure.
- JSON `schema_version` is the string `"1"`.
- Finding ids are stable and never renumbered: `S001`–`S008`, `R001`–`R004`. (`X001`–`X005` are reserved for v0.2; do not use.)
- Coverage gaps are reported, never silently excluded.
- All GGUF integers are **little-endian**.
- Package layout is `src/`-style; imports are absolute (`from ggufdoctor.models import ...`).

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config, console script entry point |
| `src/ggufdoctor/models.py` | Shared value types: `Severity`, `Finding`, `GgufModel`, `RenderResult`, `Coverage`, `Fixture`, `CheckContext` |
| `src/ggufdoctor/bytesource.py` | `ByteSource` protocol, `LocalByteSource`, `HttpRangeByteSource` |
| `src/ggufdoctor/reader.py` | GGUF header/KV parsing into `GgufModel` |
| `src/ggufdoctor/hf.py` | Hugging Face API: model info, base-model resolution, upstream template fetch |
| `src/ggufdoctor/sources.py` | Resolve CLI input into `GgufModel` + upstream template + `Coverage` |
| `src/ggufdoctor/engines/base.py` | `Engine` protocol |
| `src/ggufdoctor/engines/jinja2_engine.py` | Jinja2 implementation (the transformers reference) |
| `src/ggufdoctor/fixtures.py` | Fixture corpus loader |
| `src/ggufdoctor/fixture_data/*.json` | Versioned conversation corpus |
| `src/ggufdoctor/checks/sanity.py` | S001–S008 |
| `src/ggufdoctor/checks/reference.py` | R001–R004 |
| `src/ggufdoctor/checks/registry.py` | Check discovery and execution |
| `src/ggufdoctor/ignorefile.py` | Accepted-divergence list |
| `src/ggufdoctor/report/human.py` | Terminal output |
| `src/ggufdoctor/report/json_report.py` | Versioned JSON |
| `src/ggufdoctor/cli.py` | Argument parsing, wiring, exit codes |
| `src/ggufdoctor/survey.py` | Batch harness |
| `tests/helpers/gguf_builder.py` | Synthetic GGUF byte builder for tests |

---

### Task 1: Project scaffolding and shared value types

**Files:**
- Create: `pyproject.toml`
- Create: `src/ggufdoctor/__init__.py`
- Create: `src/ggufdoctor/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Severity` (`ERROR`/`WARN`/`INFO`, str-valued), `Finding(id, severity, message, fixture=None, evidence=dict)`, `GgufModel(source_id, architecture, chat_template, tokens, bos_token_id, eos_token_id, add_bos_token, metadata)`, `RenderResult(text, error)` with `.ok`, `Coverage(upstream, families_run)`, `Fixture(name, context)`, `CheckContext(model, engines, fixtures, upstream_template, upstream_meta)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from ggufdoctor.models import Severity, Finding, RenderResult, Coverage


def test_severity_is_string_valued():
    assert Severity.ERROR.value == "error"
    assert Severity.WARN.value == "warn"
    assert Severity.INFO.value == "info"


def test_finding_defaults_are_independent():
    a = Finding(id="S001", severity=Severity.ERROR, message="x")
    b = Finding(id="S002", severity=Severity.WARN, message="y")
    a.evidence["k"] = 1
    assert b.evidence == {}, "mutable default leaked between instances"


def test_render_result_ok_reflects_error():
    assert RenderResult(text="hi", error=None).ok is True
    assert RenderResult(text=None, error="render:ValueError").ok is False


def test_coverage_records_families_run():
    c = Coverage(upstream="gated", families_run=["S"])
    assert c.upstream == "gated"
    assert c.families_run == ["S"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ggufdoctor"
version = "0.1.0"
description = "Lint chat templates embedded in GGUF files"
requires-python = ">=3.11"
dependencies = ["jinja2>=3.1"]

[project.scripts]
ggufdoctor = "ggufdoctor.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/ggufdoctor"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["network: hits the real Hugging Face API (deselected by default)"]
addopts = "-m 'not network'"
```

```python
# src/ggufdoctor/__init__.py
__version__ = "0.1.0"
```

```python
# src/ggufdoctor/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARN: 1, Severity.ERROR: 2}


@dataclass
class Finding:
    id: str
    severity: Severity
    message: str
    fixture: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GgufModel:
    source_id: str
    architecture: str | None = None
    chat_template: str | None = None
    tokens: list[str] = field(default_factory=list)
    bos_token_id: int | None = None
    eos_token_id: int | None = None
    add_bos_token: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    text: str | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Coverage:
    upstream: str
    families_run: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Fixture:
    name: str
    context: dict[str, Any]


@dataclass
class CheckContext:
    model: GgufModel
    engines: list[Any]
    fixtures: list[Fixture]
    upstream_template: str | None = None
    upstream_meta: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e . && pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ggufdoctor/__init__.py src/ggufdoctor/models.py tests/test_models.py
git commit -m "feat: project scaffolding and shared value types"
```

---

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

### Task 4: HTTP range byte source

**Files:**
- Modify: `src/ggufdoctor/bytesource.py`
- Test: `tests/test_http_range.py`

**Interfaces:**
- Consumes: `ByteSource` from Task 2
- Produces: `HttpRangeByteSource(url, headers=None)` implementing `read(offset, length)` via a `Range: bytes=` header, raising `HttpSourceError` on non-206/200 responses.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_http_range.py
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from ggufdoctor.bytesource import HttpRangeByteSource, Cursor
from ggufdoctor.reader import read_gguf
from tests.helpers.gguf_builder import build_gguf


@pytest.fixture
def served(tmp_path):
    blob = build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.chat_template": ("string", "{{ 'x' }}"),
        "tokenizer.ggml.tokens": ("array_string", ["a", "b"]),
    })
    (tmp_path / "m.gguf").write_bytes(blob + b"\x00" * 5_000_000)
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/m.gguf"
    srv.shutdown()


def test_range_read_returns_requested_bytes(served):
    src = HttpRangeByteSource(served)
    assert src.read(0, 4) == b"GGUF"


def test_parses_remote_header_without_full_download(served):
    src = HttpRangeByteSource(served)
    m = read_gguf(src, "remote")
    assert m.architecture == "llama"
    assert m.chat_template == "{{ 'x' }}"
    assert src.bytes_fetched < 3_000_000, "should not pull the whole file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_http_range.py -v`
Expected: FAIL with `ImportError: cannot import name 'HttpRangeByteSource'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/ggufdoctor/bytesource.py`:

```python
import urllib.error
import urllib.request


class HttpSourceError(Exception):
    """Remote source could not be range-read."""


class HttpRangeByteSource:
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.headers.setdefault("User-Agent", "ggufdoctor/0.1")
        self.bytes_fetched = 0

    def read(self, offset: int, length: int) -> bytes:
        h = dict(self.headers)
        h["Range"] = f"bytes={offset}-{offset + length - 1}"
        req = urllib.request.Request(self.url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status not in (200, 206):
                    raise HttpSourceError(f"{self.url}: HTTP {resp.status}")
                data = resp.read(length)
        except urllib.error.HTTPError as e:
            raise HttpSourceError(f"{self.url}: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise HttpSourceError(f"{self.url}: {e.reason}") from e
        self.bytes_fetched += len(data)
        return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_http_range.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/bytesource.py tests/test_http_range.py
git commit -m "feat: HTTP range byte source for remote GGUF headers"
```

---

### Task 5: Jinja2 engine and fixture corpus

**Files:**
- Create: `src/ggufdoctor/engines/__init__.py`
- Create: `src/ggufdoctor/engines/base.py`
- Create: `src/ggufdoctor/engines/jinja2_engine.py`
- Create: `src/ggufdoctor/fixtures.py`
- Create: `src/ggufdoctor/fixture_data/corpus.json`
- Test: `tests/test_engine_jinja2.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: `RenderResult`, `Fixture` from Task 1
- Produces: `Engine` protocol (`.name: str`, `.version: str`, `.render(template, context) -> RenderResult`); `Jinja2Engine()`; `load_fixtures(path=None) -> list[Fixture]`; `CORPUS_VERSION: str`

The corpus is the same seven fixtures used in the motivating survey: `user_only`, `system_user`, `multiturn`, `with_tools`, `thinking_unset`, `thinking_true`, `thinking_false`. Rendering must supply `bos_token`/`eos_token` defaults and the `raise_exception` and `strftime_now` globals that real templates call; `strftime_now` is pinned to a fixed date so renders are deterministic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_jinja2.py
from ggufdoctor.engines.jinja2_engine import Jinja2Engine


def test_renders_simple_template():
    e = Jinja2Engine()
    r = e.render("{% for m in messages %}{{ m['content'] }}{% endfor %}",
                 {"messages": [{"role": "user", "content": "hi"}]})
    assert r.ok
    assert r.text == "hi"


def test_compile_error_is_captured_not_raised():
    r = Jinja2Engine().render("{% if %}", {})
    assert not r.ok
    assert r.error.startswith("compile:")


def test_render_error_is_captured_not_raised():
    r = Jinja2Engine().render("{{ raise_exception('boom') }}", {})
    assert not r.ok
    assert r.error.startswith("render:")


def test_strftime_now_is_deterministic():
    e = Jinja2Engine()
    a = e.render("{{ strftime_now('%Y') }}", {})
    b = e.render("{{ strftime_now('%Y') }}", {})
    assert a.text == b.text


def test_engine_reports_name_and_version():
    e = Jinja2Engine()
    assert e.name == "jinja2"
    assert e.version
```

```python
# tests/test_fixtures.py
from ggufdoctor.fixtures import load_fixtures, CORPUS_VERSION


def test_corpus_has_expected_fixtures():
    names = [f.name for f in load_fixtures()]
    assert names == ["user_only", "system_user", "multiturn", "with_tools",
                     "thinking_unset", "thinking_true", "thinking_false"]


def test_tools_fixture_carries_a_tool_definition():
    f = next(f for f in load_fixtures() if f.name == "with_tools")
    assert f.context["tools"][0]["function"]["name"] == "get_weather"


def test_corpus_version_is_declared():
    assert CORPUS_VERSION == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_jinja2.py tests/test_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.engines'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/engines/__init__.py
```

```python
# src/ggufdoctor/engines/base.py
from __future__ import annotations

from typing import Any, Protocol

from ggufdoctor.models import RenderResult


class Engine(Protocol):
    name: str
    version: str

    def render(self, template: str, context: dict[str, Any]) -> RenderResult: ...
```

```python
# src/ggufdoctor/engines/jinja2_engine.py
from __future__ import annotations

import datetime
import json
from typing import Any

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

from ggufdoctor.models import RenderResult

PINNED_NOW = datetime.datetime(2026, 1, 1)

BASE_CONTEXT: dict[str, Any] = {
    "bos_token": "<s>",
    "eos_token": "</s>",
    "unk_token": "<unk>",
    "pad_token": "<pad>",
    "add_generation_prompt": True,
}


def _raise_exception(msg: str) -> None:
    raise ValueError(msg)


def _strftime_now(fmt: str) -> str:
    return PINNED_NOW.strftime(fmt)


class Jinja2Engine:
    name = "jinja2"

    def __init__(self) -> None:
        self.version = jinja2.__version__
        self._env = ImmutableSandboxedEnvironment(
            trim_blocks=False, lstrip_blocks=False
        )
        self._env.globals["raise_exception"] = _raise_exception
        self._env.globals["strftime_now"] = _strftime_now
        self._env.filters["tojson"] = lambda o, **kw: json.dumps(o)

    def render(self, template: str, context: dict[str, Any]) -> RenderResult:
        try:
            tpl = self._env.from_string(template)
        except Exception as e:
            return RenderResult(None, f"compile:{type(e).__name__}: {e}")
        ctx = dict(BASE_CONTEXT)
        ctx.update(context)
        try:
            return RenderResult(tpl.render(**ctx), None)
        except Exception as e:
            return RenderResult(None, f"render:{type(e).__name__}: {e}")
```

```python
# src/ggufdoctor/fixtures.py
from __future__ import annotations

import json
from importlib import resources

from ggufdoctor.models import Fixture

CORPUS_VERSION = "1"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return [Fixture(name=item["name"], context=item["context"])
            for item in data["fixtures"]]
```

```json
// src/ggufdoctor/fixture_data/corpus.json
{
  "version": "1",
  "fixtures": [
    {"name": "user_only",
     "context": {"messages": [{"role": "user", "content": "Hello"}],
                 "add_generation_prompt": true}},
    {"name": "system_user",
     "context": {"messages": [{"role": "system", "content": "Be brief."},
                              {"role": "user", "content": "Hello"}],
                 "add_generation_prompt": true}},
    {"name": "multiturn",
     "context": {"messages": [{"role": "user", "content": "Hi"},
                              {"role": "assistant", "content": "Hey!"},
                              {"role": "user", "content": "Bye"}],
                 "add_generation_prompt": true}},
    {"name": "with_tools",
     "context": {"messages": [{"role": "user", "content": "Weather in Paris?"}],
                 "add_generation_prompt": true,
                 "tools": [{"type": "function",
                            "function": {"name": "get_weather",
                                         "description": "Get weather for a city",
                                         "parameters": {"type": "object",
                                                        "properties": {"city": {"type": "string"}},
                                                        "required": ["city"]}}}]}},
    {"name": "thinking_unset",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true}},
    {"name": "thinking_true",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true, "enable_thinking": true}},
    {"name": "thinking_false",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true, "enable_thinking": false}}
  ]
}
```

Add to `pyproject.toml` under `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/ggufdoctor/fixture_data" = "ggufdoctor/fixture_data"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_jinja2.py tests/test_fixtures.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/engines src/ggufdoctor/fixtures.py src/ggufdoctor/fixture_data pyproject.toml tests/test_engine_jinja2.py tests/test_fixtures.py
git commit -m "feat: jinja2 engine and versioned fixture corpus"
```

---

### Task 6: Family S — self-contained checks

**Files:**
- Create: `src/ggufdoctor/checks/__init__.py`
- Create: `src/ggufdoctor/checks/sanity.py`
- Test: `tests/test_checks_sanity.py`

**Interfaces:**
- Consumes: `CheckContext`, `Finding`, `Severity`, `GgufModel`, `Fixture` from Task 1; `Jinja2Engine` from Task 5
- Produces: `run_sanity_checks(ctx: CheckContext) -> list[Finding]`; individual functions `s001_missing_template`, `s002_uncompilable`, `s003_render_error`, `s004_unknown_special_token`, `s005_eos_mismatch`, `s006_double_bos`, `s007_generation_prompt_noop`, `s008_empty_render`, each `(ctx) -> list[Finding]`; `CHAT_ARCHITECTURES: set[str]` and `NON_CHAT_ARCHITECTURES: set[str]`

`s004` extracts `<|...|>`-style literals from the template and reports any absent from `ctx.model.tokens`; it is skipped entirely when `tokens` is empty (nothing to check against). `s007` re-renders `user_only` with `add_generation_prompt=False` and compares.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checks_sanity.py
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel


def ctx(**kw):
    model = GgufModel(source_id="t", architecture=kw.pop("arch", "llama"), **kw)
    return CheckContext(model=model, engines=[Jinja2Engine()],
                        fixtures=load_fixtures())


def ids(findings):
    return {f.id for f in findings}


CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}"
            "<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")


def test_s001_chat_arch_without_template():
    assert "S001" in ids(run_sanity_checks(ctx(chat_template=None)))


def test_s001_not_raised_for_non_chat_arch():
    assert "S001" not in ids(run_sanity_checks(ctx(arch="bert", chat_template=None)))


def test_s002_uncompilable_template():
    assert "S002" in ids(run_sanity_checks(ctx(chat_template="{% if %}")))


def test_s003_render_error_on_fixture():
    f = run_sanity_checks(ctx(chat_template="{{ raise_exception('no') }}"))
    assert "S003" in ids(f)


def test_s004_flags_token_absent_from_vocab():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>"]))
    assert "S004" in ids(f)
    finding = next(x for x in f if x.id == "S004")
    assert "<|im_end|>" in finding.evidence["missing"]


def test_s004_silent_when_all_tokens_present():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL,
                              tokens=["<|im_start|>", "<|im_end|>"]))
    assert "S004" not in ids(f)


def test_s004_skipped_when_vocab_unavailable():
    assert "S004" not in ids(run_sanity_checks(ctx(chat_template=CHAT_TPL, tokens=[])))


def test_s006_double_bos():
    f = run_sanity_checks(ctx(chat_template="{{ bos_token }}hi", add_bos_token=True))
    assert "S006" in ids(f)


def test_s007_generation_prompt_noop():
    f = run_sanity_checks(ctx(chat_template="{% for m in messages %}{{ m['content'] }}{% endfor %}"))
    assert "S007" in ids(f)


def test_s008_empty_render():
    assert "S008" in ids(run_sanity_checks(ctx(chat_template="{# nothing #}")))


def test_clean_template_produces_no_findings():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL,
                              tokens=["<|im_start|>", "<|im_end|>"]))
    assert f == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_checks_sanity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.checks'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/checks/__init__.py
```

```python
# src/ggufdoctor/checks/sanity.py
from __future__ import annotations

import re

from ggufdoctor.models import CheckContext, Finding, Severity

NON_CHAT_ARCHITECTURES = {
    "bert", "nomic-bert", "jina-bert", "parakeet", "asr", "audiocpp",
    "ced", "whisper", "clip", "t5", "qwen3-tts",
}

SPECIAL_TOKEN_RE = re.compile(r"<\|[^|>\s]{1,60}\|>")


def _primary(ctx: CheckContext):
    return ctx.engines[0]


def _is_chat_arch(ctx: CheckContext) -> bool:
    arch = (ctx.model.architecture or "").lower()
    return arch not in NON_CHAT_ARCHITECTURES


def s001_missing_template(ctx: CheckContext) -> list[Finding]:
    if ctx.model.chat_template or not _is_chat_arch(ctx):
        return []
    return [Finding("S001", Severity.ERROR,
                    "chat-capable architecture but no chat template embedded",
                    evidence={"architecture": ctx.model.architecture})]


def s002_uncompilable(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    r = _primary(ctx).render(tpl, {"messages": [{"role": "user", "content": "x"}]})
    if r.error and r.error.startswith("compile:"):
        return [Finding("S002", Severity.ERROR,
                        "template does not compile under Jinja2",
                        evidence={"error": r.error})]
    return []


def s003_render_error(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    out = []
    for fx in ctx.fixtures:
        r = _primary(ctx).render(tpl, fx.context)
        if r.error and r.error.startswith("render:"):
            out.append(Finding("S003", Severity.ERROR,
                               "template raises while rendering a standard conversation",
                               fixture=fx.name, evidence={"error": r.error}))
    return out


def s004_unknown_special_token(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl or not ctx.model.tokens:
        return []
    vocab = set(ctx.model.tokens)
    missing = sorted({t for t in SPECIAL_TOKEN_RE.findall(tpl) if t not in vocab})
    if not missing:
        return []
    return [Finding("S004", Severity.ERROR,
                    "template emits special tokens absent from this file's vocab; "
                    "they will be silently split into multiple tokens",
                    evidence={"missing": missing})]


def s005_eos_mismatch(ctx: CheckContext) -> list[Finding]:
    m = ctx.model
    if not m.chat_template or m.eos_token_id is None or not m.tokens:
        return []
    if m.eos_token_id >= len(m.tokens):
        return [Finding("S005", Severity.WARN,
                        "eos_token_id is out of range for this file's vocab",
                        evidence={"eos_token_id": m.eos_token_id,
                                  "vocab_size": len(m.tokens)})]
    eos = m.tokens[m.eos_token_id]
    if eos not in m.chat_template:
        return [Finding("S005", Severity.WARN,
                        "template never emits the declared EOS token",
                        evidence={"eos_token": eos})]
    return []


def s006_double_bos(ctx: CheckContext) -> list[Finding]:
    m = ctx.model
    if not m.chat_template or not m.add_bos_token:
        return []
    emits_bos = "bos_token" in m.chat_template
    if m.bos_token_id is not None and m.tokens and m.bos_token_id < len(m.tokens):
        emits_bos = emits_bos or (m.tokens[m.bos_token_id] in m.chat_template)
    if not emits_bos:
        return []
    return [Finding("S006", Severity.WARN,
                    "template emits BOS while metadata also adds BOS; "
                    "the prompt will start with a duplicated token",
                    evidence={"add_bos_token": True})]


def s007_generation_prompt_noop(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    fx = next((f for f in ctx.fixtures if f.name == "user_only"), None)
    if fx is None:
        return []
    on = _primary(ctx).render(tpl, {**fx.context, "add_generation_prompt": True})
    off = _primary(ctx).render(tpl, {**fx.context, "add_generation_prompt": False})
    if not (on.ok and off.ok) or on.text != off.text:
        return []
    return [Finding("S007", Severity.WARN,
                    "add_generation_prompt has no effect; the assistant turn is never opened",
                    fixture=fx.name)]


def s008_empty_render(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    out = []
    for fx in ctx.fixtures:
        r = _primary(ctx).render(tpl, fx.context)
        if r.ok and not (r.text or "").strip():
            out.append(Finding("S008", Severity.ERROR,
                               "template renders to empty output",
                               fixture=fx.name))
    return out


SANITY_CHECKS = [
    s001_missing_template, s002_uncompilable, s003_render_error,
    s004_unknown_special_token, s005_eos_mismatch, s006_double_bos,
    s007_generation_prompt_noop, s008_empty_render,
]


def run_sanity_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in SANITY_CHECKS:
        findings.extend(check(ctx))
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_checks_sanity.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/checks tests/test_checks_sanity.py
git commit -m "feat: family S self-contained template checks"
```

---

### Task 7: Hugging Face client and upstream resolution

**Files:**
- Create: `src/ggufdoctor/hf.py`
- Test: `tests/test_hf.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `HfClient(token=None, opener=None)` with `model_info(repo_id) -> dict`, `gguf_chat_template(repo_id) -> str | None`, `base_model_of(info) -> str | None`, `upstream_template(repo_id) -> tuple[str | None, str]`. The second element of the tuple is one of `"ok"`, `"gated"`, `"not_found"`, `"fetch_error"`, `"genuinely_absent"`.

`opener` is an injectable callable `(url: str) -> str` returning body text, raising `urllib.error.HTTPError` on failure. Tests inject a fake; production uses `urllib`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hf.py
import json
import urllib.error

import pytest

from ggufdoctor.hf import HfClient


def fake_opener(responses):
    def _open(url):
        for frag, val in responses.items():
            if frag in url:
                if isinstance(val, int):
                    raise urllib.error.HTTPError(url, val, "err", {}, None)
                return val
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    return _open


def test_base_model_from_card_data():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"cardData": {"base_model": "Qwen/Qwen3-8B"}}) == "Qwen/Qwen3-8B"


def test_base_model_from_list_takes_first():
    c = HfClient(opener=fake_opener({}))
    info = {"cardData": {"base_model": ["Qwen/Qwen3-8B", "other/x"]}}
    assert c.base_model_of(info) == "Qwen/Qwen3-8B"


def test_base_model_from_tag_fallback():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["base_model:Qwen/Qwen3-8B"]}) == "Qwen/Qwen3-8B"


def test_base_model_absent():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["gguf"]}) is None


def test_upstream_template_ok():
    body = json.dumps({"chat_template": "{{ 'hi' }}"})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    tpl, why = c.upstream_template("org/model")
    assert why == "ok"
    assert tpl == "{{ 'hi' }}"


def test_upstream_gated_is_distinguished_from_missing():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 401}))
    tpl, why = c.upstream_template("google/gemma-4")
    assert tpl is None
    assert why == "gated"


def test_upstream_404_is_not_found():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 404,
                                     "chat_template.json": 404}))
    assert c.upstream_template("dead/repo")[1] == "not_found"


def test_upstream_present_but_no_template_field():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": json.dumps({})}))
    assert c.upstream_template("org/embed")[1] == "genuinely_absent"


def test_multi_template_list_picks_default():
    body = json.dumps({"chat_template": [
        {"name": "tool_use", "template": "T"},
        {"name": "default", "template": "D"}]})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    assert c.upstream_template("org/m")[0] == "D"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.hf'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/hf.py
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

API = "https://huggingface.co/api/models"
RESOLVE = "https://huggingface.co/{repo}/resolve/main/{fn}"


def _default_opener(token: str | None) -> Callable[[str], str]:
    def _open(url: str) -> str:
        headers = {"User-Agent": "ggufdoctor/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")
    return _open


class HfClient:
    def __init__(self, token: str | None = None,
                 opener: Callable[[str], str] | None = None) -> None:
        self.token = token
        self._open = opener or _default_opener(token)

    def model_info(self, repo_id: str) -> dict[str, Any]:
        url = f"{API}/{repo_id}?expand[]=gguf&expand[]=cardData&expand[]=tags"
        return json.loads(self._open(url))

    def gguf_chat_template(self, repo_id: str) -> str | None:
        gg = (self.model_info(repo_id) or {}).get("gguf") or {}
        return gg.get("chat_template")

    def base_model_of(self, info: dict[str, Any]) -> str | None:
        bm = (info.get("cardData") or {}).get("base_model")
        if isinstance(bm, list):
            bm = bm[0] if bm else None
        if isinstance(bm, str) and "/" in bm:
            return bm
        for tag in info.get("tags", []) or []:
            if isinstance(tag, str) and tag.startswith("base_model:"):
                cand = tag.split(":")[-1]
                if "/" in cand:
                    return cand
        return None

    def upstream_template(self, repo_id: str) -> tuple[str | None, str]:
        reasons: list[str] = []
        for fn in ("tokenizer_config.json", "chat_template.json"):
            try:
                data = json.loads(self._open(RESOLVE.format(repo=repo_id, fn=fn)))
            except urllib.error.HTTPError as e:
                reasons.append("gated" if e.code in (401, 403)
                               else "not_found" if e.code == 404
                               else "fetch_error")
                continue
            except Exception:
                reasons.append("fetch_error")
                continue
            ct = data.get("chat_template")
            if isinstance(ct, list):
                pick = None
                for entry in ct:
                    if isinstance(entry, dict) and entry.get("name") == "default":
                        pick = entry.get("template")
                if pick is None and ct and isinstance(ct[0], dict):
                    pick = ct[0].get("template")
                ct = pick
            if isinstance(ct, str) and ct.strip():
                return ct, "ok"
            reasons.append("genuinely_absent")
        for preferred in ("gated", "genuinely_absent", "fetch_error", "not_found"):
            if preferred in reasons:
                return None, preferred
        return None, "not_found"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hf.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/hf.py tests/test_hf.py
git commit -m "feat: Hugging Face client with coverage-classified upstream resolution"
```

---

### Task 8: Family R — reference comparison checks

**Files:**
- Create: `src/ggufdoctor/checks/reference.py`
- Test: `tests/test_checks_reference.py`

**Interfaces:**
- Consumes: `CheckContext`, `Finding`, `Severity` from Task 1; `Jinja2Engine` from Task 5
- Produces: `run_reference_checks(ctx: CheckContext) -> list[Finding]`; `r001_output_differs`, `r002_annotated_patch`, `r003_upstream_missing`, `r004_upstream_newer`; `INTENT_COMMENT_RE`

`ctx.upstream_meta` may carry `{"coverage": str, "upstream_modified": str, "gguf_modified": str}`. R002 does not itself report a divergence — it downgrades: when the GGUF template carries an author comment naming a fix, R001's severity becomes INFO and an R002 finding is attached.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checks_reference.py
from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

A = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
B = "{% for m in messages %}{{ m['content'] }}{% endfor %}Y"


def ctx(gguf_tpl, upstream_tpl, meta=None):
    return CheckContext(
        model=GgufModel(source_id="t", architecture="llama", chat_template=gguf_tpl),
        engines=[Jinja2Engine()], fixtures=load_fixtures(),
        upstream_template=upstream_tpl, upstream_meta=meta or {})


def by_id(findings):
    return {f.id: f for f in findings}


def test_r001_flags_differing_output():
    f = by_id(run_reference_checks(ctx(A, B)))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN


def test_r001_silent_when_output_matches():
    assert run_reference_checks(ctx(A, A)) == []


def test_r001_silent_on_cosmetic_source_difference():
    # different source, identical rendered output
    same_output = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
    spaced = "{% for m in messages %}{{   m['content']   }}{% endfor %}X"
    assert run_reference_checks(ctx(spaced, same_output)) == []


def test_r002_downgrades_annotated_intentional_patch():
    annotated = "{# Unsloth chat template fixes #}" + B
    f = by_id(run_reference_checks(ctx(annotated, A)))
    assert "R002" in f
    assert f["R001"].severity == Severity.INFO


def test_r003_reports_dead_upstream():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "not_found"})))
    assert "R003" in f


def test_r003_not_reported_when_gated():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "gated"})))
    assert "R003" not in f


def test_r004_flags_upstream_modified_after_publication():
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-06-01T00:00:00Z",
        "gguf_modified": "2026-01-01T00:00:00Z"})))
    assert "R004" in f
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_checks_reference.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.checks.reference'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/checks/reference.py
from __future__ import annotations

import difflib
import re

from ggufdoctor.models import CheckContext, Finding, Severity

INTENT_COMMENT_RE = re.compile(
    r"\{#.{0,400}?(fix|fixes|patch|patched|modified|corrected).{0,400}?#\}",
    re.I | re.S)


def _diff(upstream: str, gguf: str) -> str:
    return "\n".join(difflib.unified_diff(
        upstream.splitlines(), gguf.splitlines(),
        fromfile="upstream", tofile="gguf", n=1, lineterm=""))


def r002_annotated_patch(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template or ""
    if not INTENT_COMMENT_RE.search(tpl[:800]):
        return []
    return [Finding("R002", Severity.INFO,
                    "divergence is annotated by the publisher as a deliberate fix")]


def r001_output_differs(ctx: CheckContext) -> list[Finding]:
    gguf_tpl, up_tpl = ctx.model.chat_template, ctx.upstream_template
    if not gguf_tpl or not up_tpl:
        return []
    annotated = bool(r002_annotated_patch(ctx))
    severity = Severity.INFO if annotated else Severity.WARN
    engine = ctx.engines[0]
    out: list[Finding] = []
    for fx in ctx.fixtures:
        g = engine.render(gguf_tpl, fx.context)
        u = engine.render(up_tpl, fx.context)
        if not (g.ok and u.ok):
            continue
        if g.text == u.text:
            continue
        out.append(Finding(
            "R001", severity,
            "rendered prompt differs from the upstream source model",
            fixture=fx.name,
            evidence={"diff": _diff(u.text, g.text),
                      "len_delta": len(g.text) - len(u.text)}))
    return out


def r003_upstream_missing(ctx: CheckContext) -> list[Finding]:
    if ctx.upstream_meta.get("coverage") != "not_found":
        return []
    return [Finding("R003", Severity.WARN,
                    "upstream base model no longer exists; provenance is unverifiable")]


def r004_upstream_newer(ctx: CheckContext) -> list[Finding]:
    up = ctx.upstream_meta.get("upstream_modified")
    mine = ctx.upstream_meta.get("gguf_modified")
    if not up or not mine or up <= mine:
        return []
    return [Finding("R004", Severity.INFO,
                    "upstream template changed after this file was published",
                    evidence={"upstream_modified": up, "gguf_modified": mine})]


REFERENCE_CHECKS = [r001_output_differs, r002_annotated_patch,
                    r003_upstream_missing, r004_upstream_newer]


def run_reference_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in REFERENCE_CHECKS:
        findings.extend(check(ctx))
    if not any(f.id == "R001" for f in findings):
        findings = [f for f in findings if f.id != "R002"]
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_checks_reference.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/checks/reference.py tests/test_checks_reference.py
git commit -m "feat: family R reference comparison checks with intent-aware downgrade"
```

---

### Task 9: Ignore file

**Files:**
- Create: `src/ggufdoctor/ignorefile.py`
- Test: `tests/test_ignorefile.py`

**Interfaces:**
- Consumes: `Finding` from Task 1
- Produces: `load_ignores(path) -> list[IgnoreRule]`; `IgnoreRule(id, fixture, reason)`; `apply_ignores(findings, rules) -> tuple[list[Finding], list[Finding]]` returning `(kept, suppressed)`

Format is TOML-free line-oriented to avoid a dependency: `ID [fixture] # reason`, blank lines and `#`-leading lines skipped. A rule without a reason is rejected — recording *why* is the point.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ignorefile.py
import pytest

from ggufdoctor.ignorefile import load_ignores, apply_ignores, IgnoreRule
from ggufdoctor.models import Finding, Severity


def test_parses_rule_with_reason(tmp_path):
    p = tmp_path / ".ggufdoctorignore"
    p.write_text("R001 with_tools # upstream is wrong, ours is the fix\n")
    rules = load_ignores(str(p))
    assert rules == [IgnoreRule(id="R001", fixture="with_tools",
                                reason="upstream is wrong, ours is the fix")]


def test_rule_without_fixture_matches_any(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005 # eos handled by runtime\n")
    rules = load_ignores(str(p))
    assert rules[0].fixture is None


def test_rule_without_reason_is_rejected(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005\n")
    with pytest.raises(ValueError, match="reason"):
        load_ignores(str(p))


def test_comments_and_blank_lines_skipped(tmp_path):
    p = tmp_path / "i"
    p.write_text("# header\n\nS005 # why\n")
    assert len(load_ignores(str(p))) == 1


def test_apply_splits_kept_and_suppressed():
    findings = [Finding("R001", Severity.WARN, "m", fixture="with_tools"),
                Finding("R001", Severity.WARN, "m", fixture="user_only"),
                Finding("S004", Severity.ERROR, "m")]
    rules = [IgnoreRule("R001", "with_tools", "known")]
    kept, suppressed = apply_ignores(findings, rules)
    assert len(kept) == 2
    assert len(suppressed) == 1
    assert suppressed[0].fixture == "with_tools"


def test_missing_file_yields_no_rules():
    assert load_ignores("/nonexistent/path") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ignorefile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.ignorefile'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/ignorefile.py
from __future__ import annotations

import os
from dataclasses import dataclass

from ggufdoctor.models import Finding


@dataclass(frozen=True)
class IgnoreRule:
    id: str
    fixture: str | None
    reason: str


def load_ignores(path: str) -> list[IgnoreRule]:
    if not path or not os.path.exists(path):
        return []
    rules: list[IgnoreRule] = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" not in line:
                raise ValueError(
                    f"{path}:{lineno}: ignore rules require a reason after '#'")
            head, reason = line.split("#", 1)
            parts = head.split()
            if not parts:
                raise ValueError(f"{path}:{lineno}: missing rule id")
            rule_id = parts[0]
            fixture = parts[1] if len(parts) > 1 else None
            rules.append(IgnoreRule(rule_id, fixture, reason.strip()))
    return rules


def apply_ignores(findings: list[Finding],
                  rules: list[IgnoreRule]) -> tuple[list[Finding], list[Finding]]:
    kept: list[Finding] = []
    suppressed: list[Finding] = []
    for f in findings:
        matched = any(r.id == f.id and (r.fixture is None or r.fixture == f.fixture)
                      for r in rules)
        (suppressed if matched else kept).append(f)
    return kept, suppressed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ignorefile.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/ignorefile.py tests/test_ignorefile.py
git commit -m "feat: ignore file requiring a recorded reason"
```

---

### Task 10: Reporting and exit codes

**Files:**
- Create: `src/ggufdoctor/report/__init__.py`
- Create: `src/ggufdoctor/report/human.py`
- Create: `src/ggufdoctor/report/json_report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Finding`, `Severity`, `SEVERITY_ORDER`, `Coverage`, `GgufModel` from Task 1; `CORPUS_VERSION` from Task 5
- Produces: `render_human(model, findings, suppressed, coverage, engines) -> str`; `build_json(model, findings, suppressed, coverage, engines) -> dict`; `exit_code(findings, fail_on: str) -> int`

`exit_code` returns `1` when any finding's severity is at or above `fail_on`, else `0`. `fail_on="never"` always returns `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.models import Coverage, Finding, GgufModel, Severity
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code

MODEL = GgufModel(source_id="m.gguf", architecture="llama")
COV = Coverage(upstream="gated", families_run=["S"])


def test_exit_code_threshold():
    warn = [Finding("R001", Severity.WARN, "m")]
    err = [Finding("S004", Severity.ERROR, "m")]
    assert exit_code(warn, "error") == 0
    assert exit_code(warn, "warn") == 1
    assert exit_code(err, "error") == 1
    assert exit_code(err, "never") == 0
    assert exit_code([], "info") == 0


def test_json_has_stable_schema_fields():
    d = build_json(MODEL, [Finding("S004", Severity.ERROR, "m")], [], COV,
                   [Jinja2Engine()])
    assert d["schema_version"] == "1"
    assert d["target"]["id"] == "m.gguf"
    assert d["coverage"]["upstream"] == "gated"
    assert d["summary"] == {"error": 1, "warn": 0, "info": 0}
    assert d["engines"][0]["name"] == "jinja2"
    assert d["fixture_corpus_version"] == "1"


def test_human_output_states_coverage_explicitly():
    out = render_human(MODEL, [], [], COV, [Jinja2Engine()])
    assert "gated" in out
    assert "R family skipped" in out or "families run: S" in out


def test_human_output_shows_finding_id_and_fixture():
    f = Finding("R001", Severity.WARN, "differs", fixture="with_tools",
                evidence={"diff": "-a\n+b"})
    out = render_human(MODEL, [f], [], COV, [Jinja2Engine()])
    assert "R001" in out
    assert "with_tools" in out
    assert "+b" in out


def test_human_output_reports_suppressed_count():
    sup = [Finding("R001", Severity.WARN, "m", fixture="user_only")]
    out = render_human(MODEL, [], sup, COV, [Jinja2Engine()])
    assert "1 suppressed" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/report/__init__.py
```

```python
# src/ggufdoctor/report/json_report.py
from __future__ import annotations

import datetime
from typing import Any

from ggufdoctor import __version__
from ggufdoctor.fixtures import CORPUS_VERSION
from ggufdoctor.models import (SEVERITY_ORDER, Coverage, Finding, GgufModel,
                               Severity)

_THRESHOLDS = {"error": Severity.ERROR, "warn": Severity.WARN,
               "info": Severity.INFO}


def exit_code(findings: list[Finding], fail_on: str) -> int:
    if fail_on == "never":
        return 0
    threshold = _THRESHOLDS[fail_on]
    limit = SEVERITY_ORDER[threshold]
    return 1 if any(SEVERITY_ORDER[f.severity] >= limit for f in findings) else 0


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def build_json(model: GgufModel, findings: list[Finding],
               suppressed: list[Finding], coverage: Coverage,
               engines: list[Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "tool_version": __version__,
        "fixture_corpus_version": CORPUS_VERSION,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "target": {"id": model.source_id, "architecture": model.architecture},
        "engines": [{"name": e.name, "version": e.version} for e in engines],
        "coverage": {"upstream": coverage.upstream,
                     "families_run": coverage.families_run},
        "findings": [
            {"id": f.id, "severity": f.severity.value, "message": f.message,
             "fixture": f.fixture, "evidence": f.evidence} for f in findings],
        "suppressed": [
            {"id": f.id, "fixture": f.fixture} for f in suppressed],
        "summary": summarize(findings),
    }
```

```python
# src/ggufdoctor/report/human.py
from __future__ import annotations

from typing import Any

from ggufdoctor.models import Coverage, Finding, GgufModel
from ggufdoctor.report.json_report import summarize

ALL_FAMILIES = ["S", "R"]


def render_human(model: GgufModel, findings: list[Finding],
                 suppressed: list[Finding], coverage: Coverage,
                 engines: list[Any]) -> str:
    lines: list[str] = []
    engine_names = ", ".join(f"{e.name} {e.version}" for e in engines)
    lines.append(f"{model.source_id}  [{model.architecture or 'unknown arch'}]"
                 f"  engines: {engine_names}")
    lines.append("")

    if not findings:
        lines.append("  no findings")
    for f in findings:
        head = f"  {f.id}  {f.severity.value.upper():<5} {f.message}"
        if f.fixture:
            head += f"   [{f.fixture}]"
        lines.append(head)
        diff = f.evidence.get("diff")
        if diff:
            for dl in diff.splitlines()[:12]:
                lines.append(f"        {dl}")
        missing = f.evidence.get("missing")
        if missing:
            lines.append(f"        missing from vocab: {', '.join(missing)}")
        lines.append("")

    counts = summarize(findings)
    skipped = [fam for fam in ALL_FAMILIES if fam not in coverage.families_run]
    tail = (f"{counts['error']} error, {counts['warn']} warn, "
            f"{counts['info']} info")
    if suppressed:
        tail += f", {len(suppressed)} suppressed"
    lines.append(tail)
    lines.append(f"families run: {', '.join(coverage.families_run) or 'none'}"
                 f"   upstream: {coverage.upstream}")
    for fam in skipped:
        lines.append(f"  note: {fam} family skipped")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/report tests/test_report.py
git commit -m "feat: human and JSON reporting with explicit coverage"
```

---

### Task 11: Source resolution and CLI

**Files:**
- Create: `src/ggufdoctor/sources.py`
- Create: `src/ggufdoctor/cli.py`
- Test: `tests/test_sources.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–10
- Produces: `resolve(target, compare_upstream=None, client=None) -> tuple[GgufModel, str | None, Coverage]`; `is_repo_id(target) -> bool`; `main(argv=None) -> int`

`resolve` never touches the network when `target` is an existing local path and `compare_upstream` is `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources.py
from ggufdoctor.sources import is_repo_id, resolve
from tests.helpers.gguf_builder import build_gguf


def test_repo_id_detection():
    assert is_repo_id("unsloth/Qwen3-8B-GGUF")
    assert not is_repo_id("./model.gguf")
    assert not is_repo_id("/abs/model.gguf")


def test_local_resolve_is_offline(tmp_path, monkeypatch):
    import urllib.request

    def explode(*a, **k):
        raise AssertionError("network access during local run")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p))
    assert model.architecture == "llama"
    assert upstream is None
    assert coverage.upstream == "not_requested"
    assert coverage.families_run == ["S"]


def test_local_with_compare_upstream_runs_r_family(tmp_path):
    class FakeClient:
        def upstream_template(self, repo):
            return "{{ 'up' }}", "ok"

    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p), compare_upstream="Qwen/Qwen3-8B",
                                        client=FakeClient())
    assert upstream == "{{ 'up' }}"
    assert coverage.families_run == ["S", "R"]
    assert coverage.upstream == "ok"
```

```python
# tests/test_cli.py
import json

from ggufdoctor.cli import main
from tests.helpers.gguf_builder import build_gguf

CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}"
            "<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")


def _model(tmp_path, **kv):
    base = {"general.architecture": ("string", "llama"),
            "tokenizer.chat_template": ("string", CHAT_TPL),
            "tokenizer.ggml.tokens": ("array_string",
                                      ["<|im_start|>", "<|im_end|>"])}
    base.update(kv)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf(base))
    return str(p)


def test_clean_model_exits_zero(tmp_path, capsys):
    assert main([_model(tmp_path)]) == 0
    assert "no findings" in capsys.readouterr().out


def test_missing_vocab_token_exits_one(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path]) == 1


def test_json_output_written(tmp_path):
    out = tmp_path / "r.json"
    main([_model(tmp_path), "--json", str(out)])
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1"


def test_fail_on_never_always_zero(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path, "--fail-on", "never"]) == 0


def test_unreadable_file_exits_two(tmp_path):
    bad = tmp_path / "x.gguf"
    bad.write_bytes(b"NOPE")
    assert main([str(bad)]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/sources.py
from __future__ import annotations

import os

from ggufdoctor.bytesource import HttpRangeByteSource
from ggufdoctor.hf import HfClient
from ggufdoctor.models import Coverage, GgufModel
from ggufdoctor.reader import read_gguf_file

RESOLVE_GGUF = "https://huggingface.co/{repo}/resolve/main/{fn}"


def is_repo_id(target: str) -> bool:
    if os.path.exists(target):
        return False
    return "/" in target and not target.startswith((".", "/", "~")) \
        and not target.endswith(".gguf")


def resolve(target: str, compare_upstream: str | None = None,
            client: object | None = None) -> tuple[GgufModel, str | None, Coverage]:
    families = ["S"]

    if is_repo_id(target):
        hf = client or HfClient()
        info = hf.model_info(target)
        gg = (info or {}).get("gguf") or {}
        model = GgufModel(source_id=target,
                          architecture=gg.get("architecture"),
                          chat_template=gg.get("chat_template"))
        base = compare_upstream or hf.base_model_of(info)
        if not base:
            return model, None, Coverage("no_base_model", families)
        upstream, why = hf.upstream_template(base)
        if why == "ok":
            families.append("R")
        return model, upstream, Coverage(why, families)

    model = read_gguf_file(target)
    if compare_upstream is None:
        return model, None, Coverage("not_requested", families)

    hf = client or HfClient()
    upstream, why = hf.upstream_template(compare_upstream)
    if why == "ok":
        families.append("R")
    return model, upstream, Coverage(why, families)
```

```python
# src/ggufdoctor/cli.py
from __future__ import annotations

import argparse
import json
import sys

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.ignorefile import apply_ignores, load_ignores
from ggufdoctor.models import CheckContext
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ggufdoctor",
        description="Lint the chat template embedded in a GGUF file.")
    p.add_argument("target", help="local .gguf path or a Hugging Face repo id")
    p.add_argument("--compare-upstream", metavar="REPO",
                   help="compare rendered output against this source model")
    p.add_argument("--fail-on", choices=["error", "warn", "info", "never"],
                   default="error")
    p.add_argument("--fixtures", metavar="PATH", help="custom fixture corpus JSON")
    p.add_argument("--json", metavar="PATH", dest="json_path")
    p.add_argument("--ignore-file", metavar="PATH", default=".ggufdoctorignore")
    p.add_argument("--require-upstream", action="store_true",
                   help="treat a missing upstream as a failure")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from ggufdoctor.sources import resolve
        model, upstream, coverage = resolve(args.target, args.compare_upstream)
        fixtures = load_fixtures(args.fixtures)
        engines = [Jinja2Engine()]
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream})
        findings = run_sanity_checks(ctx)
        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)
        rules = load_ignores(args.ignore_file)
        findings, suppressed = apply_ignores(findings, rules)
    except Exception as e:  # unreadable input, network failure, bad ignore file
        print(f"ggufdoctor: {e}", file=sys.stderr)
        return 2

    print(render_human(model, findings, suppressed, coverage, engines))

    if args.json_path:
        payload = build_json(model, findings, suppressed, coverage, engines)
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)

    if args.require_upstream and coverage.upstream not in ("ok",):
        return 1
    return exit_code(findings, args.fail_on)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py tests/test_cli.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/sources.py src/ggufdoctor/cli.py tests/test_sources.py tests/test_cli.py
git commit -m "feat: source resolution and CLI"
```

---

### Task 12: Survey subcommand

**Files:**
- Create: `src/ggufdoctor/survey.py`
- Modify: `src/ggufdoctor/cli.py`
- Test: `tests/test_survey.py`

**Interfaces:**
- Consumes: `HfClient` from Task 7; checks from Tasks 6/8; `Coverage` from Task 1
- Produces: `sample_repos(client, top, per_org) -> list[dict]`; `survey(client, top, per_org) -> dict`; `to_markdown(result) -> str`. CLI gains `ggufdoctor survey --top N --per-org N --out PATH --markdown PATH`.

The aggregate must include `comparable`, `divergent`, `divergent_pct`, `download_weighted_pct`, `publishers_affected`, `publishers_total`, and a `coverage_gaps` breakdown keyed by reason. `per_org` defaults to `2` and appears in the output so the methodology travels with the number.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_survey.py
from ggufdoctor.survey import sample_repos, survey, to_markdown


class FakeClient:
    """Two publishers, three repos; one repo diverges from upstream."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 100},
                {"id": "orgA/two", "downloads": 50},
                {"id": "orgA/three", "downloads": 25},
                {"id": "orgB/one", "downloads": 10}]

    def model_info(self, repo_id):
        tpl = "{% for m in messages %}{{ m['content'] }}{% endfor %}"
        if repo_id == "orgA/one":
            tpl += "DIVERGES"
        return {"gguf": {"architecture": "llama", "chat_template": tpl},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "{% for m in messages %}{{ m['content'] }}{% endfor %}", "ok"


def test_per_org_cap_limits_sample():
    repos = sample_repos(FakeClient(), top=10, per_org=2)
    assert [r["id"] for r in repos] == ["orgA/one", "orgA/two", "orgB/one"]


def test_survey_reports_divergence_and_methodology():
    r = survey(FakeClient(), top=10, per_org=2)
    assert r["aggregate"]["comparable"] == 3
    assert r["aggregate"]["divergent"] == 1
    assert r["aggregate"]["per_org"] == 2
    assert r["aggregate"]["publishers_total"] == 2
    assert r["aggregate"]["publishers_affected"] == 1


def test_download_weighting_uses_downloads():
    r = survey(FakeClient(), top=10, per_org=2)
    # divergent repo has 100 of 160 total downloads across comparable repos
    assert round(r["aggregate"]["download_weighted_pct"], 1) == 62.5


def test_markdown_includes_caveats():
    md = to_markdown(survey(FakeClient(), top=10, per_org=2))
    assert "per-org cap" in md
    assert "coverage" in md.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_survey.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.survey'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/ggufdoctor/hf.py`:

```python
    def list_gguf_models(self, skip: int, limit: int = 100) -> list[dict[str, Any]]:
        url = (f"{API}?filter=gguf&sort=downloads&direction=-1"
               f"&limit={limit}&skip={skip}")
        return json.loads(self._open(url))
```

```python
# src/ggufdoctor/survey.py
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel

COMPARABLE = {"identical", "cosmetic_only", "output_differs"}


def sample_repos(client: Any, top: int, per_org: int) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen: dict[str, int] = defaultdict(int)
    skip = 0
    while len(picked) < top and skip < top * 20:
        batch = client.list_gguf_models(skip=skip, limit=100)
        if not batch:
            break
        for m in batch:
            org = m["id"].split("/")[0]
            if seen[org] >= per_org:
                continue
            seen[org] += 1
            picked.append({"id": m["id"], "downloads": m.get("downloads", 0)})
            if len(picked) >= top:
                break
        skip += 100
    return picked


def _examine(client: Any, repo: dict[str, Any], engine: Any,
             fixtures: list[Any]) -> dict[str, Any]:
    rec = {"id": repo["id"], "org": repo["id"].split("/")[0],
           "downloads": repo["downloads"], "status": None}
    info = client.model_info(repo["id"])
    gg = (info or {}).get("gguf") or {}
    tpl = gg.get("chat_template")
    base = client.base_model_of(info)
    if not base:
        rec["status"] = "no_base_model"
        return rec
    upstream, why = client.upstream_template(base)
    if why != "ok":
        rec["status"] = {"gated": "upstream_gated",
                         "genuinely_absent": "non_chat_model"}.get(
                             why, "upstream_fetch_failed")
        return rec
    if not tpl:
        rec["status"] = "missing_template"
        return rec

    model = GgufModel(source_id=repo["id"], architecture=gg.get("architecture"),
                      chat_template=tpl)
    ctx = CheckContext(model=model, engines=[engine], fixtures=fixtures,
                       upstream_template=upstream, upstream_meta={"coverage": "ok"})
    findings = [f for f in run_reference_checks(ctx) if f.id == "R001"]
    if findings:
        rec["status"] = "output_differs"
        rec["fixtures"] = sorted({f.fixture for f in findings if f.fixture})
    elif tpl == upstream:
        rec["status"] = "identical"
    else:
        rec["status"] = "cosmetic_only"
    return rec


def survey(client: Any, top: int, per_org: int) -> dict[str, Any]:
    engine = Jinja2Engine()
    fixtures = load_fixtures()
    repos = sample_repos(client, top, per_org)
    records = [_examine(client, r, engine, fixtures) for r in repos]

    comparable = [r for r in records if r["status"] in COMPARABLE]
    divergent = [r for r in comparable if r["status"] == "output_differs"]
    dl_total = sum(r["downloads"] for r in comparable) or 1
    dl_div = sum(r["downloads"] for r in divergent)

    return {
        "records": records,
        "aggregate": {
            "sampled": len(records),
            "per_org": per_org,
            "comparable": len(comparable),
            "divergent": len(divergent),
            "divergent_pct": 100 * len(divergent) / len(comparable) if comparable else 0.0,
            "download_weighted_pct": 100 * dl_div / dl_total,
            "publishers_total": len({r["org"] for r in comparable}),
            "publishers_affected": len({r["org"] for r in divergent}),
            "coverage_gaps": dict(Counter(
                r["status"] for r in records if r["status"] not in COMPARABLE)),
        },
    }


def to_markdown(result: dict[str, Any]) -> str:
    a = result["aggregate"]
    lines = [
        "# GGUF chat-template survey",
        "",
        f"- Sampled: **{a['sampled']}** repos (per-org cap: {a['per_org']})",
        f"- Comparable chat models: **{a['comparable']}**",
        f"- Render-different from upstream: **{a['divergent']}** "
        f"({a['divergent_pct']:.1f}%)",
        f"- Download-weighted: **{a['download_weighted_pct']:.1f}%**",
        f"- Publishers affected: **{a['publishers_affected']}** of "
        f"{a['publishers_total']}",
        "",
        "## Coverage gaps",
        "",
        "Repos excluded from the denominator, by reason:",
        "",
    ]
    for reason, n in sorted(a["coverage_gaps"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{reason}`: {n}")
    lines += [
        "",
        "The per-org cap matters: without it the download ranking is dominated by "
        "a small number of publishers and the figure is not representative.",
    ]
    return "\n".join(lines)
```

Modify `src/ggufdoctor/cli.py` — replace the body of `main` with a subcommand dispatch, keeping the single-target path unchanged:

```python
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "survey":
        return _survey_main(argv[1:])
    return _lint_main(argv)


def _survey_main(argv: list[str]) -> int:
    import json as _json

    from ggufdoctor.hf import HfClient
    from ggufdoctor.survey import survey, to_markdown

    p = argparse.ArgumentParser(prog="ggufdoctor survey")
    p.add_argument("--top", type=int, default=200)
    p.add_argument("--per-org", type=int, default=2)
    p.add_argument("--out", metavar="PATH")
    p.add_argument("--markdown", metavar="PATH")
    args = p.parse_args(argv)

    try:
        result = survey(HfClient(), top=args.top, per_org=args.per_org)
    except Exception as e:
        print(f"ggufdoctor survey: {e}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump(result, f, indent=1)
    md = to_markdown(result)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0
```

Rename the existing `main` body to `_lint_main(argv)`, taking `argv` and calling `build_parser().parse_args(argv)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_survey.py tests/test_cli.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/survey.py src/ggufdoctor/hf.py src/ggufdoctor/cli.py tests/test_survey.py
git commit -m "feat: survey subcommand reproducing the ecosystem measurement"
```

---

## Deliberately deferred from this plan

These spec items belong to later plans and are **not** gaps to fix here:

- `--engines` and `--runtime` flags — meaningless with one engine; land with v0.2/v0.3.
- Engine conformance suite (bundled WASM vs real llama.cpp/Ollama) — requires the
  engines it validates; lands with v0.2.
- **Vendored real templates as test data** — the spec calls for these so reference-mode
  tests run offline. v0.1's reference tests use synthetic templates, which is
  sufficient to test the *logic*. Vendoring real ones is a v0.2 task, and should
  reuse templates already captured in `docs/research/2026-08-31-survey-raw.json`.

## Definition of done for v0.1

- [ ] `pytest` green with no network access.
- [ ] `ggufdoctor path/to/model.gguf` runs fully offline and issues zero HTTP requests (asserted by `test_local_resolve_is_offline`).
- [ ] `ggufdoctor org/repo` reports findings plus an explicit coverage line.
- [ ] `ggufdoctor survey --top 400 --per-org 2` reproduces a figure comparable to the 15.1% recorded in `docs/research/`.
- [ ] Every finding id in the spec (`S001`–`S008`, `R001`–`R004`) has at least one test.
