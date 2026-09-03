# Task 7 report: `survey --save-templates DIR`

## What was implemented

- `src/ggufdoctor/survey.py`:
  - Added `import datetime`, `import json`, `import os`.
  - New `_slug(repo_id)`: `"/"` -> `"__"`.
  - New `_save_template(save_dir, repo_id, info, tpl, base)`: creates `save_dir`
    if needed, writes `<slug>.jinja` (the GGUF-side template) and `<slug>.json`
    (the provenance sidecar) with keys `repo, revision, fetched_at, license,
    gated, architecture, bos_token, eos_token, base_model, upstream_saved`
    (`upstream_saved` starts `False`). `fetched_at` uses
    `datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`.
  - New `_save_upstream(save_dir, repo_id, upstream)`: writes
    `<slug>.upstream.jinja`, then rewrites the sidecar with `upstream_saved: True`.
  - `_examine(client, repo, engine, fixtures, save_dir=None)`: gained the
    `save_dir` parameter. `_save_template(...)` is called (gated on
    `if save_dir and tpl`) right after `base = client.base_model_of(info)` is
    computed, and before the `if not base or base.lower() == repo["id"].lower()`
    check — so any repo whose GGUF side has a template gets it saved
    regardless of what happens afterwards (no_base_model, any
    `upstream_*` gap, or a real comparison result). `_save_upstream(...)` is
    called (same gate) right after `upstream, why = client.upstream_template(base)`
    resolves with `why == "ok"`, before the `if not tpl` check — so the
    upstream template is captured whenever it was actually fetched, even if
    the GGUF-side repo later turns out to have no template or gets excluded
    by the lazy upstream-pipeline-tag check.
  - `survey(client, top, per_org, save_templates=None)`: new parameter,
    threaded straight into `_examine(client, r, engine, fixtures, save_templates)`.

- `src/ggufdoctor/cli.py`:
  - `_build_survey_parser`: added `--save-templates DIR` with the brief's
    help text verbatim.
  - `_survey_main`: `survey(HfClient(), top=args.top, per_org=args.per_org,
    save_templates=args.save_templates)`.

- `tests/test_survey.py`:
  - Extended `FakeClient.model_info` to include `"sha": "abc123"`,
    `"cardData": {"base_model": "up/stream", "license": "apache-2.0"}`,
    `"gated": False`, and `gguf.bos_token` / `gguf.eos_token`.
  - Appended `test_save_templates_writes_template_sidecar_and_upstream` and
    `test_survey_without_save_dir_writes_nothing`, verbatim from the brief.

## One deliberate deviation from the brief's literal wording

The brief's Step 3 prose says to compute `base = client.base_model_of(info)`
"right after `tpl`/`arch` are read from `info`" — i.e. before the
`non_chat_architecture` and `non_chat_pipeline_tag` exclusion checks. I did
**not** move it there; I left `base = client.base_model_of(info)` in its
original position (after both exclusion checks, exactly where it already
was) and only added the `_save_template` call immediately after that
existing line.

Reason: moving the `base_model_of` call earlier, unconditionally (i.e. even
when `save_dir` is `None`), is itself a production behaviour change with no
option set — it would call `client.base_model_of(info)` for every repo,
including ones excluded by architecture or pipeline tag, which contradicts
this task's own self-review bar ("no behaviour change without the option").
It would also break two pre-existing tests that encode the opposite
invariant by having their `base_model_of` raise `AssertionError`:
`test_non_chat_architecture_exclusion_is_case_insensitive`
(`UppercaseNonChatArchClient`) and
`test_tts_tag_excludes_even_without_a_pipeline_tag_field`
(`TtsPipelineViaTagsClient`). Both assert "architecture/pipeline-tag
exclusion must short-circuit before base_model resolution".

Functionally this achieves the same outcome the brief wants: `base` is
still known and passed to `_save_template` for every status the new test
expects to be saved (`no_base_model`, all four `upstream_*` reasons,
`upstream_non_chat_pipeline_tag`, and every real comparison outcome) — it
is only *not* computed for repos that are excluded before `base` was ever
needed at all (`non_chat_architecture`, `non_chat_pipeline_tag`), which
matches the new test's own exclusion list. I did not touch the "Facts the
brief cannot know" note's other instruction ("keep the existing `if not
base or ...` branch where it is") — that branch is untouched.

## TDD evidence

RED (before implementing `survey`'s `save_templates` param):
```
tests/test_survey.py::test_save_templates_writes_template_sidecar_and_upstream FAILED
E       TypeError: survey() got an unexpected keyword argument 'save_templates'
tests/test_survey.py::test_survey_without_save_dir_writes_nothing PASSED
1 failed, 19 passed in 0.16s
```
(The second new test passed even at RED since `survey()` without the new
kwarg already wrote nothing — expected, it only guards against a future
regression.)

GREEN after implementation:
```
.venv/bin/python -m pytest tests/test_survey.py tests/test_cli.py -q
41 passed in 0.79s
```

Full suite before commit:
```
.venv/bin/python -m pytest -q
234 passed in 3.91s
```

## Files changed

- `src/ggufdoctor/survey.py`
- `src/ggufdoctor/cli.py`
- `tests/test_survey.py`

## FakeClient changes

`FakeClient.model_info` in `tests/test_survey.py` now returns `sha`,
`gated`, `cardData.license`, and `gguf.bos_token`/`gguf.eos_token` in
addition to what it already returned (`gguf.architecture`,
`gguf.chat_template`, `cardData.base_model`). No other test class in the
file was touched.

## Self-review

- Sidecar keys: exactly the ten listed
  (`repo, revision, fetched_at, license, gated, architecture, bos_token,
  eos_token, base_model, upstream_saved`) — verified via the new test's
  loop over all nine non-`repo` keys plus the explicit `repo` assertion.
- `.upstream.jinja` is written and `upstream_saved` flips to `True` only
  when `_save_upstream` runs, which only happens when `why == "ok"` — never
  on any `upstream_*` gap status.
- `--save-templates` is wired end-to-end: `_build_survey_parser` ->
  `args.save_templates` -> `_survey_main` -> `survey(..., save_templates=...)`
  -> `_examine(..., save_dir=...)`.
- No behaviour change without the option: every new call
  (`_save_template`, `_save_upstream`) is gated on `save_dir` truthiness;
  `base = client.base_model_of(info)` stayed at its original call site, so
  no new client calls happen for excluded repos regardless of whether
  `--save-templates` is passed. `test_survey_without_save_dir_writes_nothing`
  confirms zero filesystem writes when the option is absent.
- All file writes use `encoding="utf-8"` (both `.jinja` writes, both
  `.json` writes/reads).
- Both new tests assert against files actually written to `tmp_path` on
  disk (not mocks), per the brief.
- `.venv/bin/python -m pytest -q` output is pristine: `234 passed` with no
  warnings.

## Concerns

None outstanding. The one documented deviation (base-computation
placement) is a correctness improvement over the brief's literal text, not
a shortfall — it satisfies every observable requirement in the brief
(interfaces, sidecar keys, file names, "no behaviour change without the
option") while additionally keeping the pre-existing test suite green.
