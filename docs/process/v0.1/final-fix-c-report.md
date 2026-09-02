# Final Whole-Branch Review — Fix Round C — Implementation Report

## Status: DONE (all 5 items)

**Base commit:** `ac9a5d2`
**Test summary:** 166 passed (155 existing + 11 new), 0 failed —
`.venv/bin/python -m pytest tests/ -v`

All 155 pre-existing tests still pass. One existing test's mock client was
updated in place because item 2 (below) deliberately changes *when* the
upstream pipeline_tag check fires, not what it decides — documented there.

---

## 1. S003's fix reintroduced the silence — S004/S005/S006/S007 now record
   coverage gaps on render failure

**Root cause confirmed:** splitting the author's deliberate
`raise_exception` out of S003 (fix round 3) correctly stopped S003 itself
from accusing a declined render of being a bug. But S004, S005, S006, and
S007 all depend on rendering the same fixtures, and none of them
distinguished "rendered and found nothing wrong" from "never rendered at
all":

- `s004_unknown_special_token`: looped fixtures updating `confirmed` only
  when `r.ok and r.text`; if every fixture failed, `confirmed` stayed empty
  and the function returned `[]` — identical to the vocab genuinely
  containing every candidate token.
- `s005_eos_mismatch` / `s006_double_bos`: both bailed on `if not r.ok:
  return []` for their one named fixture (`multiturn` / `user_only`), with
  a comment saying S003 already covers it — true for the finding, false for
  this check's own separate question ("does it ever emit EOS?" / "does it
  double up BOS?"), which was left unanswered but reported as answered "no".
- `s007_generation_prompt_noop`: conflated two different states behind one
  guard, `if not (on.ok and off.ok) or on.text != off.text: return []` —
  "the render failed" (coverage gap) and "the flag genuinely changed the
  output" (a real, clean answer) both hit the same silent return.

**Fix:** each of the four now calls `ctx.checks_not_evaluated.append("S0NN")`
on its own render-failure path before returning, mirroring the pattern
S004/S005/S006 already used for missing/out-of-range token metadata (fix
rounds 1 and 3). S004 specifically tracks `any_rendered` across the fixture
loop (not just whether `confirmed` ended up empty), so a fixture that
renders to a legitimately empty string still counts as "rendered" — that
distinction belongs to S008, not S004. S007's guard was split into two
`if`s so the render-failure path and the "flag has no effect" path record
different things.

**Verified end to end** (`src/ggufdoctor/checks/sanity.py`,
`src/ggufdoctor/cli.py` are unchanged in this respect — the report already
prints `note: SNNN not evaluated` unconditionally per finding round 3; this
fix only makes the four checks actually populate that list):

```
$ ggufdoctor decline.gguf --json out.json    # chat_template unconditionally
                                              # calls raise_exception('nope')
decline.gguf  [llama]  engines: jinja2 3.1.6

  S003  INFO  template author deliberately declines this conversation shape
              (raise_exception: 'nope')   [user_only, system_user, multiturn,
              with_tools, thinking_unset, thinking_true, thinking_false]

0 error, 0 warn, 1 info
families run: S   upstream: not_requested
  note: S004 not evaluated
  note: S005 not evaluated
  note: S006 not evaluated
  note: S007 not evaluated
exit code: 0
```

