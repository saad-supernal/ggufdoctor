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
