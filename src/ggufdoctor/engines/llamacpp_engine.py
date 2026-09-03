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
