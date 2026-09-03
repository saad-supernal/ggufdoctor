"""Bundled WASM engine vs the real llama-server at the same build tag.

Deselected by default (marker `conformance`): it downloads a 10-20 MB binary
and a 1 MB model on first run. Run with:
    .venv/bin/python -m pytest -m conformance tests/conformance -v
"""
import pathlib

import pytest

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from tests.conformance.llama_server import MODEL_BOS, MODEL_EOS, LlamaServer

pytestmark = pytest.mark.conformance
DATA = pathlib.Path(__file__).parent.parent / "data" / "templates"
TEMPLATES = sorted(p for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))

# (template slug, fixture name) -> reason.
#
# Only for llama.cpp behaviour that sits outside the function the bundled engine
# mirrors (common_chat_template_direct_apply_impl) -- never for a rendering
# difference. Every entry names the llama.cpp code it comes from and says what
# the engine therefore cannot predict. A skipped pair is still compared: if it
# starts matching, the entry is stale and the test says so, so this table can
# never quietly outlive its reason.
SKIP: dict[tuple[str, str], str] = {
    ("HauhauCS__Gemma-4-E4B-Uncensored-HauhauCS-Aggressive", "tool_roundtrip"):
        "common_chat_try_specialized_template (common/chat.cpp) sniffs this template as an "
        "outdated Gemma4 one ('<|tool_call>call:' without the OpenAI-Chat-Completions marker) "
        "and runs workaround::convert_tool_responses_gemma4 over the message list, collapsing "
        "assistant(tool_calls) + tool results into one assistant message with a tool_responses "
        "field and JSON-parsing each result's content. That is one of ~10 per-family message "
        "rewrites in chat.cpp's dispatch, none of which direct_apply_impl performs; the bundled "
        "engine mirrors direct_apply_impl only. Real gap, reported: for outdated Gemma4 "
        "templates with a tool round-trip, ggufdoctor renders the pre-workaround prompt.",
}


# common_params_parse (common/arg.cpp) puts preserve_reasoning="true" into every
# llama.cpp CLI tool's default_template_kwargs unless --no-reasoning-preserve is
# given, and direct_apply_impl then expands it into preserve_thinking /
# clear_thinking / truncate_history_thinking / drop_thinking via
# jinja::caps_apply_preserve_reasoning. That default belongs to the CLI layer,
# not to the engine, so the engine reacts to the key but never invents it --
# which means the harness has to hand both sides the same one, exactly as it
# does with bos/eos below. True is what a default llama-server run uses.
PRESERVE_REASONING = True


def _body(fixture):
    body = {"messages": fixture.context["messages"],
            "add_generation_prompt": fixture.context.get("add_generation_prompt", True)}
    if "tools" in fixture.context:
        body["tools"] = fixture.context["tools"]
    kwargs = {"preserve_reasoning": PRESERVE_REASONING}
    if "enable_thinking" in fixture.context:
        kwargs["enable_thinking"] = fixture.context["enable_thinking"]
    body["chat_template_kwargs"] = kwargs
    return body


def _ours(engine, template, fixture):
    ctx = dict(BASE_CONTEXT)
    ctx.update(fixture.context)
    ctx["bos_token"], ctx["eos_token"] = MODEL_BOS, MODEL_EOS
    ctx.setdefault("preserve_reasoning", PRESERVE_REASONING)
    return engine.render(template, ctx)


@pytest.fixture(scope="module")
def engine():
    e = LlamaCppEngine()
    assert e.available, e.unavailable_reason
    return e


@pytest.mark.parametrize("template_path", TEMPLATES, ids=[p.stem for p in TEMPLATES])
def test_bundled_engine_matches_real_llama_server(engine, template_path):
    template = template_path.read_text(encoding="utf-8")
    mismatches = []
    with LlamaServer(template_path) as server:
        for fx in load_fixtures():
            skipped = (template_path.stem, fx.name) in SKIP
            ours = _ours(engine, template, fx)
            try:
                theirs = server.apply_template(_body(fx))
            except Exception as e:  # the server refuses shapes the template declines
                if not ours.ok or skipped:
                    continue  # both sides fail: agreement
                mismatches.append((fx.name, "server error while we rendered", str(e)[:200]))
                continue
            if not ours.ok:
                if not skipped:
                    mismatches.append((fx.name, "we failed while server rendered", ours.error))
                continue
            expect = ours.text
            # llama-server strips the leading BOS when the vocab has add_bos (the tiny
            # model does); our engine deliberately does not (spec amendments §A).
            if expect.startswith(MODEL_BOS) and not theirs.startswith(MODEL_BOS):
                expect = expect[len(MODEL_BOS):]
            if skipped:
                if expect == theirs:
                    mismatches.append((fx.name, "stale SKIP entry: this pair now matches",
                                       "delete it from SKIP"))
                continue
            if expect != theirs:
                mismatches.append((fx.name, "text differs", f"ours={expect[:300]!r}\ntheirs={theirs[:300]!r}"))
    assert not mismatches, "\n".join(f"{n}: {why}\n{detail}" for n, why, detail in mismatches)
