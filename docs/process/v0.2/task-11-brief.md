### Task 11: Documentation and the corpus-2 survey

**Files:**
- Modify: `README.md`, `NEXT-SESSION.md`, `docs/research/README.md`, `docs/v0.2-kickoff.md`
- Create: `CHANGELOG.md`, `docs/research/2026-09-<dd>-survey-corpus2.json`, `docs/research/2026-09-<dd>-survey-corpus2.md`

**Interfaces:**
- Consumes: everything above.
- Produces: user-facing documentation for v0.2.

- [ ] **Step 1: Run the survey on corpus 2**

```bash
.venv/bin/ggufdoctor survey --top 400 --per-org 2 --out docs/research/$(date +%F)-survey-corpus2.json --markdown docs/research/$(date +%F)-survey-corpus2.md
```

Expected: about ten minutes; `unreliable: false` in the aggregate (if `examine_error` exceeds 5% the tool says so — wait for the rate limit to clear and re-run, do not publish an unreliable run). Note the figure with its corpus version.

- [ ] **Step 2: README**

- Install: `pip install ggufdoctor` pulls `wasmtime`; one sentence on what for.
- New section **"Two engines"** after "What it checks": what `llama.cpp` (`b10775`) is, that it is the real llama.cpp engine compiled to WASM, the X table (X001/X002/X004/X005 with severities and the INFO rule for normaliser-explained X002), `--engines`, and the spike result stated plainly: *on the seven standard fixtures, llama.cpp's engine agreed with transformers-style Jinja2 on 100 of 100 top GGUF templates; the divergence that exists is on typed content, `None` content and templates using `//`.* Link the spike doc.
- "The finding": keep the 14.8% table and add one line beneath: "Corpus 2 (v0.2, adds tool round-trip, typed content, no generation prompt): **N%** (a of b) — the two figures use different fixture corpora and are not comparable to one decimal."
- Limitations: replace "One engine" with "Ollama's Go conversion is not yet compared (v0.3)"; add "`llama-server` also rewrites requests before templating (tool-call arguments become strings); the bundled engine mirrors the message normaliser and whatever Task 9 ported — list it."

- [ ] **Step 3: CHANGELOG, NEXT-SESSION, research index, kickoff**

`CHANGELOG.md` with `0.2.0` (engine, X family, corpus v2 with tiers, `--engines`, `--save-templates`, conformance suite, wasmtime dependency) and `0.1.0`. `NEXT-SESSION.md`: v0.2 state, PyPI still pending (Saad's call), v0.3 pointer (Ollama engine, X003, `--runtime`), where the ledger was copied. `docs/research/README.md`: add the corpus-2 survey entry and the spike. `docs/v0.2-kickoff.md`: one line at the top saying v0.2 shipped and pointing at the plan and ledger.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md NEXT-SESSION.md docs/research docs/v0.2-kickoff.md
git commit -m "docs: v0.2 — two engines, X family, corpus-2 survey figure

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Deliberately deferred

- Ollama engine, X003, `--runtime` (v0.3).
- Counting X divergence inside `survey` (would need real tokens per repo and a second engine per record; the spike's 100/100 stands as the published statement until then).
- Per-repo vocab fetching in the survey (unchanged v0.1 limitation).
- Automatic engine bumps.

## Definition of done for v0.2

- [ ] `.venv/bin/python -m pytest -q` green with no network and no downloaded binaries.
- [ ] `ggufdoctor model.gguf` prints two engines with versions and either X findings or an "engines agree" line; `--engines jinja2` runs S only with no "partial".
- [ ] With `wasmtime` uninstalled, `ggufdoctor model.gguf` still exits 0/1 and says `llama.cpp unavailable — ...` plus "partial".
- [ ] CI: `test` × 9, `build`, `engine-build`, `conformance` green on `feat/v0.2`.
- [ ] Every id `S001–S008`, `X001/X002/X004/X005`, `R001–R004` has at least one test; ten real templates have complete finding sets.
- [ ] The corpus-2 survey figure is recorded with its corpus version and the 14.8% (corpus 1) is unchanged in the README.
