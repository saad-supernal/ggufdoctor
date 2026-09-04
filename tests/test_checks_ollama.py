from ggufdoctor.checks.ollama_registry import (CUSTOM_CORPUS_REASON, NO_GENERATION_PROMPT_REASON,
                                               OLLAMA_IDS, OLLAMA_SUFFIX, run_ollama_checks)
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

COMMIT = "b79067b0db7417f20108363bc22adb97f35c966a"
# A template the fake index recognises verbatim (distance 0): ChatML that
# honours add_generation_prompt and ignores tools -- the HyperCLOVAX shape.
CHATML = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}<|im_end|>\n{% endfor %}"
          "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")
INDEX = [("chatml", CHATML)]


def _golden_chatml(messages, tools_ignored=True):
    out = "".join(f"<|im_start|>{m['role']}\n{m['content'] or ''}<|im_end|>\n" for m in messages)
    return out + "<|im_start|>assistant\n"


def _goldens(overrides=None, corpus_version="2"):
    per = {}
    for fx in load_fixtures():
        msgs = fx.context["messages"]
        if any(isinstance(m.get("content"), list) for m in msgs):
            per[fx.name] = {"unrepresentable": "json: cannot unmarshal array into Go struct field .context.messages.content of type string"}
        else:
            per[fx.name] = _golden_chatml(msgs)
    per.update(overrides or {})
    return {"ollama_commit": COMMIT, "corpus_version": corpus_version, "renders": {"chatml": per}}


def _ctx(template=CHATML, **kw):
    model = GgufModel(source_id="t", architecture="llama", chat_template=template,
                      tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1)
    return CheckContext(model=model, engines=[Jinja2Engine()], fixtures=load_fixtures(), **kw)


def _set(findings):
    return {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}


def test_suffix_is_the_pinned_literal():
    assert OLLAMA_SUFFIX == (" (Ollama b79067b0, default 'ollama create'; RENDERER/PARSER, "
                             "OLLAMA_GO_TEMPLATE=0 and PreferChatTemplate divert to the Jinja path)")


def test_unrecognised_template_yields_no_findings_but_records_coverage():
    ctx = _ctx("{{ messages[0].content }}" * 40)
    assert run_ollama_checks(ctx, goldens=_goldens(), index=INDEX) == []
    assert ctx.stats["ollama"] == {"pinned_commit": COMMIT, "recognised": False, "template": None,
                                   "distance": None, "confident": None, "not_evaluated": None}
    assert ctx.checks_not_evaluated == []


def test_recognised_and_identical_gives_only_o001_with_exclusions_stated():
    ctx = _ctx()
    found = run_ollama_checks(ctx, goldens=_goldens(), index=INDEX)
    # tool_roundtrip: assistant content is null -> jinja2 prints "None", golden has "" -> X003.
    assert _set(found) == {("X003", Severity.ERROR, ("tool_roundtrip",)), ("O001", Severity.INFO, ())}
    o = found[-1]
    assert o.id == "O001" and o.message.endswith(OLLAMA_SUFFIX)
    assert "recognises this template as chatml (distance 0)" in o.message
    assert "ignores tools" in o.message
    assert o.evidence["not_comparable"] == {
        "no_generation_prompt": NO_GENERATION_PROMPT_REASON,
        "typed_content": "Ollama's api.Message cannot represent this conversation: json: cannot unmarshal array into Go struct field .context.messages.content of type string"}
    assert o.evidence["ignores_tools"] is True and o.evidence["ignores_tools_fixtures"] == []
    assert o.evidence["agreed_fixtures"] == 7 and o.evidence["ollama_commit"] == COMMIT
    assert ctx.stats["ollama"]["recognised"] is True and ctx.stats["ollama"]["template"] == "chatml"
    assert ctx.stats["ollama"]["distance"] == 0 and ctx.stats["ollama"]["confident"] is True
    assert ctx.stats["ollama_agreed_fixtures"] == 7


def test_tools_block_absent_is_coverage_not_divergence():
    tpl = CHATML.replace("{% for m", "{% if tools %}TOOLS:{{ tools | tojson }}\n{% endif %}{% for m", 1)
    ctx = _ctx(tpl)
    found = run_ollama_checks(ctx, goldens=_goldens(), index=[("chatml", tpl)])
    o = next(f for f in found if f.id == "O001")
    assert o.evidence["ignores_tools_fixtures"] == ["with_tools", "tool_roundtrip"] or \
        "with_tools" in o.evidence["ignores_tools_fixtures"]
    assert ("X003", Severity.ERROR, ("with_tools",)) not in _set(found)


