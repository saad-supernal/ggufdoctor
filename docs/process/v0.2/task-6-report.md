# Task 6 report: Engine registry, `--engines`, X wiring, report provenance

Status: DONE

## Step 0: engine-neutral CHAT_TPL

### Which form worked, and why the brief's two candidates didn't

Neither of the brief's two candidate templates (the primary `is string` /
`elif ... is not none` form, nor its documented `is none` / `is mapping or
iterable` fallback) is actually byte-identical across engines. I verified
this empirically before writing any implementation code, by rendering all
ten corpus-v2 fixtures through a live `Jinja2Engine()` and a live
`LlamaCppEngine()` (wasmtime 48.0.0 + the pinned b10775 module — both
available in this venv) and diffing the outputs:

* Both brief templates matched byte-for-byte on 9/10 fixtures.
* Both mismatched on `typed_content`: jinja2 rendered
  `"...Hellothere<|im_end|>..."`, llama.cpp rendered
  `"...Hello\nthere<|im_end|>..."`.

Root cause, traced through `engine/build/llamacpp/jinja/caps.cpp` and
`engine/shim.cpp` (the vendored llama.cpp jinja engine and the WASM shim
around it):

1. llama.cpp's own caps probe (`caps_get`) decides whether a template
   "supports typed content" by rendering it once with `messages[0].content`
   set to a **plain string** (`"STRING_MARKER"`) and checking whether that
   value was ever touched via an array-style operation (`for` loop /
   indexing) during that single probe render.
2. Any template that tests `content is string` (or `is iterable`/`is
   mapping`) before doing array-style access will, when fed a *string* in
   the probe, take the string branch and never touch the array branch — so
   `used_as_array` is never set, and llama.cpp concludes the template is
   "string-content-only" (`supports_string_content=True,
   supports_typed_content=False`).
3. `shim.cpp`'s `normalize_messages` then pre-flattens any *list* content
   into a string via `concat_content_parts` **before the template ever
   renders it** — joining successive text parts with `"\n"`.
4. jinja2 (the transformers-reference engine) gets no such rewrite; it sees
   the fixture's real list and must handle it in the template's own array
   branch.

So for any is-string-first template, llama.cpp will always pre-join
`typed_content`'s two text parts with `"\n"` before rendering, while jinja2
renders whatever the template's own array-handling branch produces. The
brief's `{% for p in m['content'] %}{{ p['text'] }}{% endfor %}` has no
separator, so it can never match llama.cpp's `"\n"`-joined output — this
is a real, structural mismatch, not a mistake in either candidate's Jinja
syntax.

**Fix**: keep the brief's `is string` / `elif ... is not none` structure,
but make the array branch replicate llama.cpp's own `concat_content_parts`
join (all parts in this corpus are plain `"text"`-type, so a straight
`join('\n')` over the parts' text is the correct mirror):

```python
CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n"
            "{% if m['content'] is string %}{{ m['content'] }}"
            "{% elif m['content'] is not none %}"
            "{{ m['content'] | map(attribute='text') | join('\n') }}"
            "{% endif %}<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")
```

`tool_roundtrip`'s null assistant content already matched under both
candidates (`None` is never string/array-normalised, so both engines print
nothing for it either way) — no change needed there.

### Byte-equality check performed

Verified with a one-off script (`/private/tmp/.../scratchpad/step0_probe.py`
and `step0_probe2.py`, not committed) rendering all 10 corpus-v2 fixtures
through both engines under two separate metadata configurations:

1. `tests/test_checks_sanity.py`'s `ctx()` config (tokens `<unk>,<s>,</s>`,
   `bos_token_id=1, eos_token_id=2, add_bos_token=False`) — **all 10 match
   byte-for-byte**.
2. `tests/test_cli.py`'s `_model()` config (tokens
   `<|im_start|>,<|im_end|>` only) — **all 10 match byte-for-byte**.

This is the same final template installed in both test files.

### Expectations re-derived in test_checks_sanity.py

