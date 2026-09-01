from __future__ import annotations

import re
from collections.abc import Callable
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
    failures: list[tuple[str, Any, dict[str, Any]]] = []
    declines: list[tuple[str, Any, dict[str, Any]]] = []
    for fx in ctx.fixtures:
        r = _render_fixture(ctx, fx)
        if not r.error:
            continue
        if r.error.startswith("render:"):
            failures.append((fx.name, r.error, {"error": r.error}))
        elif r.error.startswith("raise:"):
            # The template itself called raise_exception(...) -- this is the
            # author deliberately declining this conversation shape (e.g.
            # Mistral/Llama-2 rejecting a system role), not an engine
            # failure. See jinja2_engine.AuthorDeclinedRender.
            author_message = r.error[len("raise:"):]
            declines.append((fx.name, r.error, {"error": r.error,
                                                 "author_message": author_message}))
    findings = _collapse_by_signature(
        "S003", Severity.ERROR,
        "template raises while rendering a standard conversation",
        failures,
    )
    findings.extend(_collapse_by_signature(
        "S003", Severity.INFO,
        lambda evidence: (
            "template author deliberately declines this conversation shape "
            f"(raise_exception: {evidence['author_message']!r})"
        ),
        declines,
    ))
    return findings


def s004_unknown_special_token(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    if not ctx.model.tokens:
        # No vocab to check emitted special tokens against at all -- this
        # check never got to run, which is a coverage gap, not a clean pass.
        ctx.checks_not_evaluated.append("S004")
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
    if not m.chat_template:
        return []
    if m.eos_token_id is None or not m.tokens:
        # No declared eos id, or no vocab to resolve it against: the
        # emits-declared-EOS comparison has nothing to compare, so it never
        # ran. Record that as a coverage gap rather than staying silent.
        ctx.checks_not_evaluated.append("S005")
        return []
    if not (0 <= m.eos_token_id < len(m.tokens)):
        # The id itself is bad metadata, worth flagging on its own -- but
        # it also means the deeper "does the template emit EOS" comparison
        # below has no real token to look for, so it didn't evaluate either.
        ctx.checks_not_evaluated.append("S005")
        return [Finding("S005", Severity.WARN,
                        "eos_token_id is out of range for this file's vocab",
                        evidence={"eos_token_id": m.eos_token_id,
                                  "vocab_size": len(m.tokens)})]
    eos = m.tokens[m.eos_token_id]
    fx = next((f for f in ctx.fixtures if f.name == "multiturn"), None)
    if fx is None:
        # A custom --fixtures corpus that doesn't include "multiturn" gives
        # this check nothing to render, so it never evaluated.
        ctx.checks_not_evaluated.append("S005")
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
    if not m.chat_template:
        return []
    if m.add_bos_token is None:
        # We don't know whether the tokenizer itself adds a BOS on top of
        # whatever the template renders -- add_bos_token is genuinely
        # missing from this file's metadata (e.g. a remote org/repo target
        # with no vocab at all), so the check cannot even tell whether it
        # applies. That's a coverage gap, not a clean pass.
        ctx.checks_not_evaluated.append("S006")
        return []
    if not m.add_bos_token:
        # Metadata confidently says the tokenizer does not add its own BOS,
        # so there is no double-BOS risk regardless of the template -- a
        # genuine no-op, not a coverage gap.
        return []
    bos = _real_token(m, m.bos_token_id)
    if bos is None:
        # add_bos_token asked for this check to matter, but there is no
        # real bos string to look for (missing or out-of-range id, or no
        # vocab) -- the check never got to evaluate anything.
        ctx.checks_not_evaluated.append("S006")
        return []
    fx = next((f for f in ctx.fixtures if f.name == "user_only"), None)
    if fx is None:
        # A custom --fixtures corpus that doesn't include "user_only" gives
        # this check nothing to render, so it never evaluated.
        ctx.checks_not_evaluated.append("S006")
        return []
    r = _render_fixture(ctx, fx)
    if not r.ok:
        return []
    if not (r.text or "").startswith(bos):
        return []
    # Severity: current mainline llama.cpp (common/chat.cpp,
    # common_chat_template_direct_apply_impl) explicitly strips a leading
    # bos_token string from the rendered template output whenever the
    # vocab's own add_bos is set, before tokenizing -- confirmed by reading
    # that function on ggml-org/llama.cpp main (fetched via `gh api
    # repos/ggml-org/llama.cpp/contents/common/chat.cpp`): the two lines
    #     if (inputs.add_bos && string_starts_with(result, tmpl.bos_token()))
    #         result = result.substr(tmpl.bos_token().size());
    # run on every call path in that file (llama-server's --jinja chat
    # completions, llama-cli's -cnv template application). So through
    # llama.cpp's own template machinery this combination does NOT reach
    # the tokenizer as two BOS tokens -- it's a real, deliberate mitigation,
    # not just the `check_double_bos_eos` warning in src/llama-vocab.cpp
    # (which only logs, never strips, and only fires downstream of a raw
    # prompt string that already contains two BOS tokens).
    #
    # That mitigation lives in llama.cpp's chat-template glue, not in the
    # GGUF file or the template itself, so it does not help a caller who
    # renders this same chat_template independently (transformers-style
    # `apply_chat_template`, a DIY script, or any runtime that reimplements
    # template application without llama.cpp's strip) and then tokenizes
    # the result with add_special_tokens=True -- that caller genuinely gets
    # two BOS tokens. INFO, not WARN: within the reference runtime the risk
    # is neutralized; it is real only for callers outside that path.
    return [Finding("S006", Severity.INFO,
                    "template emits BOS while add_bos_token metadata also adds one; "
                    "llama.cpp's own chat-template application (common_chat_apply_template, "
                    "as used by llama-server --jinja and llama-cli -cnv) strips this "
                    "duplicate automatically, but rendering this template yourself and then "
                    "tokenizing with add_special_tokens=True (e.g. via transformers, or any "
                    "runtime that reimplements template application) will genuinely produce "
                    "two BOS tokens",
                    evidence={"add_bos_token": True})]


# Common idioms by which a template hands off to the assistant through some
# mechanism other than add_generation_prompt (a role header, a closing tag
# that conventionally ends the user/instruction turn, ...). Used only to
# pick S007's severity: a best-effort heuristic over known template
# families, not a guarantee that every such template is fine.
_ASSISTANT_OPEN_MARKERS = (
    "[/INST]",
    "<|im_start|>assistant",
    "<|assistant|>",
    "<start_of_turn>model",
    "<|start_header_id|>assistant<|end_header_id|>",
    "ASSISTANT:",
    "### Response:",
)


def _opens_assistant_turn(text: str) -> bool:
    tail = (text or "").rstrip()
    return any(tail.endswith(marker) for marker in _ASSISTANT_OPEN_MARKERS)


def s007_generation_prompt_noop(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    fx = next((f for f in ctx.fixtures if f.name == "user_only"), None)
    if fx is None:
        # A custom --fixtures corpus that doesn't include "user_only" gives
        # this check nothing to render, so it never evaluated.
        ctx.checks_not_evaluated.append("S007")
        return []
    on = _primary(ctx).render(tpl, _with_real_tokens(ctx, {**fx.context, "add_generation_prompt": True}))
    off = _primary(ctx).render(tpl, _with_real_tokens(ctx, {**fx.context, "add_generation_prompt": False}))
    if not (on.ok and off.ok) or on.text != off.text:
        return []
    # We can only observe that the flag changed nothing -- not why, and not
    # whether the assistant turn is actually opened some other way, so the
    # message states the observable fact alone.
    severity = Severity.INFO if _opens_assistant_turn(on.text or "") else Severity.WARN
    return [Finding("S007", severity,
                    "add_generation_prompt has no effect on the rendered output",
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
