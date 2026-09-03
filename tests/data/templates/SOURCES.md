# Vendored real chat templates

The `.jinja`, `.upstream.jinja` and `.json` files in this directory are
**unmodified copies of published model-repo content**, included here as test
data under each repo's own licence (see the Licence column below). Nothing has
been reformatted, minified, corrected or truncated: byte-for-byte, each
`<org>__<repo>.jinja` is the `chat_template` string as it is published in that
repo's Hugging Face GGUF metadata, and each `<org>__<repo>.upstream.jinja` is
the base model's own `chat_template` as published in *its* repo. The `.json`
sidecars are the provenance records written by
`ggufdoctor survey --save-templates`.

They exist so that `tests/test_real_templates.py` can pin the complete S + X
finding set for each one **without touching the network**. Do not edit the
`.jinja` files: if a template looks wrong, that is the point — the finding set
in the test records exactly what ggufdoctor says about it, and why.

## How these were fetched

```
mkdir -p /tmp/gd-templates
.venv/bin/ggufdoctor survey --top 80 --per-org 1 --save-templates /tmp/gd-templates \
    --out /tmp/gd-templates-survey.json > /dev/null
```

Run 2026-09-03. That sampled the 80 most-downloaded GGUF repos (one per
publisher) and saved a template for each of the 60 that published one, plus 28
`.upstream.jinja` files where the base model's own template resolved. The
survey's own aggregate for that run: 80 sampled, 28 comparable, 5 divergent
(17.9%, 45.7% download-weighted). No repo's fetch errored — `examine_error`
does not appear in that run's `coverage_gaps` — so no template here comes from
a repo whose fetch failed or was rate-limited.

## How the ten were selected

The rule: walking the survey's records **in download order**, take the first
repo for each **distinct `architecture`** in its sidecar, skipping any sidecar
whose `gated` is truthy or whose `license` is null, until ten are chosen. That
consumed the first 26 records. Applied:

| # | Rank | Repo | Architecture | Outcome |
|---|------|------|--------------|---------|
| 1 | 1 | unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF | qwen3moe | **chosen** — first qwen3moe |
| 2 | 2 | ornith-ai/Ornith-1.0-9B-GGUF | qwen35 | **chosen** — first qwen35 |
| — | 3 | mixedbread-ai/mxbai-embed-large-v1 | — | not a candidate — non-chat architecture, no template saved |
| 3 | 4 | HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive | gemma4 | **chosen** — first gemma4 |
| — | 5 | lmstudio-community/Qwen3.8-27B-GGUF | qwen35 | skipped — architecture already taken (rank 2) |
| — | 6 | JonathanColetti/Qwen3.8-27B-Uncensored-GGUF | qwen35 | skipped — architecture already taken |
| — | 7 | DavidAU/Qwen3.6-27B-Fable-Fusion-711-…-GGUF | qwen35 | skipped — architecture already taken |
| 4 | 8 | antirez/deepseek-v4-gguf | deepseek4 | **chosen** — first deepseek4 |
| — | 9 | handy-computer/nemotron-3.5-asr-streaming-0.6b-gguf | — | not a candidate — non-chat architecture, no template saved |
| — | 10 | huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF | qwen35 | skipped — architecture already taken |
| 5 | 11 | mudler/Laguna-XS-2.1-APEX-GGUF | laguna | **chosen** — first laguna |
| — | 12 | audio-cpp/audio.cpp-gguf | — | not a candidate — non-chat architecture, no template saved |
| — | 13 | nvidia/parakeet-ctc-1.1b | — | not a candidate — non-chat architecture, no template saved |
| — | 14 | 0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF | qwen35 | skipped — architecture already taken |
| — | 15 | Abiray/MiniMax-H3-GGUF | — | not a candidate — no template published |
| — | 16 | cdiamond/Qwen3.8-27B-iMatrix-NVFP4-MTP-GGUF | — | not a candidate — non-chat architecture, no template saved |
| 6 | 17 | LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-V13-GGUF | qwen35moe | **chosen** — first qwen35moe |
| — | 18 | ggml-org/Qwen3.8-27B-GGUF | qwen35 | skipped — architecture already taken |
| — | 19 | datalab-to/surya-ocr-2-gguf | qwen35 | skipped — architecture already taken |
| 7 | 20 | rippertnt/HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF | llama | **chosen** — first llama |
| 8 | 21 | LiquidAI/LFM2.5-2.6B-GGUF | lfm2 | **chosen** — first lfm2 |
| — | 22 | Serveurperso/Qwen3-TTS-GGUF | — | not a candidate — non-chat architecture, no template saved |
| — | 23 | LocalAI-io/privacy-filter-nemotron-GGUF | — | not a candidate — no template published |
| — | 24 | OBLITERATUS/Qwen3.8-27B-OBLITERATED | qwen35 | skipped — architecture already taken |
| 9 | 25 | PaddlePaddle/PaddleOCR-VL-1.6-GGUF | paddleocr | **chosen** — first paddleocr |
| 10 | 26 | legraphista/glm-4-9b-chat-IMat-GGUF | chatglm | **chosen** — first chatglm |