None needed changing. I walked every `CHAT_TPL`-using assertion in
`tests/test_checks_sanity.py` against the new template's *single-engine*
(jinja2-only, since `ctx()` only ever constructs `Jinja2Engine()`)
rendering behaviour:

* S004 scans the template's literal source text via regex, not rendered
  output — the control-flow rewrite doesn't touch the literal
  `<|im_start|>`/`<|im_end|>` text, so every S004 test is unaffected.
* `test_clean_template_produces_no_findings` (`f == []`) — walked S001–S008
  by hand: no fixture raises under jinja2 with the new template (null
  content renders as nothing instead of the old template's literal
  `"None"`; list content renders via the new `map|join`), S005/S006 are
  coverage gaps (not findings) since this test's `ctx()` call sets no
  eos/bos metadata, S007 still differs on/off because of the trailing
  `<|im_start|>assistant\n` suffix. Still `[]`.
* Every other `CHAT_TPL` use (S005/S006/S007 "not evaluated" tests) only
  cares about a named fixture's *presence*, not what it renders to.

Ran `tests/test_checks_sanity.py` and `tests/test_cli.py` right after the
Step-0 edit, before touching anything else: 55/55 passed unchanged,
confirming this empirically rather than just by inspection.

## `tests/test_cli.py::_model()` — one deviation from the brief's literal test code, and why

The brief's literal `test_engines_flag_subsets_without_recording_a_gap`
asserts `"partial" not in out` for a bare `_model(tmp_path)` run. The
existing `_model()` (pre-Task-6) never set `eos_token_id` or
`add_bos_token`, so **every** run through it — regardless of `--engines` —
already reported `"partial: S005, S006 not evaluated"` (this is exactly
what the pre-existing `test_checks_not_evaluated_reaches_the_reports`
pins down). That pre-existing gap made the brief's new assertion
unsatisfiable as literally written against the old `_model()` defaults.

Fix: `_model()` now defaults to `eos_token_id=1` (`"<|im_end|>"`, which
`CHAT_TPL` does emit every turn) and `add_bos_token=False` (`CHAT_TPL`
never emits `bos_token`, so this only settles S006 into its documented
no-op path) — the exact pair `test_default_local_run_headline_is_not_alarming`
already independently established produces a clean, gap-free run. This
gives every Task-6 CLI test (which key on the presence/absence of
`"partial"` to isolate what `--engines` itself does) a clean baseline.

Collateral fix: `test_checks_not_evaluated_reaches_the_reports` specifically
exercises the *missing*-metadata coverage-gap path, so it now builds its
GGUF directly (bypassing `_model()`) with exactly the old bare fields,
preserving its original scenario and assertions unchanged. All other
existing `_model()`-based tests were checked individually (see commit diff
comment in `_model()`) and are unaffected — either they already override
these two fields with the same values, or they don't depend on S005/S006's
finding/gap status at all.

## TDD evidence

1. Added `tests/test_registry.py` (verbatim from the brief) and the
   Task-6 additions to `tests/test_cli.py` / `tests/test_report.py`
   (verbatim from the brief, `test_cli.py`'s two data-metadata deviation
   above being the exception).
2. RED: `pytest tests/test_registry.py tests/test_cli.py tests/test_report.py`
   failed at collection (`ImportError: cannot import name 'registry'`)
   before any implementation existed.
3. Implemented `src/ggufdoctor/engines/registry.py` (verbatim from the
   brief) and the two `Coverage` fields in `models.py` — reran
   `test_registry.py` alone: 5/5 GREEN.
4. Wired the CLI (`--engines` flag, `select_engines`, family-X gating per
   ruling R3, `families_run.insert`) and both report renderers
   (`ALL_FAMILIES`, `_engine_label`/`_engine_entry`, unavailable line,
   agreement line, JSON `commit`/`backend`/`engines_unavailable`/
   `engines_agreed_fixtures`).
5. GREEN: `pytest tests/test_registry.py tests/test_cli.py tests/test_report.py
   tests/test_checks_sanity.py` — 77/77 passed (after the one `_model()`
   fix above; before that fix, exactly 1 failure:
   `test_engines_flag_subsets_without_recording_a_gap`, root-caused and
   fixed as described).
