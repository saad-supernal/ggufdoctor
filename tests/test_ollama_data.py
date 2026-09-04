import hashlib
import json
from importlib import resources

DATA = resources.files("ggufdoctor.ollama_data")


def _text(name):
    return DATA.joinpath(name).read_text(encoding="utf-8")


def test_pin_names_the_ollama_commit():
    pin = json.loads(_text("OLLAMA_PIN"))
    assert pin["commit"] == "b79067b0db7417f20108363bc22adb97f35c966a"
    assert pin["release"] == "v0.33.2"
    for key in ("fetched", "index_last_commit", "index_last_changed"):
        assert pin[key]


def test_index_has_37_entries_and_every_name_has_a_template():
    index = json.loads(_text("index.json"))
    assert len(index) == 37
    assert all(set(e) == {"name", "template"} for e in index)
    names = {e["name"] for e in index}
    assert len(names) == 19
    gotmpls = {p.name[:-len(".gotmpl")] for p in DATA.iterdir() if p.name.endswith(".gotmpl")}
    assert len(gotmpls) == 20
    assert names <= gotmpls
    assert gotmpls - names == {"vicuna"}   # embedded upstream but unreachable from the index


def test_vendored_files_match_the_sha256_manifest():
    manifest = {}
    for line in _text("sources.sha256").splitlines():
        digest, _, name = line.partition("  ")
        manifest[name] = digest
    assert "index.json" in manifest and "chatml.gotmpl" in manifest and "LICENSE-ollama" in manifest
    for name, digest in manifest.items():
        assert hashlib.sha256(DATA.joinpath(name).read_bytes()).hexdigest() == digest, name


def test_licence_is_mit_from_ollama():
    lic = _text("LICENSE-ollama")
    assert lic.startswith("MIT License") and "Ollama" in lic


def test_data_directory_fits_the_size_budget():
    total = sum(p.stat().st_size for p in DATA.iterdir() if p.is_file())
    assert total < 600_000, total
