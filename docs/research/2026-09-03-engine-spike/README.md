# Engine spike, 2026-09-03 — how llama.cpp's template engine gets into ggufdoctor

Throwaway code. Nothing here is the production build; it exists so the numbers below can
be reproduced and so the v0.2 implementer starts from a recipe that is known to work.

- `shim.cpp` — stdin/stdout JSON shim around llama.cpp's `common/jinja` engine
- `ggml-stub.h` — 4-line `GGML_ASSERT` stub so `common/json.cpp` builds without ggml
- `build.sh` — the exact wasi-sdk 34 invocation that produced the 672 KB module
- `driver.py` — Jinja2Engine vs WASM engine across the seven fixtures and nine templates
- `probe.py` / `probe-standard-fixtures.json` — 100 real GGUF templates × 7 standard fixtures
- `probe2.py` / `probe-rich-inputs.json` — the same 100 templates × 5 richer inputs

Findings are in `../2026-09-03-engine-spike.md`.