def _golden_without_opener(name):
    msgs = next(fx for fx in load_fixtures() if fx.name == name).context["messages"]
    return _golden_chatml(msgs)[: -len("<|im_start|>assistant\n")]


def test_a_real_divergence_is_x003_with_a_labelled_diff():
    # The two overridden goldens differ from jinja2 by the *same* deletion (the
    # assistant opener), so they collapse into one finding -- that is the point
    # of the assertion below. A literal "WRONG" for each would not: the
    # divergence signature carries the replaced text, and each fixture's whole
    # render is different text, so two "WRONG" goldens are two signatures and
    # two findings, testing nothing about collapsing.
    goldens = _goldens({"user_only": _golden_without_opener("user_only"),
                        "multiturn": _golden_without_opener("multiturn")})
    ctx = _ctx()
    found = run_ollama_checks(ctx, goldens=goldens, index=INDEX)
    x = [f for f in found if f.id == "X003" and f.evidence.get("failing_side") is None]
    # Two: this one, plus tool_roundtrip's own "None" vs "" divergence pinned above.
    assert len(x) == 2
    d = next(f for f in x if "user_only" in f.evidence["fixtures"])
    assert set(d.evidence["fixtures"]) == {"user_only", "multiturn"}
    assert d.message.startswith("Ollama would substitute its curated chatml template")
    assert d.message.endswith(OLLAMA_SUFFIX)
    assert d.evidence["diff"].startswith("--- jinja2\n+++ ollama:chatml")
    assert d.evidence["ollama_template"] == "chatml" and d.evidence["ollama_commit"] == COMMIT
    assert "broken" not in d.message


def test_one_sided_failures_name_the_direction_and_both_failing_is_silent():
    raising = "{% if messages|length > 1 %}{{ raise_exception('no') }}{% endif %}" + CHATML
    goldens = _goldens({"user_only": {"error": "template: :1: boom"}, "multiturn": {"error": "boom"}})
    ctx = _ctx(raising)
    found = run_ollama_checks(ctx, goldens=goldens, index=[("chatml", raising)])
    s = _set(found)
    # user_only: jinja2 renders, Ollama errors -> X003 naming Ollama as the failing side.
    assert ("X003", Severity.ERROR, ("user_only",)) in s
    ollama_fail = next(f for f in found if f.evidence.get("failing_side") == "ollama")
    assert "Ollama's curated chatml template fails to render" in ollama_fail.message
    # multiturn: both fail -> not a finding.
    assert not any("multiturn" in f.evidence.get("fixtures", ()) for f in found)
    # system_user and tool_roundtrip: jinja2 raises, Ollama renders -> X003, raise wording.
    j2_fail = [f for f in found if f.evidence.get("failing_side") == "jinja2"]
    assert j2_fail and "takes the template's raise_exception branch" in j2_fail[0].message
    assert all(f.message.endswith(OLLAMA_SUFFIX) for f in found)


def test_custom_corpus_is_not_evaluated():
    ctx = _ctx(custom_corpus=True, corpus_version="custom-1")
    assert run_ollama_checks(ctx, goldens=_goldens(), index=INDEX) == []
    assert ctx.checks_not_evaluated == OLLAMA_IDS
    assert ctx.stats["ollama"]["not_evaluated"] == CUSTOM_CORPUS_REASON
    assert ctx.stats["ollama"]["recognised"] is None


def test_corpus_version_mismatch_is_not_evaluated():
    ctx = _ctx()
    assert run_ollama_checks(ctx, goldens=_goldens(corpus_version="9"), index=INDEX) == []
    assert ctx.checks_not_evaluated == OLLAMA_IDS
    assert "corpus 9" in ctx.stats["ollama"]["not_evaluated"] and "corpus 2" in ctx.stats["ollama"]["not_evaluated"]


def test_low_confidence_band_is_named_in_the_message():
    far = CHATML + "x" * 70     # distance 70: recognised, not confident
    ctx = _ctx(far)
    found = run_ollama_checks(ctx, goldens=_goldens(), index=INDEX)
    o = next(f for f in found if f.id == "O001")
    assert "(distance 70, low confidence: the cutoff is 100)" in o.message
    assert o.evidence["confident"] is False and ctx.stats["ollama"]["confident"] is False


def test_no_template_is_silent():
    ctx = _ctx(None)
    assert run_ollama_checks(ctx, goldens=_goldens(), index=INDEX) == []
    assert "ollama" not in ctx.stats
