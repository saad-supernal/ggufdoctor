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
