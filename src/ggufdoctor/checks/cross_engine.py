"""Family X: does llama.cpp render this template the way transformers does?

Both engines get the identical context -- BASE_CONTEXT defaults, the fixture,
the model's real bos/eos tokens -- and the raw rendered text is compared.
Neither side strips BOS (spec amendments §A). A fixture both engines fail on
belongs to S003, not here.

Three explanation classes downgrade a divergence to INFO, each confirmed by a
re-render rather than assumed: llama.cpp's message normaliser rewrote the input
("normaliser", _explained_by_normaliser); llama.cpp supplies runtime defaults
the transformers path leaves undefined ("runtime_defaults",
_explained_by_runtime_defaults, with the keys under "defaults"); and both at
once ("normaliser+runtime_defaults",
_explained_by_normaliser_and_runtime_defaults). Evidence records which under
"explained_by".

The three are tried in that order by _explain, and both the
both-engines-rendered path and the one-sided X002 path call it, so a
divergence is graded by its cause and never by which engine happened to
raise (ruling R13).
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
DIFF_LINE_CHARS = 400
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


# Every context value llama.cpp supplies on its own and the transformers path does
# not -- as the *template* sees them, which is why this is six keys and not two.
#
# `enable_thinking` comes from a generation param that
# common_chat_template_direct_apply_impl writes into every render context
# unconditionally (common/chat.cpp). `preserve_reasoning` comes from
# common_params_parse, which sets it to "true" for every llama.cpp CLI tool
# whenever it was not given explicitly (common/arg.cpp:963-966) -- but a template
# almost never reads that name: direct_apply_impl hands it to
# jinja::caps_apply_preserve_reasoning, which *expands* it into the four variables
# below (common/jinja/caps.cpp:22-27):
#
#     ctx.set_val("preserve_thinking",         enabled);
#     ctx.set_val("clear_thinking",            !enabled);
#     ctx.set_val("truncate_history_thinking", !enabled);
#     ctx.set_val("drop_thinking",             !enabled);
#
# Jinja2Engine has no such expansion (nor does transformers), so listing only the
# switch would leave every template that reads an expanded name unexplainable --
# the whole point of ruling R12a. Values here are the expansion for
# `preserve_reasoning = true`, the CLI default.
#
# Insertion order fixes the order of the reported "defaults" list.
RUNTIME_DEFAULTS: dict[str, Any] = {
    "enable_thinking": True,
    "preserve_reasoning": True,
    "preserve_thinking": True,
    "clear_thinking": False,
    "truncate_history_thinking": False,
    "drop_thinking": False,
}


def _with_runtime_defaults(context: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(context plus every runtime default it lacks, the keys added).

    A key the caller already supplied is never overridden -- the caller outranks
    a default, and a divergence on a value both engines were handed is not
    explained by anything here.
    """
    added = [k for k in RUNTIME_DEFAULTS if k not in context]
    if not added:
        return context, []
    return {**context, **{k: RUNTIME_DEFAULTS[k] for k in added}}, added


def _explained_by_runtime_defaults(j2: Any, tpl: str, context: dict[str, Any],
                                   llama_text: str) -> list[str]:
    """The runtime defaults that explain this divergence, or [] if they do not.

    llama.cpp hands a template values the caller never passed: `enable_thinking`,
    written into every render context from a param that defaults to true, and
    `preserve_reasoning`, defaulted to "true" by the CLI layer. There is no
    llama.cpp path that leaves `enable_thinking` undefined (`--reasoning-budget 0`
    makes it false, not absent), and none that drops the preserve_reasoning kwarg
    unless `--no-reasoning-preserve` is given. transformers injects nothing, which
    is why model cards tell callers to pass these. So a caller who says nothing
    gets a different prompt from each runtime for the same GGUF: a runtime
    default, not a template defect -- the author cannot remove it -- so it is
    reported, and reported as INFO with the fix in the message (rulings R9, R12).

    Confirmed, never assumed: jinja2 is re-rendered with the missing defaults
    filled in and the result must equal llama.cpp's byte for byte. Where the
    caller already supplied every default, there is nothing to explain and this
    returns [].

    RUNTIME_DEFAULTS carries the *expanded* preserve_reasoning variables as well
    as the switch, because Jinja2Engine has no caps_apply_preserve_reasoning to
    expand it with: handing a jinja2 context the bare switch is inert unless the
    template happens to read that exact name, so a template reading
    `preserve_thinking` would go unexplained (ruling R12a).
    """
    filled, added = _with_runtime_defaults(context)
    if not added:
        return []
    retried = j2.render(tpl, filled)
    return added if (retried.ok and retried.text == llama_text) else []


