# Spike: an Ollama engine and X003 for ggufdoctor v0.3 (2026-09-03)

**Question.** The spec's v0.3 line is "Ollama engine and X003 (Ollama's Go conversion changes
output); `--runtime` mode". That line was written on the belief — stated in §1 of the design
doc — that "Ollama converts Jinja to **Go templates**, a conversion that is not lossless."
Nobody had read Ollama's source to check. This spike checks it, and prices the three ways an
Ollama engine could reach a pure-Python wheel.

**Answer in one line.** There is no converter: Ollama matches the GGUF's Jinja source against
37 hard-coded strings by Levenshtein distance and, on a hit, substitutes a curated Go template
— and since May 2026 the *default* path for an unrecognised template is to hand the GGUF's own
Jinja to llama-server, i.e. to the engine v0.2 already ships. X003 is therefore real but
narrow, and it needs **no engine at all**: the selection is exactly reproducible in pure Python
and the 20 Go templates can be pre-rendered by real Go in CI (29 KB of data).

All measurements were taken in this directory. Throwaway code: `match.py`, `match_fast.py`,
`jinja_render.py`, `runwasm.py`, `runwasm2.py`, `ollama-src/spikeharness/`,
`ollama-src/goldengen/`. Raw results: `go-renders.json`, `wasm-renders.json`,
`jinja-renders.json`, `golden.json`.

**Ollama source pinned at commit `b79067b0db7417f20108363bc22adb97f35c966a`**
(2026-09-02, "gemma4: image and audio input support"), latest release `v0.33.2` (2026-08-27).
Toolchain: Go 1.26.0 (auto-downloaded per `go.mod`'s `go 1.26.0`), wasmtime 48.0.0 (Python
package), jinja2 3.1.6 via the repo's own `.venv`.

---

## 1. What Ollama actually does with a GGUF chat template

It is **a lookup, not a conversion.** There is no Jinja-to-Go translator anywhere in the tree;
`grep -rni jinja --include='*.go'` returns only llama-server CLI flags and test comments.

### The import path

`ollama create` from a GGUF reaches `detectChatTemplate` (`server/model.go:92`), called from
`server/create.go:463` and `:636`:

```go
func detectChatTemplate(layers []*layerGGML) ([]*layerGGML, error) {
	for _, layer := range layers {
		if s := layer.GGML.KV().ChatTemplate(); s != "" {
			if t, err := template.Named(s); err != nil {
				slog.Debug("template detection", "error", err, "template", s)
			} else {
				layer, err := manifest.NewLayer(t.Reader(), "application/vnd.ollama.image.template")
				...
				layer.Status = fmt.Sprintf("using autodetected template %s", t.Name)
```

The matcher is `template.Named` (`template/template.go:72`) — brute-force Levenshtein against
an embedded index, with an absolute cutoff:

```go
func Named(s string) (*named, error) {
	templates, err := templatesOnce()
	...
	var template *named
	score := math.MaxInt
	for _, t := range templates {
		if s := levenshtein.ComputeDistance(s, t.Template); s < score {
			score = s
			template = t
		}
	}
	if score < 100 {
		return template, nil
	}
	return nil, errors.New("no matching template found")
}
```

`templatesOnce` (`template/template.go:29`) unmarshals `template/index.json` and pairs each
entry with an embedded `*.gotmpl` and optional `*.json` stop-parameter file.

| registry fact | value |
|---|---|
| Index entries (Jinja source strings) | **37** |
| Distinct Go templates reachable via the index | **19** |
| `.gotmpl` files embedded | 20 (`vicuna.gotmpl` has no index entry — unreachable) |
| Match rule | absolute Levenshtein `< 100`, unnormalised by length |
| `template/` directory size | 488 KB |

### On no match

Nothing happens. `slog.Debug` fires, no `image.template` layer is created, and
`m.HasGoTemplate` (`server/images.go:781`) stays false. The model then has no Go template, so
it takes the Jinja path.

