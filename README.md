# ggufdoctor

[![CI](https://github.com/saad-supernal/ggufdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/saad-supernal/ggufdoctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
**1 in 7 popular GGUF chat models sends your model a different prompt than its source model does.**

`ggufdoctor` lints the chat template embedded in a GGUF file. It renders the template
against a fixed corpus of conversations and reports what actually reaches the model —
including how the output compares to the upstream model the GGUF was converted from.

```bash
pip install ggufdoctor
ggufdoctor model.gguf
ggufdoctor model.gguf --compare-upstream mistralai/Mistral-7B-Instruct-v0.2
```

That pulls `wasmtime` alongside `jinja2`. It runs the second engine — llama.cpp's own
template engine, compiled to WebAssembly and shipped in the wheel — so ggufdoctor can
show you what `llama-server` renders, not only what transformers renders. See
[Two engines](#two-engines).

## The finding

A survey of the 400 most-downloaded GGUF repositories on Hugging Face, capped at two
repos per publisher, run on 2026-09-01 against fixture corpus 1:

| | |
|---|---|
| Comparable chat models | **108** of 400 sampled |
| Render differently from upstream | **16 (14.8%)** |
| Weighted by downloads | **31.4%** |
| Publishers affected | **15** of 87 |

Corpus 2 (v0.2, adds tool round-trip, typed content, no generation prompt): **14.4%**
(16 of 111), run on 2026-09-03 — the two figures use different fixture corpora and are
not comparable to one decimal.

Reproduce it yourself — this is the command that produced the table above:

```bash
ggufdoctor survey --top 400 --per-org 2 --markdown survey.md
```

Full output and per-repo records: [`docs/research/`](docs/research/).

### The divergence hides on the tool-calling path

**5 of the 16 divergent repos differ on nothing but the tools fixture.** Load one of
those models, chat with it, and everything looks correct. Give it a tool schema and it
receives a prompt its upstream never would.

| Repo | Downloads | Diverges on |
|---|---|---|
| `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` | 12.7M | tools only |
| `Qwen/Qwen2.5-3B-Instruct-GGUF` | 430k | tools only |
| `poolside/Laguna-S-2.1-GGUF` | 563k | 5 of 7 fixtures |
| `legraphista/glm-4-9b-chat-IMat-GGUF` | 498k | all 7 fixtures |
| `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` | 51k | 6 of 7 fixtures |

The second row is worth reading twice: Qwen's own GGUF release disagrees with Qwen's own
source model, on the tool-calling path.

Corpus 1 again, and corpus 2 sharpened it rather than changing it: 14 of that run's 16
divergent repos differ on at least one tool-calling fixture, and the four that differ on
nothing else are the same publishers — `unsloth`, `Qwen`, and two re-quantisers of the
same Qwen models.

### Provenance is thinner than the headline

Only 108 of 400 repos could be compared at all. The rest are the finding underneath the
finding:

| Why a repo could not be compared | Count |
|---|---|
| Upstream declares no chat template | 94 |
| No `base_model` declared at all | 72 |
| **Declared base model returns 404 — provenance gone** | **53** |
| Upstream is licence-gated | 34 |
| Not a chat architecture | 28 |
| Non-chat pipeline tag | 9 |
| No template in the GGUF | 2 |

53 of the top 400 GGUF repos point at a source model that no longer exists. Nobody can
check those against anything, including their publishers.

## What it checks

Offline, from the file alone — no network:

| | |
|---|---|
| `S001` | no chat template on a chat architecture |
| `S002` | template does not compile |
| `S003` | template fails to render, or declines a conversation shape by design |
| `S004` | template emits special tokens absent from the file's vocabulary |
| `S005` | template never emits the declared EOS token |
| `S006` | template emits BOS while `add_bos_token` is also set |
| `S007` | `add_generation_prompt` has no effect on the output |
| `S008` | template renders to empty output |

With `--compare-upstream`, against the source model's template:

| | |
|---|---|
| `R001` | rendered output differs from upstream (whitespace-only differences reported separately) |
| `R002` | the GGUF author annotated the change — downgrades `R001` rather than raising anything |
| `R003` | upstream could not be resolved |
| `R004` | upstream changed after this GGUF was published |

## Two engines

A GGUF's template is rendered by whatever runtime you serve it through, and those
runtimes are different programs. ggufdoctor renders every fixture twice and compares:

| engine | what it is |
|---|---|
| `jinja2` | Jinja2 configured to match transformers' environment — the evaluation, fine-tuning and `apply_chat_template` path |
| `llama.cpp` | llama.cpp's **own** engine, `common/jinja` (which replaced minja upstream in January 2026), pinned to build tag `b10775` (commit `67a17c17`), compiled to a 725 KB `wasm32-wasip1` module and run through `wasmtime` |

The `llama.cpp` engine is not a reimplementation. It is llama.cpp's C++ sources at a
pinned commit, compiled to WebAssembly, with the same entry point `llama-server` uses:
the caps probe, llama.cpp's message normaliser, its `enable_thinking` and
`preserve_reasoning` defaults, and its `add_generation_prompt` semantics. Every run
prints what it used:

```
engines: jinja2 3.1.6, llama.cpp b10775 (67a17c17, wasmtime 48.0.0)
```

A [conformance suite](tests/conformance/) keeps that claim honest: the bundled module is
checked against the real `llama-server` binary at the same build tag over ten vendored
templates × ten fixtures. 99 of the 100 pairs are byte-identical; the one exception is
skipped with a stated reason — a Gemma-4-specific `tool_responses` rewrite that
llama.cpp performs in `chat.cpp` *above* the templating entry point, so it is not
template rendering. The suite runs in CI and locally with `pytest -m conformance`.

| | | |
|---|---|---|
| `X001` | rendered output differs between the two engines | ERROR — **INFO when llama.cpp's own message normaliser or its runtime defaults explain it** |
| `X002` | renders under one engine and fails under the other, either direction; a parse failure under llama.cpp reads "template will not load in llama.cpp" | ERROR — **INFO when the normaliser or the runtime defaults explain it**, the same ladder as `X001` |
| `X004` | the difference is whitespace only | WARN |
| `X005` | `X001` on a tool-calling fixture | ERROR |

A fixture both engines decline is not an X finding — `S003` already owns that.

`--engines jinja2,llama.cpp` subsets them. `jinja2` is the reference engine and cannot be
deselected. If `wasmtime` is missing the run says `llama.cpp unavailable — <reason>`,
files the X family under checks not evaluated, and calls its own headline partial — it
does not fail and it does not pretend to have checked.

### What the second engine actually found

**On the seven standard fixtures, llama.cpp's engine agreed with transformers-style
Jinja2 on 100 of 100 top GGUF templates.** That is the headline, and it is a good result
about llama.cpp. The divergence that exists lives on richer inputs: content passed as
typed parts, `None` content on an assistant tool-call message, templates using `//`
(which llama.cpp's parser will not load at all), and runtime defaults llama.cpp supplies
that transformers leaves undefined (`enable_thinking`, `preserve_reasoning`). Corpus 2
adds fixtures for the message shapes among those. Full measurement:
[`docs/research/2026-09-03-engine-spike.md`](docs/research/2026-09-03-engine-spike.md).

Two of those classes are llama.cpp's own doing, not the template's: the normaliser
joining typed content parts into a string, and the runtime defaults llama.cpp injects
into every render. A template author cannot remove either. So a divergence they fully
account for is reported at **INFO** with the cause named and the fix in the message
(pass those values explicitly, and the runtimes agree), and the downgrade is *confirmed*
— by re-rendering under Jinja2 with the same rewrite applied — never assumed from a
flag. A warning that fires on everything is not a warning.

The rest stay at ERROR. Across the ten real templates vendored in the test suite, four
ERROR findings remain, in three classes: templates that will not accept an assistant
message with null content under transformers, where llama.cpp renders it as an empty
assistant turn and the tool call silently vanishes; a template that raises under
transformers on typed content where llama.cpp serves a prompt anyway; and one whose
output forks on whether `add_generation_prompt` is *present* rather than true — llama.cpp
omits the key entirely when generation prompting is off, so that template's own
`is defined` fallback turns it back on and appends an assistant opener transformers
never would.

When X ran and found nothing, the report says so:

```
engines agree: jinja2 and llama.cpp rendered 10 fixtures identically
```

## Why the number is trustworthy

Three ways this measurement can be got wrong, and what this tool does instead. Each of
these moved the figure during development.

**Rendered output, not template source.** Diffing template text reports every
engine-compatibility rewrite — `messages[0]` becoming `messages|first`, added whitespace
markers — none of which changes a token the model sees. Source diffing put the rate at
46.7%. Rendering both templates against the same conversations and diffing the *output*
is the honest comparison.

**Capped at two repos per publisher.** Download rankings are dominated by a handful of
prolific quantisers, at least one of whom deliberately patches templates. Without a cap
you measure that publisher, not the ecosystem. `--per-org` defaults to 2 and appears in
the output, so the methodology travels with the number.

**Every uncomparable repo is classified, never dropped.** Licence-gated repos return 401
without a token. Filing them as "no chat template" quietly shrinks the denominator and
inflates the rate. Each one lands under its own reason in the coverage table above, and
the percentage's denominator is the comparable set, stated alongside it.

A run whose fetch-failure rate is high enough to distort the result says so in its own
output rather than printing a number anyway.

## A note on double BOS

`S006` reports at INFO, not WARN, and it is worth explaining why, because the received
wisdom says otherwise.

When a GGUF sets `add_bos_token: true` and its template also emits `{{ bos_token }}`, the
common assumption is that the model receives two BOS tokens. **Through llama.cpp this does
not happen.** `common_chat_template_direct_apply_impl` in `common/chat.cpp` strips the
template's rendered leading BOS whenever the vocabulary's `add_bos` flag is set, and the
result is then tokenized with `add_special=true` — so exactly one survives. Jinja
templating is the default (`--jinja`), and with `--no-jinja` the GGUF's template is never
rendered at all. llama-cpp-python does not double either: its formatter reports
`added_special=True` and the caller tokenizes with `add_bos=False`.

The configuration is still worth knowing about, because it does double for anyone who
renders the template themselves and then tokenizes with `add_special_tokens=True` — the
transformers-style path, common in evaluation and fine-tuning harnesses. That is what the
finding says, and no more.

This is also why the bundled `llama.cpp` engine deliberately does **not** perform that
strip before family X compares the two engines: llama.cpp's tokenizer immediately re-adds
the token, so the token streams agree, and comparing post-strip text against transformers'
output would manufacture an `X001` on every model in the `S006` population.

## Limitations

- **Ollama's Go template conversion is not yet compared** (v0.3, with `X003` and
  `--runtime`). Two of the three runtimes people actually serve GGUFs through are
  covered; the third is not.
- **`llama-server` also rewrites requests before templating**, above the entry point the
  bundled engine mirrors — tool-call `arguments` move between object and string form,
  assistant prefill is applied, and `common_chat_try_specialized_template` selects
  per-family message rewrites by sniffing the template source (Gemma-4 `tool_responses`
  collapsing, DeepSeek-V4 tool-result sorting, gpt-oss/LFM2 reasoning copying, StepFun
  content trimming). The bundled engine reproduces
  `common_chat_template_direct_apply_impl` and nothing above it. Specifically, it
  mirrors: the `caps` probe; the message normaliser (typed content ⇄ string, both
  directions); null or absent content as `""`; `enable_thinking` always defined and
  defaulting to true; `add_generation_prompt` present only when the flag is on;
  `preserve_reasoning` defaulted to true and expanded through
  `caps_apply_preserve_reasoning` into `preserve_thinking`, `clear_thinking`,
  `truncate_history_thinking` and `drop_thinking`; and `reasoning_effort` expansion. It
  does **not** strip the leading BOS — llama.cpp's tokenizer re-adds it, so comparing
  post-strip text would manufacture a divergence on every model in the `S006`
  population. `datetime` / `date_string` are rendered at a pinned clock by design.
  `engine/README.md` is the authority, and every engine bump re-checks it against
  upstream `chat.cpp`.
- **`strftime_now` is pinned** to a fixed date so output is reproducible across runs. A
  template whose output depends on the date is not fully exercised.
- **Top-downloads sample**, not the long tail. The figure describes popular models.
- **Gated repos are excluded, not measured** unless `HF_TOKEN` is set in the environment (the same variable `huggingface_hub` reads); with a token, gated upstreams become comparable and the API rate limit is higher. Running with a Hugging Face token would
  bring 33–34 more repos into the comparable set and could move the number either way.
- **`survey` measures GGUF-vs-upstream, not engine-vs-engine.** The published percentages
  are the `R001` question — does this GGUF's template render differently from its source
  model's — with both sides rendered through Jinja2. Counting family X across the survey
  would need real vocabulary tokens for every repo and a second engine per record; it is
  deliberately deferred, and the spike's 100/100 is the cross-engine statement until
  then.

## Ignoring findings

A finding you have judged acceptable can be suppressed in `.ggufdoctorignore` — but only
with a reason, because a list of unexplained suppressions is a way of hiding problems
rather than resolving them:

```
S006 # llama.cpp strips the duplicate; we only serve through llama-server
R001 with_tools # deliberate: upstream schema breaks our parser
```

## Exit codes

`0` clean, `1` findings at or above `--fail-on` (default `error`), `2` usage or
operational error.

## Licence

MIT.