Notes on the two filters in the rule:

* **`gated`** never excluded anything: every one of the 26 records in the
  window reports `gated: null` (the sidecar records Hugging Face's own value,
  and a repo that is not gated reports null or false here). Four repos further
  down the sample were excluded by the *survey* for having a gated upstream
  (`upstream_gated`), which is a different thing and not this rule.
  `rippertnt/HyperCLOVAX-…` (rank 20) is one of those: its own sidecar's
  `gated` is null, which is what the rule reads, so it is eligible.
* **`license: null`** never excluded anything either, because no record in the
  first 26 has a null licence. Records that *would* have been skipped had the
  window run longer, listed for transparency: poolside/Laguna-S-2.1-GGUF (34),
  michaelw9999/Qwen3.6-35B-A3B-NVFP4-MTP-GGUF (46),
  DevQuasar/amd.Instella-MoE-16B-A3B-Think-GGUF (52),
  joeygambino/MiniMax-H3-encoder-GGUF (56),
  NorwAI/NorwAI-Magistral-24B-reasoning (57), AtomicChat/Qwen3.8-27B-GGUF (64),
  MaziyarPanahi/Qwen3-4B-GGUF (67), SulphurAI/Sulphur-2-base (78). Only one of
  those, DevQuasar/…Instella-MoE… (52, `instella-moe`), carries an
  architecture not already represented; the rest are duplicates that the
  architecture rule would have skipped anyway. So the null-licence filter would
  have begun to matter only past the tenth pick.

The rule is mechanical and was applied without exception. In particular
`legraphista/glm-4-9b-chat-IMat-GGUF` (rank 26) was kept even though its
published `chat_template` turns out not to be a Jinja template at all — see
its row below — because the rule selects on architecture, not on whether the
template looks sane, and because "a repo published the wrong kind of string
here" is exactly the sort of real-world defect this corpus should carry.

## The ten

| Repo | Architecture | Revision | Licence | Fetched at | Upstream repo (`.upstream.jinja` vendored) |
|------|--------------|----------|---------|------------|--------------------------------------------|
| unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF | qwen3moe | `b17cb02dd882` | apache-2.0 | 2026-09-03T07:29:38Z | Qwen/Qwen3-Coder-30B-A3B-Instruct ✓ |
| ornith-ai/Ornith-1.0-9B-GGUF | qwen35 | `3296bc7a4048` | mit | 2026-09-03T07:29:38Z | — (no base model declared) |
| HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive | gemma4 | `45b6a334b4bc` | gemma | 2026-09-03T07:29:39Z | google/gemma-4-e4b-it (not vendored — upstream publishes no template) |
| antirez/deepseek-v4-gguf | deepseek4 | `f71f23d552d6` | mit | 2026-09-03T07:29:41Z | deepseek-ai/DeepSeek-V4-Flash (not vendored — upstream publishes no template) |
| mudler/Laguna-XS-2.1-APEX-GGUF | laguna | `e9e9293c1979` | openmdw-1.1 | 2026-09-03T07:29:43Z | poolside/Laguna-XS-2.1 ✓ |
| LuffyTheFox/Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-V13-GGUF | qwen35moe | `0095a3d1c1e1` | apache-2.0 | 2026-09-03T07:29:45Z | HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive (not vendored — upstream not found) |
| rippertnt/HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF | llama | `3d2edd543d75` | other | 2026-09-03T07:29:46Z | naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B (not vendored — upstream gated) |
| LiquidAI/LFM2.5-2.6B-GGUF | lfm2 | `84022ce711b2` | other | 2026-09-03T07:29:47Z | LiquidAI/LFM2.5-2.6B (not vendored — upstream publishes no template) |
| PaddlePaddle/PaddleOCR-VL-1.6-GGUF | paddleocr | `511b09642bb3` | apache-2.0 | 2026-09-03T07:29:49Z | — (no base model declared) |
| legraphista/glm-4-9b-chat-IMat-GGUF | chatglm | `0c1dbb84faf5` | other | 2026-09-03T07:29:49Z | THUDM/glm-4-9b-chat ✓ |

