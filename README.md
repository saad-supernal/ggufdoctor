# ggufdoctor

[![CI](https://github.com/saad-supernal/ggufdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/saad-supernal/ggufdoctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ggufdoctor.svg)](https://pypi.org/project/ggufdoctor/)
[![Python](https://img.shields.io/pypi/pyversions/ggufdoctor.svg)](https://pypi.org/project/ggufdoctor/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lint the chat template inside a GGUF file.

ggufdoctor reads the template a GGUF carries, renders it against a fixed set of
conversations with two real template engines, and reports what actually reaches the
model: broken or missing templates, special tokens the vocabulary does not have, prompts
that differ from the source model the GGUF was converted from, and prompts that differ
between the transformers path and the llama.cpp path.

```
$ ggufdoctor Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf  [qwen3moe]  engines: jinja2 3.1.6, llama.cpp b10775 (67a17c17, wasmtime 48.0.0)

  S003  INFO  template does not handle an extended conversation shape (typed_content); older templates predate these inputs — render:TypeError: can only concatenate str (not "list") to str   [typed_content]

  X002  INFO  renders under llama.cpp only after its message normaliser rewrote the input; jinja2 (transformers path) fails on the original (TypeError: can only concatenate str (not "list") to str)   [typed_content]

  engines agree: jinja2 and llama.cpp rendered 9 fixtures identically

0 error, 0 warn, 2 info
families run: S, X   upstream: not_requested
```

## Why

Quantised GGUFs are published by third parties, and the chat template inside them is
often edited on the way: to work around an engine bug, to add tool calling, or by
accident. Nothing checks that the edited template still produces the prompt the
original model was trained on. A survey of the 400 most-downloaded GGUF repositories on
Hugging Face (two per publisher, so a single prolific quantiser cannot dominate) found:

| | corpus 1 (2026-09-01) | corpus 2 (2026-09-03) |
|---|---|---|
| Comparable chat models | 108 of 400 | 111 of 400 |
| Render a different prompt than upstream | **16 (14.8%)** | **16 (14.4%)** |
| Weighted by downloads | 31.4% | 31.2% |
| Publishers affected | 15 of 87 | 15 of 91 |

The two runs use different fixture corpora (corpus 2 adds a tool round-trip, typed
content and a no-generation-prompt conversation) and are not comparable to one decimal;
15 of the 16 divergent repositories are the same in both.

Most of the divergence is on the tool-calling path. In corpus 1, five of the sixteen
divergent repositories differ on nothing but the tools fixture: chat with them and
everything looks right, pass a tool schema and the model receives a prompt its upstream
never would.

| Repository | Downloads | Diverges on |
|---|---|---|
| `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` | 12.7M | tools only |
| `Qwen/Qwen2.5-3B-Instruct-GGUF` | 430k | tools only |
| `poolside/Laguna-S-2.1-GGUF` | 563k | 5 of 7 fixtures |
| `legraphista/glm-4-9b-chat-IMat-GGUF` | 498k | all 7 fixtures |
| `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` | 51k | 6 of 7 fixtures |

The second row is Qwen's own GGUF release disagreeing with Qwen's own source model.

Only 108 of the 400 repositories could be compared at all. 53 of them declare a base
model that no longer exists on the Hub, so nobody can check them against anything. 94
have an upstream that declares no chat template, 72 declare no base model, 34 have a
licence-gated upstream. Every excluded repository is counted under its reason; none is
dropped silently. Per-repository records and the reproduction command are in
[`docs/research/`](docs/research/).

The second engine produced the other headline: on the seven standard fixtures,
llama.cpp's template engine agreed with transformers-style Jinja2 on 100 of 100 top
templates. The disagreements that exist are on typed content, `None` content, `//`
(which llama.cpp will not parse) and runtime defaults llama.cpp supplies that
transformers leaves undefined. ggufdoctor reports those and says which side caused them.

## Install

```bash
pip install ggufdoctor
```

Python 3.11 or newer. Two dependencies: `jinja2` and `wasmtime`. The llama.cpp engine
ships inside the wheel as a 725 KB WebAssembly module; no compiler or llama.cpp install
is needed.

## Usage

Lint a local file:

```bash
ggufdoctor model.gguf
```

Lint a file on the Hub without downloading it (only the header is fetched, by HTTP range
request):

```bash
ggufdoctor unsloth/Qwen3-8B-GGUF
```

Compare against the model the GGUF was converted from:

```bash
ggufdoctor model.gguf --compare-upstream Qwen/Qwen3-8B
```

For a Hub repository that declares `base_model` in its model card, the upstream is
resolved automatically.

| Flag | Effect |
|---|---|
| `--compare-upstream REPO` | also run the R family against `REPO`'s template |
| `--require-upstream` | exit 1 if the requested upstream could not be resolved |
| `--engines jinja2,llama.cpp` | subset the engines; `jinja2` cannot be dropped |
| `--fixtures PATH` | use your own conversation corpus (JSON, same shape as the bundled one) |
| `--json PATH` | write the machine-readable report |
| `--ignore-file PATH` | suppression list, default `.ggufdoctorignore` |
| `--fail-on error\|warn\|info\|never` | severity that makes the exit code 1, default `error` |

Exit codes: `0` nothing at or above the threshold, `1` findings at or above it, `2`
usage or operational error (unreadable file, unreachable Hub, bad ignore file). No
traceback is ever printed for an expected failure.

Set `HF_TOKEN` in the environment to read licence-gated upstreams and get a higher API
rate limit. It is sent only as an `Authorization` header to `huggingface.co`.

### Suppressing a finding

Findings you have judged acceptable go in `.ggufdoctorignore`, one per line, with a
reason. A rule without a reason is rejected.

```
S006 # llama.cpp strips the duplicate; we only serve through llama-server
R001 with_tools # deliberate: upstream schema breaks our parser
```

A rule may name a fixture to suppress only that case.

### JSON output

`--json` writes a versioned report (`schema_version` `1`): tool version, fixture corpus
version, the engines used with their versions, a coverage block (which families ran,
which checks could not be evaluated and why, whether the upstream resolved), every
finding with its evidence (diffs, missing tokens, the cause of a downgrade), suppressed
findings, and a summary by severity. All fields added since 0.1 are additive.

## What it checks

Every finding has a stable id, a severity, and evidence. A check that cannot run
(missing metadata, unavailable engine, custom corpus) is recorded as not evaluated and
the headline says "partial"; it is never reported as clean.

Offline, from the file alone:

| | | |
|---|---|---|
| `S001` | chat architecture with no chat template | error |
| `S002` | template does not compile | error |
| `S003` | template fails to render a standard conversation; INFO when the template declines a shape by design (`raise_exception`) or when the shape is one older templates predate | error / info |
| `S004` | template emits special tokens the vocabulary does not contain | error |
| `S005` | template never emits the declared EOS token | warn |
| `S006` | template emits BOS while `add_bos_token` is set (see [Double BOS](#double-bos)) | info |
| `S007` | `add_generation_prompt` has no effect on the output | warn / info |
| `S008` | template renders to empty output | error |

Between the two engines, on the same input:

| | | |
|---|---|---|
| `X001` | rendered output differs between jinja2 and llama.cpp | error; info when explained by llama.cpp's message normaliser or its runtime defaults |
| `X002` | renders under one engine and fails under the other, either direction; a parse failure under llama.cpp reads "template will not load in llama.cpp" | error; info when explained the same way |
| `X004` | the difference is whitespace only | warn |
| `X005` | `X001` on a tool-calling fixture | error |

Against the upstream model, with `--compare-upstream`:

| | | |
|---|---|---|
| `R001` | rendered output differs from upstream; whitespace-only differences reported at info | error |
| `R002` | the GGUF author annotated the change in the template; downgrades `R001` | info |
| `R003` | upstream could not be resolved (gated, deleted, no base model) | warn |
| `R004` | upstream template changed after this GGUF was published | info |

The conversations rendered are a fixed, versioned corpus of ten: a single user turn,
system plus user, multi-turn, a tool schema, three `enable_thinking` variants, a
tool-call round trip, typed content parts, and a conversation with no generation prompt.
The last three are marked "extended" because many templates predate those message
shapes; a render failure on them is reported at info.

## Engines

A template is rendered by whatever you serve the model with, and the two common runtimes
are different programs.

| Engine | What it is |
|---|---|
| `jinja2` | Jinja2 configured like transformers' `apply_chat_template` environment: the evaluation and fine-tuning path |
| `llama.cpp` | llama.cpp's own engine (`common/jinja`, which replaced minja upstream in January 2026), pinned to build `b10775`, compiled from the C++ sources to `wasm32-wasip1` and run through `wasmtime` |

The `llama.cpp` engine is not a reimplementation. It is llama.cpp's code at a pinned
commit, entered the way `llama-server` enters it: the capability probe, the message
normaliser, the `enable_thinking` and `preserve_reasoning` defaults, the
`add_generation_prompt` semantics. It does not strip the leading BOS, because llama.cpp's
tokenizer re-adds it and comparing post-strip text would manufacture a divergence on
every model that emits BOS.

The claim is checked, not asserted. A [conformance suite](tests/conformance/) runs the
real `llama-server` binary at the same build against ten vendored real templates and all
ten fixtures and requires byte equality with the bundled module; 99 of 100 pairs match,
and the one exception (a Gemma-4-specific rewrite llama.cpp applies above the templating
entry point) is skipped with its reason in the code. The suite runs in CI.

Where the two engines differ because of something llama.cpp does on purpose (joining
typed content into a string, or defining `enable_thinking` and `preserve_reasoning` when
the caller did not), the finding is reported at info with the cause named and the fix in
the message. Each such downgrade is confirmed by re-rendering under Jinja2 with the same
rewrite applied; a flag saying "the normaliser ran" is never enough on its own.

Both engines run with `strftime_now` pinned to a fixed date so output is reproducible.
Templates whose output depends on the date are not fully exercised.

## The survey

```bash
ggufdoctor survey --top 400 --per-org 2 --out survey.json --markdown survey.md
ggufdoctor survey --top 80 --per-org 1 --save-templates templates/
```

`survey` samples the most-downloaded GGUF repositories on the Hub, resolves each one's
upstream, renders both templates against the corpus and reports the fraction that
produce a different prompt. `--save-templates` also writes every fetched template with a
provenance sidecar (repository, revision, licence, tokens), which is how the test
suite's vendored templates were collected.

Three choices keep the number honest, and each one moved it during development:

- **Rendered output is compared, never template source.** Diffing source reports every
  cosmetic or engine-compatibility rewrite. Source diffing put the rate at 46.7%.
- **Two repositories per publisher.** Download rankings are dominated by a handful of
  quantisers, at least one of whom patches templates deliberately. Without the cap you
  measure that publisher.
- **Every excluded repository is classified.** Gated, deleted, no base model, no
  template, not a chat model, fetch error: each has its own bucket in the output, and
  the percentage's denominator is stated next to it. A run with too many fetch errors
  marks itself unreliable instead of printing a number.

Every survey output carries the fixture corpus version it was measured with.

## Double BOS

`S006` is info, not a warning, and the reason is worth stating because the received
wisdom is the opposite. When a GGUF sets `add_bos_token` and its template also emits
`{{ bos_token }}`, llama.cpp does not send two BOS tokens: `common/chat.cpp` strips the
template's leading BOS when the vocabulary's `add_bos` flag is set, then tokenizes with
`add_special`, so exactly one survives. llama-cpp-python does not double either. The
configuration does double for anyone who renders the template themselves and tokenizes
with `add_special_tokens=True`, which is the transformers path common in evaluation
harnesses. That is what the finding says.

## Limitations

- `llama-server` rewrites some requests above the templating entry point the bundled
  engine mirrors (tool-call arguments between object and string form, assistant prefill,
  per-family message rewrites selected by sniffing the template). Those are not
  reproduced. [`engine/README.md`](engine/README.md) lists exactly what is.
- Ollama is not modelled. Ollama has no template conversion: it matches a GGUF's
  template against a small registry of known templates and substitutes a curated Go
  template on a hit; everything else it renders with llama.cpp's engine, which is the
  one bundled here. A check for the registry case is planned; see
  [`docs/research/2026-09-03-ollama-spike.md`](docs/research/2026-09-03-ollama-spike.md).
- The survey samples top downloads, not the long tail, and its percentages are the
  GGUF-versus-upstream question rendered through Jinja2 on both sides. Cross-engine
  divergence is not counted in the survey; the 100 of 100 result above is the
  cross-engine statement.
- Gated upstreams are excluded unless `HF_TOKEN` is set *and* the token's account has
  accepted each repository's licence. A run with a token that had accepted none of them
  left all 28 still-existing gated upstreams excluded and changed the figure only by
  sampling noise (13.6% versus 14.4%; see `docs/research/`). The published figures were
  measured without a token.
- `S004`, `S005` and `S006` need the file's vocabulary and token ids. When a GGUF (or a
  Hub repository's metadata) does not carry them, they are recorded as not evaluated.

## Development

```bash
git clone https://github.com/saad-supernal/ggufdoctor
cd ggufdoctor
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest -q
```

The default test run is offline and needs no toolchain. Two opt-in suites download
things: `pytest -m conformance` fetches the pinned `llama-server` release binary and a
1 MB model and checks the bundled engine against it; `pytest -m network` talks to the
Hub. Every download is verified against a pinned sha256 before use.

The WebAssembly engine is rebuilt with `engine/build.sh`, which fetches the pinned
llama.cpp sources (checksummed) and wasi-sdk 34 (checksummed) and writes the module and
its manifest. CI rebuilds it on every push and runs the suite against the fresh build.
Bumping the llama.cpp pin is a deliberate change: edit `engine/LLAMACPP_PIN`, refetch,
rebuild, re-run the conformance suite and the semantics table, update the version. The
procedure is in [`engine/README.md`](engine/README.md).

Layout:

```
src/ggufdoctor/
  reader.py        GGUF header parser (local file or HTTP range)
  sources.py       target and upstream resolution
  engines/         jinja2_engine.py, llamacpp_engine.py, registry.py
  engine_data/     llamacpp-jinja.wasm + manifest (built by engine/)
  checks/          sanity.py (S), cross_engine.py (X), reference.py (R)
  fixtures.py      the versioned conversation corpus
  survey.py        the survey harness
  report/          human and JSON output
engine/            build pipeline and the C++ shim around llama.cpp's engine
tests/             unit tests, ten vendored real templates, conformance suite
docs/research/     survey data and the two engine studies
```

## Contributing

Issues and pull requests are welcome. The most useful report is a false positive: a
finding on a template that works correctly in practice, with the GGUF (or its Hub id)
and what you ran it with. The project treats a false positive as a bug in the tool, not
in the template, and every finding on the ten vendored real templates is pinned by a
test with the reason it is a true positive written next to it.

Bumps to the llama.cpp pin, new fixtures and new checks all go through the same bar:
complete expected finding sets on the real templates, no assertion narrowed to make a
run pass.

## Licence

MIT. Vendored test templates under `tests/data/templates/` are unmodified copies of
published model repositories and remain under their own licences, recorded in
[`SOURCES.md`](tests/data/templates/SOURCES.md).
