# GGUF chat-template survey

- Fixture corpus version: **2**
- Sampled: **400** repos (per-org cap: 2)
- Comparable chat models: **111**
- Render-different from upstream: **16** (14.4%)
- Download-weighted: **31.2%**
- Publishers affected: **15** of 91

## Coverage gaps

Repos excluded from the denominator, by reason:

- `upstream_has_no_template`: 93
- `no_base_model`: 71
- `upstream_not_found`: 54
- `upstream_gated`: 33
- `non_chat_architecture`: 27
- `non_chat_pipeline_tag`: 7
- `upstream_non_chat_pipeline_tag`: 2
- `missing_template`: 2

The per-org cap matters: without it the download ranking is dominated by a small number of publishers and the figure is not representative.