# GGUF chat-template survey

- Fixture corpus version: **2**
- Sampled: **400** repos (per-org cap: 2)
- Comparable chat models: **185**
- Render-different from upstream: **26** (14.1%)
- Download-weighted: **26.8%**
- Publishers affected: **22** of 139

## Coverage gaps

Repos excluded from the denominator, by reason:

- `no_base_model`: 71
- `upstream_not_found`: 59
- `non_chat_architecture`: 28
- `upstream_gated`: 23
- `upstream_has_no_template`: 21
- `non_chat_pipeline_tag`: 7
- `missing_template`: 4
- `upstream_non_chat_pipeline_tag`: 2

The per-org cap matters: without it the download ranking is dominated by a small number of publishers and the figure is not representative.