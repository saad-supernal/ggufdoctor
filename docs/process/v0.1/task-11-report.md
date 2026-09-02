# Task 11 report: source resolution and CLI

## What was created

- `src/ggufdoctor/sources.py` — `is_repo_id(target)` and
  `resolve(target, compare_upstream=None, client=None) -> (GgufModel, str | None, Coverage)`.
  Transcribed from the brief verbatim, with one addition: docstrings on both
  functions explaining the local-path-first `os.path.exists` check in
  `is_repo_id` and the offline guarantee in `resolve` (no behavioral change).
- `src/ggufdoctor/cli.py` — `build_parser()` and `main(argv=None) -> int`.
  Transcribed from the brief with **one substantive addition**: the
  `checks_not_evaluated` merge described below (the brief's own text flagged
  this as the wiring step still needed; the sample `main()` in the brief body
  did not yet include it).
- `tests/test_sources.py` — the three tests given in the brief, verbatim.
- `tests/test_cli.py` — the five tests given in the brief, verbatim, plus one
  new test: `test_checks_not_evaluated_reaches_the_reports`.

## Test command and output

```
.venv/bin/python -m pytest tests/ -v
```

112 passed (the prior 103 + 3 in `test_sources.py` + 6 in `test_cli.py`,
one more than the brief's step 4 expected 8 because of the added merge-guard
test). No failures, no errors, no skips. Also ran plain `pytest tests/ -v`
(no `-m` override) to confirm the `network` marker's `addopts = "-m 'not
network'"` default is in effect and that neither new test file registers
anything under that marker — `grep -i network` over `--collect-only` output
matched nothing.

## Commit

`bf9f148` — "feat: source resolution and CLI" on branch `feat/v0.1`.
4 files changed, 244 insertions, 0 deletions:
`src/ggufdoctor/sources.py`, `src/ggufdoctor/cli.py`, `tests/test_sources.py`,
`tests/test_cli.py`.

## Complete CLI surface

```
ggufdoctor [-h] [--compare-upstream REPO] [--fail-on {error,warn,info,never}]
           [--fixtures PATH] [--json PATH] [--ignore-file PATH]
           [--require-upstream]
           target
```

| Flag | Default | Notes |
|---|---|---|
| `target` (positional) | — | required; local `.gguf` path or HF repo id |
| `--compare-upstream REPO` | `None` | triggers family R (upstream comparison); the only thing that makes `resolve` touch the network for a local-path target |
| `--fail-on {error,warn,info,never}` | `"error"` | threshold passed to `exit_code()` |
| `--fixtures PATH` | `None` | custom fixture corpus JSON, passed to `load_fixtures()` |
| `--json PATH` (dest `json_path`) | `None` | when set, writes `build_json()` output to this path |
| `--ignore-file PATH` | `".ggufdoctorignore"` | passed to `load_ignores()`; silently absent-tolerant (see `ignorefile.load_ignores`) |
| `--require-upstream` | `False` (store_true) | if set and `coverage.upstream != "ok"`, forces exit 1 regardless of `--fail-on` |

The package's `pyproject.toml` already declared
`[project.scripts] ggufdoctor = "ggufdoctor.cli:main"` before this task (Task
0/setup), so `.venv/bin/ggufdoctor` is a working console script once
`cli.py` exists — verified manually (see below), no further packaging change
was needed.

## The `checks_not_evaluated` merge

`resolve()` builds `Coverage(upstream_reason, families_run)` *before* any
check has run — at that point `Coverage.checks_not_evaluated` is `[]` by
its dataclass default. Checks S005/S006 (in `checks/sanity.py`) append their
own id to the **`CheckContext.checks_not_evaluated`** list — a separate
object — when they cannot evaluate at all (missing or out-of-range
`bos_token_id`/`eos_token_id`). Both `report/human.render_human` and
`report/json_report.build_json` read `coverage.checks_not_evaluated`
directly; neither one ever looks at `ctx`. So without an explicit copy, a
model that S005 could not fully check would print a bare `"no findings"`
and ship `"checks_not_evaluated": []` in the JSON — a false clean bill of
health.

`main()` closes that gap with one line, placed after `run_sanity_checks`/
`run_reference_checks` finish and before either report is built:

```python
coverage.checks_not_evaluated = list(ctx.checks_not_evaluated)
```

