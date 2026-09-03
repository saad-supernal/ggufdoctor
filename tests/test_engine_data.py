import hashlib
import json
from importlib import resources


def _data(name):
    return resources.files("ggufdoctor.engine_data").joinpath(name)


def test_manifest_pins_the_engine_build():
    manifest = json.loads(_data("llamacpp-jinja.json").read_text(encoding="utf-8"))
    assert manifest["engine"] == "llama.cpp"
    assert manifest["build_tag"] == "b10775"
    assert manifest["commit"] == "67a17c17caa95742186f8b1ecadd1b5abd6d5ebb"
    assert manifest["wasi_sdk"] == "wasi-sdk-34"
    for key in ("sha256", "size", "built_at"):
        assert key in manifest


def test_module_matches_manifest_and_fits_budget():
    manifest = json.loads(_data("llamacpp-jinja.json").read_text(encoding="utf-8"))
    blob = _data("llamacpp-jinja.wasm").read_bytes()
    assert blob[:4] == b"\x00asm", "not a WebAssembly module"
    assert len(blob) < 1_000_000, f"module is {len(blob)} bytes; budget is 1,000,000"
    assert len(blob) == manifest["size"]
    assert hashlib.sha256(blob).hexdigest() == manifest["sha256"]
