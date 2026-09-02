### Task 9: Ignore file

**Files:**
- Create: `src/ggufdoctor/ignorefile.py`
- Test: `tests/test_ignorefile.py`

**Interfaces:**
- Consumes: `Finding` from Task 1
- Produces: `load_ignores(path) -> list[IgnoreRule]`; `IgnoreRule(id, fixture, reason)`; `apply_ignores(findings, rules) -> tuple[list[Finding], list[Finding]]` returning `(kept, suppressed)`

Format is TOML-free line-oriented to avoid a dependency: `ID [fixture] # reason`, blank lines and `#`-leading lines skipped. A rule without a reason is rejected — recording *why* is the point.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ignorefile.py
import pytest

from ggufdoctor.ignorefile import load_ignores, apply_ignores, IgnoreRule
from ggufdoctor.models import Finding, Severity


def test_parses_rule_with_reason(tmp_path):
    p = tmp_path / ".ggufdoctorignore"
    p.write_text("R001 with_tools # upstream is wrong, ours is the fix\n")
    rules = load_ignores(str(p))
    assert rules == [IgnoreRule(id="R001", fixture="with_tools",
                                reason="upstream is wrong, ours is the fix")]


def test_rule_without_fixture_matches_any(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005 # eos handled by runtime\n")
    rules = load_ignores(str(p))
    assert rules[0].fixture is None


def test_rule_without_reason_is_rejected(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005\n")
    with pytest.raises(ValueError, match="reason"):
        load_ignores(str(p))


def test_comments_and_blank_lines_skipped(tmp_path):
    p = tmp_path / "i"
    p.write_text("# header\n\nS005 # why\n")
    assert len(load_ignores(str(p))) == 1


def test_apply_splits_kept_and_suppressed():
    findings = [Finding("R001", Severity.WARN, "m", fixture="with_tools"),
                Finding("R001", Severity.WARN, "m", fixture="user_only"),
                Finding("S004", Severity.ERROR, "m")]
    rules = [IgnoreRule("R001", "with_tools", "known")]
    kept, suppressed = apply_ignores(findings, rules)
    assert len(kept) == 2
    assert len(suppressed) == 1
    assert suppressed[0].fixture == "with_tools"


def test_missing_file_yields_no_rules():
    assert load_ignores("/nonexistent/path") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ignorefile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.ignorefile'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/ignorefile.py
from __future__ import annotations

import os
from dataclasses import dataclass

from ggufdoctor.models import Finding


@dataclass(frozen=True)
class IgnoreRule:
    id: str
    fixture: str | None
    reason: str


def load_ignores(path: str) -> list[IgnoreRule]:
    if not path or not os.path.exists(path):
        return []
    rules: list[IgnoreRule] = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" not in line:
                raise ValueError(
                    f"{path}:{lineno}: ignore rules require a reason after '#'")
            head, reason = line.split("#", 1)
            parts = head.split()
            if not parts:
                raise ValueError(f"{path}:{lineno}: missing rule id")
            rule_id = parts[0]
            fixture = parts[1] if len(parts) > 1 else None
            rules.append(IgnoreRule(rule_id, fixture, reason.strip()))
    return rules


def apply_ignores(findings: list[Finding],
                  rules: list[IgnoreRule]) -> tuple[list[Finding], list[Finding]]:
    kept: list[Finding] = []
    suppressed: list[Finding] = []
    for f in findings:
        matched = any(r.id == f.id and (r.fixture is None or r.fixture == f.fixture)
                      for r in rules)
        (suppressed if matched else kept).append(f)
    return kept, suppressed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ignorefile.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/ignorefile.py tests/test_ignorefile.py
git commit -m "feat: ignore file requiring a recorded reason"
```

---

