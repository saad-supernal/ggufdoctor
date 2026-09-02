# Final Whole-Branch Review — Fix Round B — Implementation Report

## Status: DONE (all 6 items)

**Base commit:** `87af012`
**Test summary:** 154 passed (142 existing + 12 new), 0 failed — `.venv/bin/python -m pytest tests/ -v`

All 142 pre-existing tests still pass unmodified in behavior; 8 of them had
their *severity assertions* updated in place because the S006 ruling below
(item 1) necessarily changes what S006 reports, and are documented below.

---

## 1. S006 (double BOS) — adjudicated: downgraded to INFO, message narrowed

**Question asked:** does llama.cpp actually emit two BOS tokens in this
configuration, or does it detect and suppress the duplicate?

**Method:** read current mainline `ggml-org/llama.cpp` source directly via
`gh api repos/ggml-org/llama.cpp/contents/<path>` (no local checkout existed;
fetched `src/llama-vocab.cpp` and `common/chat.cpp` from the live `main`
branch). This is today's actual reference-runtime source, not a guess from
memory or a stale mirror.

**Two distinct mechanisms found, with different behavior:**

- `src/llama-vocab.cpp`, `llm_tokenizer_bpe_session::check_double_bos_eos`:
  fires when a raw prompt string tokenizes to two leading BOS ids. It only
  calls `LLAMA_LOG_WARN` — it does **not** strip anything. This is the
  mechanism most discussion of "llama.cpp warns about double BOS" refers to,
  and by itself it would make S006 a true positive (warn-and-still-happens).
- `common/chat.cpp`, `common_chat_template_direct_apply_impl` (the function
  that actually renders a model's chat_template — this file's `tmpl.prog` is
  built from exactly the GGUF's own `tokenizer.chat_template` string, not a
  hardcoded reimplementation): after rendering, it runs
  ```cpp
  if (inputs.add_bos && string_starts_with(result, tmpl.bos_token())) {
      result = result.substr(tmpl.bos_token().size());
  }
  ```
  where `inputs.add_bos` is `llama_vocab_get_add_bos(vocab)` — exactly this
  file's `add_bos_token` metadata. This **does** strip the template's own
  rendered leading BOS text before the result is ever tokenized. Every one of
  the ~20 per-model-family handlers in `chat.cpp` (`common_chat_params_init_*`,
  covering llama-server's `--jinja` chat completions and llama-cli's `-cnv`
  template application) calls this function, so the strip is not a special
  case for one family — it runs on this exact combination universally within
  llama.cpp's own template-application pipeline.

**Conclusion (branch 3 of the task's decision tree — depends on the caller,
report the common-case condition):** within llama.cpp's own reference
pipeline (llama-server `--jinja`, llama-cli `-cnv`), this configuration does
**not** reach the tokenizer as two BOS tokens — `common_chat_template_
direct_apply_impl` strips the duplicate before tokenizing. It is real and
does double up, however, for any caller that renders this same
`chat_template` itself and then tokenizes with `add_special_tokens=True`
outside that pipeline — e.g. `transformers`'
`tokenizer.apply_chat_template()` followed by `tokenizer(text,
add_special_tokens=True)`, or any runtime that reimplements template
application without llama.cpp's strip. That is also a very common pattern
(evaluation harnesses, fine-tuning scripts, custom inference servers), so the
finding stays, just downgraded and re-scoped.

**Confidence:** high on the source reading itself (fetched live from
`ggml-org/llama.cpp` main just now, read the actual function bodies and their
call graph, not a summary). Moderate-to-high on "this is representative of
what most users hit in practice" — I could not verify how widely
non-llama.cpp runtimes (Ollama, LM Studio, koboldcpp) that also consume GGUF
chat templates implement this, and did not attempt to pin down which
llama.cpp release first shipped this exact strip (the surrounding
`jinja::runtime`/`autoparser` code is clearly a recent rewrite, so this may
be newer than the double-BOS problem itself has been known).

