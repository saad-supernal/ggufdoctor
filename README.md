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
accident. Nothing checks that the edited template still produces the prompt the original
model was trained on.

A survey of the 400 most-downloaded GGUF repositories on Hugging Face (two per publisher,
run 2026-09-03):

| | |
|---|---|
| Repositories whose upstream could be compared | 185 of 400 |
| Render a different prompt than their upstream | **26 (14.1%)** |
| Weighted by downloads | 26.8% |
| Publishers affected | 22 of 139 |

Most of the divergence is on the tool-calling path: 20 of the 26 differ on a tool-calling
fixture, and 4 differ on nothing else. Chat with those models and everything looks right;
pass a tool schema and the model receives a prompt its upstream never would. Two of the
four are Qwen3-Coder quants and one is Qwen's own Qwen2.5-3B GGUF release, which disagrees
with Qwen's own source model.

The 215 repositories that could not be compared are the other finding: 59 declare a base
model that no longer exists on the Hub, 71 declare none, 23 have a licence-gated upstream,
21 have an upstream that publishes no template, and the rest are not chat models. Every
excluded repository is counted under its reason. The per-repository records, the exact
command, and the history of earlier runs and their corrections are in
[`docs/research/`](docs/research/).

The second engine produced the other headline: on the seven standard fixtures, llama.cpp's
template engine agreed with transformers-style Jinja2 on 100 of 100 top templates. The
disagreements that exist are on typed content, `None` content, `//` (which llama.cpp will
not parse) and runtime defaults llama.cpp supplies that transformers leaves undefined.
ggufdoctor reports those and says which side caused them.

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
| `--runtime OLLAMA` | path to a real `ollama` binary; renders every fixture through it and reports where it differs from the prediction (`RT001`). Needs a running Ollama server and a local `.gguf` target |
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
which checks could not be evaluated and why, whether the upstream resolved,
`coverage.ollama` and `coverage.runtime`, both null when that family did not run), every
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

Against Ollama's template registry, offline:

| | | |
|---|---|---|
| `O001` | Ollama's registry recognises this template and would substitute a curated Go template for it; names the template and the distance, and says whether that template ignores tools | info |
| `X003` | the curated Go template Ollama would substitute renders differently from the GGUF's own template on a fixture; one-sided failures are reported with the direction named | error |
| `RT001` | with `--runtime`, a real Ollama rendered differently from the prediction | warn; info when it agreed |

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

### Ollama

Ollama is not a third engine in the sense above: it has no template converter of its own
to embed. `ollama create` runs the GGUF's Jinja source through `template.Named`, a
brute-force Levenshtein distance against the 37 strings in its `template/index.json`; a
score under 100 substitutes one of 19 curated Go templates for the GGUF's own, pinned
here to Ollama commit `b79067b0` (release `v0.33.2`).

Unrecognised templates — the common case, nine of the ten vendored real templates —
render with llama-server's engine, which is the one bundled here, so `X001`/`X002`
already describe Ollama for them. `O001`/`X003` only have something to say about the
recognised minority.

The check is data, not code. The Python port of `template.Named` (`ggufdoctor.ollama`)
is asserted equal to the real Go function in CI, over the ten vendored real templates
and synthetic probes built around every registry entry; the curated templates' renders
are goldens produced by Ollama's own `template` package at the pin, not reimplemented.

Two fixture shapes are excluded by construction: `add_generation_prompt: false`, which
Ollama has no concept of, and typed content, which cannot unmarshal into Ollama's
`api.Message` at all. Both are named as coverage rather than compared. The finding holds
for a default `ollama create` on that build; `RENDERER`/`PARSER` directives,
`OLLAMA_GO_TEMPLATE=0` and `PreferChatTemplate` all divert away from the curated
template, and `--runtime` against your own `ollama` binary is the only way to see past
them. See [`docs/research/2026-09-03-ollama-spike.md`](docs/research/2026-09-03-ollama-spike.md).

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

