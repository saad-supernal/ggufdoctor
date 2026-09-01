# Research evidence

`2026-08-31-survey-raw.json` — raw per-repo records from the throwaway probe that
motivated this project (400 GGUF repos sampled, max 2 per publisher, rendered-output
comparison against upstream). Produced before the tool existed; the `survey`
subcommand supersedes it and should reproduce comparable figures.

Headline derived from this file: 15.1% of comparable chat models (16/106) render
differently from upstream; 30.8% weighted by downloads; 15 of 85 publishers affected.

Known limits, carried into any published figure: only 106 of 400 sampled repos were
comparable (rest were non-chat, gated, missing base-model metadata, or dead upstreams);
top-downloads sample, not the long tail; ASR/TTS/embedding models excluded after they
produced false positives in the first cut.

## Reproducibility gap (fixed)

The 106-comparable/16-divergent figure above could not be reproduced by running
`ggufdoctor survey` against this same data, because three of the exclusions behind
it existed only as manual edits to the throwaway probe's output, never as logic in
`survey.py`. Recomputing straight from `2026-08-31-survey-raw.json` with the tool's
(then-current) logic gives 109 comparable / 18 divergent = 16.5%, not 15.1%. The gap
is exactly three records:

- Two `unslothai/Qwen3-ASR-*` repos report GGUF architecture `qwen3vl` -- a real
  architecture for actual chat models, so it was never in `NON_CHAT_ARCHITECTURES` --
  yet both are ASR models and were counted as `output_differs`. `survey.py` now
  excludes by evidence instead of by architecture name: a Hugging Face
  `pipeline_tag`/`tags` of `automatic-speech-recognition` or `text-to-speech` marks a
  repo `non_chat_pipeline_tag`, out of the comparable denominator, regardless of what
  its architecture string says.
- One record (`poolside/Laguna-S-2.1-GGUF`) was `unrenderable` in the original probe
  but `survey.py` had no such status; both templates failing to render on every
  fixture produced no findings and the record fell through to `cosmetic_only` --
  publishing "the rewrite changes nothing the model sees" about a repo the tool
  never successfully rendered. `survey.py` now restores the `unrenderable` status
  and excludes it from `COMPARABLE`.
- The original probe also skipped any repo listing itself as its own `base_model`;
  `survey.py` lacked that guard (none of the 400 archived repos happen to trigger it,
  but the guard is restored regardless, since a future sample could).

With those three criteria encoded (and confirmed against this archive, matching the
two named ASR repos by id since this archive predates `pipeline_tag`/`tags` capture),
comparable drops from 109 to 106 and divergent from 18 to 16 -- 16/106 = 15.1%,
reproducing the published headline. This was not tuned to hit that number: the
criteria were derived from what was actually observed (Hub metadata, render
outcomes, a self-reference guard), and the figure landed where it landed.
