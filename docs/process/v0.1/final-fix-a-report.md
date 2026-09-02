# Final Whole-Branch Review — Fix Round A — Implementation Report

## Status: DONE (items 1–5 fixed as specified; item 6 fixed; two items need your ruling — see below)

**Base commit:** `332995e`
**Test summary:** 142 passed (126 existing + 16 new), 0 failed — `.venv/bin/python -m pytest tests/ -v`

All 126 pre-existing tests still pass, but 6 of them asserted behaviour that the
review explicitly identified as wrong (or that the fix necessarily changes) and
were updated in place, each documented below with the reason.

---

## 1. S003 no longer accuses author-declined renders of being broken

**`src/ggufdoctor/engines/jinja2_engine.py`**

- Added `AuthorDeclinedRender(Exception)`. `_raise_exception` (the `raise_exception`
  global exposed to templates) now raises this instead of a bare `ValueError`.
- `Jinja2Engine.render` catches `AuthorDeclinedRender` before the generic
  `Exception` handler and tags `RenderResult.error` as `f"raise:{e}"` — the
  message is the author's own text, byte-for-byte, with no exception-class
  noise prepended. Genuine engine failures (undefined variable, unknown
  filter, `ZeroDivisionError`, etc.) are unaffected and keep the `render:`
  prefix.
- Verified empirically that Jinja does not re-wrap the exception raised from
  a global function call — `str(e)` round-trips the exact author message.

**`src/ggufdoctor/checks/sanity.py`**

- `s003_render_error` now splits fixture failures into two buckets by
  `RenderResult.error` prefix: `render:` → unchanged ERROR finding, same
  message, same collapsing behaviour. `raise:` → a **new, separate** S003
  finding at **INFO**, message: `template author deliberately declines this
  conversation shape (raise_exception: '<their exact text>')`. Same finding
  id, split by signature exactly like the ERROR case (so e.g. two different
  declined reasons across fixtures still collapse into two distinct INFO
  findings, each naming which fixtures hit it).
- `_collapse_by_signature` was extended to accept a callable message (in
  addition to a plain string) so the INFO message can quote each group's own
  author text. Backward compatible — every other caller still passes a
  plain string.

No finding ids were renumbered; S003 keeps firing at ERROR for real breakage.

## 2. S007's message states only what was observed

**`src/ggufdoctor/checks/sanity.py`**

- Message changed to `add_generation_prompt has no effect on the rendered
  output` — no claim about the assistant turn.
- Added `_opens_assistant_turn(text)`, a best-effort heuristic checking
  whether the rendered tail ends with one of several known turn-opening
  idioms (`[/INST]`, `<|im_start|>assistant`, `<start_of_turn>model`,
  `<|start_header_id|>assistant<|end_header_id|>`, etc.). When it matches,
  S007 fires at **INFO**; otherwise it stays **WARN**, as before.
- Documented in the docstring that this is a heuristic over known template
  families, not a guarantee.

## 3. Regression tests now assert the whole finding set, not one id

**`tests/test_checks_sanity.py`**

The two existing tests were rewritten to assert the complete `{(id, severity)}`
set instead of `"S005" not in ids(f)`, and I added the same whole-suite
assertion for real Gemma-2 and real Llama-3.3 tool-calling templates.

**All four templates are the real upstream text**, fetched live from public
Hugging Face mirrors and verified byte-for-byte (round-tripped through
`repr()`/`eval()` before being pasted into the test file, and diffed against
the original JSON after pasting — both matched exactly):

- Mistral-7B-Instruct-v0.2 and Llama-2-7b-chat: the templates already
  present in the test file (I confirmed these match the well-known
  transformers defaults for these families).
- **Gemma-2**: fetched from `unsloth/gemma-2-9b-it/tokenizer_config.json`
  (a public, unmodified mirror of `google/gemma-2-9b-it`).
- **Llama-3 tool-calling**: fetched from
  `unsloth/Llama-3.3-70B-Instruct/tokenizer_config.json` (a public mirror of
  Meta's own file — Llama 3.3 folded the separate "tool_use" template
  variant into a single default template, so this is the real tool-calling
  template, exercised against the corpus's `with_tools` fixture including
  its `| tojson(indent=4)` schema rendering).

