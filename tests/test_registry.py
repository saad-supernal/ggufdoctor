import pytest

from ggufdoctor.engines import registry


def test_default_selection_is_jinja2_then_llama_cpp():
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2", "llama.cpp"]
    assert sel.unavailable == {}


def test_subset_keeps_jinja2_first_and_declines_are_not_gaps():
    sel = registry.select_engines(["jinja2"])
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {}


def test_unknown_engine_is_an_error():
    with pytest.raises(ValueError, match="unknown engine 'minja'"):
        registry.select_engines(["minja"])


def test_jinja2_cannot_be_dropped():
    with pytest.raises(ValueError, match="jinja2"):
        registry.select_engines(["llama.cpp"])


def test_unavailable_engine_is_recorded_by_default_but_fatal_when_requested(monkeypatch):
    class Broken:
        name = "llama.cpp"
        version = "b0"
        available = False
        unavailable_reason = "wasmtime not importable: boom"
    monkeypatch.setattr(registry, "_construct", lambda name: Broken() if name == "llama.cpp" else registry._construct_default(name))
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {"llama.cpp": "wasmtime not importable: boom"}
    with pytest.raises(ValueError, match="boom"):
        registry.select_engines(["jinja2", "llama.cpp"])
