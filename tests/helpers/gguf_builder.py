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
