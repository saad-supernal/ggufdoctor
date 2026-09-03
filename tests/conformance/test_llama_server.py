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


# Both sides are built from the fixture context and nothing else. Neither
# function may add a key of its own beyond the tiny model's real bos/eos, which
# llama-server takes from the loaded vocabulary and we therefore have to state:
# a harness that supplies a llama.cpp default to *both* engines cannot see that
# default diverge, which is how the preserve_reasoning fork stayed invisible
# until ruling R11 moved that default into the engine where it belongs.
def _body(fixture):
    body = {"messages": fixture.context["messages"],
            "add_generation_prompt": fixture.context.get("add_generation_prompt", True)}
    if "tools" in fixture.context:
        body["tools"] = fixture.context["tools"]
    if "enable_thinking" in fixture.context:
        body["chat_template_kwargs"] = {"enable_thinking": fixture.context["enable_thinking"]}
    return body


def _ours(engine, template, fixture):
    ctx = dict(BASE_CONTEXT)
    ctx.update(fixture.context)
    ctx["bos_token"], ctx["eos_token"] = MODEL_BOS, MODEL_EOS
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
            # `agree` is decided in every branch, so a skipped pair is judged the
            # same way an unskipped one is: SKIP records a pair that provably
            # *disagrees*, and a skipped pair that has come to agree -- whether by
            # matching text or by both sides now failing together -- is a stale
            # entry the test reports rather than an exemption it keeps honouring.
            ours = _ours(engine, template, fx)
            try:
                theirs = server.apply_template(_body(fx))
            except Exception as e:  # the server refuses shapes the template declines
                agree, why, detail = not ours.ok, "server error while we rendered", str(e)[:200]
            else:
                if not ours.ok:
                    agree, why, detail = False, "we failed while server rendered", ours.error
                else:
                    expect = ours.text
                    # llama-server strips the leading BOS when the vocab has add_bos
                    # (the tiny model does); our engine deliberately does not (spec
                    # amendments §A).
                    if expect.startswith(MODEL_BOS) and not theirs.startswith(MODEL_BOS):
                        expect = expect[len(MODEL_BOS):]
                    agree = expect == theirs
                    why = "text differs"
                    detail = f"ours={expect[:300]!r}\ntheirs={theirs[:300]!r}"
            if skipped:
                if agree:
                    mismatches.append((fx.name, "stale SKIP entry: this pair now agrees",
                                       "delete it from SKIP"))
            elif not agree:
                mismatches.append((fx.name, why, detail))
    assert not mismatches, "\n".join(f"{n}: {why}\n{detail}" for n, why, detail in mismatches)
