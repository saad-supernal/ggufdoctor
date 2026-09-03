# Task 11 report: Documentation and the corpus-2 survey

Status: **DONE**
Commit: `44311ab` — `docs: v0.2 — two engines, X family, corpus-2 survey figure`
Branch: `feat/v0.2` (not pushed, per instructions). Working tree clean. No code changed.

## Step 1: the corpus-2 survey

Command, run once, on the first attempt, no re-run needed:

```bash
.venv/bin/ggufdoctor survey --top 400 --per-org 2 \
    --out docs/research/2026-09-03-survey-corpus2.json \
    --markdown docs/research/2026-09-03-survey-corpus2.md
```

Started 11:06, output written 11:10:29 — about four and a half minutes, exit 0. Faster
than the brief's ten-minute estimate.

### The aggregate

| | corpus 1 (2026-09-01) | **corpus 2 (2026-09-03)** |
|---|---|---|
| sampled | 400 (per-org 2) | **400** (per-org 2) |
| comparable | 108 | **111** |
| divergent | 16 | **16** |
| divergent_pct | 14.8% | **14.4%** (14.414414…) |
| download_weighted_pct | 31.4% | **31.2%** (31.1777…) |
| publishers affected | 15 of 87 | **15 of 91** |
| `unreliable` | false | **false** |
| `truncated` | false | **false** |

Coverage gaps, corpus 2 (corpus 1 in brackets): `upstream_has_no_template` 93 [94],
`no_base_model` 71 [72], `upstream_not_found` 54 [53], `upstream_gated` 33 [34],
`non_chat_architecture` 27 [28], `non_chat_pipeline_tag` 7 [7],
`upstream_non_chat_pipeline_tag` 2 [2], `missing_template` 2 [2].
**`examine_error` does not appear**, so no repo's fetch failed and the run is not
flagged unreliable.

Statuses, corpus 2: identical 85, output_differs 16, cosmetic_only 10 (= 111 comparable).
`unrenderable` fired zero times, as in corpus 1.

### How it compares to the corpus-1 run, and what actually caused the 0.4pp move

Established from the two JSON record sets, not inferred:

- **The three new fixtures brought no new divergent repo.** Zero repos in the corpus-2
  run diverge *only* on `tool_roundtrip`, `typed_content` or `no_generation_prompt`.
  Numerator is 16 in both runs, and 15 of the 16 repos are identical between them.
- **They did widen divergence inside repos that already diverged.** 14 of the 16 differ
  on at least one tool-calling fixture (`with_tools` or `tool_roundtrip`); four now
  differ on all ten fixtures. The four that differ on *nothing but* tool fixtures are
  `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`, `Qwen/Qwen2.5-3B-Instruct-GGUF`,
  `n00b001/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M-GGUF` and
  `paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF` — the v0.1 "divergence hides on
  the tool-calling path" finding, sharpened.
- **The move is the day's sample, not the corpus.** Comparable went 108 → 111.
  `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` fell out of the top 400 and
  `paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF` came in — the only difference
  between the two divergent sets. Comparability cannot be moved by the corpus in these
  runs anyway, since `unrenderable` (the only fixture-dependent comparability status)
  fired zero times in both.

The two figures are still documented as non-comparable, because the corpus genuinely
differs; the point above is recorded so nobody later reads 14.8 → 14.4 as "the new
fixtures found fewer problems".

## Files changed

| file | one-line summary |
|---|---|
| `docs/research/2026-09-03-survey-corpus2.json` | new — the corpus-2 survey run, 400 per-repo records plus aggregate |
| `docs/research/2026-09-03-survey-corpus2.md` | new — the tool's own markdown for that run |
| `CHANGELOG.md` | new — `0.2.0` (engine, X family, INFO rule, corpus v2 tiers, `--engines`, `--save-templates`, vendored templates, conformance + engine-build CI jobs, semantics test, wasmtime dependency, unavailable-is-a-state) and `0.1.0` |
| `README.md` | install note on why `wasmtime` is pulled; new "Two engines" section (engine table, provenance line, conformance 99/100, X table with severities and the INFO rule, `--engines`, unavailable behaviour, the 100/100 spike sentence, what remains at ERROR, the "engines agree" line); corpus-2 line under "The finding"; corpus-1 labelled as such; a corpus-2 note on the tool-calling subsection; double-BOS section now explains why the engine does not strip BOS; Limitations replaced "One engine" with Ollama-is-v0.3 + the full list of what the engine does and does not mirror + survey-is-not-family-X |
| `NEXT-SESSION.md` | v0.2 state (two engines, 253 tests, branch/PR); both figures with their corpus versions and why they differ; the 100/100 statement; v0.3 scope and the four deferred items; PyPI still pending Saad's step 1 with `pip install ggufdoctor` explicitly not working yet; two new hard-won lessons (7: a divergence the other runtime caused is not the template's fault; 8: the bundled engine is a copy and copies drift); process record now names `docs/process/v0.2/` |
| `docs/research/README.md` | corpus-1 figure explicitly tied to corpus version 1 (and why that tie is documentary); new "The corpus-2 re-run" section with the aggregate and the three-bullet comparison; new "The engine spike" section including the two things the spike did *not* know (runtime defaults as a fourth divergence class, with the 19-finding breakdown; the shim being the raw runtime); "Known limits" now covers both runs and states that `survey` measures GGUF-vs-upstream, not engine-vs-engine |
| `docs/v0.2-kickoff.md` | one block at the top: v0.2 shipped, pointing at the amendments spec, the plan, `docs/process/v0.2/` and `CHANGELOG.md` |