### The registry is frozen (GitHub API dates; the local clone is shallow)

| file | last commit | date |
|---|---|---|
| `template/index.json` | `f8c3dbe5` "templates: add autotemplate for gemma3" | **2025-03-20** |
| `template/chatml.gotmpl` | `413ae39f` "update templates to use messages" | **2024-08-27** |
| `template/template.go` | `6bba484f` "lint fixes" | 2026-08-20 |

The newest family the index knows is Gemma 3. Nothing from the Qwen 3.x, GLM 4.x, DeepSeek
v3/v4, LFM2 or Gemma 4 era is in it.

### The decisive change: Jinja is now the default

`template.go`'s second-most-recent commit is `9db4bdba` (2026-05-29), **"runner: Remove CGO
engines, use llama-server exclusively for GGML mode."** The header comment of
`llm/llama_server.go` now states the split outright:

> "Ollama uses two chat paths with llama-server. Models with explicit Ollama
> renderers/parsers, Harmony handling, MLX, or an enabled Go TEMPLATE layer still render
> prompts in Go and call /completion. Other GGUF chat models use llama-server's
> chat_template handling through /v1/chat/completions."

The selector is `chatModeForModel` (`server/routes.go:2361`), and note which mode is the zero
value:

```go
const (
	chatExecutionModeNative chatExecutionMode = iota   // llama-server renders the GGUF Jinja
	chatExecutionModeRendered                          // Ollama renders in Go
)

func chatModeForModel(m *Model) chatExecutionMode {
	if m.IsMLX() || usesOllamaRenderedChat(m) {
		return chatExecutionModeRendered
	}
	return chatExecutionModeNative
}

func usesOllamaRenderedChat(m *Model) bool {
	return m != nil && (m.Config.Renderer != "" || m.Config.Parser != "" || shouldUseHarmony(m) || shouldUseGoTemplate(m))
}

func shouldUseGoTemplate(m *Model) bool {
	if !m.HasGoTemplate { return false }
	if goTemplateEnvSet() { return envconfig.GoTemplate(true) }
	return !m.PreferChatTemplate && envconfig.GoTemplate(true)
}
```

In native mode the prompt comes from `(*llamaServerRunner).ApplyChatTemplate`
(`llm/llama_server.go:1848`), which POSTs to llama-server's **`/apply-template`** endpoint.
That is llama.cpp's `common/jinja` engine — the engine ggufdoctor v0.2 already embeds.

So the Go template is used only when a Go template *exists*, and even then it can be
overridden: `shouldPreferChatTemplate` (`server/images.go:338`) sets `PreferChatTemplate` when
the GGUF's Jinja has strictly more capabilities, or equal capabilities plus a tool round-trip
the Go template lacks (`server/images.go:831`).

### A third path the spec does not know about

`model/renderers/` holds **21 hand-written Go renderers** (`qwen3coder.go`, `glm46.go`,
`glm47.go`, `lfm2.go`, `laguna.go`, `ornith.go`, `deepseek3.go`, `gemma4.go`, `olmo3.go`,
`nemotron3nano.go`, `cohere.go`, `cogito.go`, `glimmer.go`, …), dispatched by `rendererForName`
(`model/renderers/renderer.go:56`). These are imperative Go code, not templates, and they are
**selected only by a Modelfile `RENDERER` directive** (`parser/parser.go:132`,
`x/create/client/create.go:81`) — never autodetected from GGUF metadata. They apply to models
published on ollama.com, not to a user's own `ollama create` from a Hugging Face GGUF.
ggufdoctor cannot predict them from a file.

**Summary of what happens to a GGUF's `tokenizer.chat_template` under Ollama at HEAD:**

| condition | what renders the prompt |
|---|---|
| Modelfile sets `RENDERER`/`PARSER` (ollama.com library models) | hand-written Go renderer, `model/renderers/` |
| Levenshtein hit `< 100` **and** not `PreferChatTemplate` | curated Go `text/template` |
| Levenshtein hit but GGUF Jinja has more capabilities | **the GGUF's Jinja**, via llama-server |
| No hit (the common case for HF GGUFs) | **the GGUF's Jinja**, via llama-server |
| `OLLAMA_GO_TEMPLATE=0` | **the GGUF's Jinja**, via llama-server |

