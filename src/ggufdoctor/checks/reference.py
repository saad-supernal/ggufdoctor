from __future__ import annotations

import difflib
import re
from datetime import datetime

from ggufdoctor.checks.sanity import _with_real_tokens
from ggufdoctor.models import CheckContext, Finding, Severity

INTENT_COMMENT_RE = re.compile(
    r"\{#.{0,400}?\b(fix|fixes|patch|patched|modified|corrected)\b.{0,400}?#\}",
    re.I | re.S)

_WHITESPACE_RE = re.compile(r"\s+")


def _diff(upstream: str, gguf: str) -> str:
    return "\n".join(difflib.unified_diff(
        upstream.splitlines(), gguf.splitlines(),
        fromfile="upstream", tofile="gguf", n=1, lineterm=""))


def _is_whitespace_only_diff(a: str, b: str) -> bool:
    """True when `a` and `b` differ only in how much/where whitespace runs.

    Stripping every whitespace run from both sides and comparing what's left
    catches leading/trailing differences as well as an inserted or dropped
    space between two tokens (e.g. TheBloke/Mistral-7B-Instruct-v0.2-GGUF's
    `<s> [INST]` vs upstream's `<s>[INST]`) -- any difference confined to
    whitespace, not just the ends of the whole string.
    """
    return _WHITESPACE_RE.sub("", a) == _WHITESPACE_RE.sub("", b)


def r002_annotated_patch(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template or ""
    if not INTENT_COMMENT_RE.search(tpl[:800]):
        return []
    return [Finding("R002", Severity.INFO,
                    "divergence is annotated by the publisher as a deliberate fix")]


def any_fixture_renders_both_sides(ctx: CheckContext) -> bool:
    """True if at least one fixture renders successfully on both the GGUF's
    own chat_template and ctx.upstream_template.

    r001_output_differs silently skips any fixture where either side fails
    to render, so a repo whose template and upstream both fail on every
    fixture produces zero R001 findings -- indistinguishable, from the
    finding list alone, from two templates that render identically. This
    helper lets a caller (survey._examine) tell the two apart and label the
    former "unrenderable" instead of quietly falling through to
    "cosmetic_only"/"identical".
    """
    gguf_tpl, up_tpl = ctx.model.chat_template, ctx.upstream_template
    if not gguf_tpl or not up_tpl:
        return False
    engine = ctx.engines[0]
    for fx in ctx.fixtures:
        real_context = _with_real_tokens(ctx, fx.context)
        g = engine.render(gguf_tpl, real_context)
        u = engine.render(up_tpl, real_context)
        if g.ok and u.ok:
            return True
    return False


def r001_output_differs(ctx: CheckContext, annotated: bool) -> list[Finding]:
    gguf_tpl, up_tpl = ctx.model.chat_template, ctx.upstream_template
    if not gguf_tpl or not up_tpl:
        return []
    engine = ctx.engines[0]
    out: list[Finding] = []
    for fx in ctx.fixtures:
        # Render both sides with this file's real bos/eos tokens (falling
        # back to the engine's fabricated placeholder only when the file
        # has no real token to offer) -- never let the *same* fabricated
        # placeholder stand in for both sides when the GGUF has simply
        # inlined its real EOS where upstream still writes `{{ eos_token }}`,
        # or the two would "diverge" on every fixture for a reason that has
        # nothing to do with the template.
        real_context = _with_real_tokens(ctx, fx.context)
        g = engine.render(gguf_tpl, real_context)
        u = engine.render(up_tpl, real_context)
        if not (g.ok and u.ok):
            continue
        if g.text == u.text:
            continue
        whitespace_only = _is_whitespace_only_diff(g.text, u.text)
        if whitespace_only:
            # A different claim from a content-changing divergence: still
            # reported, just not conflated with one that changes the
            # prompt's meaning. Never silenced, never called equivalent --
            # the diff evidence below still shows exactly what changed.
            severity = Severity.INFO
            message = ("rendered prompt differs from the upstream source "
                       "model only in whitespace")
        else:
            severity = Severity.INFO if annotated else Severity.WARN
            message = "rendered prompt differs from the upstream source model"
        out.append(Finding(
            "R001", severity, message,
            fixture=fx.name,
            evidence={"diff": _diff(u.text, g.text),
                      "len_delta": len(g.text) - len(u.text),
                      "whitespace_only": whitespace_only}))
    return out


def r003_upstream_missing(ctx: CheckContext) -> list[Finding]:
    if ctx.upstream_meta.get("coverage") != "not_found":
        return []
    return [Finding("R003", Severity.WARN,
                    "upstream base model no longer exists; provenance is unverifiable")]


def r004_upstream_newer(ctx: CheckContext) -> list[Finding]:
    up = ctx.upstream_meta.get("upstream_modified")
    mine = ctx.upstream_meta.get("gguf_modified")
    if not up or not mine:
        return []

    # Normalize and parse ISO 8601 timestamps
    try:
        up_dt = datetime.fromisoformat(up.replace("Z", "+00:00"))
        mine_dt = datetime.fromisoformat(mine.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # Unparseable or invalid timestamps: report nothing
        return []

    if up_dt <= mine_dt:
        return []

    return [Finding("R004", Severity.INFO,
                    "upstream template changed after this file was published",
                    evidence={"upstream_modified": up, "gguf_modified": mine})]


def run_reference_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    # Call r002 once and reuse the result
    annotated = bool(r002_annotated_patch(ctx))
    findings.extend(r001_output_differs(ctx, annotated))
    findings.extend(r002_annotated_patch(ctx))
    findings.extend(r003_upstream_missing(ctx))
    findings.extend(r004_upstream_newer(ctx))
    if not any(f.id == "R001" for f in findings):
        findings = [f for f in findings if f.id != "R002"]
    return findings