def _explained_by_normaliser_and_runtime_defaults(j2: Any, tpl: str, context: dict[str, Any],
                                                  llama_text: str) -> list[str]:
    """Both explanations at once: pre-flatten typed content the way llama.cpp's
    normaliser does *and* fill in the runtime defaults, in one re-render.

    Neither cause alone reproduces llama.cpp when a divergence has both -- the
    flatten leaves the thinking block missing, the defaults leave the content
    parts unjoined -- so without this a fixture that hits both is reported at
    ERROR purely because two explanations applied instead of one (ruling R10).
    Returns the defaults added, or [] if the composition does not explain it
    either.
    """
    flattened = _flatten_typed_content(context)
    if flattened is context:
        return []
    return _explained_by_runtime_defaults(j2, tpl, flattened, llama_text)


def _explain(j2: Any, tpl: str, context: dict[str, Any],
             ok_result: RenderResult) -> tuple[str | None, list[str]]:
    """The explanation ladder, in one place so every caller walks the same one.

    Returns (explained_by, defaults added) -- ("normaliser", []),
    ("runtime_defaults", keys), ("normaliser+runtime_defaults", keys) or
    (None, []) when nothing llama.cpp did on its own accounts for the
    divergence. `ok_result` is llama.cpp's successful render; each rung is
    confirmed by re-rendering under jinja2 and demanding byte equality with
    it, never inferred from a flag.

    Rung order is the classification order: the composition is tried last, so
    a divergence one cause explains on its own is never attributed to two
    (ruling R10). The `normalized` flag only gates the two rungs that involve
    the normaliser -- it says the rewrite ran, not that it explains anything
    (see _explained_by_normaliser).

    Both the both-engines-rendered path and _x002's llama.cpp-renders /
    jinja2-fails path call this: a divergence that becomes a one-sided failure
    only because jinja2 choked on the un-normalised input has exactly the same
    causes as one where both engines limped through, and reporting the first at
    ERROR while the second is INFO would grade the same fact by which engine
    happened to raise (ruling R13).
    """
    normalized_flag = bool(ok_result.extra.get("normalized"))
    if normalized_flag and _explained_by_normaliser(j2, tpl, context, ok_result.text):
        return "normaliser", []
    added = _explained_by_runtime_defaults(j2, tpl, context, ok_result.text)
    if added:
        return "runtime_defaults", added
    if normalized_flag:
        combined = _explained_by_normaliser_and_runtime_defaults(
            j2, tpl, context, ok_result.text)
        if combined:
            return "normaliser+runtime_defaults", combined
    return None, []


def _diff(a: str, b: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(),
                                 fromfile=JINJA2, tofile=LLAMACPP, lineterm="", n=1)
    # Per-line budget as well as a line count: a template that renders
    # everything on one line (minified templates do) would otherwise put both
    # engines' entire output -- unbounded, attacker-influenced text from a
    # stranger's repo -- into a JSON report as a single diff line.
    out = [ln if len(ln) <= DIFF_LINE_CHARS else ln[:DIFF_LINE_CHARS] + "…"
           for ln in lines]
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


