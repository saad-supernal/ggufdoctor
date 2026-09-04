from __future__ import annotations

import re
from typing import Any

from ggufdoctor.models import Coverage, Finding, GgufModel
from ggufdoctor.ollama import pin
from ggufdoctor.report.json_report import summarize

ALL_FAMILIES = ["S", "X", "O", "R", "RT"]

# C0 control characters and DEL. This is deliberately broad rather than a
# narrow "just ANSI CSI sequences" pattern: every value sanitised here
# (model id, messages, fixture names, evidence strings, and the O/RT
# coverage lines -- a not_evaluated reason can quote the llama.cpp engine's
# error text, which carries the template's own raise_exception argument)
# originates inside the GGUF file this tool is linting, i.e. untrusted
# input. Escaping the
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


def _skipped_families(coverage: Coverage) -> list[str]:
    """Families missing from families_run that are a genuine coverage gap.

    Controller ruling R4: a family absent from families_run is reported
    here only when it's missing for a reason beyond the user's own choice
    -- R when the upstream comparison was requested and failed (the same
    gating as the "partial" headline), X when the default engine selection
    couldn't construct an engine (coverage.engines_unavailable is
    non-empty). A user who declined X via --engines, or never asked for R
    via --compare-upstream, sees neither note: that is not a gap. S is
    never a candidate -- it never skips in this architecture -- so this
    does not iterate ALL_FAMILIES; each family's own condition is checked
    directly instead of inferring "missing == skipped" from list membership
    alone, which conflated a decline with a genuine gap before this fix.
    """
    skipped: list[str] = []
    if coverage.engines_unavailable and "X" not in coverage.families_run:
        skipped.append("X")
    if _upstream_gap(coverage.upstream) is not None and "R" not in coverage.families_run:
        skipped.append("R")
    return skipped


def _ollama_line(coverage: Coverage) -> str | None:
    """The one-line summary of the O family's verdict, or None.

    None whenever coverage.ollama itself is None -- the registry check did
    not run at all (no chat template, or an older caller that never wired
    it up). When it did run, exactly one of three sentences fires, chosen
    by the same stats the check recorded on ctx.stats["ollama"]/O001: a
    reason the check declined (not_evaluated), a registry hit (recognised),
    or the common case, a miss (neither).
    """
    o = coverage.ollama
    if o is None:
        return None
    trailer = f" (Ollama {pin().short})"
    if o["not_evaluated"] is not None:
        return f"  ollama: not evaluated — {_visible(o['not_evaluated'])}{trailer}"
    if o["recognised"]:
        low = ", low confidence" if not o["confident"] else ""
        return (f"  ollama: registry recognises this template as {_visible(o['template'])} "
                f"(distance {o['distance']}{low}) — Ollama would substitute its "
                f"curated Go template; see O001/X003{trailer}")
    return ("  ollama: template not in the registry — Ollama renders it with "
            f"llama.cpp's engine (see X001/X002){trailer}")


def _runtime_line(coverage: Coverage) -> str | None:
    """The one-line summary of the RT family's verdict, or None.

    None whenever coverage.runtime is None -- --runtime was not given, so
    no real Ollama was asked anything. When it was, the reason RT could not
    evaluate has to reach the operator here: the "note: RT001 not evaluated"
    line at the foot of the report names the check but not the cause, and
    the cause ("real Ollama failed to render every fixture (...)") is the
    whole of what makes that gap actionable.
    """
    r = coverage.runtime
    if r is None:
        return None
    if r["not_evaluated"] is not None:
        return f"  runtime: not evaluated — {_visible(r['not_evaluated'])}"
    return (f"  runtime: ollama {_visible(r['version'])} agreed with the prediction on "
            f"{r['agreed_fixtures']} of {r['compared_fixtures']} compared fixtures "
            f"via {_visible(r['predicted_path'])}")


def _engine_label(e: Any) -> str:
    label = f"{e.name} {e.version}"
    details = []
    commit = getattr(e, "commit", None)
    if commit:
        details.append(commit[:8])
    backend = getattr(e, "backend", None)
    if backend:
        details.append(backend)
    return f"{label} ({', '.join(details)})" if details else label


def render_human(model: GgufModel, findings: list[Finding],
                 suppressed: list[Finding], coverage: Coverage,
                 engines: list[Any]) -> str:
    lines: list[str] = []
    engine_names = ", ".join(_engine_label(e) for e in engines)
    arch_display = _visible(model.architecture) if model.architecture else "unknown arch"
    lines.append(f"{_visible(model.source_id)}  [{arch_display}]"
                 f"  engines: {engine_names}")
    for name, reason in coverage.engines_unavailable.items():
        lines.append(f"  {name} unavailable — {_visible(reason)}")
    lines.append("")

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

    if "X" in coverage.families_run and coverage.engines_agreed_fixtures is not None:
        lines.append(f"  engines agree: jinja2 and llama.cpp rendered "
                     f"{coverage.engines_agreed_fixtures} fixtures identically")
        lines.append("")

    ollama_line = _ollama_line(coverage)
    if ollama_line is not None:
        lines.append(ollama_line)
        lines.append("")

    runtime_line = _runtime_line(coverage)
    if runtime_line is not None:
        lines.append(runtime_line)
        lines.append("")

    counts = summarize(findings)
    tail = (f"{counts['error']} error, {counts['warn']} warn, "
            f"{counts['info']} info")
    if suppressed:
        tail += f", {len(suppressed)} suppressed"
    lines.append(tail)
    lines.append(f"families run: {', '.join(coverage.families_run) or 'none'}"
                 f"   upstream: {coverage.upstream}")
    for fam in _skipped_families(coverage):
        lines.append(f"  note: {fam} family skipped")
    for check_id in coverage.checks_not_evaluated:
        lines.append(f"  note: {check_id} not evaluated")
    return "\n".join(lines)
