# Resume here

State as of 2026-08-31. Design and planning are **complete and approved**;
**no implementation code exists yet**. Task 1 was about to be dispatched.

## What this is

`ggufdoctor` — a CLI that lints the chat template embedded in a GGUF file.
Three check families: self-contained sanity (offline), cross-engine equivalence
(Jinja2 vs minja vs Ollama's Go conversion), and opt-in upstream comparison.

Chosen after evaluating and rejecting four other ideas — see
`docs/research/idea-evaluation.md` before proposing anything different.

## Where things stand

| | |
|---|---|
| Branch | `feat/v0.1` (implementation must not land on `main`) |
| Spec | `docs/superpowers/specs/2026-08-31-ggufdoctor-design.md` — **approved** |
| Plan | `docs/superpowers/plans/2026-08-31-ggufdoctor-v0.1.md` — 12 TDD tasks, **approved** |
| Execution method | subagent-driven-development, fresh subagent per task |
| Ledger | `.superpowers/sdd/2026-08-31-ggufdoctor-v0.1/progress.md` (git-ignored, on disk) |
| Progress | pre-flight scan done, 5 findings ruled on, **0 of 12 tasks implemented** |

## To resume

1. Read the plan and the spec.
2. Read the ledger — it holds the pre-flight scan table and five rulings that
   **must** be carried into dispatches.
3. Continue subagent-driven-development from Task 1. Record `BASE` before each
   dispatch; the merge base is `36611bb`.

## Rulings that must survive (from the pre-flight scan)

These are plan defects already found and decided. Carry them into the relevant
task dispatch or the tasks will fail:

- **Task 2 must also create an empty `tests/__init__.py`.** Without it, pytest
  puts `tests/` on `sys.path` instead of the repo root and every
  `from tests.helpers.gguf_builder import …` fails (Tasks 3, 4, 6, 11, 12).
- **Task 5 must also create an empty `src/ggufdoctor/fixture_data/__init__.py`.**
  `importlib.resources.files()` needs an importable package.
- **Task 5: drop the `force-include` block** from the pyproject edit — hatchling
  already ships package data; the block risks double-inclusion.
- **Task 6: ignore `CHAT_ARCHITECTURES`** in the interfaces list — it is never
  defined or used; only `NON_CHAT_ARCHITECTURES` exists.
- **Task 12: rewrite `cli.py` in full**, do not follow the prose rename
  instruction — it is the one place the plan violates its own no-placeholder rule.

## Evidence worth not losing

- `docs/research/2026-08-31-survey-raw.json` — per-repo records behind the 15.1%.
- `docs/research/probe2-throwaway.py` — the script that produced it. Superseded by
  the `survey` subcommand once Task 12 lands; kept for auditability.
- `docs/research/reports/` — eight full research reports with citations.

## Things already learned the hard way

- **Verify against the real CLI before recommending anything.** Two earlier
  recommendations were killed by a single `--help` each (`claude plugin eval`,
  `claude --max-budget-usd`).
- **Check publisher concentration before quoting an ecosystem statistic.** The
  first survey read 46.7%; it was one publisher dominating the download
  rankings. The per-org cap is why the real figure is 15.1%.
- **Compare rendered output, never template source.** Source diffs are dominated
  by engine-compatibility rewrites that change nothing the model sees.
- **Coverage gaps must be reported, never dropped.** Gated Google repos were
  being silently misfiled as "no chat template", which shrank the denominator.
