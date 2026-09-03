# Where this stands

**v0.2 is built.** Two engines: Jinja2 configured to match transformers, and llama.cpp's
own `common/jinja` engine at build tag `b10775` (commit `67a17c17`), compiled to a
725,239-byte WASM module and run through `wasmtime`. Check family X compares them.
Fixture corpus is version 2. 253 tests, offline, plus a conformance suite that drives the
real `llama-server` binary. Branch `feat/v0.2`, draft PR #1.

v0.1 is live at https://github.com/saad-supernal/ggufdoctor (public, MIT, default branch
`main`).

## The numbers, each with its corpus

Two survey figures now exist and **neither replaces the other**. They use different
fixture corpora, so they are not comparable to one decimal place. Always state the
corpus.

- **Corpus 1 (v0.1, seven fixtures): 14.8%** of comparable top-downloaded GGUF chat
  models (16/108) render different prompt text than their upstream; 31.4%
  download-weighted; 15 of 87 publishers. Measured 2026-09-01.
- **Corpus 2 (v0.2, ten fixtures — adds tool round-trip, typed content, no generation
  prompt): 14.4%** (16/111); 31.2% download-weighted; 15 of 91 publishers. Measured
  2026-09-03, `unreliable: false`, zero fetch failures.

The 0.4pp gap between them is **not** the corpus. In the corpus-2 run no repo diverges
only on one of the three new fixtures, so the three added fixtures brought no new
divergent repo into the numerator; 15 of the 16 divergent repos are the same repos as
two days earlier. What moved is the day's top-400 sample: the comparable denominator
went 108 → 111. `docs/research/README.md` has the full comparison.

Regenerate either with the corresponding release:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

The earlier 15.1% from the throwaway probe is **superseded** —
`docs/research/README.md` explains the four reasons it differs from 14.8%. Do not quote
15.1% anywhere.

**The other publishable number is the agreement one:** on the seven standard fixtures,
llama.cpp's engine agreed with transformers-style Jinja2 on **100 of 100** top GGUF
templates. That is a good result about llama.cpp and the better launch story than a
divergence rate would have been. Evidence:
`docs/research/2026-09-03-engine-spike.md`.

## Next: v0.3

Scope, unchanged from the original build sequence: **Ollama's Go template conversion as
a third engine, `X003`, and `--runtime` mode B** (compare against a real llama.cpp or
Ollama binary the user already has, rather than the bundled module).

Also deliberately deferred out of v0.2, and still open:

- **Counting X divergence inside `survey`.** It would need real vocab tokens per repo
  and a second engine per record. Until then the spike's 100/100 is the published
  cross-engine statement.
- **Per-repo vocab fetching in the survey** (an unchanged v0.1 limitation).
- **Automatic engine bumps.** Bumping the pinned llama.cpp commit is deliberately a
  hand-written PR — see `engine/README.md` for the six steps, which include re-checking
  the ported `chat.cpp` logic by hand.

Process is the same as v0.1 and v0.2: brainstorm → spec amendments → plan →
subagent-driven development with two-verdict reviews and a whole-branch review.

## Open outside the code (Saad's calls)

- **PyPI — still pending, and still step 1 is yours.** `pip install ggufdoctor` does
  **not** work yet; nothing has been published. The name is free.
  `.github/workflows/publish.yml` publishes on a `v*` tag via trusted publishing.
  **Step 1 (Saad, needs PyPI login):** pypi.org → create project `ggufdoctor` or use
  "pending publisher" → add GitHub publisher: owner `saad-supernal`, repo `ggufdoctor`,
  workflow `publish.yml`, environment `pypi`. **Step 2 (Claude):**
  `git tag v0.2.0 && git push origin v0.2.0`, then `gh release create v0.2.0`.
  No tag is pushed yet — doing so before step 1 produces a guaranteed-failing publish
  run. The README's `pip install ggufdoctor` line is the intended install command, not a
  claim that it works today.
- **Account.** Repo is under `saad-supernal` (work-flavoured handle). If reputation
  should accrue to a personal handle, `gh repo transfer` *before* any announcement.
- **Announcement.** Nothing posted anywhere. The build sequence says launch after v0.2,
  leading with the 100/100 agreement result and the 53 dead base-model pointers, not
  with the tool.

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
7. **A divergence the *other runtime* caused is not the template's fault** (v0.2's
   version of lesson 4). Family X first reported every typed-content and
   `enable_thinking` difference at ERROR — which meant it accused working models on
   nearly every template it saw, because llama.cpp's message normaliser and its runtime
   defaults do their work whether or not the template cares. Those are now INFO with the
   cause named, and each downgrade is **confirmed by a re-render**, never inferred from a
   flag: `normalized: true` says the normaliser ran, not that it is why the two engines
   differ.
8. **The bundled engine is a copy of someone else's program, and copies drift.**
   `shim.cpp`'s normaliser and context handling are hand-ported from `chat.cpp`.
   `tests/conformance` exists to catch drift by comparing against the real
   `llama-server`; an engine bump that skips it is a silent lie about what the model
   receives.

## Where the process record lives

`docs/process/v0.1/` — the full v0.1 ledger (`ledger.md`, rulings E1–E28 and every
per-task review outcome), all twelve task briefs and reports, and the three final-fix
reports. `docs/process/v0.2/` — the same for v0.2: the v0.2 ledger (rulings R1–R12a) and
its eleven task briefs and reports, copied there from
`.superpowers/sdd/2026-09-03-ggufdoctor-v0.2/` once the whole-branch review closed. Both
committed, so they survive `git clean`. The live working copy for a plan in progress is
`.superpowers/sdd/<plan-basename>/progress.md` (git-ignored); copy it into
`docs/process/v<next>/` when that version closes.


## v0.3 — start here

Read `docs/v0.3-kickoff.md`. The Ollama spike (`docs/research/2026-09-03-ollama-spike.md`) found
there is no Jinja→Go conversion to model: Ollama swaps recognised templates for curated Go ones
and renders everything else with llama.cpp's engine (already embedded in v0.2). v0.3 is a
registry-lookup check plus `--runtime`, not a WASM engine.
