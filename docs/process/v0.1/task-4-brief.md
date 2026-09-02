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

