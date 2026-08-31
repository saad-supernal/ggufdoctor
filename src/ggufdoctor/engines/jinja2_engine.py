from __future__ import annotations

import datetime
import json
from typing import Any

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

from ggufdoctor.models import RenderResult

PINNED_NOW = datetime.datetime(2026, 1, 1)

BASE_CONTEXT: dict[str, Any] = {
    "bos_token": "<s>",
    "eos_token": "</s>",
    "unk_token": "<unk>",
    "pad_token": "<pad>",
    "add_generation_prompt": True,
}


def _raise_exception(msg: str) -> None:
    raise ValueError(msg)


def _strftime_now(fmt: str) -> str:
    return PINNED_NOW.strftime(fmt)


class Jinja2Engine:
    name = "jinja2"

    def __init__(self) -> None:
        self.version = jinja2.__version__
        self._env = ImmutableSandboxedEnvironment(
            trim_blocks=False, lstrip_blocks=False
        )
        self._env.globals["raise_exception"] = _raise_exception
        self._env.globals["strftime_now"] = _strftime_now
        self._env.filters["tojson"] = lambda o, **kw: json.dumps(o)

    def render(self, template: str, context: dict[str, Any]) -> RenderResult:
        try:
            tpl = self._env.from_string(template)
        except Exception as e:
            return RenderResult(None, f"compile:{type(e).__name__}: {e}")
        ctx = dict(BASE_CONTEXT)
        ctx.update(context)
        try:
            return RenderResult(tpl.render(**ctx), None)
        except Exception as e:
            return RenderResult(None, f"render:{type(e).__name__}: {e}")
