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

## The finding

A survey of the 400 most-downloaded GGUF repositories on Hugging Face, capped at two
repos per publisher, run on 2026-09-01:

| | |
|---|---|
| Comparable chat models | **108** of 400 sampled |
| Render differently from upstream | **16 (14.8%)** |
| Weighted by downloads | **31.4%** |
| Publishers affected | **15** of 87 |

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

## Limitations

- **One engine.** v0.1 renders through Jinja2, configured to match transformers'
  environment (`trim_blocks`, `lstrip_blocks`, `loopcontrols`, the `generation` tag, and
  transformers' `tojson` semantics). llama.cpp's minja and Ollama's Go template conversion
  are not yet compared; that is v0.2 and v0.3.
- **`strftime_now` is pinned** to a fixed date so output is reproducible across runs. A
  template whose output depends on the date is not fully exercised.
- **Top-downloads sample**, not the long tail. The figure describes popular models.
- **Gated repos are excluded, not measured.** Running with a Hugging Face token would
  bring 34 more repos into the comparable set and could move the number either way.

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
