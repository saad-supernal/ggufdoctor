## Global Constraints

- `requires-python = ">=3.11"`. Runtime dependencies are exactly `jinja2>=3.1` and `wasmtime>=48,<49`. Nothing else.
- Engine pin: llama.cpp commit `67a17c17caa95742186f8b1ecadd1b5abd6d5ebb`, build tag `b10775`. Toolchain: wasi-sdk 34. Compile flags verbatim: `--target=wasm32-wasip1 -mexec-model=reactor -std=c++17 -Oz -fwasm-exceptions -mllvm -wasm-use-legacy-eh=false -Wl,-mllvm,-wasm-use-legacy-eh=false -Wl,--strip-all`, link `-L<sysroot>/lib/wasm32-wasip1/eh ... -lunwind`. Never pass `-I<dir>/jinja` (its `string.h` shadows libc's).
- The committed module `src/ggufdoctor/engine_data/llamacpp-jinja.wasm` must be under 1,000,000 bytes and ship in the wheel with its manifest `llamacpp-jinja.json`.
- The engine does **not** strip a leading BOS. Both engines receive the identical context: `BASE_CONTEXT` defaults, then the fixture, then the model's real `bos_token`/`eos_token` via `_with_real_tokens`.
- `Engine` protocol is unchanged: `name: str`, `version: str`, `render(template, context) -> RenderResult`. Engines never raise from `render`.
- Error tag prefixes are fixed strings: `compile:`, `raise:`, `render:`, plus new `engine:unavailable:`.
- Every check that cannot evaluate appends its id(s) to `ctx.checks_not_evaluated`. A user who passes `--engines jinja2` has *declined* X, which is not a gap and is not recorded; an engine that is *unavailable* is a gap and is recorded.
- No finding message may call a template "broken". X002's message names the engine that fails, the stage, and that engine's own error text.
- False-positive discipline: S003 on an `extended`-tier fixture is INFO, never ERROR. X002 where llama.cpp rendered only after its normaliser rewrote the input is INFO.
- Tests that assert on real templates assert the **complete** finding set as `{(id, severity, fixtures...)}` — never `"S005" not in ids`. Every expected finding carries a comment saying why it is a true positive.
- No default-run test reaches the network or executes a downloaded binary. Marks: `network` (Hugging Face), `conformance` (downloads `llama-server`). `addopts = "-m 'not network and not conformance'"`.
- Fixture corpus version is `"2"`. The published 14.8% figure is tied to corpus `"1"` and must never be restated as a corpus-2 figure; both are reported with their corpus version.
- Test command: `.venv/bin/python -m pytest -q` from the repo root (the `.venv` is a `uv venv --python 3.14`; after adding a dependency run `uv pip install --python .venv/bin/python -e ".[dev]"`).
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