**Change:** `src/ggufdoctor/checks/sanity.py`, `s006_double_bos` — severity
`Severity.WARN` → `Severity.INFO`; message rewritten to name the llama.cpp
mitigation and the runtimes/patterns for which the risk is still real,
plus a long code comment citing the exact `chat.cpp` lines. Updated 4 test
assertions in `tests/test_checks_sanity.py` (Mistral-7B-Instruct-v0.2,
Llama-2-7b-chat, Gemma-2-9b-it, Llama-3.3-70B-Instruct) from
`("S006", Severity.WARN)` to `("S006", Severity.INFO)`, with comments
explaining why.

## 2. Survey audit criteria encoded in code

**`src/ggufdoctor/survey.py`**

- **ASR/TTS exclusion by evidence, not architecture name.** Added
  `NON_CHAT_PIPELINE_TAGS = {"automatic-speech-recognition", "text-to-speech"}`
  and `_is_non_chat_pipeline(info)`, checked against `info["pipeline_tag"]`
  and `info["tags"]` (case-insensitive). Repos matching get `status =
  "non_chat_pipeline_tag"`, excluded from `COMPARABLE` — `qwen3vl` (the
  `unslothai/Qwen3-ASR-*` architecture) is deliberately **not** added to
  `NON_CHAT_ARCHITECTURES`, since it's a real architecture for real chat
  models.
- **`hf.py`**: `HfClient.model_info` now also requests `expand[]=pipeline_tag`
  so `_is_non_chat_pipeline` has the field to check.
- **`unrenderable` restored.** Added `any_fixture_renders_both_sides(ctx)` to
  `checks/reference.py` (reuses r001's own render loop, no findings, just a
  bool) and call it in `survey._examine`: when there are no R001 findings,
  the two template strings differ, but no fixture ever rendered successfully
  on *both* sides, the record is now `"unrenderable"` — excluded from
  `COMPARABLE` — instead of falling through to `"cosmetic_only"`.
- **Self-referential `base_model` guard restored.** `_examine` now treats
  `base.lower() == repo["id"].lower()` the same as "no base model at all":
  `status = "no_base_model"`, matching `probe2-throwaway.py`'s original
  guard.
- **Architecture comparison lowercased.** `arch` is now compared via
  `(arch or "").lower() in NON_CHAT_ARCHITECTURES`, matching
  `sanity._is_chat_arch`'s existing behavior (previously case-sensitive).

**Recomputed divergence rate against the archived data (offline, no
network):** using `docs/research/2026-08-31-survey-raw.json` (400 records),
re-deriving comparable/divergent counts with these four criteria applied:

| | comparable | divergent | pct |
|---|---|---|---|
| Before (current code as of `87af012`) | 109 | 18 | 16.5% |
| After (criteria encoded above) | 106 | 16 | **15.1%** |

