# GGUF chat-template survey

- Fixture corpus version: **2**
- Sampled: **400** repos (per-org cap: 2)
- Comparable chat models: **110**
- Render-different from upstream: **15** (13.6%)
- Download-weighted: **30.9%**
- Publishers affected: **14** of 89

## Coverage gaps

Repos excluded from the denominator, by reason:

- `upstream_has_no_template`: 93
- `no_base_model`: 71
- `upstream_not_found`: 59
- `non_chat_architecture`: 28
- `upstream_gated`: 28
- `non_chat_pipeline_tag`: 7
- `upstream_non_chat_pipeline_tag`: 2
- `missing_template`: 2

The per-org cap matters: without it the download ranking is dominated by a small number of publishers and the figure is not representative.