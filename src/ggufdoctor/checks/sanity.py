from __future__ import annotations

import re
from typing import Any

from ggufdoctor.models import CheckContext, Finding, Fixture, GgufModel, Severity

NON_CHAT_ARCHITECTURES = {
    "bert", "nomic-bert", "jina-bert", "parakeet", "asr", "audiocpp",
    "ced", "whisper", "clip", "t5", "qwen3-tts",
}

SPECIAL_TOKEN_RE = re.compile(r"<\|[^|>\s]{1,60}\|>")


def _primary(ctx: CheckContext):
    return ctx.engines[0]


def _is_chat_arch(ctx: CheckContext) -> bool:
    arch = (ctx.model.architecture or "").lower()
    return arch not in NON_CHAT_ARCHITECTURES


def _real_token(m: GgufModel, token_id: int | None) -> str | None:
    """The model's actual string for a special-token id, or None if unknown.

    None covers both "no id declared" and "id out of range for this file's
    vocab" -- either way there is no real string to check against, so
    callers must skip rather than substitute a placeholder.
    """
    if token_id is None or not m.tokens or not (0 <= token_id < len(m.tokens)):
        return None
    return m.tokens[token_id]


def _with_real_tokens(ctx: CheckContext, context: dict[str, Any]) -> dict[str, Any]:
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
    bos = _real_token(m, m.bos_token_id)
    eos = _real_token(m, m.eos_token_id)
    if bos is not None:
        merged["bos_token"] = bos
    if eos is not None:
        merged["eos_token"] = eos
    return merged


def _render_fixture(ctx: CheckContext, fixture: Fixture):
    return _primary(ctx).render(ctx.model.chat_template, _with_real_tokens(ctx, fixture.context))