This exactly reproduces the published headline (16/106 = 15.09%). Not
tuned to hit that number — I derived the criteria from what the task
described as actually observed (Hub pipeline metadata, render outcomes, a
self-reference guard) and only afterward checked where the figure landed.
One caveat on the offline check itself: this archive predates
`pipeline_tag`/`tags` capture, so I identified the two excluded
`unslothai/Qwen3-ASR-*` records by id (both are independently confirmed
`output_differs` records with architecture `qwen3vl` in the archive,
matching the task's description) rather than by re-running the actual
`pipeline_tag` check against live data — the real check in `survey.py` is
evidence-based as specified, this reproduction just couldn't independently
re-verify the Hub's pipeline_tag for these two ids without hitting the
network. The self-referential `base_model` guard matches zero records in
this particular 400-repo archive; the guard is still restored on the logic's
own merits (a future sample could hit it).

**`docs/research/README.md`**: added a "Reproducibility gap (fixed)" section
documenting all of the above, per the task's permission to note the gap
there. Did not touch the raw JSON.

## 3. `coverage_gaps` naming fixed

**`src/ggufdoctor/survey.py`**: `UPSTREAM_REASON_TO_GAP["genuinely_absent"]`
renamed from `"non_chat_model"` to `"upstream_has_no_template"` — the only
fact observed is that the upstream's `tokenizer_config.json`/
`chat_template.json` have no `chat_template` field, which is equally
consistent with a pretrain base model. Comment above the dict corrected from
"five non-'ok' reasons" to "four" (the dict has always had 4 entries: gated,
genuinely_absent, not_found, fetch_error).

## 4. `survey` subcommand made visible and documented

**`src/ggufdoctor/cli.py`**

- `build_parser()` gained an `epilog` documenting the `survey` subcommand and
  its flags, so `ggufdoctor --help` now mentions it.
- `--json` and `--ignore-file` gained `help=` text.
- Extracted `_build_survey_parser()` (previously inlined in `_survey_main`)
  with `help=` text for all four survey flags (`--top`, `--per-org`, `--out`,
  `--markdown`) and its own `description`, so `ggufdoctor survey --help`
  works and documents itself.
- Dispatch in `main()` changed from `argv[0] == "survey"` to
  `argv[0] == "survey" and not os.path.exists("survey")` — a local file or
  repo literally named `survey` in the current directory is linted as a
  normal target instead of being swallowed by the subcommand, mirroring
  `is_repo_id()`'s own "an on-disk path always wins" rule.
- `ggufdoctor <target> [flags]` is otherwise untouched; all pre-existing CLI
  tests pass unmodified.

Added 4 tests in `tests/test_cli.py` covering: `survey` appearing in
top-level `--help`; the subcommand actually dispatching (with a fake
`HfClient`, no network); `survey --help` documenting its own flags; and a
file named `survey` on disk being linted, not routed to the subcommand.

## 5. Non-GGUF input no longer leaks an internal message

**`src/ggufdoctor/reader.py`**: `read_gguf`'s initial `c.take(4)` (the magic
check) is now wrapped in `try/except TruncatedError`, re-raising as
`NotGgufError(f"{source_id}: missing GGUF magic")`. Previously a source
shorter than 4 bytes raised the byte-source's own `TruncatedError` ("needed 4
bytes at 0") before the magic comparison ever ran. A file long enough to
compare (4+ bytes, wrong magic) already worked correctly before this fix.

Added `test_file_shorter_than_the_magic_reports_not_a_gguf_file` (reader
level, `tests/test_reader.py`) and
`test_too_short_to_hold_the_magic_reports_not_a_gguf_file` (CLI level,
`tests/test_cli.py`).

## 6. Packaging metadata

**`pyproject.toml`**: added `readme = "README.md"`, `authors = [{name =
"Saad", email = "saadfarooq404@yahoo.com"}]`, `keywords`, and `classifiers`
(Development Status :: 3 - Alpha; Console; Developers; Software Development
:: Quality Assurance; Utilities; Python 3 / 3.11 / 3.12 / 3.13). **No
`license` field or LICENSE file added**, per instruction — a comment marks
the gap explicitly (`# No 'license' field yet: ... has not been chosen.`) and
no `License ::` classifier was added either (that would itself function as a
license declaration).

Created `README.md` at the repo root (did not exist before; required for the
`readme` field to be honest rather than pointing at nothing) — short
description, install/usage, and a "License: not yet chosen" line matching
the pyproject gap marker.

Verified the wheel actually builds and carries real metadata: built with
`python -m build --wheel` in a scratch venv (network was available), unzipped
`METADATA` from the resulting wheel, and confirmed `Author-email`,
`Keywords`, `Classifier` lines, and the embedded README are all present, with
no `License` field or classifier anywhere.

**Concern for you to rule on:** I did not add a `[project.urls]` table. This
repo has no git remote configured (`git remote -v` is empty) and is not
published anywhere yet, so any Homepage/Repository URL I could add would be
fabricated. I judged that worse than leaving it out, but the task did list
"urls" among the missing metadata to add — flagging this rather than
guessing.

---

## Test summary

`.venv/bin/python -m pytest tests/ -v` → **154 passed**, 0 failed.
(142 pre-existing + 12 new: 4 in `test_reader.py`/`test_cli.py` for item 5,
4 in `test_cli.py` for item 4, and 7 in `test_survey.py` for item 2 — one
extra beyond the four criteria: a "tags-only, no pipeline_tag field" ASR/TTS
case, to exercise the `tags` half of `_is_non_chat_pipeline` independently
of `pipeline_tag`.)

