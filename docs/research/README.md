# Research evidence

## The published figure

`2026-09-01-survey.json` and `.md` — the survey the tool produced, and the source of
every headline number in the project README. Regenerate with:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

**14.8%** of comparable chat models (16/108) render differently from upstream; **31.4%**
weighted by downloads; **15 of 87** publishers affected. Zero fetch failures, so the
sample is intact and the run is not flagged unreliable.

**This figure is tied to fixture corpus version 1** — the seven fixtures v0.1 shipped
with. The survey's own output does not record the corpus version, so the tie is
documentary and it is this paragraph's job to keep it: 14.8% is a corpus-1 measurement
and must never be restated as a corpus-2 one.

## The corpus-2 re-run

`2026-09-03-survey-corpus2.json` and `.md` — the same survey re-run on fixture corpus
version 2, which adds `tool_roundtrip`, `typed_content` and `no_generation_prompt` as
`extended`-tier fixtures. Produced by v0.2 with:

```bash
ggufdoctor survey --top 400 --per-org 2 \
    --out docs/research/2026-09-03-survey-corpus2.json \
    --markdown docs/research/2026-09-03-survey-corpus2.md
```

**14.4%** of comparable chat models (16/111); **31.2%** weighted by downloads; **15 of
91** publishers affected. `unreliable: false`, and `examine_error` does not appear in
the coverage gaps, so no repo's fetch failed.

Neither figure replaces the other. They are 0.4pp apart, and it is worth being precise
about what did *not* cause that:

- **The three new fixtures added no divergent repo.** No repo in the corpus-2 run
  diverges *only* on `tool_roundtrip`, `typed_content` or `no_generation_prompt`. The
  numerator is 16 in both runs, and 15 of those 16 repos are the same repos.
- **They did widen the divergence inside repos that already diverged.** 14 of the 16
  differ on at least one of the three new fixtures, and four of them now differ on
  every fixture in the corpus. That is the new fixtures doing their job — showing more
  of an existing divergence — not finding a new one.
- **What moved is the day's sample.** The comparable denominator went 108 → 111 between
  2026-09-01 and 2026-09-03: download rankings, gated status and base-model
  resolvability all shift. `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` fell out of the top
  400 and `paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF` came in, which is the one
  repo the two divergent sets do not share.

So the corpora are genuinely different measurements and should be quoted with their
corpus version, but in this instance the difference between the two numbers is sampling,
not fixtures.

## The engine spike

`2026-09-03-engine-spike.md` (and `2026-09-03-engine-spike/`, the throwaway code and raw
probe output) — the measurement behind v0.2's second engine. Three results:

- llama.cpp **no longer uses minja**; its own `common/jinja` engine replaced it in
  January 2026, so minja would have been a year-stale oracle at launch.
- The engine builds for `wasm32-wasip1` and runs under `wasmtime`, which is the route
  v0.2 took.
- **On the seven standard fixtures, llama.cpp's engine agreed with transformers-style
  Jinja2 on 100 of 100 top GGUF templates.** The divergence the spike could find lives on
  typed content, `None` content, and templates using `//` (which llama.cpp's parser will
  not load). That is the finding corpus 2 and check family X were built around.

Two things the spike did **not** know, both established while building v0.2 and recorded
in the v0.2 ledger (`docs/process/v0.2/`):

- **A fourth divergence class: llama.cpp's runtime defaults.** `llama-server` and
  `llama-cli` write `enable_thinking` into every render context and default
  `preserve_reasoning` to true, which `caps_apply_preserve_reasoning` then expands into
  `preserve_thinking`, `clear_thinking`, `truncate_history_thinking` and
  `drop_thinking`. transformers injects none of that, so a caller who passes nothing gets
  a different prompt from each runtime for the same GGUF. The spike's shim did not
  reproduce these, so its rich-input table could not see them; they turn out to be the
  single most common cause of cross-engine divergence on real templates. Across the ten
  templates vendored in `tests/data/templates/`, family X reports 19 findings: 7
  explained by runtime defaults alone (21 fixture-instances), 4 by the message
  normaliser, 2 by both, and 6 unexplained — of which 4 are the ERRORs. Reported at
  INFO, with the fix in the message (rulings R9–R12a).