6. Full suite: `pytest -q` — 230/230 passed (219 baseline + 5 registry +
   5 new CLI + 1 new report test).

## Manual verification (beyond the test suite)

Ran the installed `ggufdoctor` entry point directly against a real built
GGUF to eyeball exact report formatting:

```
$ ggufdoctor m.gguf
m.gguf  [llama]  engines: jinja2 3.1.6, llama.cpp b10775 (67a17c17, wasmtime 48.0.0)

  no findings — local checks only (add --compare-upstream <repo> to also check against the source template)
  engines agree: jinja2 and llama.cpp rendered 10 fixtures identically

0 error, 0 warn, 0 info
families run: S, X   upstream: not_requested
```

```
$ ggufdoctor m.gguf --engines jinja2,minja
ggufdoctor: unknown engine 'minja' (choose from jinja2, llama.cpp)
```
(exit 2, single line, no traceback)

Unavailable-engine scenario (monkeypatched `registry._construct`):

```
m.gguf  [llama]  engines: jinja2 3.1.6
  llama.cpp unavailable — wasmtime not importable: boom

  no findings (partial: X001, X002, X004, X005 not evaluated)
0 error, 0 warn, 0 info
families run: S   upstream: not_requested
  note: X001 not evaluated
  note: X002 not evaluated
  note: X004 not evaluated
  note: X005 not evaluated
```

JSON provenance for the default run:

```json
"engines": [
  {"name": "jinja2", "version": "3.1.6"},
  {"name": "llama.cpp", "version": "b10775",
   "commit": "67a17c17caa95742186f8b1ecadd1b5abd6d5ebb",
   "backend": "wasmtime 48.0.0"}
],
"coverage": {
  "upstream": "not_requested", "families_run": ["S", "X"],
  "checks_not_evaluated": [], "engines_unavailable": {},
  "engines_agreed_fixtures": 10
}
```

All of this matches the brief's Interfaces section exactly, including the
`llama.cpp b10775 (67a17c17, wasmtime 48.0.0)` label format.

## Files changed

- Created: `src/ggufdoctor/engines/registry.py` (verbatim from the brief)
- Created: `tests/test_registry.py` (verbatim from the brief)
- Modified: `src/ggufdoctor/models.py` (`Coverage.engines_unavailable`,
  `Coverage.engines_agreed_fixtures`)
- Modified: `src/ggufdoctor/cli.py` (`--engines` flag, `select_engines`
  wiring, family-X gating, removed the now-unused `Jinja2Engine` import)
- Modified: `src/ggufdoctor/report/human.py` (`ALL_FAMILIES`,
  `_engine_label`, unavailable line, agreement line)
- Modified: `src/ggufdoctor/report/json_report.py` (`_engine_entry`,
  `coverage.engines_unavailable`/`engines_agreed_fixtures`)
- Modified: `tests/test_cli.py` (engine-neutral `CHAT_TPL`, `_model()`
  default metadata, `test_checks_not_evaluated_reaches_the_reports`
  rebuilt to bypass `_model()`, five new Task-6 tests)
- Modified: `tests/test_checks_sanity.py` (engine-neutral `CHAT_TPL` only —
  no expectation changes needed)
- Modified: `tests/test_report.py` (one new Task-6 test)

## Self-review

Completeness — checked against the brief's Interfaces section and the
task's self-review checklist:

- [x] `registry.ENGINE_NAMES`, `EngineSelection`, `select_engines` — all
  five `test_registry.py` cases pass, including the unavailable/declined
  distinction (ruling R3).
- [x] `--engines NAMES` CLI flag, comma-split, jinja2-always-included.
- [x] `Coverage.engines_unavailable` / `engines_agreed_fixtures` — present,
  wired through both report renderers.