**None of the four is empty.** Every remaining finding is a genuine,
independently-documented real-world property of that exact template/model
family, not an artifact of anything I changed — I did not weaken any
assertion to force `== []`; I asserted what the checks actually and
correctly produce, with the reasoning, so you can rule on whether that's the
right final shape. This needs your ruling:

| Template | add_bos_token | Findings | Why (real, documented) |
|---|---|---|---|
| Mistral-7B-Instruct-v0.2 | `False` (chosen — see note) | `S003 INFO`, `S007 INFO` | Template's own alternation guard rejects the `system_user` fixture ("Conversation roles must alternate…") — this is the author's real, deliberate behaviour, correctly downgraded to INFO with the exact message quoted. `add_generation_prompt` is genuinely never referenced in the real template; output ends in `[/INST]`, so INFO not WARN. |
| Llama-2-7b-chat | `False` (chosen) | `S007 INFO` | Same `add_generation_prompt` no-op as Mistral; system role is special-cased (folded into first turn) rather than rejected, so no S003. |
| Gemma-2-9b-it | `True` (real value) | `S003 INFO`, `S005 WARN`, `S006 WARN` | S003: template unconditionally rejects a leading system role. S005: the template only ever emits `<end_of_turn>`, never the vocab's separate `<eos>` — a well-known real Gemma quirk (recent `generation_config.json` for Gemma-2-it models lists *two* eos ids for exactly this reason). S006: real tokenizer_config has `add_bos_token: true` **and** the template does `{{ bos_token }}` itself — the documented Gemma-2 GGUF "double BOS" issue. |
| Llama-3.3-70B-Instruct (tools) | `True` (real value) | `S006 WARN` | Real tokenizer_config has `add_bos_token: true` **and** the template does `{{- bos_token }}` itself — the same double-BOS pattern, independently documented for Llama-3.x GGUF conversions. Everything else (tool-schema rendering, EOS, generation prompt) is clean. |

**Note on `add_bos_token` for Mistral/Llama-2:** their real HF
`tokenizer_config.json` also has `add_bos_token: true` (I checked both
live), so the same double-BOS finding *could* legitimately appear there
too. I deliberately used `False` for these two so the test isolates exactly
the S003/S007 behaviour items 1–2 fixed, rather than conflating it with the
double-BOS question — S006's own dedicated tests already cover that
combination in general. If you'd rather these two tests also use the real
`add_bos_token: true` (making them consistent with the Gemma-2/Llama-3
tests and surfacing a third real S006 instance), say so and I'll change it —
one line each.

**My ask:** rule on whether the four tables above are acceptable as the
final "real template" regression fixtures, or whether you want the
`add_bos_token` choice for Mistral/Llama-2 changed to match real metadata.

## 4. R001 now injects the model's real bos/eos tokens on both sides

**`src/ggufdoctor/checks/reference.py`**

- Imports `_with_real_tokens` from `checks/sanity.py` (same package) and
  applies it to the fixture context once, then renders **both** the GGUF
  and upstream templates from that same real-token context — never letting
  the engine's fabricated `BASE_CONTEXT` placeholder stand in for a real
  token on either side.
- New test `test_r001_uses_real_eos_token_not_fabricated_placeholder`
  reproduces the exact scenario the review described (GGUF inlines the real
  EOS literally, upstream still writes `{{ eos_token }}`) and asserts zero
  findings. A companion test,
  `test_r001_still_flags_a_genuine_eos_divergence`, guards against the fix
  overreaching — a real EOS mismatch between the two sides is still
  flagged.
- Existing reference tests are unaffected because they never set token
  metadata (`tokens=[]`, `bos_token_id=None`, `eos_token_id=None` by
  default), so `_with_real_tokens` is a no-op for them, exactly as before.

## 5. R001 whitespace-only divergence is now separated

**`src/ggufdoctor/checks/reference.py`**

Spec section 5 says whitespace-only differences must be separated from
semantic ones, but only lists ids R001–R004 for family R (unlike family X,
which has a dedicated X004 for this). Since finding ids are held fixed and I
can't mint a new one, I read this as: **same id, different severity and
message, evidence still shows the exact diff.**

- Added `_is_whitespace_only_diff(a, b)`: strips every whitespace run from
  both rendered strings and compares what's left. This catches not just
  leading/trailing differences but an inserted/dropped space *between*
  tokens — exactly the `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` case named
  in the spec's own motivation (`<s> [INST]` vs `<s>[INST]`).