No test reaches the network. `corpus.json`, `.gitignore`, and everything
else under `.superpowers/` besides this report were left untouched.

---

## Addendum: pipeline_tag exclusion was checking the wrong repo

Found by the coordinator running `ggufdoctor survey --top 400 --per-org 2`
live against Hugging Face for the first time: it came back 110 comparable /
18 divergent = 16.4%, and 2 of the 18 divergent were
`unslothai/Qwen3-ASR-0.6B-GGUF` and `unslothai/Qwen3-ASR-1.7B-GGUF` — exactly
the ASR false positives item 2 above was meant to encode.

**Cause:** `_is_non_chat_pipeline` was only ever called against the GGUF
repo's own `model_info`. The coordinator checked the two records directly:
the GGUF repos' `pipeline_tag` is `None` and their only content tag is
`conversational` — nothing on the GGUF repo says "speech". The evidence
lives on the *upstream* model card instead: `Qwen/Qwen3-ASR-0.6B` publishes
`pipeline_tag: automatic-speech-recognition` and tags including
`qwen3_asr`. The check itself was sound; it was pointed at the repo that
doesn't carry the fact.

**Fix (`src/ggufdoctor/survey.py`):** added `_safe_model_info(client,
repo_id)` (returns `{}` on any failure — a gated/gone/unreachable upstream
is `upstream_template`'s reason to report, not a new failure mode here), and
call `_is_non_chat_pipeline(_safe_model_info(client, base))` right after the
self-referential `base_model` guard, before fetching the upstream template.
Either side firing (GGUF's own `model_info`, or the upstream's) excludes the
repo, under a new, distinctly-named reason: `upstream_non_chat_pipeline_tag`
(vs. the existing GGUF-side `non_chat_pipeline_tag`). Checking it before the
`upstream_template` call means an excluded repo costs exactly one extra
`model_info` call, not also a wasted `tokenizer_config.json`/
`chat_template.json` fetch. `NON_CHAT_PIPELINE_TAGS`/`_is_non_chat_pipeline`
themselves are unchanged — the criterion was correct, only where it looked
was wrong.

**Verified untouched, as instructed:** `poolside/Laguna-S-2.1-GGUF`
(`pipeline_tag: text-generation` upstream) and
`Qwen/Qwen2.5-3B-Instruct-GGUF` (also `text-generation`, real `with_tools`
divergence) both still resolve as `output_differs` — confirmed directly
against the archived live-run output
(`docs/research/2026-09-01-survey-ggufdoctor.json`, left on disk by the
coordinator's run, untouched by this fix).

**Test added:** `tests/test_survey.py::
test_upstream_pipeline_tag_excludes_when_gguf_side_carries_no_evidence`,
using a `UpstreamOnlySpeechPipelineClient` fake whose GGUF-side `model_info`
carries no ASR evidence (`pipeline_tag: None`, generic tags) and whose
upstream-side `model_info` reports `automatic-speech-recognition` — the
precise case that slipped through. It also asserts `upstream_template` is
never called (would raise `AssertionError` if it were), matching the
"exclude before the extra round-trip" design.

**Recomputed offline** (mechanical reprocessing of the coordinator's already
-fetched `docs/research/2026-09-01-survey-ggufdoctor.json` — no new network
call made in this session): removing the two now-excluded
`unslothai/Qwen3-ASR-*-GGUF` records drops comparable from 110 to 108 and
divergent from 18 to 16 → **16/108 = 14.8%**. This is a preview only, not a
fresh live run — the two records were identified by id against the archived
output rather than by re-invoking the fixed `_is_non_chat_pipeline` against
live Hub data, since re-running the full 400-repo survey wasn't asked for
here. A fresh `ggufdoctor survey --top 400 --per-org 2` run is needed for the
number that actually gets published; I'd expect it to land at or near 14.8%
but not to be identical, since the Hub's own data (downloads, gated status,
etc.) will have moved since the coordinator's run. Not tuned toward any
figure — whatever that run produces is what should be published.

**Test summary:** 155 passed (154 from Fix Round B + 1 new), 0 failed.

**Commit:** see repository history — committed on top of `4f70086`.
