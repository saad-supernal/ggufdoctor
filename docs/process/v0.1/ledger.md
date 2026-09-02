# SDD ledger — plan: docs/superpowers/plans/2026-08-31-ggufdoctor-v0.1.md

Spec: docs/superpowers/specs/2026-08-31-ggufdoctor-design.md (read, reachable)
Branch: feat/v0.1
MERGE_BASE: 36611bb1abf238659db25fcb46a6663d8fad6bde
Note: TodoWrite unavailable in this session — this ledger is the sole progress record.

## Pre-flight scan

### Cross-task pairs (shared file or interface)

| Pair | Produces → consumes | Finding |
|---|---|---|
| T2 → T4 | `bytesource.py` created, then appended | clean (append-only, T2 tests untouched) |
| T1 → T3,5,6,8,10,11 | `models.py` value types | clean (names consistent across all consumers) |
| T2 → T3 | `Cursor`, `LocalByteSource`, `TruncatedError` | clean |
| T3 → T4,T11 | `read_gguf`, `read_gguf_file`, `NotGgufError` | clean |
| T5 → T6,T8,T10,T12 | `Jinja2Engine`, `load_fixtures`, `CORPUS_VERSION` | clean |
| T6 → T11 | `run_sanity_checks(ctx)` | clean |
| T7 → T11,T12 | `HfClient.model_info/base_model_of/upstream_template` | clean (tuple return honoured by both) |
| T7 → T12 | `hf.py` created, then `list_gguf_models` appended | clean (T7 tests untouched) |
| T8 → T11,T12 | `run_reference_checks(ctx)` | clean |
| T9 → T11 | `load_ignores`, `apply_ignores` | clean |
| T10 → T11 | `render_human`, `build_json`, `exit_code` | clean (arg order matches call site) |
| T11 → T12 | `cli.main` created, then restructured | **F4** (prose-only rewrite step) |
| T2 → T3,4,6,11,12 | `tests/helpers/gguf_builder` imported as `tests.helpers.…` | **F1** (blocking) |

### Per-task self-agreement

| Task | Finding |
|---|---|
| T1 | clean — mutable-default test matches `field(default_factory=dict)`; `Finding` correctly not frozen |
| T2 | **F1** — creates `tests/helpers/__init__.py` but not `tests/__init__.py` |
| T3 | clean — tokens-excluded-from-metadata test matches implementation |
| T4 | clean — `bytes_fetched` asserted and implemented |
| T5 | **F2** — `resources.files("ggufdoctor.fixture_data")` needs that dir to be a package; **F5** redundant force-include |
| T6 | **F3** — Interfaces block names `CHAT_ARCHITECTURES`, never defined or used |
| T7 | clean — every reason string in tests is produced by the implementation |
| T8 | clean — R002 downgrade path and the no-R001 filter agree with tests |
| T9 | clean |
| T10 | clean — `datetime.UTC` requires 3.11, matches Global Constraints |
| T11 | clean — `is_repo_id` returns correct values for all three test inputs |
| T12 | clean — weighting arithmetic verified: 100/(100+50+10) = 62.5% matches test |

### Rulings (pre-flight)

- **Ruling: F1 — Task 2 must also create an empty `tests/__init__.py`.** Without it
  pytest inserts `tests/` on sys.path rather than the repo root, so
  `from tests.helpers.gguf_builder import build_gguf` fails in Tasks 3, 4, 6, 11
  and 12. Spec is silent; this is a plan defect. Cost if wrong: an unnecessary
  empty file.
- **Ruling: F2 — Task 5 must also create an empty
  `src/ggufdoctor/fixture_data/__init__.py`.** `importlib.resources.files()`
  requires an importable package. Cost if wrong: an unnecessary empty file.
- **Ruling: F3 — drop `CHAT_ARCHITECTURES` from Task 6's interface list.** Only
  `NON_CHAT_ARCHITECTURES` is used; the check inverts it. Cost if wrong: a later
  task expecting that name must define it (no consumer does).
- **Ruling: F4 — Task 12's implementer must rewrite `cli.py` in full rather than
  follow the prose rename.** The step describes the change without showing the
  resulting file, the one place the plan violates its own no-placeholder rule.
  Cost if wrong: none; a full rewrite is strictly safer than a prose-guided edit.
- **Ruling: F5 — drop the `force-include` block from Task 5's pyproject edit.**
  Hatchling already ships non-Python files inside `packages`; the extra block
  risks double-inclusion. Cost if wrong: fixture corpus missing from a built
  wheel — caught immediately by `test_fixtures.py` against an installed package.

## Progress

PAUSED before Task 1 dispatch at user request (context reset).
- Task 1 brief already generated: task-1-brief.md
- BASE for Task 1 = 36611bb (note: 70a00eb landed after, docs only —
  re-read `git rev-parse HEAD` as BASE when resuming)
- 0 of 12 tasks implemented. No source code exists.
- Resume: read NEXT-SESSION.md, then this ledger's rulings, then dispatch Task 1.

