"""Family O/X003: would Ollama render this GGUF with a template that is not
this GGUF's template, and does it come out differently?

Ollama has no Jinja-to-Go converter. `ollama create` runs the GGUF's Jinja
source through `template.Named` -- a Levenshtein distance against the 37
strings in `template/index.json`, accepted only when the score is `< 100` --
and on a hit the curated `<name>.gotmpl` replaces the template entirely
(spike §1). On a miss, the common case, the GGUF's own Jinja is rendered by
llama-server, which is the engine family X already covers. So this family has
something to say only about the recognised minority: on the ten vendored real
templates it is one of ten (spike §5).

**O001 (INFO)** is the substitution itself: the registry recognises this
template as *T*, so a default `ollama create` would serve prompts built by
Ollama's curated *T*, not by the template shipped in this file. That is worth
knowing whether or not any output differs, so O001 is emitted on every
recognised template and carries the coverage facts -- how many fixtures
agreed, which were excluded and why -- as evidence.

**X003 (ERROR)** is a measured divergence on a fixture both sides can express:
the GGUF's Jinja rendered through the reference engine and Ollama's curated *T*
rendered by Ollama's own `template.Execute` produce different bytes, or exactly
one of them refuses the conversation. Goldens are recorded, not simulated:
`ollama.load_goldens()` holds text produced by Ollama's own template package at
the pinned commit (see tests/ollama_conformance), so nothing here re-implements
Go rendering. The Ollama side never renders at check time; only the jinja2 side
does, which is why `ctx.engines[0]` must be jinja2 and why goldens recorded
against one fixture corpus are never compared against another
(`corpus_version`, `custom_corpus`) -- a golden is an answer to a specific
question, and a different corpus is a different question.

Three exclusions keep this off the v0.1 false-positive path, each of them a
fact about Ollama rather than about the template (spike §2, §5):

* **`add_generation_prompt: false` is not expressible.** Ollama has no such
  concept; it always renders for generation, so the curated template appends
  the assistant opener unconditionally. A user cannot reach the "false" case
  through Ollama at all, so a difference there is an artefact of this corpus.
  Excluded by construction, and named in O001's `not_comparable`.
* **Typed content is not expressible.** `api.Message.Content` is a Go
  `string`, so the `typed_content` conversation fails to unmarshal before any
  template runs. The golden records that refusal; it is a coverage fact, not a
  divergence, and it too lands in `not_comparable`.
* **A curated template that ignores tools is a capability gap, not a
  rendering divergence.** All but one of the 19 templates the vendored index
  can select predate tool calling and never reference `.Tools` (counted over
  `ollama_data/*.gotmpl`; the spike's §2 figure of 15 was measured a different
  way), and `shouldPreferChatTemplate` exists to route around exactly that. It
  is reported as coverage on O001 (`ignores_tools`, `ignores_tools_fixtures`),
  never as X003.

That last one is *confirmed by a re-render, never inferred from the static
fact*, in the same spirit as cross_engine._explain: knowing that *T* has no
`.Tools` says the curated template ignores tools, not that ignoring them is
what explains this particular divergence. So the jinja2 side is re-rendered
with `tools` removed from the context, and the downgrade holds only if that
reproduces the golden byte for byte. Anything else stays an X003.

A fixture both sides refuse is silent -- that is S003's subject, not this
family's. A fixture exactly one side refuses is an X003 that names the
direction in its message, mirroring X002.

Every message carries OLLAMA_SUFFIX, which names the pinned Ollama commit and
the three routes that divert away from the curated template (`RENDERER` /
`PARSER` directives, `OLLAMA_GO_TEMPLATE=0`, and `PreferChatTemplate`, spike
§1). The finding is true of a default `ollama create` on that build, and the
message says so rather than implying the substitution is unconditional. No
message calls a template broken: on a recognised template the divergence is
between two documents, and which one is wrong depends on the runtime the user
is aiming at.
"""
from __future__ import annotations

from typing import Any

from ggufdoctor.checks.common import (collapse_by_signature, divergence_signature, failure_text,
                                      is_tool_fixture, render_diff, with_real_tokens)
from ggufdoctor.models import CheckContext, Finding, Severity
from ggufdoctor.ollama import CUTOFF, load_goldens, pin, references_tools, select

OLLAMA_IDS = ["X003", "O001"]
JINJA2 = "jinja2"
# Named on every message: the finding holds for a *default* `ollama create` on
# the pinned build, and each of these routes takes the prompt somewhere else
# (spike §1). Built from the pin so it can never drift from the vendored data.
OLLAMA_SUFFIX = (f" (Ollama {pin().short}, default 'ollama create'; RENDERER/PARSER, "
                 "OLLAMA_GO_TEMPLATE=0 and PreferChatTemplate divert to the Jinja path)")
NO_GENERATION_PROMPT_REASON = "Ollama has no add_generation_prompt; it always renders for generation"
CUSTOM_CORPUS_REASON = "no Ollama goldens for a custom corpus"
NO_ENGINE_REASON = "jinja2 reference engine not available"
# Defensive only: the bundled goldens cover every bundled fixture, and a
# corpus that does not match them was refused above. A missing entry means the
# goldens and the corpus disagree about what the corpus contains, which is a
# gap to report, never a divergence to infer from an absent answer.
NO_GOLDEN_REASON = "no Ollama golden was recorded for this fixture"


