from __future__ import annotations

from typing import Any

from ggufdoctor.bytesource import ByteSource, Cursor, LocalByteSource, TruncatedError
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
    try:
        magic = c.take(4)
    except TruncatedError:
        # A source shorter than the 4-byte magic can never be a GGUF file --
        # report that plainly rather than letting the read-ahead buffer's
        # "needed 4 bytes at 0" leak out as if it meant something to a user
        # who just pointed the tool at the wrong file.
        raise NotGgufError(f"{source_id}: missing GGUF magic")
    if magic != b"GGUF":
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
