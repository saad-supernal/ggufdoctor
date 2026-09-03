# engine/

This directory builds `src/ggufdoctor/engine_data/llamacpp-jinja.wasm`: llama.cpp's own
chat-template engine (`common/jinja`), compiled to WebAssembly and driven from Python via
`wasmtime`. It exists so ggufdoctor can render a template the way `llama-server` and
`llama-cli` actually do, not just the way transformers-style Jinja2 does — see
`docs/research/2026-09-03-engine-spike.md` for why the two engines can disagree.

The module is a small reactor-style WASI build: `engine/shim.cpp` links against llama.cpp's
lexer, parser, runtime, value, string and caps sources, plus `common/json.cpp` and
`common/unicode.cpp`, and exposes `gd_alloc`, `gd_free`, `gd_render` and `gd_out_len` so
Python can pass JSON in and get JSON back through linear memory.

`shim.cpp`'s `normalize_messages` is a port of `messages_inp_normalizer` from llama.cpp's
`common/chat.cpp`: it converts message content between the string and typed-parts shapes
depending on what the compiled template's `caps` say it supports. This normaliser is not
generated — it is hand-copied logic that **must be re-checked against upstream `chat.cpp` on
every engine bump**, since a behavior change there would silently make the WASM module stop
matching what `llama-server` sends to the model.

## Rebuilding the module

```sh
engine/build.sh
```

This fetches the pinned llama.cpp sources into `engine/build/llamacpp` (if not already
present), downloads wasi-sdk 34 into `engine/build/` (if `WASI_SDK` is not set to a
pre-installed SDK), compiles the module with `wasi-sdk`'s `clang++`, and writes both
`src/ggufdoctor/engine_data/llamacpp-jinja.wasm` and its manifest,
`src/ggufdoctor/engine_data/llamacpp-jinja.json`.

`engine/build/` is git-ignored; it is scratch space for fetched sources and the downloaded
SDK, not something to commit.

## Bumping the pin

1. Edit `engine/LLAMACPP_PIN` to the new `commit` and `build_tag`.
2. Run `engine/fetch-llamacpp.sh --write-sums` to re-fetch the pinned files and regenerate
   `engine/llamacpp-sources.sha256` (this is what every later `fetch-llamacpp.sh` run without
   `--write-sums` verifies against).
3. Run `engine/build.sh` to rebuild the module and manifest.
4. Run the semantics test and the conformance suite to confirm nothing regressed.
5. Re-check `normalize_messages` in `shim.cpp` against the current
   `messages_inp_normalizer` in upstream `common/chat.cpp` — port any behavior change.
6. Update `SOURCES` in the bump PR.
