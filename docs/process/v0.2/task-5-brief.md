### Task 5: Family X — cross-engine checks

**Files:**
- Create: `src/ggufdoctor/checks/common.py`
- Modify: `src/ggufdoctor/checks/sanity.py` (import the shared helpers; keep `_real_token`, `_with_real_tokens`, `_collapse_by_signature` names as aliases so existing imports keep working)
- Modify: `src/ggufdoctor/models.py` (`CheckContext.stats`)
- Create: `src/ggufdoctor/checks/cross_engine.py`
- Test: `tests/test_checks_cross_engine.py`

**Interfaces:**
- Consumes: `Jinja2Engine`, `LlamaCppEngine` (by `.name`), `Fixture.tier`, `RenderResult.extra`.
- Produces: `X_IDS = ["X001", "X002", "X004", "X005"]`; `run_cross_engine_checks(ctx: CheckContext) -> list[Finding]`; `ctx.stats["engines_agreed_fixtures"]: int` (fixtures both engines rendered byte-identically); `is_tool_fixture(fixture) -> bool`; `checks/common.py` exposing `real_token`, `with_real_tokens`, `collapse_by_signature`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_checks_cross_engine.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_checks_cross_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ggufdoctor.checks.cross_engine'`

- [ ] **Step 3: Shared helpers and `CheckContext.stats`**

Create `src/ggufdoctor/checks/common.py` by **moving** `_real_token`, `_with_real_tokens` and `_collapse_by_signature` out of `sanity.py` verbatim (docstrings included), renamed without the underscore: `real_token`, `with_real_tokens`, `collapse_by_signature`. In `sanity.py` replace the three definitions with:

```python
from ggufdoctor.checks.common import collapse_by_signature, real_token, with_real_tokens

# Kept under their old names: tests and the reference checks import these.
_real_token = real_token
_with_real_tokens = with_real_tokens
_collapse_by_signature = collapse_by_signature
```

In `models.py` add to `CheckContext`:

```python
    # Facts a check family wants the report to carry that are not findings
    # (e.g. cross_engine: "engines_agreed_fixtures"). Never used to decide
    # exit codes.
    stats: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: The checks**

```python
# src/ggufdoctor/checks/cross_engine.py
"""Family X: does llama.cpp render this template the way transformers does?

Both engines get the identical context -- BASE_CONTEXT defaults, the fixture,
the model's real bos/eos tokens -- and the raw rendered text is compared.
Neither side strips BOS (spec amendments §A). A fixture both engines fail on
belongs to S003, not here.
"""
from __future__ import annotations

import difflib
from typing import Any

from ggufdoctor.checks.common import collapse_by_signature, with_real_tokens
from ggufdoctor.models import CheckContext, Finding, Fixture, RenderResult, Severity

X_IDS = ["X001", "X002", "X004", "X005"]
JINJA2 = "jinja2"
LLAMACPP = "llama.cpp"
DIFF_LINES = 40


def is_tool_fixture(fixture: Fixture) -> bool:
    return "tools" in fixture.context


def _engine_pair(ctx: CheckContext) -> tuple[Any, Any] | None:
    by_name = {getattr(e, "name", None): e for e in ctx.engines}
    if JINJA2 in by_name and LLAMACPP in by_name:
        return by_name[JINJA2], by_name[LLAMACPP]
    return None


def _whitespace_only(a: str, b: str) -> bool:
    return a != b and "".join(a.split()) == "".join(b.split())


def _diff(a: str, b: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(),
                                 fromfile=JINJA2, tofile=LLAMACPP, lineterm="", n=1)
    out = list(lines)
    if len(out) > DIFF_LINES:
        out = out[:DIFF_LINES] + [f"... ({len(out) - DIFF_LINES} more diff lines)"]
    return "\n".join(out)


def _failure_text(r: RenderResult) -> tuple[str, str]:
    """(stage, one-line text) for a failed RenderResult."""
    tag, _, rest = r.error.partition(":")
    rest = rest.strip()
    if tag == "compile":
        stage, _, msg = rest.partition(":")
        return stage.strip() or "compile", msg.strip()
    if tag == "raise":
        return "raise", rest
    return "render", rest


