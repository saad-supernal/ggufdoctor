# Task 10 report: CI engine-build job, wheel contents, version bump

## Files changed

- `pyproject.toml` — `version = "0.2.0"` (was `0.1.0`)
- `src/ggufdoctor/__init__.py` — `__version__ = "0.2.0"` (was `0.1.0`)
- `tests/test_cli.py` — appended `test_version_is_0_2_0()` pinning the version
- `.github/workflows/ci.yml`
  - `build` job: `need` list in the wheel-contents check extended with
    `ggufdoctor/engine_data/llamacpp-jinja.wasm` and
    `ggufdoctor/engine_data/llamacpp-jinja.json`
  - `build` job: new step `installed engine renders through the wheel's module`
    after `installed console script runs`
  - new job `engine-build` (ubuntu-latest, Python 3.12): installs the package,
    runs `engine/fetch-llamacpp.sh` (verifies against
    `engine/llamacpp-sources.sha256`), runs `engine/build.sh --out /tmp/fresh`
    (wasi-sdk 34 auto-downloaded for `Linux-x86_64` since `WASI_SDK` is
    unset), runs the whole test suite against the freshly built module via
    `GGUFDOCTOR_ENGINE_WASM=/tmp/fresh/llamacpp-jinja.wasm`, then reports
    (informationally) whether the fresh `.wasm` is byte-identical to the
    committed one by comparing SHA-256 against the manifest.

No other files were touched. `engine/fetch-llamacpp.sh` and `engine/build.sh`
were already executable in git (mode `100755`, verified via `git ls-files -s`)
so no permission fix was needed.

## Local verification before push

- `.venv/bin/python -m pytest tests/test_cli.py -q` — 22 passed
- `.venv/bin/python -m pytest -q` (full suite) — 253 passed, 10 deselected
  (network/conformance markers, as intended)
- Confirmed `src/ggufdoctor/engine_data/{llamacpp-jinja.wasm,llamacpp-jinja.json,__init__.py}`
  and `LICENSE` are tracked in git, so hatchling's default VCS-based file
  selection (`[tool.hatch.build.targets.wheel] packages = ["src/ggufdoctor"]`,
  no explicit include/exclude) would carry them into the wheel — confirmed for
  real by the CI `build` job's wheel-listing output (see below).
- Could not run `python -m build` locally (repo `.venv` has no `pip`/`build`
  installed and installing into it was out of scope); deferred that check to
  CI, which is authoritative anyway.

## Commits

- `5fbd6b0` — `ci: engine-build job regenerates the module; wheel must carry it; version 0.2.0`
  (4 files changed: `.github/workflows/ci.yml`, `pyproject.toml`,
  `src/ggufdoctor/__init__.py`, `tests/test_cli.py`)

Pushed: `git push -u origin feat/v0.2` (new branch on remote
`git@github.com:saad-supernal/ggufdoctor.git`). No commits to `main`, no tags.

## Pull request

Opened as draft: **https://github.com/saad-supernal/ggufdoctor/pull/1**
("v0.2: llama.cpp engine via WASM, cross-engine checks", base `main`, head
`feat/v0.2`). Body ends with the required
`🤖 Generated with [Claude Code](https://claude.com/claude-code)` line.

## CI run

Run id **33736530232** (workflow `CI`, triggered by the PR), triggered
2026-09-03T09:01:17Z. Final status: `completed` / `success`.

Per-job outcomes (all green on the first push — no fixes were needed):

| Job | Outcome |
|---|---|
| `test (ubuntu-latest, 3.11)` | success |
| `test (ubuntu-latest, 3.12)` | success |
| `test (ubuntu-latest, 3.13)` | success |
| `test (macos-latest, 3.11)` | success |
| `test (macos-latest, 3.12)` | success |
| `test (macos-latest, 3.13)` | success |
| `test (windows-latest, 3.11)` | success |
| `test (windows-latest, 3.12)` | success |
| `test (windows-latest, 3.13)` | success |
| `build` | success |
| `engine-build` | success |
| `conformance` | success |

All 12 jobs green: `test` × 9, `build`, `engine-build`, `conformance`.

Notable log excerpts confirming the checks actually exercised the intended
behavior (not just "green"):

- `build` job, wheel listing includes `ggufdoctor/engine_data/llamacpp-jinja.json`
  and `...llamacpp-jinja.wasm` (per the `need` list) alongside
  `ggufdoctor/fixture_data/corpus.json` and
  `ggufdoctor-0.2.0.dist-info/licenses/LICENSE`; dist-info name confirms
  version `0.2.0` landed in the built artifact.
- `build` job, new step output: `engine ok: b10775 wasmtime 48.0.0` — the
  installed wheel's `LlamaCppEngine` is available and renders correctly.
- `engine-build` job: `fetch-llamacpp.sh` verified sources, `build.sh --out
  /tmp/fresh` succeeded (wasi-sdk 34 auto-fetched), then
  `GGUFDOCTOR_ENGINE_WASM=/tmp/fresh/... python -m pytest -q` reported
  `253 passed, 10 deselected` — the freshly rebuilt module passes the whole
  suite.
- `engine-build` job, final report step: `fresh` sha256
  `e3bd5fe2...` vs `committed` sha256 `4de88e68...` →
  `differs (informational: toolchain nondeterminism)`. This is the
  expected/allowed outcome per the brief — the step is purely informational,
  never fails the job, and the divergence is attributable to
  non-reproducible toolchain output rather than a defect.

## Failures encountered

None. No red job on the first CI run; no fixes, no re-pushes were required.

## Self-review

- Completeness: version `0.2.0` set in both `pyproject.toml` and
  `src/ggufdoctor/__init__.py`, and pinned by `test_version_is_0_2_0`, which
  passes locally and (transitively, as part of the full suite) in every
  `test` and `engine-build` CI job. Wheel check's `need` list carries all
  three data files (fixture corpus, engine wasm, engine manifest) and was
  confirmed against the actual wheel listing in CI. `engine-build` job is
  present exactly as specified in the brief. PR #1 is open in draft state
  against `main`.
- Honesty: all 12 jobs on run 33736530232 are `completed`/`success`, verified
  via `gh run view --json jobs`, not merely inferred from `gh run watch`
  output. No check was loosened, skipped, or worked around.
- Discipline: only the files listed in the brief were modified; YAML for the
  `engine-build` job and the `build` job additions were used verbatim from
  the brief. `main` was not touched, nothing was merged, no tags were
  created. Commit message carries the required `Co-Authored-By` trailer.

## Concerns

- None outstanding. The only asymmetry versus a "perfect" world is that the
  freshly rebuilt `.wasm` is not byte-identical to the committed one; the
  brief explicitly anticipates this ("differs (informational: toolchain
  nondeterminism)") and treats it as informational rather than a failure
  condition, so this is not a defect to fix.
- The PR remains in draft per instructions; it has not been merged and no
  further action (merge, tag, push to `main`) was taken.