def run_ollama_checks(ctx: CheckContext, *, goldens: dict | None = None,
                      index: list[tuple[str, str]] | None = None) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    goldens = load_goldens() if goldens is None else goldens
    stats: dict[str, Any] = {"pinned_commit": pin().commit, "recognised": None, "template": None,
                             "distance": None, "confident": None, "not_evaluated": None}
    ctx.stats["ollama"] = stats

    def not_evaluated(reason: str) -> list[Finding]:
        stats["not_evaluated"] = reason
        ctx.checks_not_evaluated.extend(OLLAMA_IDS)
        return []

    # A custom corpus is refused before the version comparison: its version
    # will usually differ too, but the honest reason is that these goldens
    # were never rendered for those fixtures at all.
    if ctx.custom_corpus:
        return not_evaluated(CUSTOM_CORPUS_REASON)
    golden_corpus = goldens.get("corpus_version")
    if golden_corpus != ctx.corpus_version:
        return not_evaluated(f"bundled Ollama goldens are for fixture corpus {golden_corpus} "
                             f"but corpus {ctx.corpus_version} is loaded")
    if not ctx.engines or getattr(ctx.engines[0], "name", None) != JINJA2:
        return not_evaluated(NO_ENGINE_REASON)
    j2 = ctx.engines[0]

    selection = select(tpl, index)
    stats["recognised"] = selection.recognised
    stats["template"] = selection.name
    stats["distance"] = selection.distance
    # None, not False, on a miss: there is no confidence in a decision that
    # was never made.
    stats["confident"] = selection.confident if selection.recognised else None
    if not selection.recognised:
        return []

    name, distance = selection.name, selection.distance
    ignores_tools = not references_tools(name)
    renders = goldens["renders"].get(name, {})
    base_evidence = {"ollama_template": name, "distance": distance, "ollama_commit": pin().commit}

    differs: list[tuple[str, Any, dict[str, Any]]] = []
    # Keyed by message alone (severity is always ERROR here), like X002's dict.
    one_side: dict[str, list[tuple[str, Any, dict[str, Any]]]] = {}
    not_comparable: dict[str, str] = {}
    ignores_tools_fixtures: list[str] = []
    agreed = 0

    for fx in ctx.fixtures:
        context = with_real_tokens(ctx, fx.context)
        golden = renders.get(fx.name)
        if fx.context.get("add_generation_prompt") is False:
            not_comparable[fx.name] = NO_GENERATION_PROMPT_REASON
            continue
        if isinstance(golden, dict) and "unrepresentable" in golden:
            not_comparable[fx.name] = ("Ollama's api.Message cannot represent this "
                                       f"conversation: {golden['unrepresentable']}")
            continue
        if golden is None:
            not_comparable[fx.name] = NO_GOLDEN_REASON
            continue

        a = j2.render(tpl, context)

        if isinstance(golden, dict) and "error" in golden:
            if not a.ok:
                continue  # both sides refuse this conversation -- S003's subject
            message = (f"Ollama's curated {name} template fails to render this conversation "
                       f"({golden['error']}) while jinja2 (transformers path) "
                       f"renders{OLLAMA_SUFFIX}")
            evidence = {**base_evidence, "failing_side": "ollama",
                        "stage": "render", "error": golden["error"]}
            one_side.setdefault(message, []).append(
                (fx.name, ("render", golden["error"]), evidence))
            continue

        if not a.ok:
            stage, msg = failure_text(a)
            if stage == "raise":
                message = ("jinja2 (transformers path) takes the template's raise_exception "
                           f"branch ({msg!r}) while Ollama's curated {name} template "
                           f"renders{OLLAMA_SUFFIX}")
            else:
                message = (f"jinja2 (transformers path) fails on this conversation ({stage}: "
                           f"{msg}) while Ollama's curated {name} template renders{OLLAMA_SUFFIX}")
            evidence = {**base_evidence, "failing_side": JINJA2, "stage": stage, "error": msg}
            one_side.setdefault(message, []).append((fx.name, (stage, msg), evidence))
            continue

        if a.text == golden:
            agreed += 1
            continue

        # Coverage, not divergence -- but only once a re-render proves the
        # tools are the whole of the difference (see the module docstring).
        if is_tool_fixture(fx) and ignores_tools:
            retry = j2.render(tpl, {k: v for k, v in context.items() if k != "tools"})
            if retry.ok and retry.text == golden:
                ignores_tools_fixtures.append(fx.name)
                continue

        differs.append((fx.name, divergence_signature(a.text, golden),
                        {**base_evidence,
                         "diff": render_diff(a.text, golden, JINJA2, f"ollama:{name}")}))

    ctx.stats["ollama_agreed_fixtures"] = agreed

    findings: list[Finding] = collapse_by_signature(
        "X003", Severity.ERROR,
        f"Ollama would substitute its curated {name} template for this GGUF's own template, "
        f"and it renders differently{OLLAMA_SUFFIX}", differs)
    for message, results in one_side.items():
        findings += collapse_by_signature("X003", Severity.ERROR, message, results)

    low = f", low confidence: the cutoff is {CUTOFF}" if not selection.confident else ""
    tools = "; that template ignores tools" if ignores_tools else ""
    findings.append(Finding(
        "O001", Severity.INFO,
        f"Ollama's template registry recognises this template as {name} (distance {distance}"
        f"{low}) and would substitute its curated Go template{tools}{OLLAMA_SUFFIX}",
        evidence={**base_evidence, "confident": selection.confident,
                  "ignores_tools": ignores_tools,
                  "ignores_tools_fixtures": ignores_tools_fixtures,
                  "not_comparable": not_comparable, "agreed_fixtures": agreed}))
    return findings
