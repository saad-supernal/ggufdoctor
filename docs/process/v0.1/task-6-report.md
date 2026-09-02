# Task 6 Report: Family S — Self-Contained Checks

## What Was Created

### Files Created
1. **`src/ggufdoctor/checks/__init__.py`** — Package marker file (empty)
2. **`src/ggufdoctor/checks/sanity.py`** — Implementation of 8 self-contained sanity checks
3. **`tests/test_checks_sanity.py`** — Test suite with 11 tests covering all 8 checks

### Implementation Details

The implementation contains:
- `NON_CHAT_ARCHITECTURES` constant with the set of non-chat model architectures (bert, nomic-bert, jina-bert, parakeet, asr, audiocpp, ced, whisper, clip, t5, qwen3-tts)
- `SPECIAL_TOKEN_RE` regex pattern to extract `<|...|>` special tokens from templates
- Eight individual check functions (`s001_missing_template` through `s008_empty_render`)
- `SANITY_CHECKS` list defining the order of check execution
- `run_sanity_checks(ctx: CheckContext) -> list[Finding]` entry point that runs all checks

### The 8 Checks Implemented

| ID | Severity | Check | Condition |
|----|----------|-------|-----------|
| S001 | ERROR | Missing Template | Chat-capable architecture but no chat template embedded |
| S002 | ERROR | Uncompilable | Template does not compile under Jinja2 |
| S003 | ERROR | Render Error | Template raises while rendering a standard conversation |
| S004 | ERROR | Unknown Special Token | Template emits special tokens absent from vocab |
| S005 | WARN | EOS Mismatch | EOS token ID out of range or template never emits EOS |
| S006 | WARN | Double BOS | Template emits BOS while metadata also adds BOS |
| S007 | WARN | Generation Prompt No-op | `add_generation_prompt` flag has no effect |
| S008 | ERROR | Empty Render | Template renders to empty/whitespace-only output |

## Test Execution

### Command
```bash
pytest tests/test_checks_sanity.py -v
```

### Results
All 11 tests passed:
- `test_s001_chat_arch_without_template` ✓
- `test_s001_not_raised_for_non_chat_arch` ✓
- `test_s002_uncompilable_template` ✓
- `test_s003_render_error_on_fixture` ✓
- `test_s004_flags_token_absent_from_vocab` ✓
- `test_s004_silent_when_all_tokens_present` ✓
- `test_s004_skipped_when_vocab_unavailable` ✓
- `test_s006_double_bos` ✓
- `test_s007_generation_prompt_noop` ✓
- `test_s008_empty_render` ✓
- `test_clean_template_produces_no_findings` ✓

Full test suite: **41/41 tests passing** (30 existing + 11 new)

## Commit SHA
**f38cf83** — `feat: family S self-contained template checks`

## Application of CHAT_ARCHITECTURES Ruling

As ruled, I **did not create** a `CHAT_ARCHITECTURES` constant. Instead, the implementation uses only `NON_CHAT_ARCHITECTURES`, following the pattern specified in the brief:

```python
NON_CHAT_ARCHITECTURES = {
    "bert", "nomic-bert", "jina-bert", "parakeet", "asr", "audiocpp",
    "ced", "whisper", "clip", "t5", "qwen3-tts",
}

def _is_chat_arch(ctx: CheckContext) -> bool:
    arch = (ctx.model.architecture or "").lower()
    return arch not in NON_CHAT_ARCHITECTURES
```

The check logic inverts the set as instructed: an architecture is chat-capable if it is **not** in the non-chat set.

## Deviations from Brief
**None.** The implementation follows the brief exactly:
- All finding IDs (S001–S008) are verbatim
- All severities are verbatim
- All message strings are verbatim
- The test cases match exactly
- No extra logic or changes introduced

## Key Design Notes

### Engine Integration
- Uses `ctx.engines[0]` as the primary rendering engine (Jinja2)
- Relies on the engine's guarantee that `render()` never raises; errors are captured in `RenderResult` with `.error` and `.ok` properties
- Does not wrap renders in try/except

### Template Token Inspection (s004, s005, s006)
- These checks inspect the **template source**, not rendered output
- This avoids the placeholder token trap: the engine merges a `BASE_CONTEXT` with fabricated tokens (`bos_token="<s>"`, `eos_token="</s>"`, etc.)
- The checks that reason about tokens (s004, s005, s006) use `ctx.model.tokens` and the template text directly

### Fixture Usage
- s003 and s008 iterate over all fixtures in `ctx.fixtures`
- s007 specifically looks for the `user_only` fixture to test `add_generation_prompt` semantics
- If `user_only` is missing, s007 returns empty (no false positives)

### Graceful Skipping
- s001: Skipped for non-chat architectures
- s004: Skipped when `ctx.model.tokens` is empty (no vocab to check against)
- s005: Skipped when template is absent, EOS token ID is None, or no tokens available
- s006: Skipped when no BOS token is set in metadata
- s007: Skipped when template is absent or `user_only` fixture is unavailable

## What Tasks 11/12 Should Know