def _collapse_by_signature(
    check_id: str,
    severity: Severity,
    message: str,
    results: list[tuple[str, Any, dict[str, Any]]],
) -> list[Finding]:
    """Fold one-finding-per-fixture into one-finding-per-distinct-failure.

    `results` is (fixture_name, signature, extra_evidence) triples gathered
    while looping the fixture corpus. Fixtures that fail for the same reason
    (same signature) collapse into a single Finding naming every affected
    fixture in evidence["fixtures"]; fixtures failing for different reasons
    stay as separate findings. Order follows first occurrence, which follows
    corpus order, so results are deterministic.
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
        out.append(Finding(check_id, severity, message, evidence=evidence))
    return out


def s001_missing_template(ctx: CheckContext) -> list[Finding]:
    if ctx.model.chat_template or not _is_chat_arch(ctx):
        return []
    return [Finding("S001", Severity.ERROR,
                    "chat-capable architecture but no chat template embedded",
                    evidence={"architecture": ctx.model.architecture})]


def s002_uncompilable(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    context = _with_real_tokens(ctx, {"messages": [{"role": "user", "content": "x"}]})
    r = _primary(ctx).render(tpl, context)
    if r.error and r.error.startswith("compile:"):
        return [Finding("S002", Severity.ERROR,
                        "template does not compile under Jinja2",
                        evidence={"error": r.error})]
    return []


def s003_render_error(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    results = []
    for fx in ctx.fixtures:
        r = _render_fixture(ctx, fx)
        if r.error and r.error.startswith("render:"):
            results.append((fx.name, r.error, {"error": r.error}))
    return _collapse_by_signature(
        "S003", Severity.ERROR,
        "template raises while rendering a standard conversation",
        results,
    )


def s004_unknown_special_token(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl or not ctx.model.tokens:
        return []
    vocab = set(ctx.model.tokens)
    candidates = {t for t in SPECIAL_TOKEN_RE.findall(tpl) if t not in vocab}
    if not candidates:
        return []
    confirmed: set[str] = set()
    for fx in ctx.fixtures:
        if confirmed == candidates:
            break
        r = _render_fixture(ctx, fx)
        if not r.ok or not r.text:
            continue
        confirmed.update(t for t in candidates if t not in confirmed and t in r.text)
    if not confirmed:
        return []
    return [Finding("S004", Severity.ERROR,
                    "template emits special tokens absent from this file's vocab; "
                    "they will be silently split into multiple tokens",
                    evidence={"missing": sorted(confirmed)})]


def s005_eos_mismatch(ctx: CheckContext) -> list[Finding]:
    m = ctx.model
    if not m.chat_template or m.eos_token_id is None or not m.tokens:
        return []
    if m.eos_token_id >= len(m.tokens):
        return [Finding("S005", Severity.WARN,
                        "eos_token_id is out of range for this file's vocab",
                        evidence={"eos_token_id": m.eos_token_id,
                                  "vocab_size": len(m.tokens)})]
    eos = m.tokens[m.eos_token_id]
    fx = next((f for f in ctx.fixtures if f.name == "multiturn"), None)
    if fx is None:
        return []
    r = _render_fixture(ctx, fx)
    if not r.ok:
        # S003 already reports the render failure; nothing more to say here.
        return []
    if eos not in (r.text or ""):
        return [Finding("S005", Severity.WARN,
                        "template never emits the declared EOS token",
                        evidence={"eos_token": eos})]
    return []


def s006_double_bos(ctx: CheckContext) -> list[Finding]:
    m = ctx.model
    if not m.chat_template or not m.add_bos_token:
        return []
    bos = _real_token(m, m.bos_token_id)
    if bos is None:
        return []
    fx = next((f for f in ctx.fixtures if f.name == "user_only"), None)
    if fx is None:
        return []
    r = _render_fixture(ctx, fx)
    if not r.ok:
        return []
    if not (r.text or "").startswith(bos):
        return []
    return [Finding("S006", Severity.WARN,
                    "template emits BOS while metadata also adds BOS; "
                    "the prompt will start with a duplicated token",
                    evidence={"add_bos_token": True})]


def s007_generation_prompt_noop(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    fx = next((f for f in ctx.fixtures if f.name == "user_only"), None)
    if fx is None:
        return []
    on = _primary(ctx).render(tpl, _with_real_tokens(ctx, {**fx.context, "add_generation_prompt": True}))
    off = _primary(ctx).render(tpl, _with_real_tokens(ctx, {**fx.context, "add_generation_prompt": False}))
    if not (on.ok and off.ok) or on.text != off.text:
        return []
    return [Finding("S007", Severity.WARN,
                    "add_generation_prompt has no effect; the assistant turn is never opened",
                    fixture=fx.name)]


def s008_empty_render(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    results = []
    for fx in ctx.fixtures:
        r = _render_fixture(ctx, fx)
        if r.ok and not (r.text or "").strip():
            results.append((fx.name, None, {}))
    return _collapse_by_signature(
        "S008", Severity.ERROR, "template renders to empty output", results,
    )


SANITY_CHECKS = [
    s001_missing_template, s002_uncompilable, s003_render_error,
    s004_unknown_special_token, s005_eos_mismatch, s006_double_bos,
    s007_generation_prompt_noop, s008_empty_render,
]


def run_sanity_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(s001_missing_template(ctx))

    s002_findings = s002_uncompilable(ctx)
    findings.extend(s002_findings)

    findings.extend(s003_render_error(ctx))

    # S004 and S006 ask what the template *emits*. A template that S002
    # already flagged as uncompilable has nothing meaningful to emit, so
    # asking it would only produce noise on top of the S002 finding.
    template_compiles = not s002_findings
    if template_compiles:
        findings.extend(s004_unknown_special_token(ctx))

    findings.extend(s005_eos_mismatch(ctx))

    if template_compiles:
        findings.extend(s006_double_bos(ctx))

    findings.extend(s007_generation_prompt_noop(ctx))
    findings.extend(s008_empty_render(ctx))
    return findings