## Resumed 2026-08-31 (after context reset)

- BASE re-recorded: a986a3c (was 36611bb; 70a00eb docs + a986a3c gitignore landed since)
- **Ruling: E1 — toolchain.** Repo had no venv and system python is 3.9.6, below the
  plan's >=3.11 floor. Created `.venv` with `uv venv --python 3.14` (CPython 3.14.6),
  installed pytest 9.1.1, added `.venv/` to .gitignore (commit a986a3c). Every task
  runs `.venv/bin/python -m pytest` and installs with
  `uv pip install --python .venv/bin/python -e .`. Cost if wrong: a rebuilt venv.
- Task 1 dispatched.
- Task 1: complete — commit 013b7df. 4/4 tests pass. Review: spec APPROVED, quality
  APPROVED (reviewer mutation-tested the mutable-default assertion and confirmed the
  editable install + console script resolve correctly). F1 satisfied: tests/__init__.py
  created in Task 1 rather than Task 2.
- Task 2: complete — commit 7b85f65. 6/6 tests pass. Review: spec APPROVED (every
  struct format string uses explicit `<`; type enum matches), quality APPROVED with
  one observation.
- **Ruling: E2 — close the build_gguf coverage gap in Task 3, not Task 2.** The
  reviewer noted Task 2's two tests never call `build_gguf`, so nothing in-repo proves
  the builder and `Cursor` agree on layout — the reviewer verified it ad hoc and it
  holds. Rather than reopen Task 2, Task 3's implementer adds one extra test that
  round-trips every supported type name (`string,u32,u64,bool,array_string,f32`)
  through `build_gguf` -> `read_gguf`. That is where the agreement is load-bearing.
  Cost if wrong: one redundant test.
- Task 3: complete — commit ed9a3e1. 11/11 tests pass. Review: spec APPROVED (key
  mapping and the tokens-excluded rule verified line by line; no file/network I/O
  outside `read_gguf_file`), quality APPROVED — reviewer hand-checked byte consumption
  for all 13 GGUF value types incl. nested arrays and found every one correct. E2's
  round-trip test lands and is the only coverage of u64/f32.
- **Ruling: E3 — accept the 7 untested value types.** `build_gguf` emits 6 of the 13
  types, so UINT8/INT8/UINT16/INT16/INT32/INT64/FLOAT64 and non-string arrays are
  hand-verified but untested. Widening the builder buys no linting behaviour — these
  types are skipped, never interpreted. Parked, not fixed. Cost if wrong: a mis-sized
  skip on an exotic key desyncs the cursor; would surface as a parse failure on a real
  file, which the survey corpus in v0.2 will catch.
- Task 4: review round 1 — spec APPROVED, quality CHANGES REQUESTED. Two linked
  findings, both originating in the brief's own code, both confirmed empirically:
  (a) when a server ignores `Range` and answers 200 with the whole body, `read()` at
  any nonzero offset silently returns bytes from the start of the file — reviewer
  reproduced wrong bytes at offset 500; (b) the test's `SimpleHTTPRequestHandler`
  does not implement byte ranges at all, so the suite never exercises a 206 and
  `bytes_fetched < 3_000_000` passes for an implementation that sends no `Range`
  header whatsoever (reviewer proved this with a NaiveByteSource). Stderr noise
  root-caused as benign server-side BrokenPipeError, an artifact of (b).
- **Ruling: E4 — blocking; fix both in Task 4 rather than parking.** A real GGUF
  header exceeds the 1 MB cursor chunk whenever the token array is large (100k+
  tokens is normal), so nonzero-offset remote reads are the common case, not an edge
  case — silent wrong bytes there would corrupt the metadata the whole tool reasons
  about. And the efficiency assertion is the tool's headline claim; a vacuous version
  of it is worse than none. Fix: reject 200-without-Content-Range at nonzero offset
  with `HttpSourceError`, and give the fixture a range-aware handler so the 206 path
  is genuinely covered. Cost if wrong: a stricter remote client that refuses a
  non-range-compliant host instead of silently misreading it — the correct trade.
- Task 4 fix round 1 — commit e30ca7e, 15/15 pass. Re-review: Finding A RESOLVED
  (206 good path; 200 accepted only at offset 0 and capped; 200 at nonzero offset
  raises `HttpSourceError` naming the URL — verified against a real 206 with correct
  `Content-Range`). Finding B **NOT RESOLVED**: reviewer re-ran the falsification and
  a range-ignorant `NaiveByteSource` still measures 1,048,576 bytes and still passes
  the tightened `< 2_000_000` threshold. Root cause: `bytes_fetched` counts bytes the
  *client consumed*, which is one `Cursor.CHUNK` either way; it cannot see what the
  server put on the wire. New observations, both non-blocking: the remaining stderr
  line is a `BrokenPipeError` from the deliberately non-range-aware test closing
  early, and the 0.08s->1.63s runtime is `socketserver`'s 0.5s `poll_interval` on
  fixture teardown, now paid four times instead of two — not the 5 MB body.