**Guard test:** `tests/test_cli.py::test_checks_not_evaluated_reaches_the_reports`.
It uses the existing `_model()` fixture, which never sets
`tokenizer.ggml.eos_token_id`, so `s005_eos_mismatch` always records itself
on `ctx.checks_not_evaluated` while returning no `Finding` (a "clean but
incomplete" run). The test asserts:
- exit code is still `0` (no findings fired),
- the human report contains `"S005 not evaluated"` and the qualified
  headline `"no findings (partial: ..."`,
- the JSON report's `coverage.checks_not_evaluated == ["S005"]`.

I verified this test actually catches the bug it's meant to catch: I
temporarily deleted the merge line from `cli.py`, reran just this test, and
it failed with `AssertionError: assert 'S005 not evaluated' in '...no
findings (partial: R family skipped, upstream not_requested)\n...'` —
exactly the silent-false-clean scenario the brief warned about. I then
restored the line and reran the full suite (112 passed) before committing.

## Error paths and exit codes (verified via the installed console script)

| Scenario | User sees | Exit code |
|---|---|---|
| Clean model, no upstream compared | Human report headline `"no findings"` (or qualified `"no findings (partial: ...)"` when coverage is incomplete) | 0 |
| Findings at/above `--fail-on` threshold | Full report with each finding's id/severity/message | 1 |
| `--fail-on never` | Report printed, but exit forced to 0 regardless of findings | 0 |
| Nonexistent local path | `ggufdoctor: [Errno 2] No such file or directory: '<path>'` on stderr | 2 |
| File exists but isn't GGUF (bad magic) | `ggufdoctor: <path>: missing GGUF magic` on stderr (from `NotGgufError`) | 2 |
| Unreachable network / bad ignore file / any other exception during resolve-and-check | `ggufdoctor: <exception message>` on stderr | 2 |

No stack trace reaches the user in any of these cases — `main()` wraps the
entire resolve → fixtures → checks → ignores pipeline in one
`try/except Exception`, so any expected failure surfaces as a one-line
message and exit 2, matching the global constraint.

Manually verified with the installed script (`.venv/bin/ggufdoctor`):
- `ggufdoctor /no/such/model.gguf` → stderr message, exit 2.
- `ggufdoctor <file containing "NOPE">` → `missing GGUF magic`, exit 2.
- `ggufdoctor <synthetic clean model>` → human report with `no findings
  (partial: R family skipped, upstream not_requested, S005 not evaluated)`,
  exit 0.
- `ggufdoctor --help` → full usage text with all flags listed above.

## Offline-property verification

Two layers of evidence:
1. `tests/test_sources.py::test_local_resolve_is_offline` (from the brief,
   unmodified) monkeypatches `urllib.request.urlopen` to raise
   `AssertionError` on any call, then calls `resolve(str(local_path))` with
   `compare_upstream=None` and asserts it returns successfully. This is the
   authoritative test: if any code path in `resolve()` for a local,
   non-comparison run tried to construct or call an `HfClient`, this test
   would fail loudly rather than silently succeeding.
2. Manual trace of `resolve()`: the local-path branch (`is_repo_id(target)`
   is `False`) only calls `hf = client or HfClient()` inside the
   `if compare_upstream is None: return ...` guard — i.e. that line is
   unreachable when `compare_upstream` is `None`. No `HfClient()` is ever
   constructed, let alone used, for the offline case.

Also ran plain `pytest tests/ -v` (default `-m 'not network'` from
`pyproject.toml`) and confirmed no test in `test_sources.py` or `test_cli.py`
is collected under the `network` marker — none of the new tests touch the
real network, all mocking is done via the `client=FakeClient()` /
`monkeypatch` seams that Tasks 4/7 already provide for exactly this purpose.

## Deviations from the brief

One, and it was explicitly called for by the brief's own prose (not a
judgment call I made unprompted): added the
`coverage.checks_not_evaluated = list(ctx.checks_not_evaluated)` line to
`main()`, which the brief's sample code block did not include, plus the
guard test described above. Everything else — `sources.py`, `cli.py`'s
structure/flags/exit-code logic, and all eight given tests — was
transcribed verbatim as instructed, since flag names and exit codes are a
public contract.

I used `list(ctx.checks_not_evaluated)` rather than a bare assignment of
`ctx.checks_not_evaluated` to avoid coverage and ctx sharing the same list
object (defensive; no test currently depends on this distinction, but it
costs nothing and avoids a subtle aliasing bug if a future task mutates
either list after `main()` returns).

## What Task 12 should know

