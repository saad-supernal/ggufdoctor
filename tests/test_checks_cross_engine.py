from ggufdoctor.checks.cross_engine import X_IDS, run_cross_engine_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, RenderResult, Severity


def _ctx(template, engines=None, fixtures=None):
    model = GgufModel(source_id="t", architecture="llama", chat_template=template,
                      tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1,
                      add_bos_token=True)
    return CheckContext(model=model, engines=engines or [Jinja2Engine(), LlamaCppEngine()],
                        fixtures=fixtures or load_fixtures())


def _set(findings):
    return {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}


class FakeEngine:
    def __init__(self, name, outputs):
        self.name, self.version, self._outputs = name, "fake", outputs

    def render(self, template, context):
        out = self._outputs(context)
        return out if isinstance(out, RenderResult) else RenderResult(out, None)


ALL = ("user_only", "system_user", "multiturn", "with_tools", "thinking_unset",
       "thinking_true", "thinking_false", "tool_roundtrip", "typed_content", "no_generation_prompt")


CORE = ALL[:7]
NON_TOOL = ("user_only", "system_user", "multiturn", "thinking_unset", "thinking_true",
            "thinking_false", "typed_content", "no_generation_prompt")
TOOL = ("with_tools", "tool_roundtrip")


def test_identical_engines_produce_no_findings_and_record_agreement():
    core = [f for f in load_fixtures() if f.tier == "core"]
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}<|im_end|>", fixtures=core)
    assert run_cross_engine_checks(ctx) == []
    assert ctx.stats["engines_agreed_fixtures"] == len(CORE)
    assert ctx.checks_not_evaluated == []


def test_x001_output_differs_collapses_across_fixtures_with_a_diff():
    # `{{ none }}` prints "None" under jinja2 and nothing under llama.cpp, on
    # every fixture -- one collapsed X001, not ten.
    ctx = _ctx("{{ none }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    # tool fixtures belong to X005 (same divergence, its own id), the rest to X001
    assert _set(found) == {("X001", Severity.ERROR, NON_TOOL), ("X005", Severity.ERROR, TOOL)}
    f = next(f for f in found if f.id == "X001")
    assert f.evidence["engines"] == ["jinja2", "llama.cpp"]
    assert "-None<|im_start|>" in f.evidence["diff"] and "+<|im_start|>" in f.evidence["diff"]
    assert "broken" not in f.message


def test_x001_explained_by_the_normaliser_is_info():
    # `{{ m.content }}` on typed content: jinja2 prints the Python repr of the
    # list; llama.cpp's caps probe finds the template string-only, joins the
    # parts to text first, and prints "Hello\nthere". A real divergence, but
    # one llama.cpp's compatibility rewrite explains -- INFO, and the message
    # says so. tool_roundtrip (assistant content null) is the plain
    # None-vs-empty divergence with no rewrite involved -> X005 ERROR.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}<|im_end|>")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X001", Severity.INFO, ("typed_content",)),
                           ("X005", Severity.ERROR, ("tool_roundtrip",))}
    info = next(f for f in found if f.id == "X001")
    assert info.evidence["normalized"] is True and "normalis" in info.message


def test_x005_owns_tool_fixtures_and_x001_the_rest():
    ctx = _ctx("{% if tools %}{{ none }}{% endif %}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    assert _set(run_cross_engine_checks(ctx)) == {("X005", Severity.ERROR, TOOL)}


def test_x002_template_that_will_not_load_in_llama_cpp():
    ctx = _ctx("{{ 7 // 2 }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.ERROR, ALL)}
    assert found[0].message.startswith("template will not load in llama.cpp (parser:")
    assert found[0].evidence["failing_engine"] == "llama.cpp"


def test_x002_renders_in_llama_cpp_only_via_normaliser_is_info():
    # String concatenation: jinja2 raises TypeError on typed_content; llama.cpp
    # joins the parts first because caps say the template is string-only.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content if m.content is not none else '' }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.INFO, ("typed_content",))}
    assert found[0].evidence["failing_engine"] == "jinja2"
    assert found[0].evidence["normalized"] is True
    assert "normalis" in found[0].message  # "normaliser" spelled as in the report


def test_x002_renders_in_llama_cpp_only_without_normaliser_is_error():
    # `'x' + none` is a plain engine difference (jinja2 TypeError, llama.cpp "x")
    # on tool_roundtrip (assistant content is null). No normalisation involved.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content }}{% endfor %}")
    found = {(f.id, f.severity, tuple(f.evidence["fixtures"]), f.evidence["failing_engine"],
              f.evidence.get("normalized")) for f in run_cross_engine_checks(ctx)}
    assert ("X002", Severity.ERROR, ("tool_roundtrip",), "jinja2", False) in found
    assert ("X002", Severity.INFO, ("typed_content",), "jinja2", True) in found
    assert len(found) == 2


def test_both_engines_failing_is_not_an_x_finding():
    ctx = _ctx("{{ none | length }}")
    assert run_cross_engine_checks(ctx) == []


def test_author_decline_on_one_side_only_is_x002():
    j2 = FakeEngine("jinja2", lambda c: RenderResult(None, "raise:no system role"))
    llama = FakeEngine("llama.cpp", lambda c: "ok")
    ctx = _ctx("irrelevant", engines=[j2, llama])
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.ERROR, ALL)}
    assert "raise_exception" in found[0].message and "no system role" in found[0].message