def _x002(ok_engine: str, failing: RenderResult, ok_result: RenderResult,
          failing_engine: str, *, j2: Any, tpl: str,
          context: dict[str, Any]) -> tuple[Severity, str, dict[str, Any]]:
    stage, msg = _failure_text(failing)
    evidence: dict[str, Any] = {
        "engines": [JINJA2, LLAMACPP], "failing_engine": failing_engine,
        "stage": stage, "error": msg, "normalized": False,
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

    # llama.cpp rendered and jinja2 (the transformers path) did not. Walk the
    # full explanation ladder, exactly as the both-engines-rendered path does
    # (ruling R13): the causes of a one-sided failure are the same causes, and
    # before this only the normaliser rung was tried here -- so a divergence
    # that needed the runtime defaults, or both together, was reported at ERROR
    # solely because jinja2 raised on the un-normalised input instead of
    # limping through it.
    explained_by, defaults = _explain(j2, tpl, context, ok_result)
    if explained_by:
        evidence["explained_by"] = explained_by
        evidence["normalized"] = "normaliser" in explained_by
    if defaults:
        evidence["defaults"] = defaults
    if explained_by == "normaliser":
        return (Severity.INFO,
                "renders under llama.cpp only after its message normaliser rewrote the "
                f"input; jinja2 (transformers path) fails on the original ({msg})", evidence)
    if explained_by == "runtime_defaults":
        return (Severity.INFO,
                "renders under llama.cpp only because it supplies runtime defaults the "
                f"transformers path leaves undefined ({', '.join(defaults)}); jinja2 "
                f"(transformers path) fails on the original ({msg}); pass them explicitly "
                "to make the runtimes agree", evidence)
    if explained_by == "normaliser+runtime_defaults":
        return (Severity.INFO,
                "renders under llama.cpp only after its message normaliser rewrote the "
                "input (typed content joined to text) and because it supplies runtime "
                f"defaults the transformers path leaves undefined ({', '.join(defaults)}); "
                f"jinja2 (transformers path) fails on the original ({msg}); pre-join typed "
                "content and pass those defaults explicitly to make the runtimes agree",
                evidence)
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
    # keyed by the tuple of runtime-default keys that explained the divergence,
    # so each bucket's message can name exactly the ones its fixtures needed
    defaults_only: dict[tuple[str, ...], list[tuple[str, Any, dict[str, Any]]]] = {}
    both: dict[tuple[str, ...], list[tuple[str, Any, dict[str, Any]]]] = {}
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
            explained_by, defaults = _explain(j2, tpl, context, b)
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
            # The runtime-default explanations sit between them, for the same
            # reason and by the same rule: they are *causes*, so they outrank the
            # whitespace-only magnitude test, and they outrank the tool-fixture
            # split below too -- a `with_tools` divergence that llama.cpp's
            # implicit defaults fully explain is those defaults, not a
            # tool-calling disagreement, so it does not become X005 (R9). The
            # composition is tried last of the three, so a divergence one cause
            # explains on its own is never attributed to two (R10). All three
            # rungs live in _explain, which _x002 walks too.
            if explained_by == "normaliser":
                evidence["normalized"] = True
                evidence["explained_by"] = explained_by
                evidence["llamacpp_caps"] = b.extra.get("caps", {})
                explained.append((fx.name, sig, evidence))
            elif explained_by == "runtime_defaults":
                evidence["explained_by"] = explained_by
                evidence["defaults"] = defaults
                defaults_only.setdefault(tuple(defaults), []).append((fx.name, sig, evidence))
            elif explained_by == "normaliser+runtime_defaults":
                evidence["explained_by"] = explained_by
                evidence["defaults"] = defaults
                evidence["normalized"] = True
                evidence["llamacpp_caps"] = b.extra.get("caps", {})
                both.setdefault(tuple(defaults), []).append((fx.name, sig, evidence))
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
            severity, message, evidence = _x002(JINJA2, b, a, LLAMACPP,
                                                j2=j2, tpl=tpl, context=context)
        else:
            severity, message, evidence = _x002(LLAMACPP, a, b, JINJA2,
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
    for keys, results in defaults_only.items():
        findings += collapse_by_signature(
            "X001", Severity.INFO,
            "rendered output differs only because llama.cpp supplies runtime defaults the "
            f"transformers path leaves undefined ({', '.join(keys)}); pass them explicitly "
            "to make the runtimes agree", results)
    for keys, results in both.items():
        findings += collapse_by_signature(
            "X001", Severity.INFO,
            "rendered output differs only because llama.cpp's message normaliser rewrote the "
            "input before rendering (typed content joined to text) and it supplies runtime "
            f"defaults the transformers path leaves undefined ({', '.join(keys)}); pre-join "
            "typed content and pass those defaults explicitly to make the runtimes agree",
            results)
    findings += collapse_by_signature(
        "X004", Severity.WARN, "rendered output differs between jinja2 and llama.cpp by whitespace only",
        whitespace)
    for (severity, message), results in one_side.items():
        findings += collapse_by_signature("X002", severity, message, results)
    return findings
