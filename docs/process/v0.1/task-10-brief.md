### Task 10: Reporting and exit codes

**Files:**
- Create: `src/ggufdoctor/report/__init__.py`
- Create: `src/ggufdoctor/report/human.py`
- Create: `src/ggufdoctor/report/json_report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Finding`, `Severity`, `SEVERITY_ORDER`, `Coverage`, `GgufModel` from Task 1; `CORPUS_VERSION` from Task 5
- Produces: `render_human(model, findings, suppressed, coverage, engines) -> str`; `build_json(model, findings, suppressed, coverage, engines) -> dict`; `exit_code(findings, fail_on: str) -> int`

`exit_code` returns `1` when any finding's severity is at or above `fail_on`, else `0`. `fail_on="never"` always returns `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.models import Coverage, Finding, GgufModel, Severity
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code

MODEL = GgufModel(source_id="m.gguf", architecture="llama")
COV = Coverage(upstream="gated", families_run=["S"])


def test_exit_code_threshold():
    warn = [Finding("R001", Severity.WARN, "m")]
    err = [Finding("S004", Severity.ERROR, "m")]
    assert exit_code(warn, "error") == 0
    assert exit_code(warn, "warn") == 1
    assert exit_code(err, "error") == 1
    assert exit_code(err, "never") == 0
    assert exit_code([], "info") == 0


def test_json_has_stable_schema_fields():
    d = build_json(MODEL, [Finding("S004", Severity.ERROR, "m")], [], COV,
                   [Jinja2Engine()])
    assert d["schema_version"] == "1"
    assert d["target"]["id"] == "m.gguf"
    assert d["coverage"]["upstream"] == "gated"
    assert d["summary"] == {"error": 1, "warn": 0, "info": 0}
    assert d["engines"][0]["name"] == "jinja2"
    assert d["fixture_corpus_version"] == "1"


def test_human_output_states_coverage_explicitly():
    out = render_human(MODEL, [], [], COV, [Jinja2Engine()])
    assert "gated" in out
    assert "R family skipped" in out or "families run: S" in out


def test_human_output_shows_finding_id_and_fixture():
    f = Finding("R001", Severity.WARN, "differs", fixture="with_tools",
                evidence={"diff": "-a\n+b"})
    out = render_human(MODEL, [f], [], COV, [Jinja2Engine()])
    assert "R001" in out
    assert "with_tools" in out
    assert "+b" in out


def test_human_output_reports_suppressed_count():
    sup = [Finding("R001", Severity.WARN, "m", fixture="user_only")]
    out = render_human(MODEL, [], sup, COV, [Jinja2Engine()])
    assert "1 suppressed" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/report/__init__.py
```

```python
# src/ggufdoctor/report/json_report.py
from __future__ import annotations

import datetime
from typing import Any

from ggufdoctor import __version__
from ggufdoctor.fixtures import CORPUS_VERSION
from ggufdoctor.models import (SEVERITY_ORDER, Coverage, Finding, GgufModel,
                               Severity)

_THRESHOLDS = {"error": Severity.ERROR, "warn": Severity.WARN,
               "info": Severity.INFO}


def exit_code(findings: list[Finding], fail_on: str) -> int:
    if fail_on == "never":
        return 0
    threshold = _THRESHOLDS[fail_on]
    limit = SEVERITY_ORDER[threshold]
    return 1 if any(SEVERITY_ORDER[f.severity] >= limit for f in findings) else 0


def summarize(findings: list[Finding]) -> dict[str, int]:
    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def build_json(model: GgufModel, findings: list[Finding],
               suppressed: list[Finding], coverage: Coverage,
               engines: list[Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "tool_version": __version__,
        "fixture_corpus_version": CORPUS_VERSION,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "target": {"id": model.source_id, "architecture": model.architecture},
        "engines": [{"name": e.name, "version": e.version} for e in engines],
        "coverage": {"upstream": coverage.upstream,
                     "families_run": coverage.families_run},
        "findings": [
            {"id": f.id, "severity": f.severity.value, "message": f.message,
             "fixture": f.fixture, "evidence": f.evidence} for f in findings],
        "suppressed": [
            {"id": f.id, "fixture": f.fixture} for f in suppressed],
        "summary": summarize(findings),
    }
```

```python
# src/ggufdoctor/report/human.py
from __future__ import annotations

from typing import Any

from ggufdoctor.models import Coverage, Finding, GgufModel
from ggufdoctor.report.json_report import summarize

ALL_FAMILIES = ["S", "R"]


def render_human(model: GgufModel, findings: list[Finding],
                 suppressed: list[Finding], coverage: Coverage,
                 engines: list[Any]) -> str:
    lines: list[str] = []
    engine_names = ", ".join(f"{e.name} {e.version}" for e in engines)
    lines.append(f"{model.source_id}  [{model.architecture or 'unknown arch'}]"
                 f"  engines: {engine_names}")
    lines.append("")

    if not findings:
        lines.append("  no findings")
    for f in findings:
        head = f"  {f.id}  {f.severity.value.upper():<5} {f.message}"
        if f.fixture:
            head += f"   [{f.fixture}]"
        lines.append(head)
        diff = f.evidence.get("diff")
        if diff:
            for dl in diff.splitlines()[:12]:
                lines.append(f"        {dl}")
        missing = f.evidence.get("missing")
        if missing:
            lines.append(f"        missing from vocab: {', '.join(missing)}")
        lines.append("")

    counts = summarize(findings)
    skipped = [fam for fam in ALL_FAMILIES if fam not in coverage.families_run]
    tail = (f"{counts['error']} error, {counts['warn']} warn, "
            f"{counts['info']} info")
    if suppressed:
        tail += f", {len(suppressed)} suppressed"
    lines.append(tail)
    lines.append(f"families run: {', '.join(coverage.families_run) or 'none'}"
                 f"   upstream: {coverage.upstream}")
    for fam in skipped:
        lines.append(f"  note: {fam} family skipped")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/report tests/test_report.py
git commit -m "feat: human and JSON reporting with explicit coverage"
```

---

