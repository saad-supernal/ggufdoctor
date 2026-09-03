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
depending on what the compiled template's `caps` say it supports. It also materialises a
null or absent `content` as `""`, because every llama.cpp path round-trips messages through
`common_chat_msg` (whose `content` is a `std::string`) and back out through
`common_chat_msg::to_json_oaicompat`, so a template never sees a null there.

Beyond the messages, `render_job` reproduces the rest of
`common_chat_template_direct_apply_impl`'s own context handling: `enable_thinking` is always
defined and defaults to `true`; `add_generation_prompt` is present only when the flag is on
(llama.cpp writes the key only in that case, so a template testing
`add_generation_prompt is defined` sees a missing key, never a false one); and a
`preserve_reasoning` or `reasoning_effort` key in the context is expanded through
`jinja::caps_apply_preserve_reasoning` / `jinja::caps_apply_reasoning_effort`.

`preserve_reasoning` is also *defaulted* here, which is the one place the module reaches
above `direct_apply_impl` on purpose: `common_params_parse` sets it to `"true"` for every
llama.cpp CLI tool unless `--no-reasoning-preserve` is given (`common/arg.cpp:963-966`), and
`llama-server` treats it as in force for a template whose caps report
`supports_preserve_reasoning` (`server-context.cpp:1493-1497`). So when the caller supplies
no `preserve_reasoning` and the caps say the template can use it, the module supplies `true`
— otherwise a render would match a bare library embedding rather than the `llama-server` and
`llama-cli` everyone actually runs. Note that the transformers path has no such expansion at
all, so a template reading the expanded variables genuinely diverges between the two
runtimes; that is a finding, not a bug in this module.

None of this is generated — it is hand-copied logic that **must be re-checked against
upstream `chat.cpp` on every engine bump**, since a behavior change there would silently
make the WASM module stop matching what `llama-server` sends to the model. That is what
`tests/conformance` exists to catch: it drives the real `llama-server` release binary at the
pinned build tag and asserts byte equality over every vendored template × fixture pair.

What the shim deliberately does **not** reproduce, because it lives above
`direct_apply_impl` in llama.cpp:

- the ~10 per-family message rewrites `common_chat_try_specialized_template` selects by
  sniffing the template source (Gemma4 `tool_responses` collapsing, DeepSeek-V4 tool-result
  sorting, gpt-oss/LFM2 reasoning copying, StepFun content trimming, …);
- `llama-server`'s request policies — assistant prefill (`--no-prefill-assistant`) and the
  rest of the `common_chat_msg` round-trip;
- `common_chat_extra_context()`'s `datetime` / `date_string`, which llama.cpp fills from the
  wall clock and this module renders at a pinned one by design.

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
4. Run the semantics test and the conformance suite
   (`python -m pytest -m conformance tests/conformance -v`, which fetches the matching
   `llama-server` release for the new tag) to confirm nothing regressed.
5. Re-check `normalize_messages` and `render_job`'s context handling in `shim.cpp` against
   the current `messages_inp_normalizer` and `common_chat_template_direct_apply_impl` in
   upstream `common/chat.cpp` — port any behavior change.
6. Update `SOURCES` in the bump PR.