- **Ruling: E5 — fix round 2 instruments the server, not the client.** The efficiency
  claim can only be falsified from the serving side, so the range-aware handler
  records each request's `Range` header and the byte count it wrote, and the test
  asserts every request carried a `Range`, every response was 206, and total bytes
  *sent* stayed small. A source that ignores ranges then fails on both counts.
  Cost if wrong: a slightly more elaborate test fixture.
- Task 4 fix round 2 — commit 07bc0d7, 15/15 pass. Server-side instrumentation added;
  the efficiency test now asserts every request carried a `Range`, every response was
  206, and total bytes *written by the server* stayed under 2 MB. I re-ran the
  falsification myself: a `NaiveByteSource` does fail the test, but by an accidental
  route — `request_log.append` sits *after* `self.wfile.write(...)` on both paths
  (tests/test_http_range.py:79-85), so the naive client's connection reset kills the
  write and the record is never appended. The log comes back empty and it is the
  `len(log) > 0` guard that fires, not the Range/206/bytes assertions the test is
  written around.
- **Ruling: E6 — fix round 3, move the record ahead of the body write.** The test
  already fails for a range-ignorant source, so this is not a correctness gap; it is
  a test that would report the wrong reason and would stop failing at all if the
  naive client happened to drain the body first. Record before writing on both paths.
  Cost if wrong: none — strictly more deterministic.
- Task 4: complete — commit 8a71217. 15/15 pass. Fix round 3 was a 4-line move of the
  record ahead of the body write on both paths; the naive source now logs
  `{'range_header': None, 'bytes_written': 5000184, 'status': 200}` and the test fails
  on the Range assertion, as intended. Findings A and B both resolved. Two parked
  non-blocking artefacts: one benign BrokenPipeError stderr line from the
  non-range-aware test, and ~1.5s suite runtime from socketserver's teardown poll.
- Task 5: review round 1 — spec APPROVED (all seven fixtures byte-for-byte; ruling F5
  independently confirmed by building a real wheel and importing it from an isolated
  venv outside the source tree), quality APPROVED-with-findings. Never-crash guarantee
  verified empirically across syntax errors, undefined vars, unknown filters,
  `raise_exception`, runaway recursion, a billion-iteration range and a sandbox escape
  — all return clean RenderResults, none escape or hang.
- **Ruling: E7 — the four engine-fidelity gaps are blocking, on spec grounds.**
  Spec section 9 states plainly: "Jinja2: native Python — exact by construction; this
  is the transformers reference." The reviewer compared against an installed
  transformers and showed it is not: we set `trim_blocks`/`lstrip_blocks` False where
  transformers sets both True; we omit `jinja2.ext.loopcontrols`, so a template using
  `{% break %}` fails to *compile*; we omit the `{% generation %}` extension, same
  failure; and our `tojson` swallows kwargs, defaulting `ensure_ascii=True` where
  transformers defaults False and ignoring `indent=`/`sort_keys=`.
  The middle two are the serious ones: a linter that reports a valid template as
  broken is worse than no linter. The `tojson` gap lands squarely on the tool-calling
  path, which is where 14 of the 16 divergent repos in our own survey diverge, so it
  could manufacture or mask the exact finding the project is built on. The spec is
  the binding authority and it is unambiguous here. Fix in Task 5.
  Cost if wrong: an engine that tracks transformers more closely than v0.1 strictly
  needed. Note for v0.2: once the survey runs on the real engine, the published 15.1%
  should be regenerated — divergence is a diff of two renders through the same engine
  so the figure should be stable, but that must be shown, not assumed.
- Task 5: complete — commit 592afda. 30/30 pass. Fix round 1 re-review: A/B/C/D all
  RESOLVED, each verified by rendering the same template through both our engine and a
  real transformers-compiled environment (transformers 5.14.0) and comparing strings
  byte-for-byte. Never-crash contract re-verified incl. two sandbox-escape payloads,
  both refused. `corpus.json` confirmed byte-identical to before the fix.
  Two deliberate deviations from transformers, both judged right: `strftime_now` is
  pinned to 2026-01-01 for reproducibility (cost: date-dependent template branches are
  unreachable by this tool), and `{% generation %}` renders its body without tracking
  span indices (no v0.1 consumer).
- **Carry into Task 6:** `BASE_CONTEXT` supplies placeholder `bos_token=<s>`,
  `eos_token=</s>`, `unk_token`, `pad_token` and is overridden by the caller's context
  (`dict(BASE_CONTEXT); ctx.update(context)` — caller wins, verified). Task 6's token
  checks must pass the *model's real* tokens into the render context; if they don't,
  they will silently validate against these fabricated placeholders and pass.
