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


# Prose for the upstream reasons that mean "the comparison was requested and
# the tool could not deliver it" -- as opposed to "not_requested" (the user
# simply didn't ask) or "ok" (it succeeded). Falls back to a generic
# "upstream {reason}" for any value not listed here.
_UPSTREAM_GAP_TEXT = {
    "gated": "upstream gated — cannot compare without access",
    "not_found": "upstream not found — base model no longer exists",
    "fetch_error": "upstream fetch failed — could not reach the source model",
    "genuinely_absent": "upstream has no chat template to compare against",
    "no_base_model": "no upstream base model declared",
}


def _upstream_gap(upstream: str) -> str | None:
    """Headline/tail text for a genuine coverage gap on the upstream side.

    None for "ok" (nothing to say) and, deliberately, for "not_requested"
    too: declining a comparison the user never asked for is not a gap, and
    must never be phrased like one. Everything else means a comparison was
    attempted and failed -- exactly the case a reader must not be able to
    mistake for "clean" by skimming past a warning that fires on every run.
    """
    if upstream in ("ok", "not_requested"):
        return None
    return _UPSTREAM_GAP_TEXT.get(upstream, f"upstream {upstream}")


def _coverage_caveats(coverage: Coverage) -> list[str]:
    """Short phrases describing why a clean result might not mean clean.

    Feeds the qualified "no findings (partial: ...)" headline. Only ever
    lists genuine gaps: a declined upstream comparison never appears here
    (see _upstream_gap), but an unevaluated check always does -- that's a
    coverage hole regardless of what the user asked for.
    """
    parts: list[str] = []
    gap = _upstream_gap(coverage.upstream)
    if gap:
        parts.append(gap)
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
    upstream_gap = _upstream_gap(coverage.upstream)

    if not findings:
        if upstream_gap is None and not coverage.checks_not_evaluated:
            if coverage.upstream == "not_requested":
                lines.append(
                    "  no findings — local checks only (add --compare-upstream "
                    "<repo> to also check against the source template)")
            else:
                lines.append("  no findings")
        else:
            caveats = _coverage_caveats(coverage)
            lines.append(f"  no findings (partial: {', '.join(caveats)})")
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
    # A family is only ever skipped here because the upstream comparison
    # didn't happen (family R, always -- family S never skips in this
    # architecture), so this note would fire on every default run if it
    # weren't gated the same way the headline is: silent when the user
    # simply didn't ask (upstream_gap is None for "not_requested"/"ok"),
    # voiced when the tool tried and failed.
    if upstream_gap is not None:
        for fam in skipped:
            lines.append(f"  note: {fam} family skipped")
    for check_id in coverage.checks_not_evaluated:
        lines.append(f"  note: {check_id} not evaluated")
    return "\n".join(lines)
