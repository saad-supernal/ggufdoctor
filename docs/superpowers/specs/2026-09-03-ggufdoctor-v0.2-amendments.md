# ggufdoctor v0.2 — spec amendments (2026-09-03)

Amends `2026-08-31-ggufdoctor-design.md`. Where the two disagree, this document wins for
v0.2. Everything not mentioned here stands as written. The evidence for every change is
`docs/research/2026-09-03-engine-spike.md`.

## A. The second engine is llama.cpp's `common/jinja`, delivered as WASM

Replaces every "minja" in §3, §4, §6, §9, §10, §11, §12.

- **Engine name** `llama.cpp`. **Version** is the llama.cpp build tag it was compiled
  from (`b10775` for v0.2.0), with the commit sha alongside. Reports print both.
- **Source of truth**: `common/jinja/*.{h,cpp}`, `common/json.{h,cpp}`,
  `common/unicode.{h,cpp}` from the pinned commit, plus `vendor/nlohmann/json.hpp`. A
  fetch script downloads exactly those files by sha; nothing from llama.cpp is committed
  except the compiled module.
- **Delivery**: one `.wasm` module (target `wasm32-wasip1`, `-Oz`, stripped, C++
  exceptions on) committed under `src/ggufdoctor/engine_data/` and shipped in the wheel
  as data, like `corpus.json`. Budget: under 1 MB.
- **Runtime**: `wasmtime` becomes a required dependency, pinned to its major
  (`wasmtime>=48,<49`). It publishes ABI-independent `py3-none-<platform>` wheels for
  macOS, Linux (glibc and musl, x86_64 and aarch64) and Windows. ggufdoctor's wheel stays
  pure Python. wasmtime's compile cache is enabled, keyed under the user cache directory,
  so cold start is ~120 ms once and ~6 ms after.
- **Unavailable is a state, not an error.** If `wasmtime` fails to import or the module
  fails to load, the engine reports itself unavailable with the reason, the X family is
  recorded in `checks_not_evaluated`, and the headline says "partial" — the same
  declined/failed discipline the report already has. No traceback, ever.

### What the module does (the "llama-server path")

One exported entry point, mirroring `common_chat_template_direct_apply_impl` in
`common/chat.cpp`, in this order:

1. lex and parse the template (`stage: lexer` / `parser` on failure);
2. `caps_get(prog)` — the engine's own probe of what the template supports;
3. apply llama.cpp's message normaliser (typed content → string when the template
   supports only strings, and the reverse), ported verbatim from `chat.cpp`;
4. set the runtime clock to the pinned 2026-01-01 so `strftime_now` matches Jinja2;
5. render; catch `raise_exception` (`stage: raise`) separately from engine errors
   (`stage: render`).

It returns `{ok, text | error, stage, caps, normalized}`. **It does not strip the leading
BOS.** llama.cpp strips it and its tokenizer re-adds it; transformers leaves it and
tokenizes without adding one. The token streams agree, so comparing the post-strip text
would manufacture a divergence on every model in the S006 population. Both engines are
compared on raw rendered text, with the model's real tokens injected on both sides as R001
already does.

### Python/WASM boundary

Reactor-style module: exports `alloc`, `free`, `render(in_ptr, in_len) -> out_ptr`,
`out_len`, with JSON in and JSON out through linear memory. No filesystem, no argv, no
stdio. One `Store` per render call; instantiation costs well under a millisecond. The
engine class satisfies the existing `Engine` protocol (`name`, `version`,
`render(template, context) -> RenderResult`) unchanged; it gains `available -> bool` and
`unavailable_reason -> str | None`, and `RenderResult` gains an optional `extra` dict
carrying `caps` and `normalized`.

## B. Family X — rewritten

The spike found **no divergence on the seven standard fixtures across 100 top GGUF
templates**. Divergence exists on richer inputs and at parse time. The family is
re-specified for that reality:

| id | check | severity |
|---|---|---|
| X001 | rendered output differs between jinja2 and llama.cpp (not whitespace-only, not the tools fixture) | error (INFO when explained — see below) |
| X002 | renders under one engine and fails under the other — **either direction**; a lexer/parser failure under llama.cpp is reported as "will not load in llama.cpp" | error (INFO when explained — see below) |
| X004 | output differs by whitespace only | warn |
| X005 | X001 on a tool-calling fixture | error |

X003 (Ollama) is unchanged and remains v0.3.

Rules that bind every X check:

- **Both engines get the identical context**, including the model's real BOS/EOS.
- **Collapsed by signature** across fixtures, like the S family; evidence carries
  `fixtures`, `engines`, a unified diff for X001/X004/X005, and `caps`/`normalized` from
  the llama.cpp side when the normaliser changed the input.
