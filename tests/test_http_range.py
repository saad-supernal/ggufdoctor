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