- The full pipeline is now wired end-to-end: `resolve` → `load_fixtures` →
  `Jinja2Engine` → `run_sanity_checks`/`run_reference_checks` →
  `load_ignores`/`apply_ignores` → merge `checks_not_evaluated` →
  `render_human`/`build_json` → `exit_code`. Any future check family that
  adds its own "could not evaluate" bookkeeping on `CheckContext` must be
  merged into `coverage` the same way, in the same place in `main()` —
  there is exactly one merge point, right after the ignore-filtering step
  and before either report is built.
- `resolve()`'s repo-id branch (`is_repo_id(target)` is `True`) is
  implemented per the brief but has **no direct test coverage yet** — the
  brief's `test_sources.py` only exercises the local-path branch. If Task
  12 or a later review wants confidence in the HF-repo-id path (calling
  `hf.model_info`, `hf.base_model_of`, `hf.upstream_template` and building
  a `GgufModel` from `info["gguf"]`), that would need a `FakeClient`-driven
  test analogous to `test_local_with_compare_upstream_runs_r_family`.
  Nothing in this task's brief asked for it, so it wasn't added, but it's a
  gap worth knowing about.
- `--ignore-file` defaults to `.ggufdoctorignore` in the current working
  directory (relative path) — `load_ignores` returns `[]` silently if that
  file doesn't exist, so this default is safe to leave in place for any
  directory without one.
- The console script `ggufdoctor` was already declared in `pyproject.toml`
  before this task; no packaging changes were needed here.
- `run_reference_checks` in `main()` is gated by
  `if upstream or coverage.upstream == "not_found"` — this matches the
  brief exactly and means family R also runs (to surface R003) when the
  upstream lookup came back `"not_found"`, even though there's no template
  to diff against in that case. This is intentional per the brief; other
  non-"ok" reasons (`"gated"`, `"fetch_error"`, `"no_base_model"`,
  `"genuinely_absent"`) do not trigger family R and have no dedicated
  reference check reacting to them beyond the coverage caveat text.

## Fix round 1

Four issues from review, addressed on top of `bf9f148`; commit `e51e88e`.

### 1. `--json` to an unwritable path printed a traceback and exited 1

`cli.py`'s `try/except` (inherited verbatim from the brief) ended right
after `apply_ignores`; the `render_human()` print and the `--json` file
write both ran unguarded afterward. A `PermissionError` from `open()`
therefore escaped as a full traceback, and since it was never caught, the
process's default exit path returned 1, not 2 — violating both "no
traceback on an expected failure" and "exit 2 for operational errors" at
once.

Fix: `render_human()`'s call and the entire `--json` write (build + open +
`json.dump`) now happen *inside* the same `try` block as `resolve`/checks/
ignores. `print(report)` itself moved to *after* the `try`, using a
`report` variable computed inside it — so if the JSON write fails, nothing
has been printed yet, the exception is caught, one `ggufdoctor: ...` line
goes to stderr, and `main()` returns 2. I audited the rest of `main()` for
other unguarded I/O and found none: `load_fixtures`, `load_ignores`, and
`resolve` were already inside the guard from the original implementation.

**Verified this actually fixes the reported bug**: reverted just this
restructuring (moved the `--json` write back outside the `try`, keeping
everything else), reran `test_unwritable_json_path_exits_two_without_
traceback`, and got exactly the reported failure mode — a `PermissionError`
traceback surfacing through pytest instead of a caught exit 2. Restored the
fix and confirmed the test passes again.

### 2. The "partial" coverage caveat fired on every default run

Previously `_coverage_caveats()` treated `coverage.upstream != "ok"` as
worth flagging, so the ordinary `ggufdoctor model.gguf` invocation (no
`--compare-upstream`, `coverage.upstream == "not_requested"`) always
printed `no findings (partial: R family skipped, upstream not_requested)` —
indistinguishable from a genuine failure like `gated`, training users to
skim past the word "partial" entirely.

Fix, in `report/human.py`:
- New `_upstream_gap(upstream) -> str | None` returns `None` for `"ok"` and
  `"not_requested"` (nothing wrong to report) and a specific phrase for
  every other reason, via a `_UPSTREAM_GAP_TEXT` lookup (`gated`,
  `not_found`, `fetch_error`, `genuinely_absent` covered explicitly;
  `no_base_model` also covered since `resolve()`'s repo-id branch can
  produce it; anything else falls back to `f"upstream {upstream}"`).
