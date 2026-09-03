### Task 2: `LlamaCppEngine` — the wasmtime host

**Files:**
- Modify: `src/ggufdoctor/models.py` (`RenderResult.extra`)
- Create: `src/ggufdoctor/engines/llamacpp_engine.py`
- Modify: `pyproject.toml` (`dependencies`)
- Test: `tests/test_engine_llamacpp.py`

**Interfaces:**
- Consumes: module ABI and manifest from Task 1; `BASE_CONTEXT` from `ggufdoctor.engines.jinja2_engine`.
- Produces: `class LlamaCppEngine` with `name = "llama.cpp"`, `version: str` (build tag), `commit: str`, `backend: str | None` (e.g. `"wasmtime 48.0.0"`), `available: bool`, `unavailable_reason: str | None`, `render(template, context) -> RenderResult`; `RenderResult.extra: dict[str, Any]` (keys `caps`, `normalized` when the llama.cpp engine produced the result); module constant `ENV_MODULE_PATH = "GGUFDOCTOR_ENGINE_WASM"`.

- [ ] **Step 1: Add the dependency and install**

In `pyproject.toml` set `dependencies = ["jinja2>=3.1", "wasmtime>=48,<49"]`, then:

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -c "import wasmtime; print('wasmtime ok')"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_engine_llamacpp.py
import sys

import pytest

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_llamacpp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ggufdoctor.engines.llamacpp_engine'`

- [ ] **Step 4: `RenderResult.extra`**

In `src/ggufdoctor/models.py`:

```python
@dataclass
class RenderResult:
    text: str | None
    error: str | None
    # Engine-specific facts about how this result was produced, for reports
    # and checks that need to explain a divergence (llama.cpp: "caps" and
    # "normalized"). Empty for engines with nothing to add.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None
```

- [ ] **Step 5: The engine**

```python
# src/ggufdoctor/engines/llamacpp_engine.py
"""llama.cpp's own chat-template engine (common/jinja), run from a WASM module.

The module is built by engine/build.sh from a pinned llama.cpp commit; see
engine/README.md. It mirrors common_chat_template_direct_apply_impl in
common/chat.cpp (caps probe, message normaliser, pinned clock) but does not
strip a leading BOS -- see the v0.2 spec amendments, section A.
"""
from __future__ import annotations

import json
import os
from importlib import metadata, resources
from typing import Any

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT
from ggufdoctor.models import RenderResult

MODULE_NAME = "llamacpp-jinja.wasm"
MANIFEST_NAME = "llamacpp-jinja.json"
ENV_MODULE_PATH = "GGUFDOCTOR_ENGINE_WASM"


def load_manifest() -> dict[str, Any]:
    raw = (resources.files("ggufdoctor.engine_data")
           .joinpath(MANIFEST_NAME).read_text(encoding="utf-8"))
    return json.loads(raw)


def _first_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[0] if lines else text.strip()


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else text.strip()


class LlamaCppEngine:
    name = "llama.cpp"

    def __init__(self, module_path: str | None = None) -> None:
        manifest = load_manifest()
        self.version: str = manifest["build_tag"]
        self.commit: str = manifest["commit"]
        self.backend: str | None = None
        self.available = False
        self.unavailable_reason: str | None = None
        self._module_path = module_path or os.environ.get(ENV_MODULE_PATH)
        self._wasm_bytes: bytes | None = None
        self._engine = None
        self._module = None
        self._linker = None

        try:
            import wasmtime  # noqa: F401  (import check only)
        except Exception as e:  # ImportError, or a broken native library
            self.unavailable_reason = f"wasmtime not importable: {e}"
            return
        self.backend = f"wasmtime {metadata.version('wasmtime')}"

        try:
            self._wasm_bytes = self._read_module()
        except Exception as e:
            self.unavailable_reason = f"engine module unavailable: {e}"
            return
        self.available = True

    def _read_module(self) -> bytes:
        if self._module_path:
            with open(self._module_path, "rb") as f:
                return f.read()
        return resources.files("ggufdoctor.engine_data").joinpath(MODULE_NAME).read_bytes()

    def _ensure_compiled(self) -> None:
        if self._module is not None:
            return
        import wasmtime
        cfg = wasmtime.Config()
        cfg.wasm_exceptions = True
        try:
            # ~120 ms JIT compile per process without this, ~6 ms with it.
            # A read-only or missing cache directory must never stop a render.
            cfg.cache = True
        except Exception:
            pass
        self._engine = wasmtime.Engine(cfg)
        self._module = wasmtime.Module(self._engine, self._wasm_bytes)
        self._linker = wasmtime.Linker(self._engine)
        self._linker.define_wasi()

    def render(self, template: str, context: dict[str, Any]) -> RenderResult:
        if not self.available:
            return RenderResult(None, f"engine:unavailable: {self.unavailable_reason}")
        ctx = dict(BASE_CONTEXT)
        ctx.update(context)
        payload = json.dumps({"template": template, "context": ctx, "normalize": True}).encode("utf-8")
        try:
            self._ensure_compiled()
            import wasmtime
            store = wasmtime.Store(self._engine)
            store.set_wasi(wasmtime.WasiConfig())
            exports = self._linker.instantiate(store, self._module).exports(store)
            exports["_initialize"](store)
            memory = exports["memory"]
            in_ptr = exports["gd_alloc"](store, len(payload))
            memory.write(store, payload, in_ptr)
            out_ptr = exports["gd_render"](store, in_ptr, len(payload))
            out_len = exports["gd_out_len"](store)
            raw = bytes(memory.read(store, out_ptr, out_ptr + out_len))
            exports["gd_free"](store, in_ptr)
            result = json.loads(raw)
        except Exception as e:  # wasmtime trap, compile failure, corrupt module
            return RenderResult(None, f"render:wasm: {type(e).__name__}: {_first_line(str(e))}")

        extra = {"caps": result.get("caps", {}), "normalized": bool(result.get("normalized", False))}
        if result.get("ok"):
            return RenderResult(result["text"], None, extra=extra)
        stage = result.get("stage", "render")
        err = result.get("error", "")
        if stage in ("lexer", "parser"):
            return RenderResult(None, f"compile:{stage}: {_first_line(err)}", extra=extra)
        if stage == "raise":
            return RenderResult(None, f"raise:{err}", extra=extra)
        return RenderResult(None, f"render:{_last_line(err)}", extra=extra)
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_engine_llamacpp.py tests/test_engine_jinja2.py -v`
Expected: all PASS. If `test_wasmtime_import_failure_makes_engine_unavailable` fails because `wasmtime` was already imported by an earlier test, that is fine: `monkeypatch.setitem(sys.modules, "wasmtime", None)` makes `import wasmtime` raise `ImportError` regardless of prior imports.

- [ ] **Step 7: Full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add pyproject.toml src/ggufdoctor/models.py src/ggufdoctor/engines/llamacpp_engine.py tests/test_engine_llamacpp.py
git commit -m "feat(engine): LlamaCppEngine hosts the WASM module through wasmtime

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