- Task 6: review round 1 — spec APPROVED (byte-identical to the brief; S001-S008 ids,
  severities and messages intact; `CHAT_ARCHITECTURES` correctly absent per F3; the
  BASE_CONTEXT trap confirmed clean — no check reasons about rendered token text).
  Quality CHANGES REQUESTED, four findings, all originating in the brief's own code.
- **Ruling: E8 — S005 is blocking and the S-family's source-scanning approach must
  change.** S005 asks whether the literal EOS *string* appears in the template
  *source*. But the standard convention is to emit EOS through the `{{ eos_token }}`
  variable precisely so one template works across checkpoints. The reviewer ran the
  real Mistral-7B-Instruct-v0.2 and Llama-2-chat templates through it: both are
  flagged, and both demonstrably emit `</s>` correctly at render time. The checks
  that pass (ChatML, Llama-3, Gemma) pass only because their authors happened to
  hardcode the marker. So the check is not measuring what it claims, and it misfires
  across one of the largest model families on HuggingFace. A linter that accuses
  working models is worse than no linter — this cannot ship.
  Same root cause in S006 (substring `bos_token` in source, so a comment explaining
  *why* BOS is deliberately omitted gets flagged as adding BOS) and S004 (literals
  inside `{# #}` comments and untaken `{% if %}` branches). All three are asking the
  source text a question only a render can answer.
  Fix: render with the model's *real* tokens injected and inspect the output. This is
  the carry-forward from Task 5 arriving with its use case — the checks may now put
  real `bos_token`/`eos_token` into the render context, which is what makes the
  rendered text trustworthy to match against.
  Cost if wrong: three checks that need a successful render to fire, so they go quiet
  on templates that do not compile — acceptable, since S002/S003 already report that.
- **Ruling: E9 — dedupe the fixture fan-out.** One unconditionally broken template
  currently yields seven identical S003 findings, one per fixture, and up to fourteen
  with S008. The spec has an explicit noise-control philosophy; finding-count must
  track defect-count. Collapse per (check id, error signature), naming the affected
  fixtures in evidence. Also skip S004/S006 when S002 fired — a template that does
  not parse cannot meaningfully be asked what it emits.
- Fix dispatched to a fresh implementer on a more capable model: this is redesign,
  not transcription, so the escalation rule applies rather than resuming the
  transcribing agent.
- Task 6: complete — commit e592b98. 50/50 pass. Fix round 1 re-review: all six
  required changes RESOLVED. Critically, the reviewer confirmed each redesigned check
  was *fixed*, not silenced — Mistral-7B-Instruct-v0.2 and Llama-2-chat now pass S005
  and were independently re-rendered to show `</s>` really does appear, while a
  template that genuinely never emits EOS still fires. Same true-positive evidence for
  S004 and S006. The one changed test (`test_s006_double_bos`) was judged strictly
  more faithful than the original, whose premise was the bug itself.
- **Ruling: E10 — two observations parked for Task 10/11, not fixed here.**
  (a) S005/S006 now return `[]` both when the template is clean and when the check was
  not evaluable (missing or out-of-range bos/eos id). The `Coverage` dataclass exists
  for exactly this; Task 10's reporting must distinguish "checked, clean" from "not
  evaluated" or a report will claim clean when it means silent. (b) S008 collapses on
  a constant signature, so two unrelated branches that both render empty become one
  finding — Task 10 should carry the rendered text's repr in evidence. Neither belongs
  in the checks layer. Cost if wrong: a report that overstates coverage — which is why
  (a) is written into the Task 10 dispatch rather than left to memory.
- Task 7: review round 1 — spec APPROVED (byte-identical; five reason strings intact,
  no sixth; token confirmed header-only and absent from URLs, logs, exceptions and
  return values; `list_gguf_models` correctly absent). Quality CHANGES REQUESTED, one
  blocking defect. The three-way confusion this task exists to prevent is correctly
  resolved — gated / not_found / genuinely_absent were constructed and produce three
  distinct reasons, and a status-less `URLError` lands on `fetch_error` rather than
  `genuinely_absent`. Reviewer verified network isolation by collecting with the
  marker filter disabled: 59 either way, so nothing is being hidden by `addopts`.
- **Ruling: E11 — fix the escaping AttributeError.** `data.get("chat_template")` sits
  outside the try, so a 200 whose body is valid JSON but not an object (`[1,2,3]`, or
  a bare string) raises `AttributeError` straight out of `upstream_template`,
  violating the "network failures are values, not exceptions" constraint. Narrow, but
  it is the one contract this module has, and a survey run over hundreds of repos is
  exactly where a malformed body turns up. Classify non-dict JSON as `fetch_error`.
  Cost if wrong: none.
- Task 7: complete — commit d218740. 63/63 pass. Fix round 1 verified directly by me
  rather than by another review pass: `[1,2,3]`, a bare JSON string, unparseable text
  and `null` all now return `(None, 'fetch_error')` from `upstream_template` and
  `None` from `gguf_chat_template`, with nothing escaping.
