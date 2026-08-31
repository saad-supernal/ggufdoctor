from __future__ import annotations

import difflib
import re

from ggufdoctor.models import CheckContext, Finding, Severity

INTENT_COMMENT_RE = re.compile(
    r"\{#.{0,400}?(fix|fixes|patch|patched|modified|corrected).{0,400}?#\}",
    re.I | re.S)


def _diff(upstream: str, gguf: str) -> str:
    return "\n".join(difflib.unified_diff(
        upstream.splitlines(), gguf.splitlines(),
        fromfile="upstream", tofile="gguf", n=1, lineterm=""))


def r002_annotated_patch(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template or ""
    if not INTENT_COMMENT_RE.search(tpl[:800]):
        return []
    return [Finding("R002", Severity.INFO,
                    "divergence is annotated by the publisher as a deliberate fix")]


def r001_output_differs(ctx: CheckContext) -> list[Finding]:
    gguf_tpl, up_tpl = ctx.model.chat_template, ctx.upstream_template
    if not gguf_tpl or not up_tpl:
        return []
    annotated = bool(r002_annotated_patch(ctx))
    severity = Severity.INFO if annotated else Severity.WARN
    engine = ctx.engines[0]
    out: list[Finding] = []
    for fx in ctx.fixtures:
        g = engine.render(gguf_tpl, fx.context)
        u = engine.render(up_tpl, fx.context)
        if not (g.ok and u.ok):
            continue
        if g.text == u.text:
            continue
        out.append(Finding(
            "R001", severity,
            "rendered prompt differs from the upstream source model",
            fixture=fx.name,
            evidence={"diff": _diff(u.text, g.text),
                      "len_delta": len(g.text) - len(u.text)}))
    return out


def r003_upstream_missing(ctx: CheckContext) -> list[Finding]:
    if ctx.upstream_meta.get("coverage") != "not_found":
        return []
    return [Finding("R003", Severity.WARN,
                    "upstream base model no longer exists; provenance is unverifiable")]


def r004_upstream_newer(ctx: CheckContext) -> list[Finding]:
    up = ctx.upstream_meta.get("upstream_modified")
    mine = ctx.upstream_meta.get("gguf_modified")
    if not up or not mine or up <= mine:
        return []
    return [Finding("R004", Severity.INFO,
                    "upstream template changed after this file was published",
                    evidence={"upstream_modified": up, "gguf_modified": mine})]


REFERENCE_CHECKS = [r001_output_differs, r002_annotated_patch,
                    r003_upstream_missing, r004_upstream_newer]


def run_reference_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for check in REFERENCE_CHECKS:
        findings.extend(check(ctx))
    if not any(f.id == "R001" for f in findings):
        findings = [f for f in findings if f.id != "R002"]
    return findings
