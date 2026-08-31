from __future__ import annotations

import datetime
import json
from typing import Any

import jinja2
import jinja2.ext
import jinja2.nodes
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


def _tojson(
    x: Any,
    ensure_ascii: bool = False,
    indent: int | str | None = None,
    separators: tuple[str, str] | None = None,
    sort_keys: bool = False,
) -> str:
    # Mirrors transformers.utils.chat_template_utils's tojson override: Jinja's
    # built-in tojson filter escapes HTML characters and ignores these kwargs,
    # but real chat templates rely on ensure_ascii=False and on `|tojson(indent=...)`
    # actually indenting (the tool-calling path is where this matters most).
    return json.dumps(
        x,
        ensure_ascii=ensure_ascii,
        indent=indent,
        separators=separators,
        sort_keys=sort_keys,
    )


class GenerationExtension(jinja2.ext.Extension):
    """Minimal support for the `{% generation %}...{% endgeneration %}` tag.

    Real chat templates that mark assistant spans (for
    `return_assistant_tokens_mask`) use this tag; transformers provides it via
    an `AssistantTracker` extension that also records the start/end character
    offsets of each span. v0.1 of ggufdoctor has no consumer for those
    offsets, so this extension deliberately does NOT track span indices -- it
    only parses the tag pair and renders the enclosed body unchanged, which is
    enough to make such templates compile and produce the same rendered text
    a real engine would produce.
    """

    tags = {"generation"}

    def parse(self, parser: jinja2.parser.Parser) -> jinja2.nodes.CallBlock:
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(["name:endgeneration"], drop_needle=True)
        return jinja2.nodes.CallBlock(
            self.call_method("_generation_support"), [], [], body
        ).set_lineno(lineno)

    def _generation_support(self, caller: jinja2.runtime.Macro) -> str:
        return caller()


class Jinja2Engine:
    name = "jinja2"

    def __init__(self) -> None:
        self.version = jinja2.__version__
        self._env = ImmutableSandboxedEnvironment(
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=[jinja2.ext.loopcontrols, GenerationExtension],
        )
        self._env.globals["raise_exception"] = _raise_exception
        self._env.globals["strftime_now"] = _strftime_now
        self._env.filters["tojson"] = _tojson

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