- Task 8: review round 1 — spec APPROVED (byte-identical; R001-R004 ids, severities
  and messages intact; no I/O — imports only difflib, re and models). Quality CHANGES
  REQUESTED. The highest-risk item passed: both sides render through the same engine
  with a freshly built context each call, verified by construction — an
  engine-compatibility-only edit (`messages[0]` -> `messages|first`, no-op trim
  markers) produces zero R001, while a genuine one-character output change fires on
  all seven fixtures. All four render-failure combinations produce no finding rather
  than a fabricated divergence, `with_tools` reaches the comparison, and `gated` never
  masquerades as divergence or as upstream-missing.
- **Ruling: E12 — two blocking defects, both from the brief's own code, both fix now.**
  (a) `INTENT_COMMENT_RE` matches bare substrings, so `{# minor prefix cleanup #}`
  downgrades a real WARN to INFO because "prefix" contains "fix". This silently
  *undercounts* divergence — it corrupts the exact statistic the project is built on,
  in the direction that looks like good news. Anchor the alternation with `\b`.
  (b) R004 compares ISO timestamps as raw strings. `"not-a-date"` sorts after any
  real timestamp and fires R004; `2026-01-02T00:00:00+09:00` (= 15:00Z Jan 1) is
  judged newer than `2026-01-01T20:00:00Z` though it is earlier. Both fabricate
  findings. Parse with `datetime.fromisoformat`, normalise `Z`, compare aware
  datetimes, and stay silent on unparseable input.
  Cost if wrong: R002 downgrades slightly less often and R004 goes quiet on malformed
  metadata — both fail toward reporting less, which is the safe direction.
- Task 8: complete — commit c57a4be. 77/77 pass. Fix round 1 verified directly:
  `{# minor prefix cleanup #}` and `{# unmodified copy #}` no longer match
  INTENT_COMMENT_RE while `{# fixes the tool-call role #}` and `{# patched for minja #}`
  still do; R004 now parses with `datetime.fromisoformat` and stays silent on
  unparseable input; the duplicate `r002_annotated_patch` call is gone.
- Task 9: review round 1 — spec APPROVED (the `(kept, suppressed)` tuple order was
  confirmed by execution, not by reading; no new dependency; I/O confined to
  `load_ignores`). Quality CHANGES REQUESTED, three items.
- **Ruling: E13 — teach `apply_ignores` about collapsed findings.** Task 6's collapse
  gave S003/S008 `fixture=None` with the affected names in `evidence["fixtures"]`, and
  Task 9 was written before that landed. The consequence, confirmed by construction: a
  rule `S003 with_tools` can never match, and the only rule that works (bare `S003`)
  suppresses S003 for every fixture sharing that signature — including fixtures the
  user never inspected, and any future fixture that joins the signature, with no
  re-consent. So the scoped form is silently inert and the working form is broader
  than anyone would intend. Fix: when `finding.fixture` is None, match against
  `evidence["fixtures"]`, and let a fixture-scoped rule suppress only when that list
  is exactly the one fixture named. A collapsed finding spanning several fixtures
  stays suppressible only by the un-scoped rule — you cannot half-suppress one
  finding, and pretending otherwise would be worse than refusing.
  Cost if wrong: a user with a genuinely multi-fixture S003 must suppress it wholesale
  and says so in their reason, which is the honest outcome anyway.
- **Ruling: E14 — the parse error must quote the offending line, and the unreachable
  branch goes.** A reasonless line aborts the whole run, so the message needs to be
  fixable without reopening the file. Separately, the "missing rule id" branch is dead:
  `strip()` runs before the comment check, so any line whose first non-space character
  is `#` is swallowed as a comment and the branch cannot fire. The report claimed it
  handles a case it cannot reach. Remove it and correct the report.
- Task 9: complete — commit c88a10d. 87/87 pass. Fix round 1 verified directly:
  a single-fixture collapsed finding is suppressed by `S003 with_tools`, a two-fixture
  one is not (scoped) but is by the bare `S003`, the parse error now quotes the
  offending line, and the unreachable branch is gone.
- Task 10: review round 1 — spec APPROVED. `exit_code` was exercised across the full
  3-severity x 4-threshold matrix rather than one happy path: not inverted. JSON
  round-trips through real `json.dumps` with nested evidence, and `Severity.ERROR`
  serialises as `"error"`, not `"Severity.ERROR"`. Quality CHANGES REQUESTED.
- **Ruling: E15 — sanitise control characters in the human report. Blocking, security.**
  `model.source_id`, finding messages and fixture names all reach `render_human`
  unescaped, and every one of them originates in a GGUF file — the untrusted input
  this tool exists to inspect. The reviewer injected `\x1b[2J` (clear screen), `\x1b[31m`,
  `\x07` and embedded newlines and watched them pass through verbatim, which is enough
  to blank the report and forge a fake "no findings" line in the victim's terminal.
  `json.dumps` already escapes these, so only the human path is exposed. A linter that
  can be made to lie by the file it is linting is worse than no linter.