- **The spike's shim was the raw runtime, not the shipped engine** — it did not port
  llama.cpp's message normaliser, so its numbers describe `common/jinja` alone rather
  than the `llama-server` path. The shipped engine ports the normaliser and is checked
  against the real `llama-server` at the same build tag by `tests/conformance`: 99 of 100
  vendored template × fixture pairs byte-identical, one skipped with a stated reason (a
  Gemma-4 `tool_responses` rewrite llama.cpp performs above the templating entry point).

## The earlier probe, and why its number differed

`2026-08-31-survey-raw.json` — raw per-repo records from the throwaway probe that
motivated the project, written before the tool existed. It reported 15.1% (16/106).

That figure is superseded. It should not be quoted, and the difference between it and
14.8% is not noise — it is four identifiable corrections, three of which the probe got
wrong and one of which is simply a different day's sample:

- **Manual exclusions, now encoded.** The probe's 15.1% was reached by editing three
  records out of its output by hand. Recomputing from the raw file without those edits
  gives 16.5% (18/109). The tool now excludes by published evidence instead: a Hugging
  Face `pipeline_tag` of `automatic-speech-recognition` or `text-to-speech`, checked on
  both the GGUF repo and its upstream. That is what catches the two `unslothai/Qwen3-ASR-*`
  repos, whose GGUF-side architecture (`qwen3vl`) is a legitimate chat architecture and
  whose GGUF repos carry no pipeline tag at all — only the upstream says "speech".
- **`unrenderable` was a probe artifact, not a property of the model.** The probe filed
  `poolside/Laguna-S-2.1-GGUF` as unrenderable. It is not: all seven fixtures render
  cleanly on both sides through the shipped engine, and five of them differ. The probe's
  Jinja environment lacked `loopcontrols`, the `generation` tag, and transformers'
  `tojson` semantics, so it raised a syntax error where a real engine does not. The repo
  is a genuine divergence and is counted as one. The `unrenderable` status exists in the
  tool for the case the probe was reaching for — neither side rendering — and fired zero
  times in the live run.
- **Engine fidelity moved tool-path verdicts.** The probe's `tojson` ignored its filter
  arguments; the tool honours them, matching transformers. Since 5 of the 16 divergences
  are tool-path-only, this is exactly where it matters.
- **A different day.** The live run sampled Hugging Face on 2026-09-01; download rankings
  and gated status had moved since the archive.

## Known limits, carried into any published figure

- **Most of the sample is not comparable at all** — 108 of 400 in the corpus-1 run, 111
  of 400 in the corpus-2 run. The rest are classified in each run's coverage table, never
  dropped. Corpus 1: 94 upstreams with no chat template, 72 with no declared base model,
  53 whose declared base model now returns 404, 34 licence-gated, 28 non-chat
  architectures, 9 non-chat pipeline tags, 2 with no template in the GGUF. Corpus 2:
  93, 71, 54, 33, 27, 9, 2 respectively.
- Top-downloads sample, not the long tail.
- Gated repos are excluded rather than measured; a token-authenticated run would bring
  33–34 more into the denominator and could move the figure either way.
- **The survey figure is a one-engine measurement in both runs.** It compares the GGUF's
  template against its upstream's, both rendered through Jinja2. It does *not* count
  cross-engine (family X) divergence: doing so needs real vocabulary tokens per repo and
  a second engine per record, and was deliberately deferred. The published cross-engine
  statement is the spike's 100/100.
- Ollama's Go template conversion is compared by neither run; that is v0.3.

## Other files

- `reports/` — the eight prior-art research reports behind the project's direction.
- `probe2-throwaway.py` — the throwaway probe, kept for auditability. Superseded by
  `ggufdoctor survey`; it is not maintained and its engine is known to be less faithful.
- `idea-evaluation.md` — the ideas evaluated and rejected before this one, with reasons.