- When the divergence is whitespace-only: severity **INFO** (one step below
  the WARN default, mirroring how X004 sits one step below X001), message
  `"rendered prompt differs from the upstream source model only in
  whitespace"`, and `evidence["whitespace_only"] = True`. The diff and
  `len_delta` evidence are still populated — the difference is reported
  honestly, never silenced, never called equivalent.
- When it changes actual content: unchanged behaviour (WARN, or INFO if
  R002-annotated), plus `evidence["whitespace_only"] = False` added for
  consistency.
- New tests: `test_r001_separates_whitespace_only_divergence_from_content_divergence`
  (reproduces the TheBloke-style single-space case) and
  `test_r001_content_divergence_is_not_marked_whitespace_only`.

**My ask:** confirm INFO is the right severity choice for whitespace-only
(vs. e.g. keeping it WARN but just tagging it, or some other treatment) —
this was a judgment call where the spec is silent on the exact severity.

## 6. Coverage gaps are now recorded everywhere they occur

**`src/ggufdoctor/checks/sanity.py`**

- **S004**: now appends `"S004"` to `ctx.checks_not_evaluated` when the
  template exists but `ctx.model.tokens` is empty (previously silent).
- **S006**: distinguishes `add_bos_token is None` (metadata genuinely
  absent — e.g. a remote org/repo target with no vocab at all) from
  `add_bos_token is False` (metadata confidently says the tokenizer does
  not add its own BOS). Only the former is now recorded as a coverage gap;
  the latter remains a correct no-op, unchanged. Previously both were
  silently treated as "doesn't apply."
- **S005, S006, S007**: each now records itself in `checks_not_evaluated`
  when a custom `--fixtures` corpus lacks the specific fixture it needs
  (`"multiturn"` for S005, `"user_only"` for S006/S007) — previously a
  silent `return []`.

Six new tests cover each of these paths directly.

### Test changes forced by item 6 (existing tests asserted the old, silent
behaviour — updated with justification, not just patched to pass)

- **`tests/test_checks_sanity.py::test_s006_not_recorded_when_add_bos_token_is_false`**
  — was actually exercising the *default* (`add_bos_token` unset → `None`),
  despite its name and comment claiming that was "False." Changed to pass
  `add_bos_token=False` explicitly, which is what the test name always
  claimed to test; the `None`/absent case now has its own new test
  (`test_s006_records_not_evaluated_when_add_bos_token_absent`).
- **`tests/test_checks_sanity.py::test_s005_records_not_evaluated_when_eos_id_missing`**,
  **`..._eos_id_out_of_range`**, **`..._negative_eos_id_takes_the_out_of_range_warn_path`**
  — none of these set `add_bos_token`, so under the fixed S006 logic they'd
  now *also* pick up an `"S006"` coverage gap, breaking their
  `checks_not_evaluated == ["S005"]` assertions. Added `add_bos_token=False`
  to isolate each test to the S005 behaviour it's actually testing (S006 is
  covered separately).
- **`tests/test_report.py::test_out_of_range_eos_token_id_records_s005_as_not_evaluated`**
  — same isolation fix (`add_bos_token=False` added), same reason.
- **`tests/test_cli.py::test_checks_not_evaluated_reaches_the_reports`** —
  the model built by `_model()` never sets
  `tokenizer.ggml.add_bos_token`, i.e. it's genuinely absent, which is
  exactly the real-world scenario item 6 is about. This test's assertions
  (`"S005 not evaluated" in human`, `checks_not_evaluated == ["S005"]`)
  encoded the *old, buggy* silence around S006 as expected behaviour.
  Updated to expect both: `"S005, S006 not evaluated"` in the human report,
  `checks_not_evaluated == ["S005", "S006"]` in the JSON.
- **`tests/test_cli.py::test_default_local_run_headline_is_not_alarming`** —
  same root cause: this test's whole point is asserting a fully-clean,
  unqualified "no findings" headline, but it never set `add_bos_token`
  either, so it would now (correctly) show a partial headline for the S006
  gap — which is precisely the bug this whole item exists to expose, not a
  false alarm. Added `tokenizer.ggml.add_bos_token: ("bool", False)` to the
  test's model so the scenario is genuinely fully covered (matching the
  test's stated intent: "the only thing missing is the upstream comparison
  the user never asked for").