- `_coverage_caveats()` now calls `_upstream_gap()` instead of the blanket
  `!= "ok"` check, so a declined comparison never appears in the
  parenthetical, but a real one always does.
- The headline in `render_human()` branches three ways when there are no
  findings:
  - `upstream_gap is None and not coverage.checks_not_evaluated` and
    `upstream == "not_requested"` → the new, unqualified-but-informative
    line (exact wording below).
  - `upstream_gap is None and not coverage.checks_not_evaluated` and
    `upstream == "ok"` → plain `"  no findings"` (unchanged from before).
  - Otherwise → `"  no findings (partial: {caveats})"`, where `caveats`
    combines the upstream-gap phrase (if any) and the
    `checks_not_evaluated` phrase (if any) — so a check gap alone (upstream
    `"not_requested"` or `"ok"`) still forces "partial", and a check gap
    plus a genuine upstream gap combine into one clause exactly as
    specified (`"upstream gated — cannot compare without access, S005 not
    evaluated"`).
- The tail's `note: {fam} family skipped` line is now gated by
  `upstream_gap is not None` too — family R is only ever skipped because
  of upstream status in this codebase (family S never skips), so without
  this gate the tail would carry the same always-on noise the headline had.
  The tail's `note: {check_id} not evaluated` lines are unconditional, as
  before, since a check gap is always genuine regardless of upstream
  status.

**Exact new headline wording, one per coverage case:**
- Nothing missing, comparison declined (`upstream == "not_requested"`,
  `checks_not_evaluated == []`):
  `no findings — local checks only (add --compare-upstream <repo> to also check against the source template)`
- Nothing missing, comparison succeeded (`upstream == "ok"`,
  `checks_not_evaluated == []`): `no findings` (unqualified, unchanged).
- Comparison requested but failed, e.g. gated (`upstream == "gated"`,
  `checks_not_evaluated == []`):
  `no findings (partial: upstream gated — cannot compare without access)`
  — and correspondingly `upstream not found — base model no longer exists`
  for `not_found`, `upstream fetch failed — could not reach the source
  model` for `fetch_error`, `upstream has no chat template to compare
  against` for `genuinely_absent`, `no upstream base model declared` for
  `no_base_model`.
- Check gap alone, any upstream status (e.g. `checks_not_evaluated ==
  ["S005"]`, `upstream == "not_requested"` or `"ok"`):
  `no findings (partial: S005 not evaluated)`
- Both a genuine upstream gap and a check gap combined:
  `no findings (partial: upstream gated — cannot compare without access, S005 not evaluated)`

**Verified against the existing report tests** (`tests/test_report.py`,
unmodified): `test_headline_is_qualified_when_coverage_is_partial` (uses
`Coverage(upstream="gated", families_run=["S"])`) still finds `"no findings
(partial:"`, `"upstream gated"`, and `"R family skipped"` all present in
the output — the first two from the new headline text, the third from the
still-gated tail note (gated is a genuine gap, so that gate stays open).
`test_headline_is_unqualified_when_coverage_is_complete` and
`test_out_of_range_eos_token_id_records_s005_as_not_evaluated` also pass
unchanged. Added new CLI-level tests
(`test_default_local_run_headline_is_not_alarming`,
`test_gated_upstream_produces_a_partial_headline`) exercising both ends
through `main()` itself, not just `render_human()` directly.

The JSON report was left untouched, as instructed — `coverage.upstream`
and `coverage.checks_not_evaluated` are already structured fields there;
no prose to reconcile.

### 3. `is_repo_id()` sent mistyped local paths to the network

Old rule: not an existing path, doesn't start with `.`/`/`/`~`, doesn't end
in `.gguf`, and contains a `/`. Any nonexistent relative path with a slash
qualified — `does/not/exist`, `models/foo`, `checkpoints/model` all read as
repo ids and would trigger a real HTTP request to `huggingface.co`.