**On the Licence column.** These values are the Hugging Face `license` card field
verbatim, and three of them — `other` (three repos) and `gemma` (one) — do not
name a licence: they are pointers to a licence file or a licence agreement in the
repo, which nobody has read here. Anyone redistributing these files beyond
ggufdoctor's own test data must open each such repo's actual licence text first
and confirm it permits that; the field alone settles nothing.

**On the Revision column.** The original fetch recorded `"revision": null`
for all sixty repos: `survey --save-templates` reads it from the Hub
`model_info` response's `sha`, and `HfClient.model_info` was not asking for
that field — the Hub returns only the fields named in `expand[]` and silently
omits the rest. Ruling R8 fixed that (`&expand[]=sha`), and the survey was
re-run on 2026-09-03 against `/tmp/gd-templates-2`. **All ten of these
templates re-fetched byte-identical to the vendored copies**, so each sidecar's
`revision` was filled in from that second run and nothing else in it changed;
the template text was not touched. Had any template's bytes moved, its
`revision` would have stayed null and be listed here as such — none did, so
there is nothing to list. Every entry above is now pinned by commit as well as
by content and `fetched_at`.

Three `.upstream.jinja` files are present (the ✓ rows). Of those,
`mudler__Laguna-XS-2.1-APEX-GGUF.upstream.jinja` is byte-identical to the
GGUF-side template beside it (the survey classified that repo `identical`); the
unsloth and legraphista pairs genuinely differ. Both copies are kept as fetched
— the redundant one costs nothing and is what a later conformance task will
want to iterate over uniformly. The other seven repos
either declare no base model or have an upstream the survey could not read —
gated, missing, or publishing no template of its own — which is recorded per
repo above and in each sidecar's `upstream_saved: false`.

## One entry worth calling out

`legraphista__glm-4-9b-chat-IMat-GGUF.jinja` is eight bytes long and its entire
content is the literal string `ChatGLM4` — llama.cpp's legacy *named* built-in
template, published in the GGUF field where a Jinja template belongs. It is
kept verbatim. The real GLM-4 Jinja template is vendored beside it as
`legraphista__glm-4-9b-chat-IMat-GGUF.upstream.jinja` (from THUDM/glm-4-9b-chat)
for comparison. `tests/test_real_templates.py` pins what ggufdoctor says about
it: it "renders" the constant `ChatGLM4` for every fixture, so S007 fires at
WARN (`add_generation_prompt` cannot change a constant, and nothing in the
output opens an assistant turn).

Its worse property — that a constant prompt can never emit an EOS token, so a
turn would never terminate — is what S005 exists to catch, and S005 is
*unevaluated* on this corpus rather than firing. That is not the check being
wrong: HF's `gguf` metadata carries `bos_token`/`eos_token` strings but no
vocabulary, so the tests build the model with no vocab at all and S004/S005/S006
correctly record themselves as not evaluated (ruling R6 — an earlier revision
synthesised a two-token vocab from those strings and got false S004 ERRORs on
six of these ten working models). Establishing the S005 fact needs a real GGUF
file, which is outside what this metadata-only corpus can offer.
