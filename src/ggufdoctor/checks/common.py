from __future__ import annotations

import difflib
from collections.abc import Callable
from typing import Any

from ggufdoctor.models import CheckContext, Finding, Fixture, GgufModel, RenderResult, Severity

# Per-line budget as well as a line count, for render_diff: a template that
# renders everything on one line (minified templates do) would otherwise put
# an engine's entire output -- unbounded, attacker-influenced text from a
# stranger's repo -- into a JSON report as a single diff line.
DIFF_LINES = 40
DIFF_LINE_CHARS = 400


def is_tool_fixture(fixture: Fixture) -> bool:
    return "tools" in fixture.context


def render_diff(a: str, b: str, from_name: str, to_name: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(),
                                 fromfile=from_name, tofile=to_name, lineterm="", n=1)
    out = [ln if len(ln) <= DIFF_LINE_CHARS else ln[:DIFF_LINE_CHARS] + "…"
           for ln in lines]
    if len(out) > DIFF_LINES:
        out = out[:DIFF_LINES] + [f"... ({len(out) - DIFF_LINES} more diff lines)"]
    return "\n".join(out)


def divergence_signature(a: str, b: str) -> tuple[tuple[str, str, str], ...]:
    """A dedup key describing *what* differs, independent of surrounding
    text that both sides render identically.

    Two fixtures that hit "the same divergence" (e.g. one side prints "None"
    where the other prints nothing, at a fixed spot in the template) do not
    generally render byte-identical *lines* -- fixture corpus messages carry
    a different number/shape of roles, so the line-based unified diff used
    for the human-readable evidence["diff"] differs per fixture even though
    the underlying divergence is the same one. A character-level opcode diff
    isolates just the replaced/deleted/inserted substrings (dropping the
    "equal" spans), which collapses correctly across fixtures that vary only
    in the parts both sides agree on.
    """
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return tuple(
        (tag, a[i1:i2], b[j1:j2])
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    )


def failure_text(r: RenderResult) -> tuple[str, str]:
    """(stage, one-line text) for a failed RenderResult."""
    tag, _, rest = r.error.partition(":")
    rest = rest.strip()
    if tag == "compile":
        stage, _, msg = rest.partition(":")
        return stage.strip() or "compile", msg.strip()
    if tag == "raise":
        return "raise", rest
    return "render", rest


def real_token(m: GgufModel, token_id: int | None) -> str | None:
    """The model's actual string for a special-token id, or None if unknown.

    None covers both "no id declared" and "id out of range for this file's
    vocab" -- either way there is no real string to check against, so
    callers must skip rather than substitute a placeholder.
    """
    if token_id is None or not m.tokens or not (0 <= token_id < len(m.tokens)):
        return None
    return m.tokens[token_id]


def with_real_tokens(ctx: CheckContext, context: dict[str, Any]) -> dict[str, Any]:
    """Merge a render context with the model's real bos/eos token strings.

    Jinja2Engine.render fills in fabricated placeholder bos_token/eos_token
    values (BASE_CONTEXT) when the caller doesn't supply them -- fine for
    checks that only care whether a template compiles, renders, or produces
    output, but any check that inspects *which* tokens show up in the
    rendered text must see the model's real tokens, supplied here, or
    nothing at all. Never let a fabricated placeholder stand in for a real
    token when reasoning about what the template actually emits.
    """
    m = ctx.model
    merged = dict(context)
    bos = real_token(m, m.bos_token_id)
    eos = real_token(m, m.eos_token_id)
    if bos is not None:
        merged["bos_token"] = bos
    if eos is not None:
        merged["eos_token"] = eos
    return merged


def collapse_by_signature(
    check_id: str,
    severity: Severity,
    message: str | Callable[[dict[str, Any]], str],
    results: list[tuple[str, Any, dict[str, Any]]],
) -> list[Finding]:
    """Fold one-finding-per-fixture into one-finding-per-distinct-failure.

    `results` is (fixture_name, signature, extra_evidence) triples gathered
    while looping the fixture corpus. Fixtures that fail for the same reason
    (same signature) collapse into a single Finding naming every affected
    fixture in evidence["fixtures"]; fixtures failing for different reasons
    stay as separate findings. Order follows first occurrence, which follows
    corpus order, so results are deterministic.

    `message` may be a plain string, or a callable that receives the group's
    evidence (including the just-added "fixtures" key) and returns the
    message -- used when the wording needs to quote something from that
    particular group's evidence (see S003's author-declined case).
    """
    order: list[Any] = []
    fixtures_by_sig: dict[Any, list[str]] = {}
    evidence_by_sig: dict[Any, dict[str, Any]] = {}
    for name, sig, extra in results:
        if sig not in fixtures_by_sig:
            fixtures_by_sig[sig] = []
            evidence_by_sig[sig] = extra
            order.append(sig)
        fixtures_by_sig[sig].append(name)
    out = []
    for sig in order:
        evidence = dict(evidence_by_sig[sig])
        evidence["fixtures"] = fixtures_by_sig[sig]
        msg = message(evidence) if callable(message) else message
        out.append(Finding(check_id, severity, msg, evidence=evidence))
    return out
