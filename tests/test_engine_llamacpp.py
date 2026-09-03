import sys

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT, Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import ENV_MODULE_PATH, LlamaCppEngine

MESSAGES = {"messages": [{"role": "user", "content": "hi"}]}


def test_engine_identifies_the_pinned_llama_cpp_build():
    e = LlamaCppEngine()
    assert e.available, e.unavailable_reason
    assert e.name == "llama.cpp"
    assert e.version == "b10775"
    assert e.commit == "67a17c17caa95742186f8b1ecadd1b5abd6d5ebb"
    assert e.backend.startswith("wasmtime ")


def test_renders_simple_template():
    r = LlamaCppEngine().render(
        "{% for m in messages %}{{ m['content'] }}{% endfor %}", MESSAGES)
    assert r.ok
    assert r.text == "hi"
    assert r.extra["normalized"] is False
    assert "supports_tools" in r.extra["caps"]


def test_base_context_defaults_match_jinja2_engine():
    # Both engines must see the identical context. BASE_CONTEXT is what
    # Jinja2Engine fills in; the llama.cpp engine must fill in the same.
    tpl = "{{ bos_token }}|{{ eos_token }}|{{ add_generation_prompt }}"
    a = Jinja2Engine().render(tpl, {})
    b = LlamaCppEngine().render(tpl, {})
    assert a.ok and b.ok
    assert a.text == b.text == f"{BASE_CONTEXT['bos_token']}|{BASE_CONTEXT['eos_token']}|True"


def test_parser_failure_is_a_compile_error():
    # `//` (floor division) is valid Jinja but llama.cpp's parser rejects it.
    r = LlamaCppEngine().render("{{ 7 // 2 }}", {})
    assert not r.ok
    assert r.error.startswith("compile:parser:")


def test_author_decline_is_tagged_raise_with_verbatim_message():
    r = LlamaCppEngine().render(
        "{{ raise_exception('Only user and assistant roles are supported!') }}", {})
    assert not r.ok
    assert r.error == "raise:Only user and assistant roles are supported!"


def test_engine_failure_is_tagged_render():
    r = LlamaCppEngine().render("{{ none | length }}", {})
    assert not r.ok
    assert r.error.startswith("render:")
    assert "\n" not in r.error, "render errors are one line for the report"


def test_strftime_now_is_pinned_like_jinja2():
    tpl = "{{ strftime_now('%d %b %Y') }}"
    assert LlamaCppEngine().render(tpl, {}).text == Jinja2Engine().render(tpl, {}).text == "01 Jan 2026"


def test_normaliser_rewrites_typed_content_for_string_only_templates():
    # This template concatenates content as a string, so caps say
    # supports_typed_content=false; llama.cpp joins the parts with "\n".
    tpl = "{% for m in messages %}<{{ m['content'] }}>{% endfor %}"
    ctx = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "Hello"}, {"type": "text", "text": "there"}]}]}
    r = LlamaCppEngine().render(tpl, ctx)
    assert r.ok
    assert r.text == "<Hello\nthere>"
    assert r.extra["normalized"] is True
    assert r.extra["caps"]["supports_typed_content"] is False


def test_missing_module_file_makes_engine_unavailable_not_raising(tmp_path):
    e = LlamaCppEngine(module_path=str(tmp_path / "missing.wasm"))
    assert e.available is False
    assert "missing.wasm" in e.unavailable_reason
    r = e.render("x", {})
    assert not r.ok
    assert r.error.startswith("engine:unavailable:")


def test_env_var_overrides_module_path(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.wasm"
    bad.write_bytes(b"\x00asm\x01\x00\x00\x00garbage")
    monkeypatch.setenv(ENV_MODULE_PATH, str(bad))
    e = LlamaCppEngine()
    assert e.available  # the file exists; compile happens lazily
    r = e.render("x", {})
    assert not r.ok
    assert r.error.startswith("render:wasm:")


def test_wasmtime_import_failure_makes_engine_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "wasmtime", None)  # forces ImportError
    e = LlamaCppEngine()
    assert e.available is False
    assert "wasmtime" in e.unavailable_reason


def test_non_serializable_context_is_a_render_error_not_an_exception():
    r = LlamaCppEngine().render("test", {"messages": [], "junk": {1, 2}})
    assert not r.ok
    assert r.error.startswith("render:")
