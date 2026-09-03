"""Family X: does llama.cpp render this template the way transformers does?

Both engines get the identical context -- BASE_CONTEXT defaults, the fixture,
the model's real bos/eos tokens -- and the raw rendered text is compared.
Neither side strips BOS (spec amendments §A). A fixture both engines fail on
belongs to S003, not here.

Two explanation classes downgrade a divergence to INFO, each confirmed by a
re-render rather than assumed: llama.cpp's message normaliser rewrote the input
("normaliser", _explained_by_normaliser), and llama.cpp defines
enable_thinking=true by default where the transformers path leaves it undefined
("enable_thinking_default", _explained_by_thinking_default). Evidence records
which one under "explained_by".
"""
from __future__ import annotations

import difflib
from typing import Any

from ggufdoctor.checks.common import collapse_by_signature, with_real_tokens
from ggufdoctor.models import CheckContext, Finding, Fixture, RenderResult, Severity

X_IDS = ["X001", "X002", "X004", "X005"]
JINJA2 = "jinja2"
LLAMACPP = "llama.cpp"
DIFF_LINES = 40
UNAVAILABLE_PREFIX = "engine:unavailable:"


def is_tool_fixture(fixture: Fixture) -> bool:
    return "tools" in fixture.context


def _engine_pair(ctx: CheckContext) -> tuple[Any, Any] | None:
    by_name = {getattr(e, "name", None): e for e in ctx.engines}
    if JINJA2 in by_name and LLAMACPP in by_name:
        return by_name[JINJA2], by_name[LLAMACPP]
    return None


def _engine_unavailable(r: RenderResult) -> bool:
    return not r.ok and r.error.startswith(UNAVAILABLE_PREFIX)


def _whitespace_only(a: str, b: str) -> bool:
    return a != b and "".join(a.split()) == "".join(b.split())


def _signature(a: str, b: str) -> tuple[tuple[str, str, str], ...]:
    """A dedup key describing *what* differs, independent of surrounding
    text that both engines render identically.

    Two fixtures that hit "the same divergence" (e.g. jinja2 prints "None"
    where llama.cpp prints nothing, at a fixed spot in the template) do not
    generally render byte-identical *lines* -- fixture corpus messages carry
    a different number/shape of roles, so the line-based unified diff used
    for the human-readable evidence["diff"] differs per fixture even though
    the underlying divergence is the same one. A character-level opcode diff
    isolates just the replaced/deleted/inserted substrings (dropping the
    "equal" spans), which collapses correctly across fixtures that vary only
    in the parts both engines agree on.
    """
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return tuple(
        (tag, a[i1:i2], b[j1:j2])
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    )


def _flatten_typed_content(context: dict[str, Any]) -> dict[str, Any]:
    """Best-effort mirror of llama.cpp's typed-content-to-text join (text
    parts of a message's content list, joined with "\\n"), used only to test
    whether an observed divergence is actually *caused* by that join.

    llama.cpp's message normaliser runs whenever its caps probe decided a
    template is string-content-only and a message's content happens to be a
    list -- regardless of whether the template ever looks at m.content. A
    template that never references content still gets RenderResult.extra
    "normalized": True on such a fixture, even though the normalisation
    changed nothing observable. Returns `context` unchanged (same object) if
    there is nothing to flatten, so callers can check `is context` to skip
    the confirmatory re-render entirely. This does NOT mirror every rewrite
    llama.cpp's normaliser can make -- notably request-level rewrites of
    tool_calls[].function.arguments (string <-> object) and
    reasoning_content are not reproduced here, so a divergence caused by
    those is reported at ERROR rather than INFO (the conservative
    direction: a real divergence surfaced, never a real one hidden).
    """
    messages = context.get("messages")
    if not isinstance(messages, list):
        return context
    changed = False
    flattened_messages = []
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            text = "\n".join(
                str(part.get("text", "")) for part in content
                if isinstance(part, dict) and "text" in part
            )
            m = {**m, "content": text}
            changed = True
        flattened_messages.append(m)
    if not changed:
        return context
    return {**context, "messages": flattened_messages}


def _explained_by_normaliser(j2: Any, tpl: str, context: dict[str, Any], llama_text: str) -> bool:
    """True only if re-rendering under jinja2 with typed content pre-flattened
    the way llama.cpp's normaliser does reproduces llama.cpp's own output --
    i.e. the normaliser's rewrite, not some unrelated engine difference, is
    what explains this divergence. A bare "normalized" flag on the
    RenderResult is not sufficient: it says llama.cpp's normaliser ran, not
    that it is why these two renders differ (see _flatten_typed_content).
    """
    flattened = _flatten_typed_content(context)
    if flattened is context:
        return False
    retried = j2.render(tpl, flattened)
    return retried.ok and retried.text == llama_text


