# Task 12 report: survey subcommand

## What was created

- **`src/ggufdoctor/hf.py`** — appended `list_gguf_models(self, skip, limit=100)`,
  which paginates `GET /api/models?filter=gguf&sort=downloads&direction=-1&limit=&skip=`
  via the client's existing `_open` opener. Nothing above it in the file was touched.
- **`src/ggufdoctor/survey.py`** (new) — `sample_repos`, `survey`, `to_markdown`,
  transcribed from the brief with one addition (see Deviation below).
- **`src/ggufdoctor/cli.py`** — rewritten in full per the ruling. `main()` is now a
  two-line dispatcher: `argv[0] == "survey"` routes to `_survey_main(argv[1:])`,
  everything else routes to `_lint_main(argv)` (the old `main` body, renamed,
  unchanged in behavior). `build_parser()` is untouched.
- **`tests/test_survey.py`** (new) — the four tests given in the brief, verbatim.

## Test command and output

```
.venv/bin/python -m pytest tests/ -v
```
Result: **123 passed** in ~2s (119 pre-existing + 4 new in `test_survey.py`). No
skips, no errors, no warnings.

Also ran `pytest tests/ --collect-only -q` → 123 tests collected, confirming no
test is tagged `network` and none were silently excluded.

## Commit

`377e13c` — "feat: survey subcommand reproducing the ecosystem measurement"
Files: `src/ggufdoctor/cli.py`, `src/ggufdoctor/hf.py`, `src/ggufdoctor/survey.py`
(new), `tests/test_survey.py` (new). 4 files changed, 225 insertions.

## Complete new CLI surface

Both invocation forms coexist in `main(argv=None)`:

1. **Lint form (unchanged):** `ggufdoctor <target> [--compare-upstream REPO]
   [--fail-on {error,warn,info,never}] [--fixtures PATH] [--json PATH]
   [--ignore-file PATH] [--require-upstream]` — dispatches to `_lint_main`,
   byte-for-byte the old `main` body (same argparse parser from `build_parser()`,
   same exception handling, same exit codes 0/1/2).
2. **Survey form (new):** `ggufdoctor survey [--top N] [--per-org N] [--out PATH]
   [--markdown PATH]` — dispatches to `_survey_main`, which builds a real
   `HfClient()`, calls `survey(...)`, writes `--out` (JSON) and `--markdown` if
   given, prints the markdown report, and returns 0, or prints
   `ggufdoctor survey: <e>` to stderr and returns 2 on any exception.

Verified manually: `main(['nonexistent/path.gguf'])` → prints
`ggufdoctor: [Errno 2] No such file or directory: ...` and returns 2 (old form
intact); `main(['survey', '--top', '5'])` ran end-to-end against the live HF
API and printed a markdown report with exit 0 (new form works; this manual
check, not a test, is the only network traffic in this session).

## Denominator of `divergent_pct` and `coverage_gaps`

`comparable` is exactly the count of records whose `status` is one of
`{"identical", "cosmetic_only", "output_differs"}` — i.e. repos that were
actually rendered and compared against upstream via `run_reference_checks`
(Task 8), never the sample size (`sampled`). `divergent_pct = 100 *
divergent / comparable` (guarded to `0.0` when `comparable == 0`).

