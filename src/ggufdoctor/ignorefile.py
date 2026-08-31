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
                    f"{path}:{lineno}: ignore rules require a reason after '#': {raw.rstrip()}")
            head, reason = line.split("#", 1)
            parts = head.split()
            rule_id = parts[0]
            fixture = parts[1] if len(parts) > 1 else None
            rules.append(IgnoreRule(rule_id, fixture, reason.strip()))
    return rules


def apply_ignores(findings: list[Finding],
                  rules: list[IgnoreRule]) -> tuple[list[Finding], list[Finding]]:
    kept: list[Finding] = []
    suppressed: list[Finding] = []
    for f in findings:
        matched = False
        for r in rules:
            if r.id != f.id:
                continue
            # ID matches - now check fixture
            if r.fixture is None:
                # Un-scoped rule matches everything with this ID
                matched = True
                break
            # Rule is fixture-scoped
            if f.fixture is not None:
                # Finding has explicit fixture - must match exactly
                if r.fixture == f.fixture:
                    matched = True
                    break
            else:
                # Finding has no explicit fixture - check evidence for collapsed case
                fixtures_in_evidence = f.evidence.get("fixtures", [])
                if fixtures_in_evidence == [r.fixture]:
                    # Scoped rule matches collapsed finding only if it lists exactly that one fixture
                    matched = True
                    break
        (suppressed if matched else kept).append(f)
    return kept, suppressed