New rule, same function signature: after the existing-path and
prefix/suffix checks, split on `/` and require *exactly* two non-empty
segments (`does/not/exist` → 3 segments → never a repo id, matching "a
repo id has exactly two /-separated segments"). For a genuine two-segment
candidate, check whether the *first* segment already exists on disk as its
own local entry (e.g. a real `models/` directory sitting in the current
directory) — if so, treat the whole thing as local, since a same-named
local directory shadowing a real Hub namespace makes local resolution the
safer default (matches the brief's own reasoning: "every other CLI treats
an existing path" this way, extended one level to the shadowing directory
rather than only the exact full path).

This does mean a two-segment, nonexistent path with no locally-shadowing
first segment (e.g. `unsloth/Qwen3-8B-GGUF`, or `checkpoints/model` before
any `checkpoints/` directory exists anywhere relevant) is still classified
as a repo id — that's unavoidable without either a real namespace registry
lookup or an allowlist of "known local-looking words," neither of which
was asked for or is appropriate. The fix specifically closes the two gaps
the review named as bugs: nested (3+ segment) paths, and paths shadowed by
a real local directory of the same first-segment name.

**New tests** (`tests/test_sources.py`): `test_multi_segment_path_is_not_a_
repo_id` (`org/sub/repo`, `does/not/exist`); `test_nonexistent_path_under_
an_existing_local_directory_is_not_a_repo_id` (`checkpoints/model` is `True`
before a `checkpoints/` directory exists in the test's `tmp_path` cwd, then
`False` once it does — same for `models/foo` against a pre-existing
`models/` directory); `test_existing_local_path_is_never_a_repo_id`
(unchanged behavior, re-asserted explicitly with a nested directory).

**Verified this actually fixes the reported bugs**: reverted `is_repo_id`
to the old implementation, reran `tests/test_sources.py`, and got exactly
two failures — `test_multi_segment_path_is_not_a_repo_id` and
`test_nonexistent_path_under_an_existing_local_directory_is_not_a_repo_id`
— both failing with `is_repo_id(...)` returning `True` where it should be
`False`, i.e. the network-bound-typo bug reproduced. Restored the fix and
confirmed both pass again.

### 4. `--require-upstream` alone was a silent usage error

Previously `--require-upstream` only affected the final `if
args.require_upstream and coverage.upstream not in ("ok",): return 1` check
at the end of `main()`. With no `--compare-upstream`, `coverage.upstream`
is always `"not_requested"` (never `"ok"`), so the flag alone forced exit 1
on every run — failing because the user didn't ask for the thing they also
didn't ask for.

Fix: `main()` now checks `args.require_upstream and not args.compare_
upstream` immediately after parsing args, before `resolve()` or any other
work runs, and if true prints `ggufdoctor: --require-upstream requires
--compare-upstream` to stderr and returns 2 — a usage error, not a finding.
The existing behavior with `--compare-upstream` present is untouched: any
non-`"ok"` `coverage.upstream` still forces exit 1. The flag's `--help` text
now reads "fail (exit 1) if the upstream comparison requested via
--compare-upstream could not be resolved (gated, not found, or otherwise
unreachable); requires --compare-upstream" instead of the old "treat a
missing upstream as a failure," which didn't say what it actually gated.

**Verified this actually fixes the reported bug**: reverted just the new
pre-check block, reran `test_require_upstream_without_compare_upstream_is_
a_usage_error`, and got `assert 1 == 2` — main() returning 1, exactly the
reported behavior. Restored the fix and confirmed the test passes again.

### Test command and result

```
.venv/bin/python -m pytest tests/ -v
```

119 passed (112 from the initial Task 11 commit + 3 new in
`tests/test_sources.py` + 4 new in `tests/test_cli.py`). Re-ran plain
`pytest tests/ -v --collect-only | grep -i network` and confirmed no test
carries the `network` marker. No subagents were dispatched, per
instruction — all four fixes, their regression-catching verification, and
this report were done directly.

### Concerns / things Task 12 should know

- The `is_repo_id` "shadowing directory" check (`os.path.exists(segments[0])`)
  is relative to the process's current working directory, same as the
  pre-existing `os.path.exists(target)` check it sits next to — behavior is
  consistent, but it does mean `is_repo_id`'s answer for a given string can
  differ depending on cwd. This was already true before this fix (the
  existing-target check has the same property) so it isn't a new class of
  behavior, just extended one level.
- The headline/tail wording changes are human-report-only; `build_json()`
  and its schema are completely unchanged (verified by
  `test_json_has_stable_schema_fields` and `test_json_output_written`
  still passing, and by not touching `report/json_report.py` at all in
  this fix round).
- `_UPSTREAM_GAP_TEXT` in `report/human.py` is the single place that maps
  an upstream-coverage reason string to user-facing prose. If a future task
  adds a new `Coverage.upstream` reason value, it will fall back to the
  generic `f"upstream {upstream}"` phrasing automatically (still correctly
  gated as a genuine "partial" case, just without bespoke wording) unless
  that dict is extended.
