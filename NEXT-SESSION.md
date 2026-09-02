# Where this stands

**v0.1 is shipped.** Live at https://github.com/saad-supernal/ggufdoctor (public, MIT,
default branch `main`; `feat/v0.1` is identical and kept for history). 166 tests, CI on
three OSes × Python 3.11–3.13, wheel verified to carry the fixture corpus.

## The number

**14.8%** of comparable top-downloaded GGUF chat models (16/108) render different prompt
text than their upstream; **31.4%** weighted by downloads; 15 of 87 publishers. Measured
2026-09-01 by the shipped tool, zero fetch failures. Regenerate with:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

The earlier 15.1% from the throwaway probe is **superseded** — `docs/research/README.md`
explains the four reasons they differ. Do not quote 15.1% anywhere.

## Next: v0.2 — start here

**Read `docs/v0.2-kickoff.md` first.** It carries the scope (minja engine, X001/X002/
X004/X005, `--engines`, the conformance suite, vendored templates), the one design
question that decides the architecture (how minja gets into Python — settle it with a
spike, not a plan), a correction to the old deferred note (the survey JSON files do
**not** contain template text, so vendoring needs a fetch step), and the v0.1 lessons
the X family must not repeat. v0.3 (Ollama engine, X003, `--runtime`) follows it.

Process is the same as v0.1: brainstorm → spec amendments → plan → subagent-driven
development with two-verdict reviews and a whole-branch review. Branch `feat/v0.2`.

## Open outside the code (Saad's calls)

- **PyPI.** `pip install ggufdoctor` does not work yet; the name is free.
  `.github/workflows/publish.yml` publishes on a `v*` tag via trusted publishing.
  **Step 1 (Saad, needs PyPI login):** pypi.org → create project `ggufdoctor` or use
  "pending publisher" → add GitHub publisher: owner `saad-supernal`, repo `ggufdoctor`,
  workflow `publish.yml`, environment `pypi`. **Step 2 (Claude):**
  `git tag v0.1.0 && git push origin v0.1.0`, then `gh release create v0.1.0`.
  The tag is deliberately **not** pushed yet — doing so before step 1 produces a
  guaranteed-failing publish run on a fresh public repo.
- **Account.** Repo is under `saad-supernal` (work-flavoured handle). If reputation
  should accrue to a personal handle, `gh repo transfer` *before* any announcement.
- **Announcement.** Nothing posted anywhere. Lead with the 53 dead base-model pointers
  and the Qwen-vs-Qwen row, not the tool.

## Things learned the hard way — read before changing checks

Every one of these was a real defect that shipped into a review:

1. **Never ask template source a question only a render can answer.** S004, S005 and S006
   all did, and S005 flagged the entire Mistral and Llama-2 families as broken because
   those templates emit EOS through `{{ eos_token }}` rather than a literal.
2. **A regression test scoped to one finding id will miss the next one.** The guard added
   after that S005 bug asserted `"S005" not in ids` and sat green on top of an S003 bug in
   the same fixtures for the rest of the build. The real-template tests now assert the
   *complete* finding set with the models' genuine metadata.
3. **Silence is a lie the tool tells.** Three separate times a check returned no findings
   because it could not run, and the report read as clean. `Coverage.checks_not_evaluated`
   exists for this; every bail-out must record itself.
4. **A warning that fires on everything is not a warning.** Qualifying the headline on
   every default run made "partial" meaningless. Declining to check is not the same as
   failing to check.
5. **Verify vendor behaviour in the vendor's source.** S006 was about to warn every
   llama.cpp user about a double BOS that `common/chat.cpp` strips.
6. **The survey must survive its own API budget.** An extra `model_info` per repo got us
   rate-limited and silently computed the figure over a sample a fifth of which never
   loaded. Fetch failures above 5% now flag the run unreliable.

## Where the process record lives

`docs/process/v0.1/` — the full v0.1 ledger (`ledger.md`, rulings E1–E28 and every
per-task review outcome), all twelve task briefs and reports, and the three final-fix
reports. Committed, so it survives `git clean`. The live working copy for a plan in
progress is `.superpowers/sdd/<plan-basename>/progress.md` (git-ignored); copy it into
`docs/process/v0.2/` when v0.2 closes.
