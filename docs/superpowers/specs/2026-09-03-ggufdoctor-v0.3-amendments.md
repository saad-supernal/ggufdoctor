# ggufdoctor v0.3 — spec amendments (2026-09-03)

Amends `2026-08-31-ggufdoctor-design.md` (as already amended for v0.2). Where they disagree,
this document wins for v0.3. Evidence: `docs/research/2026-09-03-ollama-spike.md`, Ollama
pinned at commit `b79067b0db7417f20108363bc22adb97f35c966a` (2026-09-02).

## A. There is no Ollama engine to embed

The original spec (§1, §3, §9, §12) assumed Ollama converts a GGUF's Jinja template to a Go
template and that the conversion is lossy. It does not. Ollama's `template.Named` matches the
Jinja source against 37 hard-coded strings by unnormalised Levenshtein distance (cutoff `< 100`)
and, on a hit, substitutes one of 19 curated Go `text/template` files; on a miss — the common
case — the GGUF's own Jinja is rendered by llama-server's engine, which v0.2 already embeds.
Hand-written renderers in `model/renderers/` are selected only by a Modelfile `RENDERER`
directive and are not derivable from a GGUF file.

Consequences, replacing the corresponding spec text:

- §3 `engines`: the implementations are `jinja2`, `llama.cpp` and `external` (`--runtime`).
  There is no `ollama` engine. Delete "Ollama Go conversion (WASM)".
- §9: delete "Ollama Go conversion: vendored/ported and compiled to WASM". Add: "Ollama's
  registry substitution is reproduced by data, not by an engine: the pinned `index.json` and
  `.gotmpl` sources are vendored, the selection is computed in Python with an algorithm asserted
  equal to `template.Named` in CI, and the Go renders are goldens produced by Ollama's own
  `template` package in CI at the pinned commit."
- §11 risks: the row "Ollama's conversion is not a library and can drift" becomes "Ollama's
  registry is data that can drift silently; mitigation: a CI job re-derives the selector's
  agreement and the goldens from real Go at the pinned commit and fails on any difference; every
  report prints the pinned Ollama commit."
- §12: "v0.3 — Ollama engine and X003" becomes "v0.3 — Ollama registry check (X003, O001) and
  `--runtime`".

## B. X003 re-posed, and a coverage family for Ollama facts

| id | check | severity |
|---|---|---|
| X003 | Ollama's template registry recognises this template (distance `< 100`) and the curated Go template it substitutes renders differently from the GGUF's own Jinja on a fixture | error |
| O001 | Ollama's registry recognises this template — informational statement of the substitution: template name, distance, and whether the curated template ignores `tools` | info |

Rules binding X003 and O001:

- **Selection** is `ollama.select(template_source) -> Selection(name, distance, confident)`;
  `confident` is `distance < 60`; distances in `[60, 100)` are reported as low-confidence in
  the message. The selector's agreement with real `template.Named` is asserted over the
  vendored templates in the Go conformance job (§E).
- **Comparison** is the GGUF's Jinja render (via `Jinja2Engine`, real tokens injected as for
  R001/X001) against the **golden** render of the selected Go template for that fixture. Goldens
  are produced by Ollama's own `template.Parse`/`Execute` including its message pipeline
  (`collate`, `convertMessagesForTemplate`), never by a reimplementation.
- **Fixtures excluded by construction**, with the reason stated in evidence and never counted
  as divergence: `no_generation_prompt` (Ollama has no `add_generation_prompt`; it always
  renders for generation) and any fixture whose messages Ollama's `api.Message` cannot
  represent (`typed_content`: `Content` is a `string`). These appear as
  `evidence["not_comparable"] = {fixture: reason}` on O001.
- **Tools ignored is coverage, not divergence.** When the selected Go template does not
  reference `.Tools`, a difference on a tool fixture that consists only of the tools block being
  absent is reported through O001's `ignores_tools: true`, not as X003. Any other difference on
  a tool fixture is X003.
- **Both-fail is not a finding**; one side failing is X003 with the direction named, mirroring
  X002's wording.