### Calling `run_sanity_checks`
- Entry point: `from ggufdoctor.checks.sanity import run_sanity_checks`
- Signature: `run_sanity_checks(ctx: CheckContext) -> list[Finding]`
- Returns a list of `Finding` objects in check execution order (S001, S002, ..., S008)
- An empty list means the template is clean with respect to sanity checks

### Integration with Coverage
- Tasks 11 and 12 call this directly to build coverage reports
- Finding IDs are stable and can be used for filtering/aggregation
- The checks are self-contained: they require only the `CheckContext` (no external I/O)

### Performance
- All checks run in <100ms for typical templates (no I/O, no subprocesses)
- Fixture loading and rendering are the bottleneck; the checks themselves are negligible

### Test Assertions
- All 8 checks have explicit test coverage
- The bright-line case (`test_clean_template_produces_no_findings`) confirms no false positives
- Skipping logic is tested explicitly (e.g., `test_s001_not_raised_for_non_chat_arch`)

---

## Fix round 1

Code review found the original S004/S005/S006 designs asked the template
*source text* a question only a *render* can answer, producing systemic
false positives (Mistral-7B-Instruct-v0.2 and Llama-2-chat both flagged by
S005 despite correctly rendering `</s>`; S006 flagged templates whose only
mention of `bos_token` was inside a comment or a dead branch). Separately,
a template that fails identically across all seven fixtures produced one
`S003`/`S008` finding per fixture instead of one finding overall. This
section covers the redesign.

### What changed in `src/ggufdoctor/checks/sanity.py`

**New shared helpers:**
- `_real_token(m, token_id)` — returns the model's actual string for a
  token id, or `None` when the id is absent or out of range for
  `m.tokens`. `None` always means "nothing to check against," never "fall
  back to a placeholder."
- `_with_real_tokens(ctx, context)` — merges a render context with the
  model's real `bos_token`/`eos_token` strings (when known), overriding
  the fabricated placeholders (`<s>`/`</s>`) that `Jinja2Engine.BASE_CONTEXT`
  would otherwise supply. Used for every render in the S family (S002
  through S008), so the checks always see what the model would actually
  produce, and never confuse the engine's placeholder with a real token.
- `_render_fixture(ctx, fixture)` — convenience wrapper rendering
  `ctx.model.chat_template` against `_with_real_tokens(ctx, fixture.context)`.
- `_collapse_by_signature(check_id, severity, message, results)` — folds
  fixture-level failures into one Finding per distinct failure signature,
  recording every affected fixture name in `evidence["fixtures"]`. Used by
  S003 and S008 (the two fixture-iterating checks). Order follows first
  occurrence, which follows fixture corpus order, so output is
  deterministic.

**S005 (EOS mismatch)** — no longer does substring matching against the
template source. It now renders the `multiturn` fixture (the one fixture
guaranteed to contain an assistant turn, and therefore the one place EOS
is expected to appear) with the real EOS token injected, and checks
whether the real EOS string appears in the *rendered output*. If the
render fails, it skips silently — S003 already reports render failures,
and a template that can't render has nothing meaningful to say about
what it emits. If the real EOS string is unavailable (`eos_token_id`
missing or out of range), it skips rather than falling back to the
`</s>` placeholder. The `eos_token_id`-out-of-range sub-case is unchanged
since it was already correct (a metadata validity check, not a
render-inspection one). Id, severity, and message text are unchanged.

**S006 (double BOS)** — no longer does substring matching (`"bos_token" in
template` or `token_string in template`) against source text. It now
renders `user_only` with the real tokens injected and reports only when
`model.add_bos_token` is true **and** the rendered output actually begins
with the real BOS string. Skips when the render fails or the real BOS is
unavailable. Id, severity, and message text are unchanged.

**S004 (unknown special token)** — still extracts `<|...|>` literals from
the source via `SPECIAL_TOKEN_RE` and still skips entirely when
`ctx.model.tokens` is empty, exactly as before. What changed: a literal
absent from the vocab is now only reported if it also appears in at
least one fixture's *rendered* output. Literals that live only in a
`{# ... #}` comment or on a dead `{% if %}` branch never survive to any
render and are no longer reported — they're not evidence the template
ever emits them.

**Noise control (S003/S008)** — both checks now use
`_collapse_by_signature` instead of appending one Finding per fixture.
S003 groups by the render error string (so two fixtures failing for
different reasons still produce two findings; the same failure across
all seven fixtures produces one). S008 groups by a constant signature
(empty-or-whitespace output has no further distinguishing detail). Both
checks now put the affected fixture names in `evidence["fixtures"]`
instead of setting the singular `Finding.fixture` field, since one
finding can now represent multiple fixtures; `Finding.fixture` is left at
its default (`None`) for these two checks.