Every record that fails to reach a comparable state gets its own `status`
string instead of being folded into "no template" or dropped:
`non_chat_architecture`, `no_base_model`, `upstream_gated`, `non_chat_model`
(from `upstream_template`'s `genuinely_absent`), `upstream_fetch_failed`
(from `fetch_error`/`not_found`), and `missing_template` (repo itself has no
`chat_template` in its GGUF metadata). `coverage_gaps` is
`Counter(status for status in records if status not in COMPARABLE)`, so any
gap reason automatically appears in the output — none is silently swallowed
into the comparable set or omitted from the aggregate.

## Non-chat architecture exclusion

`_examine` checks `gg.get("architecture")` against
`NON_CHAT_ARCHITECTURES` (imported from `checks/sanity.py`) **before** the
base-model/upstream lookup. A match short-circuits with
`status = "non_chat_architecture"`, landing in `coverage_gaps` rather than
being scored as divergent or lumped under "missing template".

## Download weighting

`dl_total = sum(downloads for r in comparable) or 1` (guards divide-by-zero);
`dl_div = sum(downloads for r in comparable if r.status == "output_differs")`;
`download_weighted_pct = 100 * dl_div / dl_total`. Weighting is over the
comparable set only (same denominator discipline as `divergent_pct`), using
each repo's `downloads` count carried through from `sample_repos`.

## Verifying no test hits the network

- `tests/test_survey.py` never imports or constructs `HfClient` — it passes a
  hand-written `FakeClient` (no `_open`, no `urllib` anywhere in its call
  graph) directly to `sample_repos`/`survey`.
- Every `HfClient(...)` construction anywhere in `tests/` (`tests/test_hf.py`)
  passes `opener=fake_opener(...)`, confirmed by `grep -n "HfClient(" tests/`.
- `pyproject.toml` already carries `markers = ["network: ..."]` and
  `addopts = "-m 'not network'"` from an earlier task; no test in the suite is
  marked `network` (`grep -rn "pytest.mark.network" tests/` → no matches), and
  `pytest --collect-only -q` shows all 123 tests collected under the default
  (network-excluding) marker expression — nothing is being silently skipped
  that should have been marked.
- The only network traffic in this session was two manual, ad-hoc
  `main([...])` calls I ran by hand outside pytest to sanity-check the CLI
  dispatcher end-to-end; not part of the test suite.

## Deviations from the brief's literal code, and why

1. **Added a `NON_CHAT_ARCHITECTURES` short-circuit in `_examine`** that the
   brief's Step 3 sample code omits. The task's own "why this number is
   load-bearing" section explicitly requires excluding non-chat architectures
   from the comparison rather than counting them as divergent, and names
   `NON_CHAT_ARCHITECTURES` in `checks/sanity.py` as the mechanism to use.
   The given sample code never imports or checks it, which would have left
   ASR/TTS/embedding repos to fall through to `missing_template` (correct
   only by accident, if such a repo happens to lack `chat_template`) or,
   worse, be scored by `run_reference_checks` if it happened to carry one.
   This is a strict superset of the given behavior for the four required
   unit tests — `FakeClient`'s architecture is `"llama"` in every fixture, so
   this new branch is never taken by the existing tests, and all four still
   pass unchanged. No new test was added for this branch since the brief
   defines the test file verbatim and instructed transcription; I verified
   the branch manually via a one-off `_examine` call locally (removed
   before commit) rather than editing the specified test file.
2. No other deviations. `hf.py` was extended by strict append; `cli.py` was
   rewritten in full per the explicit ruling, preserving `build_parser()`,
   every flag name/default/behavior, and the no-subcommand invocation form.

## Fix round 1

Both review verdicts approved the original arithmetic (per-org cap moving
90.9% → 28.6%, `divergent_pct` dividing by `comparable`, `comparable +
sum(coverage_gaps) == sampled`, divergence verdicts coming only from
`run_reference_checks`) and the `NON_CHAT_ARCHITECTURES` addition. Two
robustness/reporting gaps remained; both are fixed in commit `332995e`,
touching only `src/ggufdoctor/survey.py` and `tests/test_survey.py`.

### 1. Pagination/examine failures no longer abort the survey

- Introduced a private `_sample_repos(client, top, per_org) -> (list, bool)`
  that does the real collection work. `sample_repos` (public signature
  unchanged) is now a one-line wrapper that discards the bool, so the
  original three tests (`test_per_org_cap_limits_sample` et al.) still see a
  plain list and pass unmodified.
- Inside `_sample_repos`, `client.list_gguf_models(...)` is now called
  inside a `try/except Exception`. On failure the loop breaks immediately
  (no retry, no backoff) and `truncated=True` is returned alongside whatever
  was already collected. `survey()` threads that flag into a new
  `aggregate["truncated"]` key (additive — no existing key removed or
  renamed).
- `_examine` now wraps its entire body (the calls to `model_info`,
  `base_model_of`, `upstream_template`, and the render/compare path) in a
  `try/except Exception`. A failure there sets `rec["status"] =
  "examine_error"` and returns — the record lands in `coverage_gaps` like
  any other non-comparable status, and the loop over the remaining repos in
  `survey()` is untouched, so the rest of the sample is still scored.
- `to_markdown` now emits a leading blockquote — "**Truncated sample:**
  pagination stopped early after an API failure... do not quote this run as
  a complete survey" — whenever `aggregate["truncated"]` is true, and emits
  nothing extra when it is false, so a complete run's markdown is unchanged
  byte-for-byte from before this fix.

### 2. All five upstream reasons now produce distinct `coverage_gaps` keys

Replaced the inline two-entry dict literal (which defaulted every
unmapped reason, including both `not_found` and `fetch_error`, to a single
`"upstream_fetch_failed"` bucket) with a module-level `UPSTREAM_REASON_TO_GAP`
mapping covering all four non-"ok" reasons `hf.upstream_template` can return:

| `upstream_template` reason | `coverage_gaps` key    |
|-----------------------------|------------------------|
| `gated`                      | `upstream_gated`       |
| `genuinely_absent`           | `non_chat_model`        |
| `not_found`                  | `upstream_not_found`    |
| `fetch_error`                | `upstream_fetch_error`  |

The `.get(why, "upstream_fetch_error")` fallback only matters if
`upstream_template` ever returned something outside its documented set,
which it does not today; it exists so an unexpected value degrades to a
gap reason rather than a `KeyError`, without inventing a new bucket name.

### Full list of `coverage_gaps` keys the survey can now emit

`non_chat_architecture`, `no_base_model`, `upstream_gated`,
`non_chat_model`, `upstream_not_found`, `upstream_fetch_error`,
`missing_template`, `examine_error`.

### Tests added (all in `tests/test_survey.py`, appended under a
### "Fix round 1" comment — none of the four original tests were touched)

- `test_pagination_failure_keeps_partial_sample_and_flags_truncated` — a
  client whose second page raises; asserts `truncated is True`, the partial
  sample (`sampled == 1`) is still scored (`comparable == 1`), and the
  markdown mentions "truncated".
- `test_examine_failure_is_recorded_as_gap_and_survey_continues` — one of
  two repos raises inside `model_info`; asserts `truncated is False`,
  `sampled == 2`, `comparable == 1`, and
  `coverage_gaps["examine_error"] == 1`.
- `test_not_found_and_fetch_error_are_distinct_gap_keys` — two repos
  pointing at different-but-unreachable upstreams, one `not_found` and one
  `fetch_error`; asserts both `coverage_gaps["upstream_not_found"] == 1`
  and `coverage_gaps["upstream_fetch_error"] == 1`, and that both key
  strings appear verbatim in the markdown output.

### Verification

`.venv/bin/python -m pytest tests/ -v` → **126 passed** (123 prior + 3 new).
`pytest tests/ --collect-only -q` → 126 tests collected, confirming nothing
is network-marked or silently skipped. No new dependency was introduced
(still stdlib `try/except`, no retry/backoff library, no `requests`).

### Commit

`332995e` — "fix(task-12): survive pagination/examine failures, keep
upstream reasons distinct", on top of `377e13c`.