def _x002(fx: Fixture, ok_engine: str, failing: RenderResult, ok_result: RenderResult,
          failing_engine: str) -> tuple[Severity, str, dict[str, Any]]:
    stage, msg = _failure_text(failing)
    normalized = bool(ok_result.extra.get("normalized")) if ok_engine == LLAMACPP else False
    evidence: dict[str, Any] = {
        "engines": [JINJA2, LLAMACPP], "failing_engine": failing_engine,
        "stage": stage, "error": msg, "normalized": normalized,
    }
    if ok_engine == LLAMACPP and ok_result.extra.get("caps"):
        evidence["llamacpp_caps"] = ok_result.extra["caps"]
    if stage == "raise":
        text = (f"{failing_engine} takes the template's raise_exception branch "
                f"({msg!r}) while {ok_engine} renders")
        return Severity.ERROR, text, evidence
    if failing_engine == LLAMACPP and stage in ("lexer", "parser"):
        return Severity.ERROR, f"template will not load in llama.cpp ({stage}: {msg})", evidence
    if failing_engine == LLAMACPP:
        return Severity.ERROR, f"renders under jinja2 but fails under llama.cpp ({msg})", evidence
    if normalized:
        return (Severity.INFO,
                "renders under llama.cpp only after its message normaliser rewrote the "
                f"input; jinja2 (transformers path) fails on the original ({msg})", evidence)
    return Severity.ERROR, f"renders under llama.cpp but fails under jinja2 (transformers path) ({msg})", evidence


def run_cross_engine_checks(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    pair = _engine_pair(ctx)
    if pair is None:
        ctx.checks_not_evaluated.extend(X_IDS)
        return []
    j2, llama = pair

    differs: list[tuple[str, Any, dict[str, Any]]] = []
    differs_tools: list[tuple[str, Any, dict[str, Any]]] = []
    explained: list[tuple[str, Any, dict[str, Any]]] = []   # llama.cpp rewrote the input first
    whitespace: list[tuple[str, Any, dict[str, Any]]] = []
    one_side: dict[tuple[Severity, str], list[tuple[str, Any, dict[str, Any]]]] = {}
    agreed = 0

    for fx in ctx.fixtures:
        context = with_real_tokens(ctx, fx.context)
        a = j2.render(tpl, context)
        b = llama.render(tpl, context)
        if a.ok and b.ok:
            if a.text == b.text:
                agreed += 1
                continue
            evidence: dict[str, Any] = {"engines": [JINJA2, LLAMACPP], "diff": _diff(a.text, b.text)}
            if b.extra.get("normalized"):
                evidence["normalized"] = True
                evidence["llamacpp_caps"] = b.extra.get("caps", {})
            if _whitespace_only(a.text, b.text):
                whitespace.append((fx.name, evidence["diff"], evidence))
            elif evidence.get("normalized"):
                explained.append((fx.name, evidence["diff"], evidence))
            elif is_tool_fixture(fx):
                differs_tools.append((fx.name, evidence["diff"], evidence))
            else:
                differs.append((fx.name, evidence["diff"], evidence))
            continue
        if not a.ok and not b.ok:
            continue  # S003 owns "fails everywhere"
        if a.ok:
            severity, message, evidence = _x002(fx, JINJA2, b, a, LLAMACPP)
        else:
            severity, message, evidence = _x002(fx, LLAMACPP, a, b, JINJA2)
        one_side.setdefault((severity, message), []).append(
            (fx.name, (evidence["failing_engine"], evidence["stage"], evidence["error"]), evidence))

    ctx.stats["engines_agreed_fixtures"] = agreed

    findings: list[Finding] = []
    findings += collapse_by_signature(
        "X001", Severity.ERROR, "rendered output differs between jinja2 and llama.cpp", differs)
    findings += collapse_by_signature(
        "X005", Severity.ERROR, "tool-calling output differs between jinja2 and llama.cpp", differs_tools)
    findings += collapse_by_signature(
        "X001", Severity.INFO,
        "rendered output differs only because llama.cpp's message normaliser rewrote the "
        "input before rendering (typed content joined to text); jinja2 (transformers path) "
        "rendered the original", explained)
    findings += collapse_by_signature(
        "X004", Severity.WARN, "rendered output differs between jinja2 and llama.cpp by whitespace only",
        whitespace)
    for (severity, message), results in one_side.items():
        findings += collapse_by_signature("X002", severity, message, results)
    return findings
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_checks_cross_engine.py tests/test_checks_sanity.py tests/test_checks_reference.py -v`
Expected: all PASS. If `test_identical_engines_produce_no_findings_and_record_agreement` disagrees on the count, check whether `typed_content` rendered on both engines (`default('', true)` on a list is falsy-safe under both) and adjust the *template in the test* — not the check — so that exactly the intended fixtures agree; then fix the expected number with a comment.

- [ ] **Step 6: Full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add src/ggufdoctor/checks/common.py src/ggufdoctor/checks/sanity.py src/ggufdoctor/checks/cross_engine.py src/ggufdoctor/models.py tests/test_checks_cross_engine.py
git commit -m "feat(checks): family X — cross-engine comparison of jinja2 and llama.cpp

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