---

## 2. Is X003 well posed?

**Yes, but it is a much smaller check than the spec implies, and its name is wrong.**
"Ollama's Go conversion changes output" describes a thing that does not exist. The well-posed
check is:

> **X003** — Ollama's template registry recognises this GGUF's chat template (Levenshtein
> `< 100` against `template/index.json`) and substitutes the curated Go template *T*.
> Rendering *T* through Ollama's own value pipeline produces different text than rendering
> the GGUF's own Jinja template on the same fixture.

### Inputs the check needs

1. **The picked Go template** — `index.json` plus the 20 `.gotmpl` sources, pinned to an
   Ollama commit. 488 KB vendored, or ~50 KB for just the files needed.
2. **Ollama's message pipeline, not the raw fixture.** `(*Template).Execute`
   (`template/template.go:255`) does not hand the fixture straight to `text/template`:
   - `collate` (`template/template.go:357`) merges consecutive same-role messages with
     `"\n\n"`, and joins **all** system messages into one `.System` string with `"\n\n"` —
     while *also* leaving them in the message list, so a template that ranges `.Messages`
     renders each system message a second time.
   - `convertMessagesForTemplate` (`:485`) projects to `templateMessage{Role, Content,
     Thinking, Images, ToolCalls, ToolName, ToolCallID}`.
   - Tool-call arguments become `templateArgs`, a map whose `String()` marshals to JSON
     (`:387`), with `nil` rendering as `"{}"`.
   - If the template does not reference `messages`, Execute falls into a legacy
     `.System`/`.Prompt`/`.Response` loop that re-executes the template once per turn and
     splices a `.Response` node (`:279`-`:330`).
