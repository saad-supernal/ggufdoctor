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