- **Ruling: E16 — the headline must carry its own caveat.** With zero findings and a
  gated upstream the report asserts a bare `no findings` and puts `upstream: gated` /
  `note: R family skipped` three lines below at equal visual weight. Anyone skimming,
  and any CI grep, takes the first line. Qualify the headline itself.
- **Ruling: E17 — add per-check coverage, and lift the file boundary to do it.**
  S005/S006 return `[]` when `bos_token_id`/`eos_token_id` is missing or out of range,
  yet the S family still reports as "run" and nothing anywhere records the skip. The
  reviewer is right that Task 10 cannot fabricate what was never captured: the gap is
  in `Coverage`'s shape. Normally the fix would wait for a later plan, but "silently
  reports clean when it could not check" is the one failure this project cannot
  survive, and the whole point of the last three review rounds has been to make the
  findings trustworthy in both directions. So the Task 10 fix round may add a
  defaulted field to `models.Coverage` and record skips in `checks/sanity.py`.
  Cost if wrong: a field two later tasks must carry through; both are still unwritten,
  so the cost is lowest now and rises every task.
- **Ruling: E18 — keep `generated_at`, and make Task 12 exclude it.** Provenance is
  worth more than byte-identical output, and everything else in the document was
  verified deterministic. Carried into the Task 12 dispatch so the survey does not
  compare on it.
- Task 10: complete — commit 7459ab9. 103/103 pass. Fix rounds 1-2 verified directly:
  `\x1b[2J\x1b[31m` in `source_id` renders as visible escaped text instead of executing;
  the headline reads `no findings (partial: R family skipped, upstream gated)` when
  coverage is partial and a bare `no findings` when complete; a negative
  `eos_token_id` now takes the out-of-range WARN instead of silently skipping.
  New field `Coverage.checks_not_evaluated: list[str]` (JSON `coverage.checks_not_evaluated`),
  populated via a matching mutable field on `CheckContext` that S005/S006 append to.
- **Carry into Task 11 (the implementer flagged this and it is easy to lose):** the
  `ctx.checks_not_evaluated` -> `Coverage(checks_not_evaluated=...)` wiring is manual.
  Nothing builds `Coverage` today, so if Task 11's CLI forgets to pass it through, the
  entire E17 fix silently reverts to reporting clean when it could not check.
- Task 11: review round 1 — spec APPROVED. The `checks_not_evaluated` merge is present
  and the reviewer re-verified it the right way: commented the line out, watched
  `test_checks_not_evaluated_reaches_the_reports` fail, restored it. Offline guarantee
  verified through the whole `main()` pipeline with `urlopen` patched to raise. Network
  isolation confirmed by collecting with `-m network`: zero tests carry the marker, so
  `addopts` is not hiding anything. Quality CHANGES REQUESTED, four items.
- **Ruling: E19 — `--json` to an unwritable path must not traceback. Blocking.** The
  write sits outside `main()`'s try/except (inherited from the brief's sample), so a
  `PermissionError` prints a full traceback and exits 1 instead of a one-line message
  and exit 2. It breaks both the no-traceback constraint and the exit-code contract.
- **Ruling: E20 — split `not_requested` from genuine coverage failures.** Every default
  invocation currently prints `no findings (partial: R family skipped, upstream
  not_requested)`. E16 added that qualifier so nobody could mistake a partial check for
  a clean bill of health — but if it fires on the path almost everyone runs, the word
  stops meaning anything, and by the time it appears for a genuinely gated upstream it
  reads identically to the common case. A warning that is always on is not a warning.
  Not asking for upstream is a choice; failing to reach it is a gap. They get different
  words, and `checks_not_evaluated` stays under "partial" regardless.
- **Ruling: E21 — `is_repo_id` must not send local paths to the network.** Any
  nonexistent relative path with a slash and no `.gguf` suffix (`models/foo`,
  `checkpoints/model`) is classified as a repo id and triggers an HTTP request; the
  user sees a network error for what is a mistyped filename. Require exactly two
  segments and no local file at that path. Cost if wrong: a genuine `org/name` repo
  shadowed by a same-named local directory resolves locally — which is the safer
  default and matches how every other CLI treats an existing path.
- **Ruling: E22 — `--require-upstream` alone is a usage error.** It currently exits 1
  even when no `--compare-upstream` was given, i.e. it fails because the user did not
  ask for the thing they also did not ask for. Reject the combination up front.
- Task 11: complete — commit e51e88e. 119/119 pass. Fix round 1 verified directly by
  me: default clean run now reads `no findings — local checks only (add
  --compare-upstream <repo> ...)` with no alarm; `--require-upstream` alone gives
  `--require-upstream requires --compare-upstream` and exit 2; `--json` to a
  nonexistent directory gives a one-line message and exit 2 with no traceback;
  `org/sub/repo` and existing local paths are no longer repo ids. `models/foo` still
  resolves as a repo id when no local `models/` directory exists — accepted: with no
  such directory on disk it is genuinely ambiguous, and the implementer's rule (an
  existing first segment means local) covers the case E21 was written for.
