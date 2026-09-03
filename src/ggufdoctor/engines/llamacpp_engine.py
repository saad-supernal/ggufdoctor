"""llama.cpp's own chat-template engine (common/jinja), run from a WASM module.

The module is built by engine/build.sh from a pinned llama.cpp commit; see
engine/README.md. It mirrors common_chat_template_direct_apply_impl in
common/chat.cpp (caps probe, message normaliser, that function's own context
handling -- an always-defined `enable_thinking` defaulting to true, an
`add_generation_prompt` key present only when the flag is on, and the
caps_apply_preserve_reasoning / caps_apply_reasoning_effort expansions --
pinned clock) but does not strip a leading BOS -- see the v0.2 spec
amendments, section A. It also supplies the one default llama.cpp's CLI layer
adds above that function, `preserve_reasoning` (common/arg.cpp), so a render
matches a default `llama-server` run rather than a bare library embedding.
The conformance suite (tests/conformance) holds it to byte equality with the
real llama-server at the same build tag.
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

# Every render runs in a bounded store, because the template text comes from
# strangers' repos and `{% for i in range(200000000) %}{% endfor %}` is a
# perfectly valid Jinja template. Once Python has called into the module there
# is no way back out: a Ctrl-C sets a flag that is only checked between Python
# bytecodes, and we are inside one native call for the whole render, so an
# unbounded loop in there hangs the process until it is killed. Fuel makes the
# runtime itself stop, and the resulting trap surfaces through the same
# `render:wasm: ...` path as any other engine failure -- a reported render
# error, never a hang and never a traceback.
#
# Both limits are far above what a real chat template needs. The whole
# vendored corpus renders inside a few million fuel units and a couple of
# megabytes of linear memory, so these are ~1000x and ~100x headroom
# respectively: a template that trips either one is not a template ggufdoctor
# can usefully report on anyway. Raising them is cheap if that is ever wrong;
# the point is that the ceiling exists.
FUEL_BUDGET = 5_000_000_000
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024


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
        # Constructing this engine NEVER raises (spec amendments §A):
        # "unavailable" is a state with a stated reason, so a missing manifest,
        # a broken wasmtime install or an absent dist-info degrades the run to
        # jinja2-only instead of taking the CLI down with a traceback. Every
        # attribute a report or the registry may read is therefore set before
        # anything that can fail.
        self.version: str = "unknown"
        self.commit: str = "unknown"
        self.backend: str | None = None
        self.available = False
        self.unavailable_reason: str | None = None
        self._module_path = module_path or os.environ.get(ENV_MODULE_PATH)
        self._wasm_bytes: bytes | None = None
        self._engine = None
        self._module = None
        self._linker = None

        try:
            manifest = load_manifest()
            self.version = manifest["build_tag"]
            self.commit = manifest["commit"]
        except Exception as e:  # missing/corrupt/incomplete manifest data file
            self.unavailable_reason = f"engine manifest unavailable: {e}"
            return

        try:
            import wasmtime  # noqa: F401  (import check only)
        except Exception as e:  # ImportError, or a broken native library
            self.unavailable_reason = f"wasmtime not importable: {e}"
            return
        try:
            self.backend = f"wasmtime {metadata.version('wasmtime')}"
        except Exception:
            # The import worked, so the runtime is there; only its dist-info is
            # not (a vendored copy, a zipapp, a stripped container image). That
            # is a missing version string, not a missing engine.
            self.backend = "wasmtime"

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
        # Compiled-in fuel accounting; the per-render budget is set on the
        # store in render(). Must be configured here, before the module is
        # compiled, because it changes the generated code.
        cfg.consume_fuel = True
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
        try:
            payload = json.dumps({"template": template, "context": ctx, "normalize": True}).encode("utf-8")
            self._ensure_compiled()
            import wasmtime
            store = wasmtime.Store(self._engine)
            # Bound this render: see FUEL_BUDGET / MEMORY_LIMIT_BYTES. Exceeding
            # either traps, and the except below turns that into a render error.
            # (wasmtime-py 48 has no StoreLimits object -- the limits are set
            # directly on the store, and a negative argument means "leave
            # alone", which is why only memory_size is passed.)
            store.set_fuel(FUEL_BUDGET)
            store.set_limits(memory_size=MEMORY_LIMIT_BYTES)
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
        except Exception as e:  # wasmtime trap, compile failure, corrupt module, context serialization
            return RenderResult(None, f"render:wasm: {type(e).__name__}: {_first_line(str(e))}")

        extra = {"caps": result.get("caps", {}), "normalized": bool(result.get("normalized", False))}
        if result.get("ok"):
            text = result.get("text")
            if not isinstance(text, str):
                return RenderResult(None, "render:wasm: module returned ok without valid text", extra=extra)
            return RenderResult(text, None, extra=extra)
        stage = result.get("stage", "render")
        err = result.get("error", "")
        if stage in ("lexer", "parser"):
            return RenderResult(None, f"compile:{stage}: {_first_line(err)}", extra=extra)
        if stage == "raise":
            return RenderResult(None, f"raise:{err}", extra=extra)
        return RenderResult(None, f"render:{_last_line(err)}", extra=extra)
