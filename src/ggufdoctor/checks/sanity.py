from __future__ import annotations

import re

from ggufdoctor.models import CheckContext, Finding, Severity

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
    r = _primary(ctx).render(tpl, {"messages": [{"role": "user", "content": "x"}]})
    if r.error and r.error.startswith("compile:"):
        return [Finding("S002", Severity.ERROR,
                        "template does not compile under Jinja2",
                        evidence={"error": r.error})]
    return []


def s003_render_error(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    out = []
    for fx in ctx.fixtures:
        r = _primary(ctx).render(tpl, fx.context)
        if r.error and r.error.startswith("render:"):
            out.append(Finding("S003", Severity.ERROR,
                               "template raises while rendering a standard conversation",
                               fixture=fx.name, evidence={"error": r.error}))
    return out


def s004_unknown_special_token(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl or not ctx.model.tokens:
        return []
    vocab = set(ctx.model.tokens)
    missing = sorted({t for t in SPECIAL_TOKEN_RE.findall(tpl) if t not in vocab})
    if not missing:
        return []
    return [Finding("S004", Severity.ERROR,
                    "template emits special tokens absent from this file's vocab; "
                    "they will be silently split into multiple tokens",
                    evidence={"missing": missing})]


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
    if eos not in m.chat_template:
        return [Finding("S005", Severity.WARN,
                        "template never emits the declared EOS token",
                        evidence={"eos_token": eos})]
    return []


def s006_double_bos(ctx: CheckContext) -> list[Finding]:
    m = ctx.model
    if not m.chat_template or not m.add_bos_token:
        return []
    emits_bos = "bos_token" in m.chat_template
    if m.bos_token_id is not None and m.tokens and m.bos_token_id < len(m.tokens):
        emits_bos = emits_bos or (m.tokens[m.bos_token_id] in m.chat_template)
    if not emits_bos:
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
    on = _primary(ctx).render(tpl, {**fx.context, "add_generation_prompt": True})
    off = _primary(ctx).render(tpl, {**fx.context, "add_generation_prompt": False})
    if not (on.ok and off.ok) or on.text != off.text:
        return []
    return [Finding("S007", Severity.WARN,
                    "add_generation_prompt has no effect; the assistant turn is never opened",
                    fixture=fx.name)]


def s008_empty_render(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    out = []
    for fx in ctx.fixtures:
        r = _primary(ctx).render(tpl, fx.context)
        if r.ok and not (r.text or "").strip():
            out.append(Finding("S008", Severity.ERROR,
                               "template renders to empty output",
                               fixture=fx.name))
    return out


SANITY_CHECKS = [
    s001_missing_template, s002_uncompilable, s003_render_error,
    s004_unknown_special_token, s005_eos_mismatch, s006_double_bos,
    s007_generation_prompt_noop, s008_empty_render,
]


def run_sanity_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in SANITY_CHECKS:
        findings.extend(check(ctx))
    return findings