3. **Ollama's defaults.** Critically, **Ollama has no `add_generation_prompt` concept at all**
   — `grep -rni add_generation_prompt --include='*.go'` finds it only in test fixtures and in
   comments describing the reference Jinja semantics they compare against (e.g.
   `model/renderers/lfm2.go:330`: "RenderWithRenderer uses add_generation_prompt=true for chat
   rendering"). Ollama always renders for generation.

### Failure modes

| failure mode | why it bites |
|---|---|
| **`add_generation_prompt: false` is not expressible.** Ollama never renders without a generation prompt, so a diff on the `no_generation_prompt` fixture is an artefact of our corpus, not a defect a user can hit. Reporting it would be the v0.1 false-positive lesson again. | must exclude that fixture from X003 |
| **Typed content is not expressible.** `api.Message.Content` is a plain `string`; the `typed_content` fixture fails to unmarshal outright (measured, §5). | X003 must skip, not "fail", such fixtures |
| **Tool comparison is mostly vacuous.** 15 of the 19 reachable Go templates predate tool calling and simply ignore `.Tools`. A "difference" is Ollama dropping the tools entirely — true, but a capability gap, not a rendering divergence, and `shouldPreferChatTemplate` exists precisely to route around it. | report as its own class, not as X003 |
| **The registry is not the whole story.** `PreferChatTemplate`, `OLLAMA_GO_TEMPLATE`, `RENDERER`/`PARSER`, Harmony and MLX all divert away from the Go template. A finding that says "Ollama will render this differently" is only true for a *default* `ollama create` of a *recognised* template on a build where none of those apply. | the finding must be conditional, and must name the Ollama version |
| **Levenshtein `< 100` is unnormalised**, so it is length-sensitive in a way that looks arbitrary: an 8-character template scored 194 (no match) while a 291-character one scored 0. Near-threshold behaviour is brittle across Ollama versions. | pin the version; treat scores in 60-99 as low-confidence |

---

## 3. How an Ollama engine could reach a pure-Python wheel

### Measurements

All builds `GOOS=wasip1 GOARCH=wasm`, Go 1.26.0. `-s -w` = stripped.

| module | raw | gzipped | JIT compile | `.cwasm` cache | instantiate | render |
|---|---|---|---|---|---|---|
| minimal `text/template` + `encoding/json` | 5,208,300 B | 1,353,775 B | — | — | — | — |
| same, stripped | **5,087,659 B** | 1,322,805 B | **305 ms** | 11.4 MB | 12.6 ms first | **1.0 ms** warm |
| Ollama's real `template` package | 10,906,092 B | 2,736,253 B | — | — | — | — |
| same, stripped | **10,646,450 B** | 2,680,188 B | **556-581 ms** | **22.1 MB** | 3.1 ms | see below |
| *(v0.2's shipped llama.cpp engine, for scale)* | *725,239 B* | *~173 KB* | *120-130 ms* | *0.8 MB* | — | *2-9 ms* |

`wasmtime.Engine()` construction: 7.5 ms. Deserialize from `.cwasm`: 3.4 ms (minimal), 5.5 ms
(Ollama).

**(a) Go to `wasip1` under wasmtime: it works, and it is too big.**

Go's wasip1 runtime is fully functional under wasmtime 48 — goroutines, memory, `os.Args`,
stdin/stdout, and WASI preopened directories all behaved. I ran Ollama's *real* `template`
package in WASM against the ten vendored templates and the corpus, and the output was
**byte-identical to the native run** (`go-renders.json == wasm-renders.json` compared in
Python: `True`). No exception-handling flags, no linker archaeology — it compiled first try,
unlike the wasi-sdk work in v0.2.

The problem is the Go runtime floor. **A program that does nothing but execute one Go
`text/template` is 5.1 MB stripped** — 7x v0.2's entire llama.cpp engine — and Ollama's
package is 10.6 MB, **14.7x v0.2's engine**, with a 22 MB compilation cache and a 0.6 s cold
JIT. TinyGo is what would normally fix this, and it cannot.

**(b) TinyGo: ruled out.** TinyGo's own stdlib support table lists `text/template` as
importable but failing its tests, with `panic: unimplemented: (reflect.Type).NumOut()`;
`html/template` fails identically. Go templates resolve methods through
`reflect.Value.MethodByName`, which TinyGo has not implemented. Ollama's templates call
methods on its own types (`templateArgs.String`, `templateTools.String`,
`ToolProperty.ToTypeScriptType`), so this is not an edge case we could avoid — it is the
mechanism the templates rely on. I did not install TinyGo; the vendor's documented status is
unambiguous.

**(c) Subprocess to a real `ollama`: fine as `--runtime`, useless as a default.**
Latest release assets (`v0.33.2`):

| asset | size |
|---|---|
| `ollama-darwin.tgz` | 158.6 MB |
| `ollama-linux-amd64.tar.zst` | 1,422.3 MB |
| `ollama-linux-arm64.tar.zst` | 1,543.3 MB |
| `ollama-windows-amd64.zip` | 1,460.1 MB |

Nobody downloads 1.4 GB to lint a template. This is the opt-in `--runtime` oracle the spec
already describes, and it is the right shape for that — but it cannot be the engine.

### The measurement that changes the design

Benchmarked natively (`go test -bench`, `ollama-src/spikeharness/bench_test.go`), on a 6.9 KB
template:

| operation | time |
|---|---|
| `template.Named` — Levenshtein vs 37 index entries | **212,219,456 ns/op (212 ms)** |
| `template.Execute` — the actual Go `text/template` render | **2,131 ns/op (2.1 us)** |

**Ollama's template selection costs 100,000x more than its template rendering.** All the
interesting logic — "which Go template would Ollama pick for this GGUF?" — is in the part that
is a pure string algorithm, and none of it is in the part that needs Go.

So: reproduce the selection in Python, and pre-render the templates in CI.

**Selection in pure Python, exactly.** `agnivade/levenshtein.ComputeDistance` is plain
unnormalised Levenshtein. A naive Python port is unusable (>120 s for ten templates, killed on
timeout). But the decision is only ever "is the distance `< 100`?", which admits a length
prefilter (`abs(len(a)-len(b)) >= 100` implies no match) and a banded Ukkonen DP with an early
band-exhaustion exit. `match_fast.py` implements that:

| | |
|---|---|
| Ten templates, all 37 candidates | **96.3 ms total** (~10 ms/template) |
| Candidates eliminated by the length prefilter alone | 37/37 for 8 of 10 templates |
| Agreement with real Go `template.Named()` | **exact, 10/10** (asserted in `match_fast.py`) |

**Rendering by precomputed goldens.** The 20 `.gotmpl` files are frozen (2024-08-27) and the
fixture corpus is versioned. Their cross product is therefore a constant, generated by *real
Go* in CI (`ollama-src/goldengen/main.go`, which drives Ollama's own
`template.Parse`/`Execute`/`Values` so `collate` and the value pipeline are genuine):

| | |
|---|---|
| 20 Go templates x 10 corpus fixtures | `golden.json`, **29,212 B raw / 3,364 B gzipped** |
| Parse failures | 0 |
| Runtime engine needed | **none** |

---

## 4. An oracle for conformance

**There is a render-only API, and it still loads the model.** `/api/chat` and `/api/generate`
accept an undocumented `_debug_render_only: true` (`api/types.go:119`, `:169`), returning
`DebugInfo.RenderedTemplate` (`api/types.go:551`) without generating — `server/routes.go:626`,
`:2712`, `:2995`. But in native mode the handler calls `r.ApplyChatTemplate` on an
already-scheduled runner (`server/routes.go:2995`, inside `handleNativeChat`), so a model must
be loaded. There is no "render this template against these messages" endpoint that skips
weights.

Options, cheapest first:

| oracle | cost | what it proves |
|---|---|---|
| **`go test` against a vendored copy of Ollama's `template` package** (what `goldengen` does) | one Go toolchain in CI; seconds | that our goldens and our Python selector match real Ollama code at a pinned commit. Covers §3's two claims exactly. |
| `ollama show --template <model>` | needs a pulled model; no weights loaded for the render | that the registry picked what we predicted — but only for models already in the ollama.com library |
| `ollama serve` + tiny model + `_debug_render_only` | 158 MB-1.5 GB binary + a model; slow | end-to-end truth, including `PreferChatTemplate` and the renderers |

**Recommendation:** the CI conformance job is the Go-toolchain one. It is a real oracle — it
executes Ollama's actual `Named`, `collate` and `Execute` — and it is the same shape as the
differential suite §10 of the spec already demands. A full `ollama serve` job is a nightly at
most, and is what `--runtime` exists for.

---

## 5. Which templates X003 would fire on today

`template.Named` run for real (Go, `ollama-src/spikeharness/`) over the ten templates in
`tests/data/templates/`. The Python selector agrees on all ten.

| vendored template | chars | best distance | picked | recognised |
|---|---|---|---|---|
| `HauhauCS__Gemma-4-E4B-Uncensored-...-Aggressive` | 11,926 | 9,131 | — | no |
| `LiquidAI__LFM2.5-2.6B-GGUF` | 5,443 | 3,784 | — | no |
| `LuffyTheFox__Qwen3.6-35B-A3B-...-Hermes-V13` | 7,764 | 5,250 | — | no |
| `PaddlePaddle__PaddleOCR-VL-1.6-GGUF` | 1,831 | 1,124 | — | no |
| `antirez__deepseek-v4-gguf` | 4,988 | 3,645 | — | no |
| `legraphista__glm-4-9b-chat-IMat-GGUF` | 8 | 194 | — | no |
| `mudler__Laguna-XS-2.1-APEX-GGUF` | 3,788 | 2,798 | — | no |
| `ornith-ai__Ornith-1.0-9B-GGUF` | 7,594 | 5,140 | — | no |
| `rippertnt__HyperCLOVAX-SEED-Text-Instruct-1.5B` | 291 | **0** | **`chatml`** | **yes** |
| `unsloth__Qwen3-Coder-30B-A3B-Instruct-GGUF` | 6,896 | 4,680 | — | no |

**1 of 10.** Distances are not close: the nearest miss is 194 against a cutoff of 100, and
eight of the nine misses are off by thousands. The one hit is exact (distance 0) — a verbatim
copy of the canonical ChatML template.

Note that four of the nine unrecognised templates (LFM2, Laguna, Ornith, Qwen3-Coder) have a
hand-written renderer in `model/renderers/`. Those renderers would apply to the ollama.com
library build of those models, but not to `ollama create` from these GGUFs, because `RENDERER`
is a Modelfile directive (§1). ggufdoctor cannot see that from the file.

### Head-to-head for the one recognised template

Ollama's `chatml.gotmpl` driven through Ollama's own `template.Execute`, versus the GGUF's
Jinja through the repo's `Jinja2Engine` (jinja2 3.1.6). Full data in `go-renders.json` /
`jinja-renders.json`.

| fixture | result |
|---|---|
| `user_only` | identical |
| `system_user` | identical |
| `multiturn` | identical |
| `with_tools` | identical (both ignore `tools`) |
| `thinking_true` / `thinking_unset` / `thinking_false` | identical |
| `typed_content` | both decline — Jinja2 `TypeError`, Ollama **cannot represent the input** |
| `no_generation_prompt` | **differs** |
| `tool_roundtrip` | **differs** — Jinja2 raises, Ollama renders |

```
no_generation_prompt
  jinja2 : '<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\nHello!<|im_end|>\n'
  ollama : '<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\nHello!<|im_end|>\n<|im_start|>assistant\n'

tool_roundtrip
  jinja2 : render:TypeError: can only concatenate str (not "NoneType") to str
  ollama : '<|im_start|>system\nBe brief.<|im_end|>\n<|im_start|>user\nWeather in Paris?<|im_end|>\n
            <|im_start|>assistant\n<|im_end|>\n<|im_start|>tool\n{"temp_c": 18}<|im_end|>\n<|im_start|>assistant\n'

typed_content
  jinja2 : render:TypeError: can only concatenate str (not "list") to str
  ollama : UNREPRESENTABLE in api.Message: json: cannot unmarshal array into
           Go struct field .context.messages.content of type string
```

**So divergence exists, and it is of three kinds — only one of which is a defect.**

1. `no_generation_prompt` — **not a real finding.** `chatml.gotmpl` appends the generation
   prompt unconditionally because Ollama has no `add_generation_prompt` (§2). No user can
   reach the "false" case through Ollama. Reporting this would be a false positive.
2. `tool_roundtrip` — **a real, interesting finding**, and it is the *bidirectional* shape
   v0.2 already learned to report: the template raises under transformers on a `None`
   assistant content, while Ollama renders it happily. It also shows `collate` leaking the
   system message into the loop body (`<|im_start|>system` appears even though
   `chatml.gotmpl` ranges `.Messages` and Ollama also hoisted it into `.System`), and it shows
   the tool result rendered under a bare `tool` role the template never anticipated.
3. `typed_content` — **a coverage fact, not a diff.** Ollama's wire type cannot carry it.

Net: on the current corpus, honest X003 fires on **1 template x 1 fixture**.

---

## 6. Recommendation

**Route: drop the WASM Ollama engine. Implement X003 as vendored-registry selection in pure
Python plus CI-generated golden renders, and make `--runtime` the real Ollama oracle.**

The spike kills the spec's premise. There is no lossy Jinja-to-Go conversion to model, so there
is no engine to embed; and since 2026-05-29 an unrecognised template — the overwhelmingly
common case, 9 of our 10 — is rendered by llama-server from the GGUF's own Jinja, which is
*already* what v0.2's engine reproduces. What remains of X003 is a registry-substitution
check: 37 pinned strings, a distance cutoff, 19 curated Go templates, and a comparison whose
Go half is a compile-time constant. Building 10.6 MB of WASM to compute a 2 us render — 14.7x
the size of the entire llama.cpp engine, for a check that fires on one of ten templates —
would be the worst size-to-value trade in the project. The Python selector is exact against
real Go on all ten templates and the goldens are generated by Ollama's own code, so §9's
"no engine-alikes" rule is honoured: we are not reimplementing `text/template`, we are caching
its output over a frozen, pinned input set.

The risk this buys is **silent staleness**, and it is the one to watch. Goldens and a vendored
index are correct only for the pinned commit; if Ollama adds index entries — it has not since
2025-03-20, but it could — ggufdoctor would under-report until the pin moves. The mitigations
are a CI job that re-derives everything from real Go at the pinned commit and fails on drift,
printing the pinned Ollama commit in every report, and skipping X003 with an explicit coverage
line rather than guessing whenever the user supplies `--fixtures` (no goldens exist for a
corpus we have not pre-rendered).

### Decisions

| Decision | Rationale | Cost if wrong |
|---|---|---|
| No Ollama WASM engine | 10.6 MB and 0.6 s cold JIT for a 2.1 us render; 14.7x v0.2's whole engine | must revisit if Ollama ever ships a real converter |
| TinyGo not pursued | vendor documents `text/template` as failing on `(reflect.Type).NumOut()`; Ollama's templates call methods on custom types | none identified |
| X003 = "registry substitution changes output", renamed from "Go conversion changes output" | the conversion does not exist; the substitution does | a wrong name in the spec is a wrong finding in the report |
| Selection in Python via bounded Levenshtein + length prefilter, asserted equal to real `template.Named` in CI | exact, 10/10; 10 ms/template vs 212 ms in Go; no engine | brittle only near the cutoff — flag scores 60-99 as low confidence |
| Go renders precomputed by real Go in CI (`golden.json`, 29 KB) | honours §9 without embedding a runtime; goldens come from Ollama's own `Execute`/`collate` | staleness if the pin is not maintained |
| `no_generation_prompt` excluded from X003 | Ollama has no `add_generation_prompt`; a diff there is unreachable by users | the false-positive lesson, again |
| Typed content and tools-ignored reported as coverage, not divergence | `api.Message.Content` is a `string`; 15/19 templates predate tools | inflated, unactionable error counts |
| `--runtime` shells out to a real `ollama` and uses `_debug_render_only` | the only path that sees `PreferChatTemplate`, `RENDERER` and the 21 hand-written renderers | 158 MB-1.5 GB, opt-in, so no default cost |
| The renderers in `model/renderers/` are out of scope | selected by Modelfile directive, not derivable from a GGUF | a real Ollama behaviour ggufdoctor will not predict — must be said in the README |

### What v0.3 should and should not promise

v0.3 should promise this: ggufdoctor tells you whether Ollama's template registry recognises
your GGUF's chat template, which of its 19 curated Go templates it would substitute, and
whether that substitution changes the prompt on the fixture corpus — pinned to a named Ollama
commit, computed offline, with the Go side generated by Ollama's own code in CI. It should also
promise the honest headline this spike found, which is more useful than a divergence rate:
**for 9 of 10 real-world templates Ollama's registry recognises nothing, and modern Ollama
therefore renders the GGUF's own Jinja through llama.cpp — so v0.2's X001/X002 already describe
what Ollama does**, and X003 is the narrow remainder. v0.3 should **not** promise an "Ollama
engine": there is nothing to embed, and claiming one would imply we model `RENDERER`-selected
renderers, Harmony, MLX and `PreferChatTemplate`, none of which are visible in a GGUF file. It
should not promise that a passing X003 means Ollama will render your model identically — only
`--runtime` against the user's own binary can say that, and that is exactly why `--runtime`
stays in scope.