def _explained_by_thinking_default(j2: Any, tpl: str, context: dict[str, Any],
                                   llama_text: str) -> bool:
    """True only if re-rendering under jinja2 with `enable_thinking=True` added
    reproduces llama.cpp's own output -- i.e. llama.cpp's implicit default, and
    not some unrelated engine difference, is what explains this divergence.

    common_chat_template_direct_apply_impl (llama.cpp common/chat.cpp) writes
    `enable_thinking` into every render context unconditionally, from a
    generation param that defaults to true; there is no path through llama.cpp
    that leaves the variable undefined (`--reasoning-budget 0` makes it false,
    not absent). transformers injects nothing, so a caller who does not pass
    `enable_thinking` gets the thinking form of a template under llama.cpp and
    the non-thinking form under transformers. That is a runtime default, not a
    template defect -- the template author cannot remove it -- so it is
    reported, and reported as INFO with the fix in the message (ruling R9).

    Only applies where the caller said nothing: if the context already carries
    `enable_thinking`, both engines saw the same value and this is not the
    explanation for anything.
    """
    if "enable_thinking" in context:
        return False
    retried = j2.render(tpl, {**context, "enable_thinking": True})
    return retried.ok and retried.text == llama_text


def _diff(a: str, b: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(),
                                 fromfile=JINJA2, tofile=LLAMACPP, lineterm="", n=1)
    out = list(lines)
    if len(out) > DIFF_LINES:
        out = out[:DIFF_LINES] + [f"... ({len(out) - DIFF_LINES} more diff lines)"]
    return "\n".join(out)


def _failure_text(r: RenderResult) -> tuple[str, str]:
    """(stage, one-line text) for a failed RenderResult."""
    tag, _, rest = r.error.partition(":")
    rest = rest.strip()
    if tag == "compile":
        stage, _, msg = rest.partition(":")
        return stage.strip() or "compile", msg.strip()
    if tag == "raise":
        return "raise", rest
    return "render", rest


def _x002(fx: Fixture, ok_engine: str, failing: RenderResult, ok_result: RenderResult,
          failing_engine: str, *, j2: Any, tpl: str,
          context: dict[str, Any]) -> tuple[Severity, str, dict[str, Any]]:
    stage, msg = _failure_text(failing)
    normalized = False
    if ok_engine == LLAMACPP and ok_result.extra.get("normalized"):
        # Confirm the normaliser is actually why jinja2 failed and llama.cpp
        # didn't, rather than trusting the bare flag -- see
        # _explained_by_normaliser.
        normalized = _explained_by_normaliser(j2, tpl, context, ok_result.text)
    evidence: dict[str, Any] = {
        "engines": [JINJA2, LLAMACPP], "failing_engine": failing_engine,
        "stage": stage, "error": msg, "normalized": normalized,
    }
    if ok_engine == LLAMACPP and ok_result.extra.get("caps"):
        evidence["llamacpp_caps"] = ok_result.extra["caps"]
    if stage == "raise":
        text = (f"{failing_engine} takes the template's raise_exception branch "
                f"({msg!r}) while {ok_engine} renders")
        return Severity.ERROR, text, evidence
    if failing_engine == LLAMACPP and stage in ("lexer", "parser"):
        return Severity.ERROR, f"template will not load in llama.cpp ({stage}: {msg})", evidence
    if failing_engine == LLAMACPP:
        return Severity.ERROR, f"renders under jinja2 but fails under llama.cpp ({stage}: {msg})", evidence
    if normalized:
        return (Severity.INFO,
                "renders under llama.cpp only after its message normaliser rewrote the "
                f"input; jinja2 (transformers path) fails on the original ({msg})", evidence)
    return (Severity.ERROR,
            f"renders under llama.cpp but fails under jinja2 (transformers path) ({stage}: {msg})", evidence)


