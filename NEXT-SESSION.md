# Where this stands

**v0.1 is built.** Branch `feat/v0.1`, 166 tests passing, the CLI and the `survey`
subcommand both work end to end against live Hugging Face.

## The number

**14.8%** of comparable top-downloaded GGUF chat models (16/108) render different prompt
text than their upstream; **31.4%** weighted by downloads; 15 of 87 publishers. Measured
2026-09-01 by the shipped tool, zero fetch failures. Regenerate with:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

The earlier 15.1% from the throwaway probe is **superseded** — `docs/research/README.md`
explains the four reasons they differ. Do not quote 15.1% anywhere.

## Not done yet

- **No git remote.** Nothing is pushed anywhere; `[project.urls]` is deliberately absent
  until a real URL exists.
- **v0.2:** minja via WASM, the `X` check family (cross-engine equivalence), `--engines`,
  the engine conformance suite, and vendoring real templates as offline test data
  (reuse `docs/research/2026-09-01-survey.json`).
- **v0.3:** Ollama's Go template conversion, `--runtime`.

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

`.superpowers/sdd/2026-08-31-ggufdoctor-v0.1/progress.md` — the full ledger, including
rulings E1–E28 and the per-task review outcomes. It is git-ignored (`.superpowers/sdd/`
carries a blanket ignore), so it will not survive `git clean -fdx`.