- **Unrecognised is the headline.** When the registry recognises nothing, the coverage line
  says `Ollama: template not in the registry — Ollama renders it with llama.cpp's engine
  (see X001/X002)`. That is the common case and the honest, useful statement.
- **Custom fixtures**: with `--fixtures`, no goldens exist; X003 and O001 are recorded in
  `checks_not_evaluated` with the reason `no Ollama goldens for a custom corpus` and the
  headline is partial.
- **Findings are conditional and versioned.** Every X003/O001 message ends with
  `(Ollama <short commit>, default 'ollama create'; RENDERER/PARSER, OLLAMA_GO_TEMPLATE=0 and
  PreferChatTemplate divert to the Jinja path)`; evidence carries `ollama_commit`.

## C. Vendored Ollama data

`src/ggufdoctor/ollama_data/`: `index.json` (the 37 entries, verbatim), the 20 `.gotmpl`
sources, `goldens.json` (20 templates × the fixture corpus, keyed by template name and
fixture name, with `CORPUS_VERSION` and the Ollama commit recorded), `OLLAMA_PIN` (commit,
release tag `v0.33.2`, fetched date) and `LICENSE-ollama` (MIT). The data ships in the wheel;
the `build` CI job asserts its presence. Size budget: under 600 KB.

## D. CLI and report

- `--runtime <path-to-ollama>` (spec §6 mode B): shells out to the user's real `ollama` for
  ground truth — creates a temporary model from the GGUF (`ollama create` from a Modelfile that
  points at the file), renders each fixture with `/api/chat` `_debug_render_only: true`, and
  reports differences against the bundled prediction as `RT001` (INFO when identical, WARN when
  the real Ollama picked a different path than predicted). Opt-in, network-free, never run by
  default or in tests; documented as the only way to see `PreferChatTemplate`, `RENDERER` and
  `OLLAMA_GO_TEMPLATE` effects. v0.3 ships `--runtime` for Ollama only; llama.cpp already has
  its conformance suite.
- Human report: engine line unchanged; a new `ollama:` coverage line (recognised → name and
  distance; unrecognised → the headline sentence; not evaluated → the reason). JSON: additive
  `coverage.ollama = {pinned_commit, recognised, template, distance, confident}` and finding
  ids X003/O001/RT001. `schema_version` stays `"1"`.
- `--engines` is unchanged (there is no Ollama engine to select).

## E. Testing

- **Selector conformance (Go, CI):** a `go test` in `engine/ollama/` (Go toolchain in CI only)
  runs Ollama's real `template.Named` over the vendored templates plus a set of near-threshold
  synthetic variants and asserts the Python selector's `(name, distance)` matches exactly; the
  same job regenerates `goldens.json` from Ollama's `template` package at the pinned commit and
  fails if it differs from the committed file. Marker `ollama_conformance`, deselected by
  default; nothing in the default suite needs Go.
- **Unit tests** for the selector (exact on the ten vendored templates using their recorded
  distances; the length prefilter; the cutoff; low-confidence band), for X003/O001 with
  synthetic goldens, for the excluded fixtures, for the coverage lines and JSON.
- **Real-template tests** extend `EXPECTED` with the X003/O001 outcome for each of the ten
  templates (nine unrecognised; HyperCLOVAX → `chatml`, X003 on `tool_roundtrip`).
- **Staleness guard (CI, weekly + on demand):** fetch `template/index.json` and the `.gotmpl`
  files from Ollama `main`; fail (open an issue) when they differ from the vendored copy.

## F. Versioning

ggufdoctor `0.3.0`. The Ollama pin bumps by hand: edit `OLLAMA_PIN`, re-vendor, regenerate
goldens with the Go job, re-run the selector conformance, update the version string. Every
report prints the pin.

## G. What v0.3 does not promise

No Ollama engine. No prediction of `RENDERER`/`PARSER`-selected renderers, Harmony or MLX
paths. No claim that a clean X003 means Ollama renders the model identically — only
`--runtime` against the user's own binary says that. The README states each of these.