def run_cross_engine_checks(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    pair = _engine_pair(ctx)
    if pair is None:
        ctx.checks_not_evaluated.extend(X_IDS)
        return []
    j2, llama = pair

    differs: list[tuple[str, Any, dict[str, Any]]] = []
    differs_tools: list[tuple[str, Any, dict[str, Any]]] = []
    explained: list[tuple[str, Any, dict[str, Any]]] = []   # llama.cpp rewrote the input first
    thinking: list[tuple[str, Any, dict[str, Any]]] = []    # llama.cpp's implicit enable_thinking
    whitespace: list[tuple[str, Any, dict[str, Any]]] = []
    one_side: dict[tuple[Severity, str], list[tuple[str, Any, dict[str, Any]]]] = {}
    agreed = 0

    for fx in ctx.fixtures:
        context = with_real_tokens(ctx, fx.context)
        a = j2.render(tpl, context)
        b = llama.render(tpl, context)
        if _engine_unavailable(a) or _engine_unavailable(b):
            # The CLI is expected to keep an unavailable engine out of
            # ctx.engines and record the gap itself (ledger R3), but this
            # check must not trust that -- an unavailable llama.cpp engine
            # reaching here would otherwise collapse into a spurious X002
            # "fails under llama.cpp (unavailable: ...)" on every fixture.
            ctx.checks_not_evaluated.extend(X_IDS)
            return []
        if a.ok and b.ok:
            if a.text == b.text:
                agreed += 1
                continue
            evidence: dict[str, Any] = {"engines": [JINJA2, LLAMACPP], "diff": _diff(a.text, b.text)}
            explained_flag = bool(b.extra.get("normalized")) and _explained_by_normaliser(
                j2, tpl, context, b.text)
            if explained_flag:
                evidence["normalized"] = True
                evidence["explained_by"] = "normaliser"
                evidence["llamacpp_caps"] = b.extra.get("caps", {})
            sig = _signature(a.text, b.text)
            # The normaliser test comes FIRST, before the whitespace-only test:
            # the *cause* of a divergence outranks its magnitude. A divergence
            # we can prove llama.cpp's own message normaliser created (see
            # _explained_by_normaliser) is fully explained by that rewrite
            # whether the resulting bytes differ by a newline or by a whole
            # message, and it belongs in the X001 INFO bucket that says so.
            # Testing whitespace first put the common real-world case --
            # templates that walk typed content themselves and join the text
            # parts with no separator, where llama.cpp joined them with "\n" --
            # into X004 WARN, which made the INFO downgrade unreachable for
            # exactly the overlap it was written for (ruling R7).
            # The enable_thinking explanation sits between them, for the same
            # reason and by the same rule: it is a *cause*, so it outranks the
            # whitespace-only magnitude test, and it outranks the tool-fixture
            # split below too -- a `with_tools` divergence that llama.cpp's
            # implicit default fully explains is that default, not a
            # tool-calling disagreement, so it does not become X005 (R9).
            if explained_flag:
                explained.append((fx.name, sig, evidence))
            elif _explained_by_thinking_default(j2, tpl, context, b.text):
                evidence["explained_by"] = "enable_thinking_default"
                thinking.append((fx.name, sig, evidence))
            elif _whitespace_only(a.text, b.text):
                whitespace.append((fx.name, sig, evidence))
            elif is_tool_fixture(fx):
                differs_tools.append((fx.name, sig, evidence))
            else:
                differs.append((fx.name, sig, evidence))
            continue
        if not a.ok and not b.ok:
            continue  # S003 owns "fails everywhere"
        if a.ok:
            severity, message, evidence = _x002(fx, JINJA2, b, a, LLAMACPP,
                                                 j2=j2, tpl=tpl, context=context)
        else:
            severity, message, evidence = _x002(fx, LLAMACPP, a, b, JINJA2,
                                                 j2=j2, tpl=tpl, context=context)
        one_side.setdefault((severity, message), []).append(
            (fx.name, (evidence["failing_engine"], evidence["stage"], evidence["error"]), evidence))

    ctx.stats["engines_agreed_fixtures"] = agreed

    findings: list[Finding] = []
    findings += collapse_by_signature(
        "X001", Severity.ERROR, "rendered output differs between jinja2 and llama.cpp", differs)
    findings += collapse_by_signature(
        "X005", Severity.ERROR, "tool-calling output differs between jinja2 and llama.cpp", differs_tools)
    findings += collapse_by_signature(
        "X001", Severity.INFO,
        "rendered output differs only because llama.cpp's message normaliser rewrote the "
        "input before rendering (typed content joined to text); jinja2 (transformers path) "
        "rendered the original", explained)
    findings += collapse_by_signature(
        "X001", Severity.INFO,
        "rendered output differs only because llama.cpp defines enable_thinking=true by "
        "default while jinja2 (transformers path) leaves it undefined; pass enable_thinking "
        "explicitly to make the runtimes agree", thinking)
    findings += collapse_by_signature(
        "X004", Severity.WARN, "rendered output differs between jinja2 and llama.cpp by whitespace only",
        whitespace)
    for (severity, message), results in one_side.items():
        findings += collapse_by_signature("X002", severity, message, results)
    return findings
