from ggufdoctor.checks.cross_engine import (DIFF_LINE_CHARS, RUNTIME_DEFAULTS,
                                            X_IDS, run_cross_engine_checks)
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, Fixture, GgufModel, RenderResult, Severity


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
    # Named, so the two INFO explanation classes are distinguishable in JSON.
    assert info.evidence["explained_by"] == "normaliser"


# Fixtures whose context does not pin `enable_thinking`, in corpus order --
# i.e. every fixture on which llama.cpp's implicit default can diverge from the
# transformers path. thinking_true and thinking_false are the two that pin it.
NO_THINKING = ("user_only", "system_user", "multiturn", "with_tools", "thinking_unset",
               "tool_roundtrip", "typed_content", "no_generation_prompt")


def test_x001_explained_by_llama_cpps_runtime_defaults_is_info():
    # common_chat_template_direct_apply_impl always defines `enable_thinking`
    # and defaults it to true; transformers defines nothing. So this template's
    # `{% if not enable_thinking %}` branch is taken under jinja2 and skipped
    # under llama.cpp on every fixture that does not pin the variable -- a real
    # divergence, but a runtime default rather than a template defect, so INFO
    # with the fix in the message (rulings R9, R12).
    ctx = _ctx("{% if not enable_thinking %}<think>\n\n</think>\n\n{% endif %}"
               "{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    # One collapsed finding: the inserted reasoning block is the same
    # divergence on all eight, whatever the messages around it look like. Note
    # with_tools and tool_roundtrip are in it rather than in an X005 -- the
    # cause outranks the fixture.
    assert _set(found) == {("X001", Severity.INFO, NO_THINKING)}
    assert found[0].evidence["explained_by"] == "runtime_defaults"
    # Every default is reported, because the fixture context supplies none of
    # them: `defaults` says what the confirming re-render had to add, not which
    # key the template happened to read. Compared against RUNTIME_DEFAULTS
    # itself so the list cannot drift out of step with the source of truth.
    assert found[0].evidence["defaults"] == list(RUNTIME_DEFAULTS)
    assert "pass them explicitly" in found[0].message
    assert ", ".join(RUNTIME_DEFAULTS) in found[0].message
    # thinking_true and thinking_false hand both engines the same value, so
    # they agree and are the only fixtures that do.
    assert ctx.stats["engines_agreed_fixtures"] == 2


def test_runtime_defaults_reports_only_the_keys_it_had_to_add():
    # A context that already pins every preserve_reasoning variable leaves only
    # `enable_thinking` for the re-render to supply, and `defaults` says so --
    # a caller's value is never overridden by a default.
    pinned = {k: v for k, v in RUNTIME_DEFAULTS.items() if k != "enable_thinking"}
    fx = [Fixture(name="pinned_preserve", tier="core",
                  context={"messages": [{"role": "user", "content": "Hi"}],
                           "add_generation_prompt": True, **pinned})]
    ctx = _ctx("{% if not enable_thinking %}<think>{% endif %}"
               "{% for m in messages %}{{ m.role }}{% endfor %}", fixtures=fx)
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X001", Severity.INFO, ("pinned_preserve",))}
    assert found[0].evidence["defaults"] == ["enable_thinking"]
    assert "(enable_thinking)" in found[0].message


def test_runtime_defaults_cover_the_expanded_preserve_reasoning_variables():
    # `preserve_reasoning` is a switch llama.cpp expands into four variables via
    # jinja::caps_apply_preserve_reasoning before rendering, and jinja2 has no
    # such expansion -- so a template reading an expanded name diverges, and
    # only a re-render that supplies the *expansion* can explain it. Handing
    # jinja2 the bare switch would be inert here and this would be an ERROR
    # (ruling R12a).
    ctx = _ctx("{% if preserve_thinking is defined and preserve_thinking %}[keep]{% endif %}"
               "{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    # Every fixture diverges: unlike `enable_thinking`, no fixture in the corpus
    # pins any preserve_reasoning variable, so there is nothing to agree on.
    assert ctx.stats["engines_agreed_fixtures"] == 0
    # Two buckets, not one, and the reason is the point of `defaults`: the text
    # of the divergence is identical everywhere ("[keep]" appearing), but
    # thinking_true and thinking_false pin `enable_thinking`, so the confirming
    # re-render had one fewer key to add there and their finding says so.
    assert _set(found) == {("X001", Severity.INFO, NO_THINKING),
                           ("X001", Severity.INFO, ("thinking_true", "thinking_false"))}
    by_fixtures = {tuple(f.evidence["fixtures"]): f for f in found}
    unpinned = by_fixtures[NO_THINKING]
    pinned = by_fixtures[("thinking_true", "thinking_false")]
    assert unpinned.evidence["explained_by"] == "runtime_defaults"
    assert "preserve_thinking" in unpinned.evidence["defaults"]
    assert unpinned.evidence["defaults"] == list(RUNTIME_DEFAULTS)
    assert "preserve_thinking" in pinned.evidence["defaults"]
    assert "enable_thinking" not in pinned.evidence["defaults"]


def test_x001_explained_by_the_normaliser_and_runtime_defaults_together_is_info():
    # typed_content needs BOTH explanations: jinja2 prints the content list's
    # repr *and* takes the thinking branch, so pre-flattening alone still
    # leaves the `<think>` behind and filling the defaults alone still leaves
    # the parts unjoined. Composing them in one re-render reproduces llama.cpp,
    # so it is INFO rather than an ERROR earned only by having two causes
    # (ruling R10). Every other fixture has just the one cause and lands in the
    # plain runtime_defaults bucket, which is what keeps the two apart here.
    ctx = _ctx("{% if not enable_thinking %}<think>{% endif %}"
               "{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {
        # typed_content needs both causes and tool_roundtrip has a third, so the
        # plain runtime_defaults bucket is the rest.
        ("X001", Severity.INFO,
         tuple(f for f in NO_THINKING if f not in ("typed_content", "tool_roundtrip"))),
        ("X001", Severity.INFO, ("typed_content",)),
        # Unrelated to either explanation: `{{ m.content }}` on tool_roundtrip's
        # `content: null` prints "None" under jinja2 and "" under llama.cpp,
        # which no amount of defaults or flattening reproduces.
        ("X005", Severity.ERROR, ("tool_roundtrip",)),
    }
    composed = next(f for f in found
                    if f.evidence.get("explained_by") == "normaliser+runtime_defaults")
    assert tuple(f for f in composed.evidence["fixtures"]) == ("typed_content",)
    assert composed.evidence["defaults"] == list(RUNTIME_DEFAULTS)
    assert composed.evidence["normalized"] is True
    assert "normaliser" in composed.message and "runtime defaults" in composed.message


def test_runtime_defaults_are_not_the_explanation_for_an_unrelated_divergence():
    # `{{ none }}` differs for reasons no default touches: filling them in
    # cannot reproduce llama.cpp's output, so no INFO downgrade may apply.
    ctx = _ctx("{{ none }}{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert all(f.severity is Severity.ERROR for f in found), _set(found)
    assert all("explained_by" not in f.evidence for f in found)


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
    # The X005 comes free with this template's `is not none` guard: the engine
    # mirrors llama.cpp in materialising a null `content` as "" (every llama.cpp
    # path round-trips messages through common_chat_msg, whose content is a
    # std::string), so on tool_roundtrip the guard passes there and fails under
    # jinja2 -- "x" against nothing. A real divergence for this template, kept
    # here rather than engineered away, so the fixture that exercises the null
    # keeps saying what the two engines do with it.
    assert _set(found) == {("X002", Severity.INFO, ("typed_content",)),
                           ("X005", Severity.ERROR, ("tool_roundtrip",))}
    x002 = next(f for f in found if f.id == "X002")
    assert x002.evidence["failing_engine"] == "jinja2"
    assert x002.evidence["normalized"] is True
    assert "normalis" in x002.message  # "normaliser" spelled as in the report


def test_x002_renders_in_llama_cpp_only_via_normaliser_and_defaults_is_info():
    # The X002 shape of ruling R10, and what ruling R13 fixed: two causes, and
    # jinja2 fails outright on the original input rather than limping through
    # it. Same template shape as the composed X001 test above, but with `'x' +
    # m.content` in place of `{{ m.content }}` so typed content raises a
    # TypeError under jinja2 instead of printing a list repr.
    #
    # On typed_content llama.cpp renders (its normaliser joined the parts, and
    # its `enable_thinking` default skips the `<think>`) while jinja2 raises.
    # Neither cause explains that alone -- pre-flattening leaves jinja2's
    # `<think>` behind, filling the defaults leaves the `+` looking at a list
    # and still raising -- so before R13, which tried only the normaliser rung
    # here, this was an ERROR earned purely by having two causes and by which
    # engine happened to raise.
    ctx = _ctx("{% if not enable_thinking %}<think>{% endif %}"
               "{% for m in messages %}<|{{ m.role }}|>"
               "{{ 'x' + m.content if m.content is not none else '' }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {
        # The single-cause fixtures: jinja2 emits the `<think>` llama.cpp's
        # default suppresses, and nothing else differs.
        ("X001", Severity.INFO,
         tuple(f for f in NO_THINKING if f not in ("typed_content", "tool_roundtrip"))),
        ("X002", Severity.INFO, ("typed_content",)),
        # tool_roundtrip has a third cause on top: the engine materialises the
        # assistant's null `content` as "" (as every llama.cpp path does), so
        # the `is not none` guard passes there and fails under jinja2 -- "x"
        # against nothing, which no default or flatten reproduces.
        ("X005", Severity.ERROR, ("tool_roundtrip",)),
    }
    x002 = next(f for f in found if f.id == "X002")
    assert x002.evidence["failing_engine"] == "jinja2"
    assert x002.evidence["explained_by"] == "normaliser+runtime_defaults"
    assert x002.evidence["normalized"] is True
    assert x002.evidence["defaults"] == list(RUNTIME_DEFAULTS)
    assert "normalis" in x002.message and "runtime defaults" in x002.message
    # The one-sided half of the fact is still stated: jinja2 does not merely
    # differ here, it refuses the original input.
    assert "fails on the original" in x002.message
    assert ctx.stats["engines_agreed_fixtures"] == 2  # thinking_true, thinking_false


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


def test_diff_evidence_is_bounded_per_line_not_just_per_line_count():
    # A minified template renders everything on one line, so the 40-line cap
    # bounds nothing: without a per-line budget a single diff line would carry
    # both engines' entire output -- unbounded text from a stranger's repo --
    # into the JSON report.
    j2 = FakeEngine("jinja2", lambda c: "a" * 100_000)
    llama = FakeEngine("llama.cpp", lambda c: "b" * 100_000)
    ctx = _ctx("irrelevant", engines=[j2, llama])
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X001", Severity.ERROR, NON_TOOL), ("X005", Severity.ERROR, TOOL)}
    for f in found:
        for line in f.evidence["diff"].splitlines():
            assert len(line) <= DIFF_LINE_CHARS + 1, len(line)  # +1 for the "…" marker
    assert "…" in found[0].evidence["diff"]


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