def test_x004_whitespace_only_is_warn():
    j2 = FakeEngine("jinja2", lambda c: "a b\n")
    llama = FakeEngine("llama.cpp", lambda c: "a  b")
    ctx = _ctx("irrelevant", engines=[j2, llama])
    assert _set(run_cross_engine_checks(ctx)) == {("X004", Severity.WARN, ALL)}


def test_normaliser_explained_divergence_outranks_whitespace_only():
    # Ruling R7: the *cause* of a divergence outranks its magnitude. A
    # divergence llama.cpp's own message normaliser demonstrably created
    # belongs in the X001 INFO bucket that says so, even when the surviving
    # byte difference is only whitespace -- and whitespace is the common
    # real-world shape of it: a template that walks typed content itself and
    # joins the text parts with no separator, against llama.cpp's "\n" join
    # (five of the ten vendored templates in tests/test_real_templates.py do
    # exactly this). Before R7 the whitespace-only test ran first, so this
    # landed at X004 WARN and the INFO downgrade was unreachable for precisely
    # the overlap it was written for.
    def has_list_content(context):
        return any(isinstance(m.get("content"), list) for m in context["messages"])

    # jinja2 joins the typed-content parts with no separator ("Hello there");
    # on the normaliser's pre-flattened context (content already a string) it
    # renders exactly what llama.cpp rendered, which is what
    # _explained_by_normaliser demands before crediting the rewrite with the
    # whole explanation. Every other fixture agrees byte for byte.
    j2 = FakeEngine("jinja2",
                    lambda c: "Hello there" if has_list_content(c) else "Hello  there")
    llama = FakeEngine("llama.cpp", lambda c: RenderResult(
        "Hello  there", None,
        extra={"normalized": True, "caps": {"supports_typed_content": False}}))
    ctx = _ctx("irrelevant", engines=[j2, llama])
    found = run_cross_engine_checks(ctx)
    # The divergence IS whitespace-only -- assert that, so this test cannot
    # pass by accident on a non-whitespace diff that never reaches the branch
    # under test.
    assert "".join("Hello there".split()) == "".join("Hello  there".split())
    assert _set(found) == {("X001", Severity.INFO, ("typed_content",))}
    assert found[0].evidence["normalized"] is True and "normalis" in found[0].message
    assert ctx.stats["engines_agreed_fixtures"] == len(ALL) - 1


def test_single_engine_records_x_family_as_not_evaluated():
    ctx = _ctx("{{ messages[0].content }}", engines=[Jinja2Engine()])
    assert run_cross_engine_checks(ctx) == []
    assert ctx.checks_not_evaluated == X_IDS
    assert "engines_agreed_fixtures" not in ctx.stats


def test_no_template_is_not_an_x_finding():
    ctx = _ctx(None)
    assert run_cross_engine_checks(ctx) == []
    assert ctx.checks_not_evaluated == []


def test_real_tokens_reach_both_engines():
    seen = {}
    j2 = FakeEngine("jinja2", lambda c: seen.setdefault("j2", c["bos_token"]) and "x")
    llama = FakeEngine("llama.cpp", lambda c: seen.setdefault("llama", c["bos_token"]) and "x")
    run_cross_engine_checks(_ctx("irrelevant", engines=[j2, llama]))
    assert seen == {"j2": "<s>", "llama": "<s>"}


def test_unavailable_engine_records_x_family_as_not_evaluated():
    j2 = FakeEngine("jinja2", lambda c: "ok")
    llama = FakeEngine(
        "llama.cpp",
        lambda c: RenderResult(None, "engine:unavailable: wasmtime not importable: boom"),
    )
    ctx = _ctx("irrelevant", engines=[j2, llama])
    assert run_cross_engine_checks(ctx) == []
    assert ctx.checks_not_evaluated == X_IDS
    assert "engines_agreed_fixtures" not in ctx.stats
