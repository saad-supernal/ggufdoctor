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