### Test change forced by item 1 (S003 severity split)

- **`tests/test_engine_jinja2.py::test_render_error_is_captured_not_raised`**
  — asserted `r.error.startswith("render:")` for a template that calls
  `raise_exception(...)`. That is now precisely the case that must **not**
  get the `render:` prefix (that's the whole point of item 1). Replaced its
  body with a genuine engine failure (`{{ 1 / 0 }}`) so it still tests what
  its name says, and added a new test,
  `test_author_raised_exception_is_tagged_distinctly_from_engine_failures`,
  asserting the exact `raise:` contract that `checks/sanity.py` now relies
  on (`r.error == "raise:<exact author text>"`).

## Not touched

`survey.py`, `cli.py`, `hf.py`, `report/`, `corpus.json`, `.gitignore`,
`docs/`, `.superpowers/` — verified via `git diff --stat` against those
paths after the fix, all empty. All finding ids, `run_sanity_checks(ctx)`,
`run_reference_checks(ctx)`, and every `sNNN_*`/`rNNN_*` signature are
unchanged. No I/O or network added to any check; Jinja2 remains the only
runtime dependency.

## Nothing was left unfixed

All six items have code changes. The two open items above (Mistral/Llama-2
`add_bos_token` choice for item 3, and INFO severity choice for item 5) are
judgment calls the task explicitly asked to be routed back for a ruling
rather than resolved unilaterally — they are not unfinished work, the
current state is fully consistent and tested either way.

---

## Addendum (fix round 4): coordinator ruling applied

Coordinator ruled on both open items:

- **Item 5 (R001 whitespace-only)**: confirmed as-is — `R001` at INFO with
  `evidence["whitespace_only"]=True`, diff still shown. No change made.
- **Item 3 (real template `add_bos_token`)**: ruled that Mistral and
  Llama-2's tests must carry their genuine published `add_bos_token: true`
  (both confirmed live against `mistralai/Mistral-7B-Instruct-v0.2` and
  `meta-llama/Llama-2-7b-chat-hf` tokenizer_config.json), not the `False`
  I'd substituted to keep the assertion narrow. Also asked that Gemma-2 and
  Llama-3-tools be checked for any other stubbed (vs. genuine) metadata.

Applied:

- `tests/test_checks_sanity.py`: Mistral and Llama-2 tests now use
  `add_bos_token=True` (the real value) and assert the complete finding set
  each produces, including the resulting `S006 WARN` — the real,
  independently-documented llama.cpp "double BOS" footgun for both
  families (their templates each prepend `{{ bos_token }}` to output while
  metadata also says the tokenizer adds it). Renamed both tests
  (`..._matches_documented_real_world_footguns`) since "is clean apart
  from" was no longer accurate framing once S006 genuinely fires too.
- Audited Gemma-2 and Llama-3-tools for any other stand-in values:
  - **Gemma-2**: `bos_token_id=2`, `eos_token_id=1`, `add_bos_token=True`
    were already the genuine published values (cross-checked against
    `config.json`, `generation_config.json`, and `tokenizer_config.json`
    for `google/gemma-2-9b-it` via a public mirror) — no change needed.
  - **Llama-3-tools**: `bos_token_id`/`eos_token_id` were previously
    renumbered to small convenience indices (`0`/`2`) rather than Meta's
    real ids. Fixed to the genuine published ids —
    `bos_token_id=128000` (`<|begin_of_text|>`), `eos_token_id=128009`
    (`<|eot_id|>`), both confirmed against the live
    `config.json`/`generation_config.json`/`tokenizer_config.json` — using
    a sparse 128,011-entry vocab list with each real special token at its
    real numeric id (filler elsewhere; no check here ever indexes a filler
    slot). `add_bos_token=True` was already the genuine value.

### Complete real finding sets (final)

| Template | Complete finding set |
|---|---|
| Mistral-7B-Instruct-v0.2 | `S003 INFO`, `S006 WARN`, `S007 INFO` |
| Llama-2-7b-chat | `S006 WARN`, `S007 INFO` |
| Gemma-2-9b-it | `S003 INFO`, `S005 WARN`, `S006 WARN` (unchanged) |
| Llama-3.3-70B-Instruct (tools) | `S006 WARN` (unchanged; ids now genuine) |

All 142 tests still pass. New commit on top of `57f6f54`.
