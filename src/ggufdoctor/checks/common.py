from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ggufdoctor.models import CheckContext, Finding, GgufModel, Severity


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
