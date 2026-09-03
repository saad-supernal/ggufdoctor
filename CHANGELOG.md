# Changelog

All notable changes to `ggufdoctor`. Dates are the day the work landed on `main`.

## 0.2.1 — unreleased

### Fixed

- Upstream template resolution now reads the standalone `chat_template.jinja` first, the
  file transformers has saved to since 4.55 and prefers on load. Upstreams that carry only
  that file (Mistral 3, Gemma 4, GLM 5 and others) were being classified as having no
  chat template, which excluded 73 of the top 400 GGUF repositories from the survey's
  comparable set. The corrected survey figure is in the README.

### Added

- `HF_TOKEN` in the environment is honoured for Hub requests (gated upstreams, higher
  rate limit). It is sent only as an `Authorization` header to `huggingface.co`.
- The `User-Agent` now carries the real package version.

## 0.2.0 — 2026-09-03

The second engine. v0.1 could only say what transformers-style Jinja2 renders; v0.2 also
renders the template the way `llama-server` and `llama-cli` do, and reports where the two
disagree.

### Added

- **A second engine: `llama.cpp`.** llama.cpp's own template engine (`common/jinja`,
  which replaced minja upstream in January 2026) compiled to a 725,239-byte
  `wasm32-wasip1` module and driven from Python through `wasmtime`. Pinned to llama.cpp
  build tag `b10775` (commit `67a17c17`), built with wasi-sdk 34. The module mirrors
  `common_chat_template_direct_apply_impl`: the caps probe, llama.cpp's message
  normaliser, `enable_thinking` and `preserve_reasoning` defaults and their expansion,
  llama.cpp's `add_generation_prompt` presence semantics, and null content as an empty
  string. Reports now print both engines with versions, e.g.
  `engines: jinja2 3.1.6, llama.cpp b10775 (67a17c17, wasmtime 48.0.0)`.
  Rebuilt by `engine/build.sh`; bumped by hand, never automatically (`engine/README.md`).
- **Check family X — cross-engine comparison.** `X001` rendered output differs;
  `X002` renders under one engine and fails under the other, in either direction (a
  lexer/parser failure under llama.cpp is reported as "template will not load in
  llama.cpp"); `X004` the difference is whitespace only (warn); `X005` `X001` on a
  tool-calling fixture. Both engines are handed the identical context, including the
  model's real BOS/EOS, and neither side strips BOS.
- **The INFO rule for explained divergence.** `X001` and `X002` walk one shared ladder,
  so a divergence is graded by its cause and not by which engine happened to raise. A
  divergence that llama.cpp's own message normaliser or its runtime defaults
  (`enable_thinking`, `preserve_reasoning` and the four variables it expands into) fully
  account for is reported at INFO with the cause named, not at ERROR. Every such
  downgrade is *confirmed* by re-rendering under Jinja2 with the same rewrite applied —
  a bare "the normaliser ran" flag is never enough.
  Evidence carries `explained_by` (`normaliser`, `runtime_defaults` or
  `normaliser+runtime_defaults`) and, for the defaults, the keys.
- **"Engines agree" is a result.** When family X ran and found nothing, the report says
  `engines agree: jinja2 and llama.cpp rendered N fixtures identically`, so a clean run
  is distinguishable from an X family that never ran.
- **Fixture corpus version 2.** Three `extended`-tier fixtures where the engine spike
  found divergence to live: `tool_roundtrip` (assistant `tool_calls` with dict
  arguments and null content, then a `tool` reply), `typed_content` (content as
  `{"type": "text"}` parts), `no_generation_prompt`. `S003` on an extended fixture is
  reported at INFO, because older templates predate these message shapes.
  JSON reports and survey aggregates carry `fixture_corpus_version`, and the survey's
  markdown prints it.
- **`--engines jinja2,llama.cpp`** subsets the engines. `jinja2` is the reference engine
  and cannot be deselected. Requesting an unavailable engine is exit 2 with the reason.
- **`survey --save-templates DIR`** writes each fetched template as
  `<org>__<repo>.jinja` with a provenance sidecar (`repo`, `revision`, `fetched_at`,
  `license`, `gated`, `architecture`, `bos_token`, `eos_token`, `base_model`,
  `upstream_saved`) and the upstream template where it resolved.
- **Ten real chat templates vendored** under `tests/data/templates/` with provenance
  (`SOURCES.md`). Their complete S + X finding sets are pinned by test, using each
  model's genuine metadata rather than a fabricated vocabulary.
- **Engine conformance suite** (`pytest -m conformance`, and a `conformance` job in CI):
  drives the real `llama-server` release binary at build tag `b10775` through
  `POST /apply-template` and asserts byte equality with the bundled module over every
  vendored template × fixture pair.
- **Engine build job in CI** regenerates the module from the pinned sources with the
  pinned wasi-sdk (verified against a per-host sha256) and runs the suite against the
  fresh build, so the committed module is one anyone can regenerate. The job compares the
  fresh module's hash with the committed one and prints the result, but does not require a
  match: `-Oz` output is not bit-reproducible across toolchain builds, so that comparison
  is informational and the committed module stays the artifact of record.
- **A semantics test** pinning both engines' behaviour on the edge cases the spike found
  (`None`, list and dict printing, `+` with `None`, `default` on `None`, `//`), so an
  engine bump that changes any row is visible.

### Changed

- `wasmtime>=48,<49` is now a required dependency. It publishes ABI-independent
  `py3-none-<platform>` wheels; ggufdoctor's own wheel stays pure Python with the
  module as a data file.
- An unavailable `llama.cpp` engine is a **state, not an error**: the run says
  `llama.cpp unavailable — <reason>`, records `X001/X002/X004/X005` in
  `checks_not_evaluated`, and qualifies the headline as partial. Exit codes are
  unchanged and no traceback is ever printed.
- The survey figure is now published with its corpus version. The 14.8% headline is a
  corpus-1 measurement and stays exactly as it was; the corpus-2 re-run is recorded
  beside it, not in place of it.
- `schema_version` stays `"1"`: every JSON change is additive (new finding ids, richer
  `engines` entries, an `extra` dict on `RenderResult` -- findings carry their own
  `evidence`, which gained the `explained_by`/`defaults` keys).

## 0.1.0 — 2026-09-02

First release.

- Reads the chat template and tokenizer metadata straight out of a GGUF file — local
  path, URL or Hugging Face repo — over HTTP range requests where possible.
- **Sanity checks `S001`–`S008`**, offline and from the file alone: no template on a chat
  architecture, template does not compile, fails to render or declines a conversation
  shape, emits special tokens absent from the vocabulary, never emits the declared EOS,
  emits BOS while `add_bos_token` is set, `add_generation_prompt` with no effect, renders
  to empty output.
- **Reference checks `R001`–`R004`** with `--compare-upstream`: rendered output differs
  from upstream, the author annotated the change, upstream could not be resolved,
  upstream changed after the GGUF was published.
- One engine: Jinja2, configured to match transformers' environment (`trim_blocks`,
  `lstrip_blocks`, `loopcontrols`, the `generation` tag, transformers' `tojson`
  semantics), with `strftime_now` pinned for reproducibility.
- **`ggufdoctor survey`** — the ecosystem measurement, with a per-publisher cap, every
  uncomparable repo classified rather than dropped, and a run whose fetch-failure rate
  could distort the result flagged unreliable in its own output.
- `.ggufdoctorignore` suppressions, which require a reason.
- JSON reports (`--json`), `--fail-on`, exit codes `0`/`1`/`2`.
