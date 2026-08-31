import os
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from ggufdoctor.bytesource import HttpRangeByteSource, HttpSourceError, Cursor
from ggufdoctor.reader import read_gguf
from tests.helpers.gguf_builder import build_gguf


# Build GGUF blob once for all tests
GGUF_BLOB = build_gguf({
    "general.architecture": ("string", "llama"),
    "tokenizer.chat_template": ("string", "{{ 'x' }}"),
    "tokenizer.ggml.tokens": ("array_string", ["a", "b"]),
})


class RangeAwareHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler that properly implements byte-range serving (206)."""

    def do_GET(self):
        # Get the filesystem path
        path = self.translate_path(self.path)

        # Check if it's a regular file
        if not os.path.isfile(path):
            return super().do_GET()

        try:
            with open(path, "rb") as f:
                file_data = f.read()
        except OSError:
            self.send_error(404)
            return

        # Check for Range header
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            try:
                range_spec = range_header[6:]
                start_str, end_str = range_spec.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else len(file_data) - 1

                if 0 <= start <= end < len(file_data):
                    # Valid range
                    data = file_data[start : end + 1]
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(file_data)}")
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            except (ValueError, IndexError):
                pass

        # No range or invalid range, send full file
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(file_data)))
        self.end_headers()
        self.wfile.write(file_data)

    def log_message(self, format, *args):
        # Suppress logging noise
        pass


@pytest.fixture
def served(tmp_path):
    """HTTP server with proper byte-range support."""
    blob = GGUF_BLOB + b"\x00" * 5_000_000
    (tmp_path / "m.gguf").write_bytes(blob)
    handler = partial(RangeAwareHTTPRequestHandler, directory=str(tmp_path))
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/m.gguf"
    srv.shutdown()


@pytest.fixture
def served_no_range(tmp_path):
    """HTTP server without byte-range support (always returns 200)."""
    blob = GGUF_BLOB + b"\x00" * 5_000_000
    (tmp_path / "m.gguf").write_bytes(blob)
    # Use standard handler which doesn't implement ranges
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/m.gguf"
    srv.shutdown()


def test_range_read_returns_requested_bytes(served):
    """Test basic offset-0 range read."""
    src = HttpRangeByteSource(served)
    assert src.read(0, 4) == b"GGUF"


def test_nonzero_offset_returns_correct_bytes(served):
    """Test that nonzero offsets read correct bytes from range-aware server."""
    src = HttpRangeByteSource(served)
    offset = 100
    length = 50
    # Get expected bytes from reconstructed file
    expected = (GGUF_BLOB + b"\x00" * 5_000_000)[offset : offset + length]
    assert src.read(offset, length) == expected


def test_parses_remote_header_without_full_download(served):
    """Test that parsing remote header uses byte ranges and fetches minimal bytes."""
    src = HttpRangeByteSource(served)
    m = read_gguf(src, "remote")
    assert m.architecture == "llama"
    assert m.chat_template == "{{ 'x' }}"
    # With range support, bytes_fetched should be small (just metadata + one chunk)
    assert src.bytes_fetched < 2_000_000, f"bytes_fetched={src.bytes_fetched} should be small with ranges"


def test_nonzero_offset_against_non_range_server_raises_error(served_no_range):
    """Test that nonzero offset against server without range support raises HttpSourceError."""
    src = HttpRangeByteSource(served_no_range)
    with pytest.raises(HttpSourceError, match="server does not support byte ranges"):
        src.read(100, 10)