- **A divergence that llama.cpp's own behaviour explains is INFO, for X001 and X002 alike**
  (rulings R9–R13, 2026-09-03). The check re-renders jinja2 with the rewrite applied and
  downgrades only when that reproduces llama.cpp's text byte for byte. Three explanation
  classes, recorded in `evidence["explained_by"]`: `normaliser` (typed content joined to text
  or wrapped as a part), `runtime_defaults` (llama.cpp defines `enable_thinking=true` and
  `preserve_reasoning=true` — expanded into `preserve_thinking`, `clear_thinking`,
  `truncate_history_thinking`, `drop_thinking` — where transformers leaves them undefined;
  `evidence["defaults"]` names the keys added), and `normaliser+runtime_defaults` when only
  both together reproduce it. Explained divergences on tool fixtures stay X001 INFO rather
  than X005 — the cause outranks the fixture. The llama.cpp engine itself mirrors these
  defaults (spec §A, `common_chat_template_direct_apply_impl` plus `common/arg.cpp`'s
  `preserve_reasoning` default); the explanation lives in the checks layer.
- **A divergence that llama.cpp's normaliser explains is INFO.** When the llama.cpp side
  reports `normalized: true` (it joined typed content to text, or wrapped text as a part,
  before rendering), the resulting X001 or X002 is reported at INFO with the rewrite named.
  It is a true divergence between the transformers path and llama-server, but one caused
  by a deliberate compatibility shim, not by the template.
  This classification is applied before the whitespace-only test: an explained divergence is
  X001 INFO even when the residual difference is only whitespace.
- **Both engines failing is not an X finding.** S003 already owns that.
- **The message never calls the template broken.** X002's message names the engine that
  fails, the stage, and the engine's own error text. A template that uses `//` is a valid
  Jinja template that llama.cpp cannot load; that is the fact to state.
- **"Engines agree" is a result.** When X ran and found nothing, the human report says so
  in the coverage line (`engines agree on N fixtures`), so a clean run is distinguishable
  from an X family that did not run.

## C. Fixture corpus version 2

Three fixtures are added where the spike found divergence to live. `CORPUS_VERSION`
becomes `"2"`; JSON reports carry it.

| name | shape |
|---|---|
| `tool_roundtrip` | system, user, assistant with one `tool_calls` entry (`arguments` as a **dict**, content `null`), `tool` message with `tool_call_id`, `tools` declared, `add_generation_prompt: true` |
| `typed_content` | one user message whose `content` is two `{"type": "text"}` parts |
| `no_generation_prompt` | user + assistant, `add_generation_prompt: false` |

`arguments` is a dict because that is the transformers convention and 98/100 templates
render it; the string form makes 67/100 templates decline on both engines and measures
nothing. **The survey figure is tied to corpus version 1.** v0.2 re-runs the survey on
version 2 and records the new figure next to the old with the corpus version stated;
neither replaces the other silently.

## D. CLI

`--engines jinja2,llama.cpp` subsets the engines (default: all available). Requesting an
unavailable engine is exit 2 with the reason. `--runtime` is still v0.3.

## E. Testing additions

- **Engine conformance suite** (`conformance` marker, CI-only, not in the default run):
  drives a pinned `llama-server` release binary at the same `b` tag through
  `POST /apply-template` with `--jinja --chat-template-file`, over every vendored
  template × every fixture, and asserts byte equality with the bundled module. Divergence
  fails the build. `llama-cpp-python` was not verified to expose the new engine and is
  not used.
- **Vendored real templates**: `ggufdoctor survey --save-templates DIR` writes each
  fetched template as `<org>__<repo>.jinja` plus a sidecar `.json` (repo, revision sha,
  fetched-at, licence from card data, gated flag). Ten templates from that output are
  committed under `tests/data/templates/` with a `SOURCES.md`. Tests that assert complete
  finding sets on real templates use these, not string literals.
- **Semantics table as tests**: the spike's edge-case table (None/list/dict printing,
  `+` with None, `default` on None, `//`) becomes a test that pins *both* engines'
  behaviour, so an engine bump that changes any row is visible.
- **Engine build job in CI**: rebuilds the module from the pinned sources with the pinned
  wasi-sdk and runs the full test suite against the fresh build. The committed module is
  the artifact of record; the job proves it can be regenerated.

## F. Versioning and bumps

- ggufdoctor `0.2.0`. `schema_version` stays `"1"` (all JSON changes are additive:
  new finding ids, richer `engines` entries, `extra` on `RenderResult` -- findings carry
  `evidence`, not `extra`).
- The engine bumps **by hand, on purpose**, never automatically: a bump is a PR that
  changes the pinned sha, rebuilds the module, re-runs conformance and the semantics
  table, and updates the version string. Cadence: with each ggufdoctor release, or when
  llama.cpp changes template semantics users would notice.

## G. Risks (replaces the first row of §11)

| risk | mitigation |
|---|---|
| wasi-sdk exception-handling flags change again | flags live in one `build.sh`; the CI build job catches it |
| `chat.cpp` normaliser drifts from the ported copy | conformance suite compares against real `llama-server`, which exercises the real normaliser |
| wasmtime drops a platform or breaks the API | major pinned; "unavailable" state degrades to S+R with a stated reason |
| adding fixtures moves the survey number | corpus version printed with every figure; both figures kept |

## H. Build sequence (replaces §12 for v0.2)

**v0.2** — llama.cpp engine via WASM; X001/X002/X004/X005; corpus v2; `--engines`;
conformance suite; vendored templates; survey re-run. **Launch after v0.2**, leading with
the 100/100 agreement result and the 53 dead base-model pointers, not with the tool.

**v0.3** — unchanged: Ollama engine and X003; `--runtime`.
