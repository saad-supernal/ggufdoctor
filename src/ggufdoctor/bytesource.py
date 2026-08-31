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
                if resp.status == 206:
                    # Range request was honored, partial content
                    data = resp.read(length)
                elif resp.status == 200:
                    # Range request was not honored, got full file
                    if offset != 0:
                        raise HttpSourceError(f"{self.url}: server does not support byte ranges")
                    # At offset 0, full file response is acceptable; cap to requested length
                    data = resp.read(length)
                else:
                    raise HttpSourceError(f"{self.url}: HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            raise HttpSourceError(f"{self.url}: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise HttpSourceError(f"{self.url}: {e.reason}") from e
        self.bytes_fetched += len(data)
        return data
