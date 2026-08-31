from __future__ import annotations

import re
from typing import Any

from ggufdoctor.models import Coverage, Finding, GgufModel
from ggufdoctor.report.json_report import summarize

ALL_FAMILIES = ["S", "R"]

# C0 control characters and DEL. This is deliberately broad rather than a
# narrow "just ANSI CSI sequences" pattern: every value sanitised here
# (model id, messages, fixture names, evidence strings) originates inside
# the GGUF file this tool is linting, i.e. untrusted input. Escaping the
# ESC byte alone defangs any ANSI sequence (the printable bytes that would
# follow it, like "[2J", are harmless text once ESC itself is gone), and
# escaping CR/LF/etc. stops a file from forging extra report lines.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _visible(text: str | None) -> str | None:
    """Render control characters and ANSI escapes as visible \\xHH escapes.

    Used only for the human report -- build_json() must NOT run its output
    through this, because json.dumps() already escapes control characters
    correctly and double-escaping would corrupt the machine-readable value.
    """
    if text is None:
        return None
    return _CONTROL_RE.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def _coverage_caveats(coverage: Coverage, skipped_families: list[str]) -> list[str]:
    """Short phrases describing why a clean result might not mean clean.

    Feeds the qualified "no findings (partial: ...)" headline -- each part
    matches the wording used in the coverage detail lines it summarises, so
    skimming the headline and skimming the tail line agree with each other.
    """
    parts: list[str] = []
    if skipped_families:
        label = "family" if len(skipped_families) == 1 else "families"
        parts.append(f"{', '.join(skipped_families)} {label} skipped")
    if coverage.upstream != "ok":
        parts.append(f"upstream {coverage.upstream}")
    if coverage.checks_not_evaluated:
        parts.append(f"{', '.join(coverage.checks_not_evaluated)} not evaluated")
    return parts


def render_human(model: GgufModel, findings: list[Finding],
                 suppressed: list[Finding], coverage: Coverage,
                 engines: list[Any]) -> str:
    lines: list[str] = []
    engine_names = ", ".join(f"{e.name} {e.version}" for e in engines)
    arch_display = _visible(model.architecture) if model.architecture else "unknown arch"
    lines.append(f"{_visible(model.source_id)}  [{arch_display}]"
                 f"  engines: {engine_names}")
    lines.append("")

    skipped = [fam for fam in ALL_FAMILIES if fam not in coverage.families_run]

    if not findings:
        caveats = _coverage_caveats(coverage, skipped)
        if caveats:
            lines.append(f"  no findings (partial: {', '.join(caveats)})")
        else:
            lines.append("  no findings")
    for f in findings:
        head = f"  {f.id}  {f.severity.value.upper():<5} {_visible(f.message)}"
        fixtures_evidence = f.evidence.get("fixtures")
        if f.fixture:
            head += f"   [{_visible(f.fixture)}]"
        elif fixtures_evidence:
            head += f"   [{', '.join(_visible(x) for x in fixtures_evidence)}]"
        lines.append(head)
        diff = f.evidence.get("diff")
        if diff:
            for dl in diff.splitlines()[:12]:
                lines.append(f"        {_visible(dl)}")
        missing = f.evidence.get("missing")
        if missing:
            lines.append(f"        missing from vocab: "
                         f"{', '.join(_visible(x) for x in missing)}")
        lines.append("")

    counts = summarize(findings)
    tail = (f"{counts['error']} error, {counts['warn']} warn, "
            f"{counts['info']} info")
    if suppressed:
        tail += f", {len(suppressed)} suppressed"
    lines.append(tail)
    lines.append(f"families run: {', '.join(coverage.families_run) or 'none'}"
                 f"   upstream: {coverage.upstream}")
    for fam in skipped:
        lines.append(f"  note: {fam} family skipped")
    for check_id in coverage.checks_not_evaluated:
        lines.append(f"  note: {check_id} not evaluated")
    return "\n".join(lines)
