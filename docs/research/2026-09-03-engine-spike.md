# Spike: embedding llama.cpp's template engine in ggufdoctor (2026-09-03)

**Question.** v0.2 needs a second engine that renders chat templates the way llama.cpp does.
The spec assumed "minja compiled to WASM, shipped in the wheel". Nobody had verified that a
WASI build works, that the runtime footprint is acceptable, or that minja is still the thing
to embed. This spike answers all three and measures how much the two engines actually
disagree on real templates.

**Answer in one line.** WASM via `wasmtime` is a clear winner, but the engine is not minja:
llama.cpp replaced minja with its own engine in January 2026, and on the seven standard
fixtures that engine agrees with transformers-style Jinja2 on **100 of 100** top GGUF
templates. Divergence exists, but it lives on richer inputs and on parse-time gaps.

Throwaway code and raw results: [`2026-09-03-engine-spike/`](2026-09-03-engine-spike/).

## 1. minja is gone; the engine is `common/jinja`

- `common/minja/` no longer exists in llama.cpp. Its last sync was 2025-05-30. The upstream
  `google/minja` repo has had no push since 2025-09-22.
- llama.cpp merged its own engine in
  [PR #18462](https://github.com/ggml-org/llama.cpp/pull/18462) on 2026-01-16
  (`common/jinja/`: lexer, parser, runtime, value, string, caps — about 250 KB of C++).
  44 commits have touched it since; the most recent on 2026-08-22.
- It is what `llama-server`, `llama-cli` and every `--jinja` path render with. minja is
  therefore the wrong oracle for "what llama.cpp sends the model" — anything built on it
  would already be a year stale at launch.

**Consequence for the spec.** Every mention of "minja" in the v0.2 scope becomes "llama.cpp's
`common/jinja` engine". The engine's version string is the llama.cpp build tag it was built
from (`b10775` at spike time, commit `67a17c17`). llama.cpp now also publishes `v0.x` tags;
the `b` tag identifies a commit exactly and is the one to pin.

## 2. It builds for WASI and runs under wasmtime

| | |
|---|---|
| Toolchain | wasi-sdk 34 (clang 23.1.0), target `wasm32-wasip1` |
| Required flags | `-fwasm-exceptions -mllvm -wasm-use-legacy-eh=false`, link with `-lunwind` against `lib/wasm32-wasip1/eh` |
| Runtime | `wasmtime` 48.0.0 with `Config.wasm_exceptions = True` |
| Module size | 672 KB (`-Oz`, stripped); 173 KB gzipped; 4.2 MB at `-O2` unstripped |
| JIT compile per process | 120–130 ms cold; 6–7 ms with wasmtime's on-disk cache (0.8 MB) |
| Render, 7 fixtures | 2–9 ms including instantiation; Jinja2 takes 4–52 ms for the same |

The engine uses C++ exceptions structurally (`break`/`continue` are thrown), so the
kickoff's worry about exceptions under WASI was the right one. wasi-sdk ≥ 33 ships a second
libc++ built with exceptions; it is selected by `-fwasm-exceptions` at link time but
`-lunwind` must be passed by hand, and the legacy-EH default must be switched off or
wasmtime refuses to compile the module. `std::regex` and `<chrono>` were not problems: the
engine uses neither.

Two build details worth recording: `common/json.cpp` includes `ggml.h` only for
`GGML_ASSERT`, so a four-line stub replaces ggml entirely; and `-I` must not point at the
`jinja/` directory, because `jinja/string.h` then shadows the C `<string.h>` and libc++
fails to compile.

**Runtime dependency.** `wasmtime` publishes `py3-none-<platform>` wheels — ABI-independent,
so one wheel per OS/arch, not per Python version — for macOS x86_64/arm64, manylinux and
musllinux x86_64/aarch64, Windows amd64/arm64 and Android, 7–10 MB each, `requires-python
>= 3.9`. ggufdoctor's own wheel stays pure Python with a 672 KB data file. The alternatives
are dead or unsuitable: `wasmer`'s last PyPI release is 2022, and a native extension would
mean a 3 OS × 3 Python × 2 arch build matrix for a project whose real constraint is
maintenance surface.

## 3. How much the engines actually disagree

### Standard fixtures: not at all

Top 150 GGUF repos by downloads, two per publisher (the survey's own sampling), 100 of which
carry a template. Each template rendered by both engines against the seven v0.1 fixtures
with placeholder tokens on both sides.

| Outcome | Templates |
|---|---|
| All seven fixtures byte-identical (or both engines decline the same fixture) | **100** |
| Any fixture differs, or renders on one engine and fails on the other | **0** |

The same held for the four templates vendored in the test suite (Mistral-v0.2, Llama-2,
Gemma-2, Llama-3.3 with tools) and for two live GGUF/upstream pairs from Qwen and unsloth.
Where a template calls `raise_exception` (Mistral and Gemma on a system message), both
engines decline. This is a positive result about llama.cpp, and it is publishable as such.

### Richer inputs: divergence appears, and it is about leniency

Same 100 templates, five inputs the v0.1 corpus does not have:

| Input | Same | Both fail | llama.cpp renders, Jinja2 raises | Output differs |
|---|---|---|---|---|
| Tool-call round trip, `arguments` as dict | 98 | 2 | 0 | 0 |
| Tool-call round trip, `arguments` as string | 30 | 67 | 1 | 2 |
| User content as typed parts `[{"type":"text",...}]` | 86 | 2 | **10** | **2** |
| Assistant message carrying `reasoning_content` | 100 | 0 | 0 | 0 |
| `add_generation_prompt: false` | 100 | 0 | 0 | 0 |

Every one of the 12 typed-content and 3 string-argument divergences reduces to the same
engine-level differences, confirmed with minimal templates:

| Expression | Jinja2 (transformers) | llama.cpp `common/jinja` |
|---|---|---|
| `{{ none_value }}` | `None` | empty |
| `{{ some_list }}` | `[1, 'a']` | `1a` |
| `{{ some_dict }}` | `{'a': 1}` | empty |
| `'x' + none_value` | `TypeError` | `x` |
| `'x' + some_list` | `TypeError` | `x['a']` |
| `n \| default('d')` with `n = None` | `None` | `d` |
| `7 // 2` | `3` | **parse error** — the template does not load at all |

The engine's own source flags the first row as a known deviation (`gather_string_parts`:
"probably allow print value_none as 'None' string? currently this breaks some templates").
Everything else tested — `tojson` with indent and non-ASCII, `namespace`, `{% generation %}`,
`strftime_now`, `dictsort`, negative slicing, `is mapping`, string methods, loop variables —
matched byte for byte.

### What this means for the X family

- **X001/X002 will fire rarely on the default corpus, and that is the finding.** "llama.cpp's
  2026 engine matches transformers on 100/100 popular templates" is a trustworthy headline and
  a better launch story than a divergence rate would have been. The report must be able to
  say "engines agree" without sounding like nothing ran.
- **The divergence that exists is on inputs the corpus lacks.** v0.2 should add fixtures
  where it lives: typed content parts, a tool-call round trip (dict arguments), `None`
  content on an assistant tool-call message. Tool calling stays first, as the survey said.
- **X002 must be bidirectional.** The interesting cases are "renders under llama.cpp, raises
  under transformers" as often as the reverse. Each side is a user-facing fact: one is what
  llama-server does, the other is what an evaluation harness does.
- **Parse-time gaps are a distinct class.** A template that fails to *load* under llama.cpp
  (`//`) is more severe than one that renders differently, and the finding should say the
  template will fail to load, not that it is "broken".

## 4. Faithfulness: the engine is more than the renderer

`common_chat_template_direct_apply_impl` in `common/chat.cpp` does four things before and
after the Jinja runtime runs, and a faithful "llama.cpp path" must do all four:

1. `caps_get(prog)` — probes the compiled template for what it supports (typed content,
   tool calls, system role, object arguments, …). `common/jinja/caps.cpp` is part of the
   engine and compiles into the module already.
2. `messages_inp_normalizer(caps).normalize(messages)` — converts typed content to string
   (joined with newlines) when the template only supports strings, and the reverse. About
   60 lines in `chat.cpp`; it has to be ported into the shim.
3. `ctx.current_time` — set to the pinned 2026-01-01 so `strftime_now` matches Jinja2.
4. After rendering, strip a leading `bos_token` when `add_bos` is set (the double-BOS
   behaviour the README already documents).

The spike shim did only step 3, so its "engine" is the raw runtime. That is the right
basis for the semantics table above, but the *user-facing* engine must be the normalised
path, or `ggufdoctor` will report typed-content divergences llama-server users never see.
Recommendation: the WASM module exposes one entry point that mirrors
`common_chat_template_direct_apply_impl`, and reports `caps` alongside the text so the
report can explain *why* a normalisation happened.

## 5. Decisions taken

| Decision | Rationale | Cost if wrong |
|---|---|---|
| WASM via `wasmtime`, not a native extension | pure-Python wheel, one 672 KB data file, one ABI-independent dependency | 8–10 MB install, 120 ms cold start (6 ms cached) |
| Engine is llama.cpp `common/jinja`, pinned by `b` tag | minja is unmaintained and no longer what llama.cpp runs | none identified |
| Engine mirrors the llama-server path (caps + normaliser + BOS strip) | reporting raw-runtime divergences users never see would be the false-positive lesson again | must keep the ported normaliser in sync with `chat.cpp` |
| Corpus grows by three fixtures where divergence lives | on the current corpus X001/X002 find nothing | more fixtures, more render time (still < 50 ms) |
| X002 reports both directions; a parse failure is its own class | each direction is a distinct user-facing fact | none |

Not decided here, for the spec: whether the bundled engine version bumps with each
ggufdoctor release or is rebuilt on a schedule; how the conformance suite obtains its oracle
(`llama-cpp-python` has not been checked for exposing the new engine; a pinned
`llama-server` binary in CI is the fallback).
