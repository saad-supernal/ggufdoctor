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


def test_file_shorter_than_the_magic_reports_not_a_gguf_file(tmp_path):
    # A source with fewer than 4 bytes can't even be compared against the
    # "GGUF" magic -- the byte-source's read-ahead buffer used to raise its
    # own TruncatedError ("needed 4 bytes at 0") before the magic check ever
    # ran, leaking an internal detail instead of the same clear
    # "missing GGUF magic" a merely-wrong-but-long-enough file gets.
    for blob in (b"", b"G", b"GG", b"GGU"):
        with pytest.raises(NotGgufError, match="missing GGUF magic"):
            read_gguf_file(_write(tmp_path, blob))


def test_tokens_excluded_from_metadata_blob(tmp_path):
    blob = build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.ggml.tokens": ("array_string", ["a"] * 50),
    })
    m = read_gguf_file(_write(tmp_path, blob))
    assert "tokenizer.ggml.tokens" not in m.metadata
    assert len(m.tokens) == 50


def test_round_trips_every_builder_type(tmp_path):
    """Verify all supported builder types survive the round-trip."""
    blob = build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.chat_template": ("string", "test_template"),
        "tokenizer.ggml.tokens": ("array_string", ["tok1", "tok2", "tok3"]),
        "tokenizer.ggml.bos_token_id": ("u32", 42),
        "tokenizer.ggml.eos_token_id": ("u32", 99),
        "tokenizer.ggml.add_bos_token": ("bool", True),
        "test.f32": ("f32", 3.14),
        "test.u64": ("u64", 9876543210),
    })
    m = read_gguf_file(_write(tmp_path, blob))

    # Special mapped fields
    assert m.architecture == "llama"
    assert m.chat_template == "test_template"
    assert m.tokens == ["tok1", "tok2", "tok3"]
    assert m.bos_token_id == 42
    assert m.eos_token_id == 99
    assert m.add_bos_token is True

    # Other types in metadata
    assert "tokenizer.ggml.tokens" not in m.metadata
    assert m.metadata["test.f32"] == pytest.approx(3.14)
    assert m.metadata["test.u64"] == 9876543210