- Task 12: review round 1 — spec APPROVED and quality APPROVED. All three historical
  traps verified by construction: a fake dominated by one publisher caps at two per
  org and moves the rate from 90.9% (uncapped) to 28.6% (capped); an 11-repo fake
  spanning every gap type gives `comparable=4`, `divergent_pct=50.0` (2/4, not 2/11),
  with `comparable + sum(coverage_gaps) == 11` so the denominator never quietly
  shrinks; and the divergence verdict comes only from `run_reference_checks`' R001,
  never from a template string comparison. `download_weighted_pct` confirmed to mean
  divergent downloads over *comparable* downloads (63.83% on a hand-computed case).
  Zero-denominator safe. The legacy `ggufdoctor <target>` form is behaviourally
  identical after the full `cli.py` rewrite, with all 11 prior CLI tests unmodified.
- **Ruling: E23 — fix both observations; they are about the published number.**
  (a) A single failed HTTP call propagates out of `sample_repos`/`survey` and discards
  the whole run. A `--top 400` survey is hundreds of live calls against someone else's
  API; losing all of it to one transient 503 makes the headline artifact impractical
  to regenerate, and "regenerable by one command" is what makes the statistic citable.
  Degrade per repo instead.
  (b) `not_found` and `fetch_error` collapse into one `upstream_fetch_failed` bucket.
  It does not distort the rate, but it erases a real finding: the original probe found
  51 of 400 repos pointing at base models that now 404. "The upstream no longer exists"
  is a different claim from "we could not reach it", and it is one of the more
  interesting things the survey can say. Keep all five reasons distinct.
  Cost if wrong: one more bucket in the output and a survey that finishes with partial
  data rather than none — both strictly more informative.
- Task 12: complete — commit 332995e. 126/126 pass. Fix round 1 landed: pagination and
  per-repo failures now degrade instead of discarding the run (a `truncated` flag says
  so), and all five upstream reasons keep distinct `coverage_gaps` keys, so the survey
  can report "the upstream no longer exists" separately from "we could not reach it".
- **All 12 tasks complete.** 24 commits on feat/v0.1. Finding-id test coverage
  confirmed for all twelve ids S001-S008 and R001-R004. Dispatching the final
  whole-branch review.

## Final whole-branch review — NOT PUBLISHABLE as-is

Four blocking findings, all of a piece with E8, plus a measurement gap.

- **S003 reports ERROR on the Mistral / Llama-2 / Gemma lineage.** Those templates call
  `raise_exception('Only user and assistant roles are supported!')` on a system message
  — correct, documented, upstream-identical behaviour that transformers reproduces —
  and the tool calls it "template raises while rendering a standard conversation" and
  exits 1. Identical in kind to the S005 bug E8 called disqualifying, and it survived
  because E8's fix was scoped to S005.
- **S007's message states a falsehood on the same families.** "the assistant turn is
  never opened" — `[/INST]` opens it; the flag is merely unused. The check can observe
  the no-op, not the consequence it asserts.
- **The regression tests written to prevent exactly this passed over the live bug.**
  `test_s005_no_false_positive_on_mistral_template` calls the full `run_sanity_checks`
  on real vendored templates and asserts only `"S005" not in ids`. The fixture already
  held the evidence: mistral yields S003+S007, llama2 yields S007. This is the most
  serious item — the guard was there, looked right, and was blind.
- **`cosmetic_only` is asserted about templates that never rendered.** When both sides
  fail to render, `survey.py` labels the repo "the rewrite changes nothing the model
  sees" and counts it comparable — a positive public claim about a named third-party
  repo on no evidence.
- **The survey will not reproduce 15.1%.** Recomputing from the evidence file gives
  16.5% raw (18/109); the published figure comes from three hand-audited removals that
  exist nowhere in `survey.py` — two ASR repos on `qwen3vl` (absent from
  `NON_CHAT_ARCHITECTURES`) and one unrenderable. probe2's self-base guard is also
  missing. E7's `tojson` fidelity fix moves tool-path verdicts too, and 14 of 16
  published divergences are on that path.
- **Ruling: E24 — encode the audit in code and publish what the tool outputs.** The
  number must be the tool's result, not a figure the tool approximates. Fix the
  exclusions, re-run, and quote whatever comes out.
Cleared as sound: the five reason strings end to end, `checks_not_evaluated` reaching
both renderers, packaging (wheel carries the corpus; console script works installed
outside the tree), the first-five-minutes output, and true positives confirmed on real
Llama-3/Gemma-2/ChatML templates with Qwen2.5 correctly clean.
- Final fix A: commits 57f6f54 + 87af012. 142/142 pass. S003 now distinguishes an
  author's deliberate `raise_exception` (INFO, quoting the author's text) from an
  engine failure (ERROR); S007's message states only what it can observe; R001 injects
  real tokens on both sides and separates whitespace-only divergence at INFO with
  `evidence["whitespace_only"]`; S004/S006 and the missing-fixture paths now record
  their skips. The four real templates assert their *complete* finding sets with
  genuine metadata.