Method: rendered output is compared, never template source (source diffing counts
every cosmetic rewrite); at most two repositories per publisher, so one prolific quantiser
cannot dominate; every excluded repository is classified by reason and the denominator is
stated next to the percentage. A run with too many fetch errors marks itself unreliable
instead of printing a number. Set `HF_TOKEN` to include licence-gated upstreams your
account has access to. Output carries the fixture corpus version it was measured with.

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
- Hand-written renderers in Ollama's `model/renderers/` are selected by a Modelfile
  `RENDERER` directive, never from a GGUF, so ggufdoctor cannot predict them. A clean
  `X003` does not mean Ollama renders the model identically — only `--runtime` against
  your own binary says that. `X003` itself is a finding about a *pair* — this file under
  a default `ollama create` — and not about the file in isolation: the same template
  under llama.cpp is fine. Findings hold for the pinned Ollama commit, which the
  weekly drift job watches.
- The survey samples top downloads, not the long tail, and its percentages are the
  GGUF-versus-upstream question rendered through Jinja2 on both sides. Cross-engine
  divergence is not counted in the survey; the 100 of 100 result above is the
  cross-engine statement.
- Gated upstreams are excluded unless `HF_TOKEN` is set and the token's account has been
  granted access to each one.
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

The default test run is offline and needs no toolchain. Three opt-in suites reach
outside the default run: `pytest -m conformance` fetches the pinned `llama-server`
release binary and a 1 MB model and checks the bundled engine against it; `pytest -m
network` talks to the Hub; `pytest -m ollama_conformance tests/ollama_conformance`
checks the Python port of Ollama's template selector against the real Go
`template.Named` and the committed goldens against a real render, and needs Go plus, on
first run, the network to fetch Ollama's source at the pin. Every download is verified
against a pinned sha256 before use, except Ollama's source, which is fetched at a
pinned commit id and verified by that.

The WebAssembly engine is rebuilt with `engine/build.sh`, which fetches the pinned
llama.cpp sources (checksummed) and wasi-sdk 34 (checksummed) and writes the module and
its manifest. CI rebuilds it on every push and runs the suite against the fresh build.
Bumping the llama.cpp pin is a deliberate change: edit `engine/LLAMACPP_PIN`, refetch,
rebuild, re-run the conformance suite and the semantics table, update the version. The
procedure is in [`engine/README.md`](engine/README.md).

The Ollama registry is vendored data, refreshed the same deliberate way: goldens are
regenerated with `engine/ollama/regen-goldens.sh`, which needs an Ollama checkout at
`engine/build/ollama` (`engine/ollama/fetch-ollama.sh` creates one at the pin). The
bump procedure — edit the pin, refetch, re-vendor, regenerate goldens, re-run the
conformance suite — is in [`engine/ollama/README.md`](engine/ollama/README.md).

Layout:

```
src/ggufdoctor/
  reader.py        GGUF header parser (local file or HTTP range)
  sources.py       target and upstream resolution
  engines/         jinja2_engine.py, llamacpp_engine.py, registry.py
  engine_data/     llamacpp-jinja.wasm + manifest (built by engine/)
  checks/          sanity.py (S), cross_engine.py (X), reference.py (R),
                   ollama_registry.py (O, X003); common.py holds the shared
                   diff/collapse helpers used by the X and O checks
  ollama.py        Ollama's template registry, reproduced as data (selection)
  runtime_ollama.py  family RT — asks a real `ollama` binary what it renders
  ollama_data/     vendored registry, curated templates and goldens
  fixtures.py      the versioned conversation corpus
  survey.py        the survey harness
  report/          human and JSON output
engine/            build pipeline and the C++ shim around llama.cpp's engine
engine/ollama/     fetch/vendor/regen scripts and the Go oracle for the registry
tests/             unit tests, ten vendored real templates, conformance suite
docs/research/     survey data and the engine and Ollama studies
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
