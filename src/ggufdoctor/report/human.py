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
