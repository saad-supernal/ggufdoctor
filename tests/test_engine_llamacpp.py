import pathlib
import sys
import time
from importlib import metadata

from ggufdoctor.engines import llamacpp_engine
from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT, Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import ENV_MODULE_PATH, LlamaCppEngine
from ggufdoctor.engines.registry import select_engines
from ggufdoctor.fixtures import load_fixtures

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


def test_missing_manifest_makes_engine_unavailable_not_raising(monkeypatch):
    # Constructing the engine must never raise (spec amendments §A): a wheel
    # whose engine_data lost its manifest degrades the run to jinja2-only with
    # a stated reason, it does not take the CLI down with a traceback.
    def boom():
        raise FileNotFoundError("llamacpp-jinja.json")
    monkeypatch.setattr(llamacpp_engine, "load_manifest", boom)
    e = LlamaCppEngine()
    assert e.available is False
    assert "manifest" in e.unavailable_reason and "llamacpp-jinja.json" in e.unavailable_reason
    r = e.render("x", {})
    assert not r.ok
    assert r.error.startswith("engine:unavailable:")


def test_unknown_wasmtime_dist_version_still_leaves_the_engine_available(monkeypatch):
    # The import worked, so the runtime is there; only its dist-info is not (a
    # vendored copy, a zipapp, a stripped image). A missing version string is
    # not a missing engine.
    def boom(_name):
        raise metadata.PackageNotFoundError("wasmtime")
    monkeypatch.setattr(llamacpp_engine.metadata, "version", boom)
    e = LlamaCppEngine()
    assert e.available is True, e.unavailable_reason
    assert e.backend == "wasmtime"
    assert e.render("hi", {}).text == "hi"


def test_select_engines_degrades_instead_of_raising_when_the_manifest_is_gone(monkeypatch):
    # The registry's default construction path must survive the same failure:
    # `select_engines(None)` records the gap rather than propagating.
    def boom():
        raise FileNotFoundError("llamacpp-jinja.json")
    monkeypatch.setattr(llamacpp_engine, "load_manifest", boom)
    selection = select_engines(None)
    assert [e.name for e in selection.engines] == ["jinja2"]
    assert "manifest" in selection.unavailable["llama.cpp"]


def test_a_runaway_template_traps_on_fuel_instead_of_hanging():
    # Template text comes from strangers' repos, and once Python has called
    # into the module a loop that never ends cannot be interrupted -- Ctrl-C is
    # only checked between Python bytecodes and we are inside one native call.
    # 100M iterations of an empty body allocate nothing, so only the fuel
    # budget can stop it; without one this render never returns.
    start = time.monotonic()
    r = LlamaCppEngine().render(
        "{% for i in range(10000) %}{% for j in range(10000) %}{% endfor %}{% endfor %}", {})
    elapsed = time.monotonic() - start
    assert not r.ok
    assert r.error.startswith("render:wasm:"), r.error
    assert "\n" not in r.error, "render errors are one line for the report"
    assert elapsed < 30, f"fuel budget did not stop the render (took {elapsed:.1f}s)"


def test_a_memory_hungry_template_is_bounded_too():
    # The other half of the bound, and a different mechanism worth pinning: a
    # single huge `range` asks for the whole list at once, so it hits
    # MEMORY_LIMIT_BYTES while growing linear memory long before it burns any
    # fuel (3M units, against the 5e9 budget). memory.grow then returns -1,
    # the module's own allocator throws, and its C++ catch turns that into an
    # ordinary reported render error rather than a trap -- which is why this
    # asserts `render:` and the fuel test above asserts `render:wasm:`. Either
    # way the process comes back.
    start = time.monotonic()
    r = LlamaCppEngine().render("{% for i in range(200000000) %}{% endfor %}", {})
    elapsed = time.monotonic() - start
    assert not r.ok
    assert r.error.startswith("render:"), r.error
    assert elapsed < 30, f"memory limit did not stop the render (took {elapsed:.1f}s)"


def test_the_whole_fixture_corpus_renders_on_the_longest_vendored_template():
    # The limits have to be generous enough for real work: the biggest
    # template this project has, on every fixture, inside one FUEL_BUDGET each.
    # (Measured worst case across all ten vendored templates x ten fixtures:
    # 60.5M fuel units, ~1.2% of the budget.)
    templates = sorted((pathlib.Path(__file__).parent / "data" / "templates").glob("*.jinja"),
                       key=lambda p: p.stat().st_size)
    longest = templates[-1].read_text(encoding="utf-8")
    engine = LlamaCppEngine()
    for fx in load_fixtures():
        r = engine.render(longest, fx.context)
        assert r.ok, f"{templates[-1].name} / {fx.name}: {r.error}"
