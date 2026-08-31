# ggufdoctor — design

**Date:** 2026-08-31
**Status:** approved, ready for implementation planning

## 1. Motivation

GGUF files embed their own chat template. That template is frequently *not* the
template the model was trained with, and nothing in the ecosystem checks this.

### Measured evidence

A survey run on 2026-08-31 against the most-downloaded GGUF repositories on
Hugging Face found:

| Metric | Value |
|---|---|
| Comparable chat models sampled | 106 |
| Render-different from upstream | **16 (15.1%)** |
| Share of downloads on a divergent repo | **30.8%** |
| Publishers affected | 15 of 85 |
| GGUF repos whose upstream base model 404s | 51 of 400 sampled |

Divergence is concentrated on the **tool-calling path**: 14 of the 16 divergent
repos differ on the tools fixture, and 4 differ on *nothing else* — a defect
class invisible to anyone testing with plain chat.

Representative real findings:

- `Qwen/Qwen2.5-3B-Instruct-GGUF` diverges from `Qwen/Qwen2.5-3B-Instruct` —
  the model author's own conversion drifts from the author's own source.
- `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` diverges from upstream.
- A reasoning model ships `<think>\n\n</think>` where upstream ships `<think>\n`,
  silently disabling reasoning by default.
- `enable_thinking` conditions inverted with branches swapped: identical when the
  flag is set, different when unset — the common path.

### Methodology and its limits

The figure compares **rendered output**, not template source. Source diffs are
dominated by engine-compatibility rewrites (`[0]` → `|first`,
`arguments|items` → manual loop) that change nothing the model sees.

Sampling caps repos per publisher. Without that cap the figure reads 46.7%,
because the download ranking is dominated by one publisher who deliberately
patches templates. Any published number must state the cap.

Excluded from the denominator, and reported as coverage gaps rather than
silently dropped: non-chat architectures (ASR, TTS, embeddings), licence-gated
repos (the entire Gemma family, unreadable without a token), repos with no
base-model metadata, and dead upstreams. Only 106 of 400 sampled repos were
comparable.

### Why divergence happens

llama.cpp evaluates templates with **minja**, a Jinja2 subset. Ollama converts
Jinja to **Go templates**, a conversion that is not lossless. Publishers rewrite
templates to survive these engines, and the rewrites sometimes change behaviour.
The user-facing question is therefore not only "does this match upstream" but
**"will this template behave the same in the runtime I am about to use."**

## 2. Goals and non-goals

**Goals**

- Detect chat-template defects in a GGUF file with no network access.
- Detect behavioural disagreement between Jinja2, minja, and Ollama's Go conversion.
- Optionally compare against the upstream source model.
- Produce a reproducible ecosystem survey using the same code path users run.
- Be trustworthy enough that a reported finding is believed without re-derivation.

**Non-goals**

- Not a general GGUF validator (quantization quality, tensor integrity).
- Does not download weights or run inference.
- Does not fix templates. Reporting only, at least through v0.3.
- Not a registry, index, or hosted service.

## 3. Architecture

Organizing principle: **checks perform no I/O.** All data is fetched and parsed
up front; each check is a pure function over loaded data. Rules are therefore
unit-testable without network or disk fixtures.

| Module | Responsibility |
|---|---|
| `reader` | Parse GGUF metadata from a local file or via HTTP range request. Produces one `GgufModel` value: chat template, vocab, BOS/EOS/pad, architecture, quantization. No knowledge of checks or network policy. |
| `sources` | Resolve user input (local path, `org/repo`, URL) into a `GgufModel`. Resolves the upstream base model for reference mode and classifies failures: gated, 404, no base-model metadata, fetch error. |
| `engines` | Uniform `render(template, context) -> RenderResult(text \| error)`. Implementations: native Jinja2, minja (WASM), Ollama Go conversion (WASM), `external` (shells out to a real `llama-cli`/`ollama`). |
| `fixtures` | Versioned conversation corpus as data files. User-extensible. |
| `checks` | One pure function per rule. Returns `Finding` records with stable ids. |
| `report` | Human output, JSON, exit codes. |
| `survey` | Batch harness. A consumer of the modules above, not a parallel implementation. |

The `engines` interface is the seam that allows WASM work to land after v0.1
without redesign.

## 4. Check taxonomy

### Family S — self-contained (offline, no reference)

| id | check | severity |
|---|---|---|
| S001 | chat architecture but no template embedded | error |
| S002 | template will not compile under Jinja2 | error |
| S003 | compiles but raises on a standard fixture | error |
| S004 | template emits a special token absent from the file's own vocab | error |
| S005 | template's terminal token disagrees with `eos_token_id` | warn |
| S006 | template emits BOS while metadata also adds BOS | warn |
| S007 | `add_generation_prompt` does not change output | warn |
| S008 | render is empty or whitespace-only | error |

S004 and S006 are novel: they compare the template against the file's *own*
tokenizer. A template emitting `<|im_end|>` when that string is absent from the
vocab is silently split into several tokens; double-BOS measurably degrades
output. No existing tool checks either.

### Family X — cross-engine equivalence

| id | check | severity |
|---|---|---|
| X001 | Jinja2 and minja produce different output | error |
| X002 | renders under Jinja2, fails under minja | error |
| X003 | Ollama's Go conversion changes output | error |
| X004 | difference is whitespace-only | warn |
| X005 | divergence on the tool-calling fixture | error |

X005 is separated from X001 because the survey shows tool-calling is the
worst-affected path; folding it into X001 would bury the most consequential case.

### Family R — reference comparison (opt-in, network)