- [x] JSON `engines[]` entries gain `commit`/`backend` only when present
  (jinja2's entry stays a plain `{name, version}` — verified above).
- [x] `coverage.engines_unavailable` / `engines_agreed_fixtures` in JSON.
- [x] Human report engine line format
  `llama.cpp b10775 (67a17c17, wasmtime 48.0.0)` — verified manually,
  matches the brief exactly (8-char commit prefix + backend string).
- [x] `llama.cpp unavailable — <reason>` line — verified manually and by
  test.
- [x] `engines agree: ...` line only when `"X" in families_run` and
  `engines_agreed_fixtures is not None` — verified by
  `test_human_report_prints_agreement_line_only_when_x_ran` and manually.
- [x] `ALL_FAMILIES = ["S", "X", "R"]`.
- [x] Unknown engine → one-line `ggufdoctor: ...` on stderr, exit 2, no
  traceback (verified manually: `err.count("\n") == 0` for the raw
  message, and the existing `test_unwritable_json_path_exits_two_without_
  traceback` pattern already pins the general "one-line, no traceback"
  contract for this except block).
- [x] `Jinja2Engine` import removed from `cli.py`.
- [x] `families_run` gets `"X"` inserted after `"S"` (not appended) — verified
  both by test and manually (`families run: S, X   upstream: not_requested`).
- [x] R3 ruling: a user-requested `--engines jinja2` subset never calls
  `run_cross_engine_checks` and records nothing in
  `checks_not_evaluated`/`families_run`/`engines_unavailable` — verified
  by `test_engines_flag_subsets_without_recording_a_gap` and by reading
  `select_engines`'s `ordered = [n for n in ENGINE_NAMES if n in names]`
  (llama.cpp is never even constructed for an explicit `["jinja2"]`
  request, so it can't land in `unavailable`).

Quality / testing — full suite green (230/230), targeted re-runs green at
each TDD step, manual CLI runs cross-checked against the JSON output for
the same run.

## Concerns

One pre-existing, out-of-scope wrinkle I found but did not fix (the brief
explicitly says "Do not restructure anything else" and no test — brief's
or existing — exercises this combination):

`human.py`'s "family skipped" note (`if upstream_gap is not None: for fam
in skipped: ...`) predates Task 6 and assumes every family absent from
`coverage.families_run` is absent *because* the upstream comparison failed
— true before this task, since only R could ever be conditionally skipped
that way. Adding `"X"` to `ALL_FAMILIES` (as the brief specifies verbatim)
means that if a user runs `--engines jinja2 --compare-upstream <gated
repo>`, the report prints both `note: X family skipped` and `note: R
family skipped` — but X was *declined* by the user's own `--engines`
choice, not blocked by the failed upstream comparison. This conflates a
decline with a genuine gap in exactly the way ruling R3 says never to do,
though only in this one cosmetic "note" line (never in the `partial`
headline, `checks_not_evaluated`, or JSON — those all correctly treat the
subset as a decline). Confirmed by direct call:

```
render_human(model, [], [], Coverage(upstream="gated", families_run=["S"]), [Jinja2Engine()])
```
prints `note: X family skipped` alongside `note: R family skipped`, purely
from `Coverage.families_run` lacking `"X"` — with no information at that
call site about *why* X is absent (declined vs. unavailable vs. never
attempted). Fixing this correctly would need `render_human` to distinguish
"X declined by --engines" from "X blocked by something else," which the
brief doesn't ask for and which isn't visible from `Coverage` alone; I've
flagged it here rather than improvising a fix beyond the brief's scope.

---

## Fix round 1

Coordinator review approved the registry/CLI/report wiring and the Step 0 /
`_model()` corrections, and asked for two fixes:

### 1. Important — R4: "family skipped" note conflated decline with gap

**Problem** (my own concern 3 from the original report): `human.py`
computed `skipped = [fam for fam in ALL_FAMILIES if fam not in
coverage.families_run]` and printed a `note: {fam} family skipped` line
for every entry, gated only on `upstream_gap is not None`. Since `"X"` is
now in `ALL_FAMILIES`, a user-declined `--engines jinja2` subset combined
with a failed `--compare-upstream` produced `note: X family skipped` even
though X was never a gap — the user chose not to run it.

**Fix**: replaced the `ALL_FAMILIES`-minus-`families_run` computation with
a new `_skipped_families(coverage)` helper (`src/ggufdoctor/report/
human.py`) that checks each family's own genuine-gap condition directly,
per controller ruling R4:

* `"R"` is reported only when `_upstream_gap(coverage.upstream) is not
  None and "R" not in coverage.families_run` (unchanged from before —
  this was already correct for R).
* `"X"` is reported only when `coverage.engines_unavailable` is non-empty
  and `"X" not in coverage.families_run` — i.e. only when the *default*
  engine selection actually failed to construct an engine, never for a
  user's own `--engines` choice (which leaves `engines_unavailable`
  empty by construction — see `registry.select_engines`).
* `"S"` was never a candidate before and still isn't; the helper doesn't
  iterate `ALL_FAMILIES` at all, precisely so a family's presence in that
  list can never by itself imply "missing == skipped".

No new `Coverage` field was added — `engines_unavailable` already carried
everything the R4 condition needs. `ALL_FAMILIES` is left defined (Task 6
required it and nothing outside `_skipped_families` depended on the old
computation), though it's no longer consulted by this logic.

Added two tests to `tests/test_report.py`:

* `test_family_skipped_note_never_fires_for_a_declined_engine` —
  `Coverage(upstream="gated", families_run=["S"])` (empty
  `engines_unavailable`, the default) → `"R family skipped"` present,
  `"X family skipped"` absent.
* `test_family_skipped_note_fires_for_x_when_an_engine_is_unavailable` —
  same coverage plus `engines_unavailable={"llama.cpp": "boom"}` →
  `"X family skipped"` present.

Verified manually too:

```
>>> render_human(model, [], [], Coverage(upstream="gated", families_run=["S"]), [Jinja2Engine()])
...
families run: S   upstream: gated
  note: R family skipped
>>> render_human(model, [], [], Coverage(upstream="gated", families_run=["S"], engines_unavailable={"llama.cpp": "boom"}), [Jinja2Engine()])
...
families run: S   upstream: gated
  note: X family skipped
  note: R family skipped
```

### 2. Minor — re-derived S00x rationale missing from the test file itself

Added a comment block directly above the test functions in
`tests/test_checks_sanity.py` (right after the `CHAT_TPL` definition),
stating per finding family why the existing expectations still hold under
the engine-neutral template, based only on facts already verified while
doing Step 0 (not new claims):

* S001/S002 — don't touch content-handling logic at all; template still
  compiles.
* S003 — no fixture newly raises or stops raising under jinja2 (null
  content renders as nothing instead of literal `"None"`; list content
  renders via `map|join` instead of a list `repr()`; neither is a
  failure); `test_clean_template_produces_no_findings` reran and still
  returns `[]`.
* S004 — scans literal template source via regex, never rendered output;
  the literal `<|im_start|>`/`<|im_end|>` text is byte-for-byte unchanged.
* S005/S006 — both compare against `multiturn`/`user_only`, which carry
  only plain string content and so take the unchanged `is string` branch
  under both the old and new template.
* S007 — depends only on the unchanged trailing
  `{% if add_generation_prompt %}...{% endif %}` fragment.
* S008 — every fixture still emits the literal `<|im_start|>{role}\n` /
  `<|im_end|>\n` wrapper regardless of content handling, so no render
  becomes (or stops being) empty.

## Re-run of covering tests

* `pytest tests/test_report.py tests/test_cli.py tests/test_checks_sanity.py -q`
  → 74 passed (72 pre-existing across these three files + 2 new R4 tests).
* Full suite: `pytest -q` → 232 passed (230 + 2 new tests).

## Files changed in this fix round

* `src/ggufdoctor/report/human.py` — `_skipped_families` helper replacing
  the `ALL_FAMILIES`-based computation; no new `Coverage` field.
* `tests/test_report.py` — two new tests for R4.
* `tests/test_checks_sanity.py` — comment block re-deriving S00x
  expectations next to `CHAT_TPL`; no behavioural change.

## Concerns

None new. The concern raised in the original report is resolved by this
fix.