- **Ruling: E25 — S006 firing on all four major families must be adjudicated before
  release.** Mistral-v0.2, Llama-2-chat, Gemma-2 and Llama-3.3 all now yield S006 WARN.
  Either that is a true and rather large finding about the GGUF ecosystem, or it is a
  false positive at the widest possible scale — and the two look identical from inside
  our own test suite. The deciding fact is external: whether llama.cpp actually emits
  two BOS tokens when `add_bos_token` is true and the template also emits one, or
  whether it detects and suppresses the duplicate. Recent llama.cpp carries handling
  for precisely this. Verify against llama.cpp's actual behaviour, not against our
  reading of the metadata. Cost if wrong in the reporting direction: the tool warns
  everybody about everything and gets uninstalled; in the other: we miss the single
  most widespread defect in the ecosystem.
- Final fix B: commit 340ec0c. 154/154 pass. S006 adjudicated by reading llama.cpp
  source: `src/llama-vocab.cpp` only warns, but `common/chat.cpp` strips the template's
  rendered leading BOS when the vocab's `add_bos` is set — so llama.cpp's own pipeline
  never double-adds. Downgraded to INFO with the risk narrowed to callers who render
  and tokenize outside that glue. Survey audit criteria encoded; `non_chat_model`
  renamed `upstream_has_no_template`; survey documented in `--help`; short files now
  report `missing GGUF magic`.
- Commit 4f70086: MIT LICENSE, packaging metadata, README stub. Wheel builds.
- **First live survey run** (2026-09-01, `--top 400 --per-org 2`): 110 comparable,
  18 divergent = **16.4%**, 31.5% download-weighted, 16 of 88 publishers. Saved to
  `docs/research/2026-09-01-survey-ggufdoctor.{json,md}`.
- **Ruling: E26 — the pipeline_tag exclusion reads the wrong repo. Blocking the
  number.** Both `unslothai/Qwen3-ASR-*` repos are back in the divergent list, so the
  16.4% carries two known false positives. Cause: `_is_non_chat` tests the *GGUF*
  repo's `pipeline_tag`, which is `None` for these (their only tag is
  `conversational`), while the ASR evidence sits on the *upstream* —
  `Qwen/Qwen3-ASR-0.6B` publishes `pipeline_tag: automatic-speech-recognition`.
  Check the upstream's tag as well; we already fetch that repo for its template.
  Verified `poolside/Laguna-S-2.1` is genuinely `text-generation`, so it stays a real
  divergence — the probe's old `unrenderable` label for it no longer applies.
  Cost if wrong: one extra API call per repo carrying a base model.
- Final fix B addendum: commit ac9a5d2. 155/155 pass. Scoped re-review confirms all six
  named defects RESOLVED, each by reversion testing. Item 6 verified not over-broad:
  the reviewer ran the new criterion live against all 110 comparable repos from the
  first run and it excluded exactly the two ASR repos, touching nothing else.
  `poolside/Laguna-S-2.1` and `Qwen/Qwen2.5-3B-Instruct` both stay divergent.
  S006's downgrade independently confirmed and strengthened: `--jinja` is now the
  *default*, the stripped prompt is tokenized with `add_special=true` so exactly one
  BOS survives, the `--no-jinja` path never renders the GGUF's template at all, and
  llama-cpp-python sets `add_bos=False` after its own formatter. The residual risk is
  essentially transformers-style `apply_chat_template` + `add_special_tokens=True`.
- **Ruling: E27 — the S003 fix reintroduced silence, and it must not ship.** A template
  that declines every fixture now reports one INFO, `0 error`, exit 0 and an *empty*
  `checks_not_evaluated`, because S004/S005/S006/S007 all bail on a failed render
  without recording it. Nothing was evaluated, and the tool says so nowhere. This is
  the lint-side twin of the `cosmetic_only` bug we just fixed on the survey side, and
  before the S003 change this case was at least a loud ERROR. The machinery already
  exists; four `append` calls close it.
- **Ruling: E28 — the second live run is throttle-damaged; the survey must survive its
  own API budget.** Re-running at ac9a5d2 gave 90 comparable / 13 divergent (14.4%),
  but with **75 `examine_error`** — the addendum's extra `model_info` per repo roughly
  doubled Hub calls and we were rate-limited, so `upstream_non_chat_pipeline_tag`
  caught 1 of the 2 ASR repos it should have. A figure measured on a sample a third of
  which failed to fetch is not publishable, and worse, throttling silently changes the
  number rather than announcing itself. Make the upstream check lazy — it is only
  needed for repos that would actually be counted — and back off on 429 rather than
  filing it as an examine error. `examine_error` must be rare enough that a reader can
  ignore it; when it is not, the run should say the number is unreliable.
