### Task 8: Family R — reference comparison checks

**Files:**
- Create: `src/ggufdoctor/checks/reference.py`
- Test: `tests/test_checks_reference.py`

**Interfaces:**
- Consumes: `CheckContext`, `Finding`, `Severity` from Task 1; `Jinja2Engine` from Task 5
- Produces: `run_reference_checks(ctx: CheckContext) -> list[Finding]`; `r001_output_differs`, `r002_annotated_patch`, `r003_upstream_missing`, `r004_upstream_newer`; `INTENT_COMMENT_RE`

`ctx.upstream_meta` may carry `{"coverage": str, "upstream_modified": str, "gguf_modified": str}`. R002 does not itself report a divergence — it downgrades: when the GGUF template carries an author comment naming a fix, R001's severity becomes INFO and an R002 finding is attached.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checks_reference.py
from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

A = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
B = "{% for m in messages %}{{ m['content'] }}{% endfor %}Y"


def ctx(gguf_tpl, upstream_tpl, meta=None):
    return CheckContext(
        model=GgufModel(source_id="t", architecture="llama", chat_template=gguf_tpl),
        engines=[Jinja2Engine()], fixtures=load_fixtures(),
        upstream_template=upstream_tpl, upstream_meta=meta or {})


def by_id(findings):
    return {f.id: f for f in findings}


def test_r001_flags_differing_output():
    f = by_id(run_reference_checks(ctx(A, B)))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN


def test_r001_silent_when_output_matches():
    assert run_reference_checks(ctx(A, A)) == []


def test_r001_silent_on_cosmetic_source_difference():
    # different source, identical rendered output
    same_output = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
    spaced = "{% for m in messages %}{{   m['content']   }}{% endfor %}X"
    assert run_reference_checks(ctx(spaced, same_output)) == []


def test_r002_downgrades_annotated_intentional_patch():
    annotated = "{# Unsloth chat template fixes #}" + B
    f = by_id(run_reference_checks(ctx(annotated, A)))
    assert "R002" in f
    assert f["R001"].severity == Severity.INFO


def test_r003_reports_dead_upstream():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "not_found"})))
    assert "R003" in f


def test_r003_not_reported_when_gated():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "gated"})))
    assert "R003" not in f


def test_r004_flags_upstream_modified_after_publication():
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-06-01T00:00:00Z",
        "gguf_modified": "2026-01-01T00:00:00Z"})))
    assert "R004" in f
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_checks_reference.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.checks.reference'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/checks/reference.py
from __future__ import annotations

import difflib
import re

from ggufdoctor.models import CheckContext, Finding, Severity

INTENT_COMMENT_RE = re.compile(
    r"\{#.{0,400}?(fix|fixes|patch|patched|modified|corrected).{0,400}?#\}",
    re.I | re.S)


def _diff(upstream: str, gguf: str) -> str:
    return "\n".join(difflib.unified_diff(
        upstream.splitlines(), gguf.splitlines(),
        fromfile="upstream", tofile="gguf", n=1, lineterm=""))


def r002_annotated_patch(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template or ""
    if not INTENT_COMMENT_RE.search(tpl[:800]):
        return []
    return [Finding("R002", Severity.INFO,
                    "divergence is annotated by the publisher as a deliberate fix")]


def r001_output_differs(ctx: CheckContext) -> list[Finding]:
    gguf_tpl, up_tpl = ctx.model.chat_template, ctx.upstream_template
    if not gguf_tpl or not up_tpl:
        return []
    annotated = bool(r002_annotated_patch(ctx))
    severity = Severity.INFO if annotated else Severity.WARN
    engine = ctx.engines[0]
    out: list[Finding] = []
    for fx in ctx.fixtures:
        g = engine.render(gguf_tpl, fx.context)
        u = engine.render(up_tpl, fx.context)
        if not (g.ok and u.ok):
            continue
        if g.text == u.text:
            continue
        out.append(Finding(
            "R001", severity,
            "rendered prompt differs from the upstream source model",
            fixture=fx.name,
            evidence={"diff": _diff(u.text, g.text),
                      "len_delta": len(g.text) - len(u.text)}))
    return out


def r003_upstream_missing(ctx: CheckContext) -> list[Finding]:
    if ctx.upstream_meta.get("coverage") != "not_found":
        return []
    return [Finding("R003", Severity.WARN,
                    "upstream base model no longer exists; provenance is unverifiable")]


def r004_upstream_newer(ctx: CheckContext) -> list[Finding]:
    up = ctx.upstream_meta.get("upstream_modified")
    mine = ctx.upstream_meta.get("gguf_modified")
    if not up or not mine or up <= mine:
        return []
    return [Finding("R004", Severity.INFO,
                    "upstream template changed after this file was published",
                    evidence={"upstream_modified": up, "gguf_modified": mine})]


REFERENCE_CHECKS = [r001_output_differs, r002_annotated_patch,
                    r003_upstream_missing, r004_upstream_newer]


def run_reference_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in REFERENCE_CHECKS:
        findings.extend(check(ctx))
    if not any(f.id == "R001" for f in findings):
        findings = [f for f in findings if f.id != "R002"]
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_checks_reference.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/checks/reference.py tests/test_checks_reference.py
git commit -m "feat: family R reference comparison checks with intent-aware downgrade"
```

---

