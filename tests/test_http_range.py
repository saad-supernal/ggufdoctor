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
    """HTTP handler that properly implements byte-range serving (206).

    Instruments each request with Range header and bytes written for testing.
    """

    # Class attribute to store request records: list of dicts with 'range_header' and 'bytes_written'
    request_log = []

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

        # Record the Range header (or None)
        range_header = self.headers.get("Range")

        # Check for Range header
        if range_header and range_header.startswith("bytes="):
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
                    # Log this request
                    self.request_log.append({
                        "range_header": range_header,
                        "bytes_written": len(data),
                        "status": 206,
                    })
                    return
            except (ValueError, IndexError):
                pass

        # No range or invalid range, send full file
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(file_data)))
        self.end_headers()
        self.wfile.write(file_data)
        # Log this request
        self.request_log.append({
            "range_header": range_header,
            "bytes_written": len(file_data),
            "status": 200,
        })

    def log_message(self, format, *args):
        # Suppress logging noise
        pass


@pytest.fixture
def served(tmp_path):
    """HTTP server with proper byte-range support."""
    blob = GGUF_BLOB + b"\x00" * 5_000_000
    (tmp_path / "m.gguf").write_bytes(blob)
    # Reset request log for this fixture
    RangeAwareHTTPRequestHandler.request_log = []
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
    """Test that parsing remote header uses byte ranges and fetches minimal bytes.

    Verifies server-side metrics to ensure the client actually sent Range headers
    and the server sent partial content (206), not full file (200).
    """
    src = HttpRangeByteSource(served)
    m = read_gguf(src, "remote")
    assert m.architecture == "llama"
    assert m.chat_template == "{{ 'x' }}"

    # Verify server-side: all requests had Range headers
    assert len(RangeAwareHTTPRequestHandler.request_log) > 0, "server should have received requests"
    for req in RangeAwareHTTPRequestHandler.request_log:
        assert req["range_header"] is not None, "all requests must include Range header"
        assert req["status"] == 206, "all responses must be 206 Partial Content"

    # Verify server sent much less than the full file (~5.2 MB)
    total_bytes_sent = sum(req["bytes_written"] for req in RangeAwareHTTPRequestHandler.request_log)
    assert total_bytes_sent < 2_000_000, (
        f"server sent {total_bytes_sent} bytes (should be << 5.2MB), "
        f"not using ranges properly"
    )


def test_nonzero_offset_against_non_range_server_raises_error(served_no_range):
    """Test that nonzero offset against server without range support raises HttpSourceError."""
    src = HttpRangeByteSource(served_no_range)
    with pytest.raises(HttpSourceError, match="server does not support byte ranges"):
        src.read(100, 10)