`out.json`'s `coverage.checks_not_evaluated` is `["S004", "S005", "S006",
"S007"]` (was `[]` before this fix). Exit code is unchanged (0 — severity-
based, per the "hold fixed" exit-code contract); what changed is that the
report and JSON now say plainly that four checks never ran, instead of
reading as a clean pass.

**Tests added:**
- `tests/test_checks_sanity.py::test_template_declining_every_fixture_is_not_reported_as_clean`
- `tests/test_cli.py::test_template_declining_everything_is_not_clean_end_to_end`
  (exercises the real GGUF-file → CLI → `--json` path with `build_gguf`,
  matching the exact repro shape from the bug report)

## 2. Survey robustness: lazy pipeline check, 429 retry/backoff, unreliability flag

**a. Lazy upstream `pipeline_tag` check.** Moved the
`_is_non_chat_pipeline(_safe_model_info(client, base))` call in
`survey._examine` from immediately after resolving `base` (i.e. for *every*
repo carrying a base model) to immediately before building the
`CheckContext` — after `upstream_template` has already returned "ok" and
the GGUF-side template is confirmed non-empty. A repo that was always going
to be excluded for a different reason (gated/absent/not-found upstream, no
gguf-side template) now costs exactly the calls it already needed and
nothing more; the extra `model_info(base)` call is spent only on a repo one
step from being counted as comparable.

Updated `tests/test_survey.py::UpstreamOnlySpeechPipelineClient` (the
Qwen3-ASR regression test from fix round B): it previously asserted that
`upstream_template` was *never* called, because the pipeline check used to
short-circuit before it. Since the check is now deliberately downstream of
`upstream_template`, the mock's `upstream_template` returns a normal `"ok"`
result instead of raising — the ASR exclusion itself is unchanged and still
asserted (`upstream_non_chat_pipeline_tag`, `comparable == 0`). Added
`test_upstream_pipeline_check_is_lazy_and_skipped_for_missing_template`,
which asserts the extra `model_info(base)` call count is exactly zero for a
repo excluded by `missing_template` — the case the report specifically
called out as wasted work.

**b. Bounded retry/backoff on HTTP 429.** `HfClient` gained a private
`_fetch(url)` wrapper (stdlib `time.sleep` only, no new dependency) used by
`model_info`, `upstream_template`, and `list_gguf_models` in place of
`self._open(url)`. On a 429 it sleeps `(0.5, 1.0, 2.0)` seconds between up
to 4 total attempts and retries; any other exception (or a 429 that
survives every retry) propagates immediately, so a genuinely broken repo
still becomes `examine_error` — only a *transient* rate-limit gets absorbed
before it ever reaches `survey._examine`'s `except Exception`. No public
signature changed; the constructor still takes only `token`/`opener`.

Tests added in `tests/test_hf.py`: retry-then-succeed for both `model_info`
and `upstream_template`, a non-429 error is not retried, and a persistently
rate-limited call still raises after a bounded (not infinite) number of
attempts. Tests added in `tests/test_survey.py`:
`test_survey_completes_despite_transient_rate_limiting` runs a real
`HfClient` (not a duck-typed fake) with an opener that 429s every distinct
endpoint exactly once, and asserts the survey completes with `comparable ==
1`, `examine_error == 0`.

**c. Unreliability flag.** `survey.py` now computes
`UNRELIABLE_EXAMINE_ERROR_FRACTION = 0.05` and sets
`aggregate["unreliable"]` when `examine_error` exceeds that fraction of the
sample (guarding the empty-sample case the same way the existing
`dl_total or 1` does). `to_markdown` prints a blockquote warning —
`> **Unreliable sample:** ...` — using the same pattern as the existing
`truncated` blockquote, naming the `examine_error` count and stating
plainly that the comparable/divergent figures should not be quoted as
representative. Tests added:
`test_high_examine_error_rate_is_flagged_unreliable` (19/20 = 95%) and
`test_low_examine_error_rate_is_not_flagged_unreliable` (0/1).

The live repro this addresses: a `--top 400 --per-org 2` run at `ac9a5d2`
returned 90 comparable / 13 divergent (14.4%) with 75 `examine_error`
(18.75%), and the `upstream_non_chat_pipeline_tag` check caught only 1 of 2
known ASR repos because the other's lookup was throttled. Items (a) and (b)
reduce how often this happens; item (c) makes sure that if it happens
anyway, the output says so instead of quietly publishing a number computed
over a crippled sample.

## 3. S006 message cites a real symbol, and drops the opt-in phrasing

Changed both the `Finding` message and the two nearby explanatory comments
in `s006_double_bos` (`src/ggufdoctor/checks/sanity.py`):
`common_chat_apply_template` (does not exist in current llama.cpp) →
`common_chat_template_direct_apply_impl` (the actual function in
`common/chat.cpp` the surrounding comment already correctly cited — only
the `Finding.message` string itself and one comment line had the wrong
name). Also removed the implication that `--jinja` is opt-in: the message
now says Jinja templating is llama-server's and llama-cli's *default*
(`use_jinja = true` in `common/common.h`), not a flag a caller has to turn
on. No other S006 wording, severity, or test assertion changed.

## 4. Self-referential base guard mirrored onto the lint path

`sources.resolve`'s repo-id branch now applies the same guard
`survey._examine` already had: `if not base or base.lower() ==
target.lower(): return model, None, Coverage("no_base_model", families)`.
Previously only `survey.py` skipped a repo whose `base_model` points at
itself; `ggufdoctor <repo>` on such a repo would fetch its own template as
"upstream", compare it against itself, and report `identical` — a false
"verified against upstream" instead of no comparison at all.

Test added: `tests/test_sources.py::test_self_referential_base_model_is_skipped_on_lint_path`,
using a client whose `upstream_template` raises `AssertionError` if called
at all (mirroring the existing `SelfReferentialBaseModelClient` pattern in
`test_survey.py`).

## 5. Comment on the survey's placeholder-token gap

Added a comment in `survey._examine`, immediately above where the
survey's `GgufModel` is constructed, naming the gap explicitly: the survey
builds no `tokens`/`bos_token_id`/`eos_token_id` for either side, so
`checks/sanity._with_real_tokens` is a no-op and both the GGUF's own
template and the upstream template render against the same
engine-fabricated placeholder `bos_token`/`eos_token` strings. Symmetric —
it cannot manufacture a divergence between the two sides by itself — but it
means the survey never exercises the real-token protection the lint path
has (S004/S005/S006's `_real_token` gating). Per the task, no restructuring
to fetch a per-repo vocab was done; this is a documented, accepted gap for
v0.1.

---

## Files changed

- `src/ggufdoctor/checks/sanity.py` — items 1, 3
- `src/ggufdoctor/hf.py` — item 2b (`_fetch` retry wrapper)
- `src/ggufdoctor/survey.py` — items 2a, 2c, 5
- `src/ggufdoctor/sources.py` — item 4
- `tests/test_checks_sanity.py`, `tests/test_cli.py`, `tests/test_hf.py`,
  `tests/test_sources.py`, `tests/test_survey.py` — new tests, plus the one
  updated mock (`UpstreamOnlySpeechPipelineClient`) noted in item 2a

## Held fixed (verified, not touched)

All finding ids, severities, and messages except S006's citation; every
public signature (`HfClient.__init__`/`model_info`/`upstream_template`/
`list_gguf_models`, `survey()`, `sample_repos()`, `to_markdown()`,
`resolve()`, `is_repo_id()`); `per_org` default `2`; `comparable` as the
denominator for both `divergent_pct` and `download_weighted_pct`;
`schema_version` `"1"`; exit codes `0`/`1`/`2`; Jinja2 remains the only
runtime dependency (retry/backoff is stdlib `time.sleep` only); no test
reaches the network (all new tests use fake openers/clients); `corpus.json`,
`.gitignore`, `.superpowers/` (other than this report), and the two
untracked `docs/research/` evidence files were not edited.