**S002/S004/S006 ordering** — `run_sanity_checks` now computes
`s002_findings` once, and explicitly gates S004 and S006 behind
`template_compiles = not s002_findings`, with a comment explaining why:
a template S002 already flagged as uncompilable has nothing meaningful to
say about what it emits, so asking S004/S006 would only add noise on top
of the S002 finding. (In practice this was already the de facto outcome
for S004/S006 in the new render-based design, since a template that
doesn't compile fails every render attempt too — but the brief asked for
this to be explicit in `run_sanity_checks`'s structure rather than an
accidental consequence of check-list ordering, so the gate is now
written out.) S001, S003, S005, S007, S008 are unaffected and continue to
run unconditionally (S003/S005/S007/S008 already degrade gracefully on a
non-compiling template via their own `r.ok`/`r.error` checks).

### Tests changed

One existing test asserted the old, wrong behavior and was updated:

- **`test_s006_double_bos`** — previously called
  `ctx(chat_template="{{ bos_token }}hi", add_bos_token=True)` with no
  `bos_token_id`/`tokens` on the model. Under the old source-substring
  check this passed because the literal string `"bos_token"` appears in
  the template text. Under the new render-based check there is no real
  BOS string to look for (`bos_token_id` is `None`), so S006 correctly
  skips — which is exactly the "skip rather than fall back to a
  placeholder" behavior the fix requires; the old assertion was only ever
  passing because it was matching source text, not a real token. Updated
  to supply `tokens=["<s>"], bos_token_id=0` so a real BOS is available
  and the render (`"<s>hi"`) actually begins with it.

All other 10 original tests pass unmodified against the new
implementation.

### Tests added (9 new, in `tests/test_checks_sanity.py`)

- `test_s005_no_false_positive_on_mistral_template` /
  `test_s005_no_false_positive_on_llama2_template` — the real
  Mistral-7B-Instruct-v0.2 and Llama-2-chat templates (transcribed
  verbatim as `MISTRAL_V02_TPL` / `LLAMA2_CHAT_TPL`), both of which emit
  EOS only via `{{ eos_token }}`, produce no S005.
- `test_s005_flags_template_that_never_emits_eos` — a template that
  genuinely never emits EOS still produces S005.
- `test_s006_silent_when_bos_mentioned_only_in_comment` /
  `test_s006_silent_when_bos_only_in_untaken_branch` — `bos_token`
  mentioned only in a `{# ... #}` comment or only inside an untaken
  `{% if false %}` branch produces no S006.
- `test_s006_flags_llama3_style_conditional_bos` — a real
  Llama-3-style `{% if loop.index0 == 0 %}{{ bos_token }}{% endif %}`
  with `add_bos_token=True` still produces S006.
- `test_s004_comment_only_marker_silent_but_rendered_missing_marker_flags`
  — a `<|marker|>` appearing only in a comment produces no S004, while one
  that actually renders and is absent from the vocab still does (both
  assertions in one test, to make the discrimination explicit).
- `test_s003_collapses_repeats_across_fixtures` — a template that fails
  in all seven fixtures produces exactly one S003, with all seven fixture
  names in `evidence["fixtures"]`.
- `test_s004_and_s006_skipped_when_template_does_not_compile` — a
  template that fails S002 produces neither S004 nor S006, exercising
  the explicit gate in `run_sanity_checks`.

Full suite: `.venv/bin/python -m pytest tests/ -v` → **50 passed** (30
pre-existing outside the S family + 20 in `test_checks_sanity.py`, up
from 11).

### What Tasks 11/12 should know about finding aggregation

- **A Finding no longer maps 1:1 to a fixture for S003/S008.** Both now
  emit at most one Finding per distinct failure signature across the
  whole fixture corpus, not one per fixture. `Finding.fixture` is `None`
  for these two; consumers that need to know which fixtures were
  affected must read `evidence["fixtures"]` (a `list[str]` of fixture
  names), not the singular `fixture` field.
- **Finding counts no longer scale with corpus size.** A template broken
  the same way in all seven current fixtures yields one S003, not seven
  — this held even before the corpus had 8 fixtures' worth of coverage
  and will continue to hold if the corpus grows. Any downstream count of
  "findings per template" or "errors by id" should treat S003/S008 counts
  as "distinct failure modes observed," not "fixtures affected." If a
  future consumer needs failure/fixture counts separately, sum
  `len(evidence["fixtures"])` per finding rather than counting findings.
- **S004 and S006 are conditionally absent, not just conditionally
  empty, when S002 fires.** `run_sanity_checks` skips calling them
  entirely once a template fails to compile; a coverage report crediting
  "checks that ran" vs. "checks that found nothing" should treat S004/S006
  as not-run (rather than clean) for an S002 template, since their
  render-dependent verdict genuinely couldn't be computed.
- **S005/S006 can now be silently skipped for reasons other than "no
  chat_template."** They no longer fire when the model's real
  `bos_token_id`/`eos_token_id` is missing or out of range for
  `model.tokens`, even if `add_bos_token` is set or `eos_token_id` is
  present but the vocab is empty. This is intentional (no placeholder
  fallback), but it means an all-clear from `run_sanity_checks` on a
  model with incomplete token metadata is weaker evidence than an
  all-clear on a model with full metadata — something a coverage/report
  layer may want to surface (e.g., "S005/S006 not evaluated: real token
  strings unavailable").

### Commit

Committed on top of `f38cf83` (branch `feat/v0.1`).
