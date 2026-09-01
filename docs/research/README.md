# Research evidence

## The published figure

`2026-09-01-survey.json` and `.md` — the survey the tool produced, and the source of
every number in the project README. Regenerate with:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

**14.8%** of comparable chat models (16/108) render differently from upstream; **31.4%**
weighted by downloads; **15 of 87** publishers affected. Zero fetch failures, so the
sample is intact and the run is not flagged unreliable.

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

- Only 108 of 400 sampled repos were comparable. The rest are classified in the coverage
  table, never dropped: 94 upstreams with no chat template, 72 with no declared base
  model, 53 whose declared base model now returns 404, 34 licence-gated, 28 non-chat
  architectures, 9 non-chat pipeline tags, 2 with no template in the GGUF.
- Top-downloads sample, not the long tail.
- Gated repos are excluded rather than measured; a token-authenticated run would bring 34
  more into the denominator and could move the figure either way.
- One engine (Jinja2, configured to match transformers). minja and Ollama's Go conversion
  are v0.2 and v0.3.

## Other files

- `reports/` — the eight prior-art research reports behind the project's direction.
- `probe2-throwaway.py` — the throwaway probe, kept for auditability. Superseded by
  `ggufdoctor survey`; it is not maintained and its engine is known to be less faithful.
- `idea-evaluation.md` — the ideas evaluated and rejected before this one, with reasons.