## Verification

- `.venv/bin/python -m pytest -q` → **253 passed, 10 deselected**, before and after the
  edits. `git diff --stat` for the commit touches only `.md` files and the two survey
  artifacts — no code.
- Every number in the docs was checked against a file or a run rather than copied from
  the brief:
  - module size 725,239 bytes and build tag/commit `b10775` / `67a17c17` —
    `src/ggufdoctor/engine_data/llamacpp-jinja.json`.
  - the report line `engines: jinja2 3.1.6, llama.cpp b10775 (67a17c17, wasmtime 48.0.0)`
    — reproduced by calling `report.human._engine_label` over the real selection.
  - conformance 10 templates × 10 fixtures = 100 pairs, exactly one `SKIP` entry
    (Gemma-4 `tool_responses`) → 99 byte-identical —
    `tests/conformance/test_llama_server.py`.
  - `engines agree: … 10 fixtures identically` is achievable and real:
    `legraphista__glm-4-9b-chat-IMat-GGUF` agrees on all ten.
  - "four ERROR findings in three classes" on the vendored templates — computed by
    running `run_cross_engine_checks` over all ten: X001 ERROR 1, X002 ERROR 3,
    X001 INFO 13, X002 INFO 2.
  - the 19-finding `explained_by` breakdown (7 runtime_defaults / 4 normaliser / 2 both /
    6 unexplained; 21 fixture-instances for runtime_defaults) — same run.
  - "14 of 16 divergent repos touch a tool fixture", "four tool-only", "four differ on
    all ten" — computed from the corpus-2 records.
  - ledger rulings span R1–R12a, eleven tasks — `progress.md`.
  - CI jobs `test`, `build`, `engine-build`, `conformance` — `.github/workflows/ci.yml`.
- No template is called broken anywhere. The only occurrence of "broken" is in
  `NEXT-SESSION.md` lesson 1, describing a v0.1 *defect* that wrongly flagged models.
- No claim that PyPI works. `README.md` keeps `pip install ggufdoctor` as the intended
  command; `NEXT-SESSION.md` says in as many words that it does not work yet, nothing is
  published, and step 1 is Saad's.
- The published 14.8% is unchanged in the README, and is now explicitly labelled
  corpus 1 in both the README and `docs/research/README.md`.

## Concerns

1. **The survey's own output does not record the corpus version.** Neither the JSON
   aggregate nor the markdown carries `fixture_corpus_version` (the per-model JSON report
   does; `survey.py` never writes it). So the tie between "14.4%" and "corpus 2" is
   documentary — it lives in the filename, `docs/research/README.md` and the README, not
   in the artifact. A future run could be misfiled. Cheap v0.3 fix: have `survey` write
   `CORPUS_VERSION` into its aggregate and its markdown header. I did not change code.
2. **`docs/process/v0.2/` does not exist yet.** `NEXT-SESSION.md` and
   `docs/v0.2-kickoff.md` point at it as the v0.2 process record; the controller copies
   the ledger there after the final review, per my instructions. Until that copy happens,
   those two links dangle.
3. **The 0.4pp difference invites misreading.** Two things changed at once (the corpus
   and the sample day), and only the sample moved the number. I have documented that
   explicitly in `docs/research/README.md` and `NEXT-SESSION.md`, but the README's own
   one-line corpus-2 note only says the figures are not comparable — it does not carry
   the explanation. That is deliberate (the README stays short), but if the number is
   quoted anywhere externally it should come with the research-README paragraph.
4. **The spike doc's own numbers are now partly superseded and it does not say so.**
   `docs/research/2026-09-03-engine-spike.md` reports a 672 KB module (the shipped one is
   725,239 bytes, built with the normaliser and shim in it) and its rich-input table was
   produced by a shim that lacked the normaliser and the runtime defaults. I documented
   both corrections in `docs/research/README.md` rather than editing the spike doc, since
   a research record should stay as it was written. If a reviewer prefers, a one-line
   "superseded in these two respects" banner at the top of the spike doc would close it.