| id | check | severity |
|---|---|---|
| R001 | rendered output differs from upstream | warn |
| R002 | divergence carries an author comment claiming a deliberate fix | info |
| R003 | upstream base model no longer exists | warn |
| R004 | upstream template changed after this file was published | info |

## 5. Severity philosophy and noise control

The tool's only asset is being trusted about other people's bugs. A linter that
flags all 15.1% as errors is a noise machine.

- R001 is a **warning**, not an error. Divergence is often an intentional fix.
- R002 detects an author's own annotation (e.g. a Jinja comment naming a fix) and
  downgrades severity accordingly.
- Whitespace-only differences are always separated from semantic differences.
- A checked-in ignore file records accepted divergences **with a reason**, so a
  clean run means "reviewed", not "nothing found".
- Coverage gaps are reported explicitly and never inflate a pass.

## 6. CLI

```
ggufdoctor model.gguf                                    # local: S + X, fully offline
ggufdoctor unsloth/Qwen3-8B-GGUF                         # remote: adds R
ggufdoctor model.gguf --compare-upstream Qwen/Qwen3-8B   # local + R
ggufdoctor survey --top 1000 --per-org 2 --out survey.json --markdown survey.md
```

**Network rule:** no request is made unless the input is remote or upstream
comparison was requested. A local file with no flags is hermetic.

| flag | effect |
|---|---|
| `--runtime <path>` | use a real `llama-cli`/`ollama` as ground truth instead of bundled WASM |
| `--engines jinja2,minja,ollama` | subset the engines |
| `--fail-on error\|warn\|info\|never` | exit-code threshold (default `error`) |
| `--require-upstream` | make coverage gaps fatal |
| `--fixtures <dir>` | user-supplied conversation corpus |
| `--json <path>` | machine-readable report |
| `--ignore-file <path>` | accepted-divergence list |

**Exit codes:** `0` nothing at or above threshold; `1` findings at or above
threshold; `2` tool or usage failure.

## 7. Output

**Human output leads with rendered-output evidence**, not template source diffs:

```
X001  tool-calling output differs: jinja2 vs minja      [with_tools]
      - <|im_start|>assistant
      + <|im_start|>assistant
      + <think>
```

Every run ends with counts by severity plus an explicit coverage line
(e.g. `upstream: gated — R family skipped`).

**JSON** is versioned and stable:

```json
{
  "schema_version": "1",
  "tool_version": "0.1.0",
  "fixture_corpus_version": "1",
  "generated_at": "2026-08-31T00:00:00Z",
  "target": {"kind": "local|repo", "id": "...", "architecture": "..."},
  "engines": [{"name": "jinja2", "version": "3.1.6"}],
  "coverage": {"upstream": "ok|gated|not_found|no_base_model", "families_run": ["S","X"]},
  "findings": [
    {"id": "X001", "severity": "error", "fixture": "with_tools",
     "message": "...", "evidence": {"diff": "...", "engines": ["jinja2","minja"]}}
  ],
  "summary": {"error": 1, "warn": 0, "info": 0}
}
```

## 8. Survey subcommand

`survey` runs the same checks across the top N repos and emits per-repo records,
the aggregate, and the full coverage taxonomy — not only the headline. `--per-org`
is a first-class flag because it is the parameter that moves the result from
46.7% to 15.1%; exposing it makes the methodology visible.

The published statistic must be regenerable by any reader with one command.

## 9. Engine fidelity

Faithful cross-engine comparison requires the **real** engines. A Jinja2-alike
would make our own implementation differences indistinguishable from the bugs we
report.

- **Jinja2**: native Python — exact by construction; this is the transformers reference.
- **minja**: C++ compiled to WASM, shipped in the wheel.
- **Ollama Go conversion**: vendored/ported and compiled to WASM; pinned by version.
- **external** (`--runtime`): shells out to the user's real binaries. Strictly
  more truthful than bundled copies; opt-in because most users lack both.

Every report prints engine names and versions so findings are attributable to a
specific engine build.

## 10. Testing

- **Rule unit tests**: small synthetic templates, each tripping exactly one rule.
  Hermetic, no network.
- **Engine conformance (critical)**: differential suite asserting bundled WASM
  minja matches a pinned real llama.cpp build, and the Ollama path matches a
  pinned real Ollama, across the whole fixture corpus. Divergence is a build
  failure — the product's credibility depends on this.
- **Vendored real templates**: templates from real repos checked in as test data
  so reference-mode tests run offline.
- **Network tests**: separate, opt-in suite.
- **Property test**: unknown or malformed template constructs must produce a
  `Finding`, never a traceback.

## 11. Risks

| risk | mitigation |
|---|---|
| WASM builds of minja and the Go converter are the main engineering risk | engine interface seam; v0.1 ships without them with no loss of other function |
| Ollama's conversion is not a library and can drift | pin version, differential-test in CI, print engine versions in reports |
| False positives destroy credibility | severity philosophy; R002 annotation detection; ignore file; manual audit of every finding in the published survey before launch |
| HF API changes or rate limits | token support, caching, backoff |

## 12. Build sequence

- **v0.1** — `reader`, `fixtures`, family S, Jinja2 engine, reporting, JSON,
  reference mode (family R), `survey`. Reproduces the 15.1% end-to-end; useful offline.
- **v0.2** — minja via WASM; X001/X002/X005. The differentiator.
- **v0.3** — Ollama engine and X003; `--runtime` mode B.

**Launch at v0.2.** The survey is the hook; cross-engine checking is the
differentiator. Shipping reference comparison alone invites "this is a diff script."
