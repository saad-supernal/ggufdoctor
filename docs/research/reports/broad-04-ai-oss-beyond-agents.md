# AI/ML Open Source Beyond Agents — Opportunity Scout Report

**Research date: 2026-08-31.** All GitHub star counts, push dates, issue counts and release dates fetched live via authenticated `gh api` on 2026-08-31 (02:00–03:30 UTC). All Hacker News data from hn.algolia.com live, sorted both by date and by points. Hugging Face figures from the live HF API. **No number in this report is stated from memory.** Items I could not confirm are marked UNVERIFIED.

Scope deliberately excludes agent frameworks, agent security, and coding-agent tooling.

---

## 0. Executive summary

Three areas carry strong, dated, primary evidence of unsolved pain, and all three share one shape: **an incumbent cannot ship the fix, because the fix consists of grading the incumbent.**

1. **Silent correctness failure in local inference** — broken chat templates and wrong sampling defaults, where the *model* gets blamed for a *packaging* bug. 54 chat-template and 80 jinja issues opened in llama.cpp in 2026 alone; a 509-point HN thread; an ecosystem-wide Gemma 4 re-upload event in May 2026. Every existing tool has **0–3 stars**.
2. **GPU memory-budget accounting in serving engines is structurally broken** — `--gpu-memory-utilization` and `--mem-fraction-static` silently lie, because real allocations are invisible to the budgeter. Verified open bugs in both vLLM and SGLang. A community wrote a *markdown recipe book* to work around it and got 2,131 stars in four months.
3. **Hugging Face supply-chain risk has moved from weights to repo code, and the scanners have not followed** — a typosquat hit #1 trending with ~244K downloads via `loader.py`, not a pickle. The reference model-signing project has **243 stars and no release since 2025-10-10**.

Meanwhile **fine-tuning, experiment tracking, dataset dedup, watermarking, generic RAG and document parsing are consolidated, corporate-controlled, or show no demonstrated demand.** Details and explicit negative results in §1.

---

## 1. WHERE IS THE PAIN? — ranked by evidence strength

### TIER 1 — Strong, primary, dated evidence

#### 1.1 Chat templates / sampling defaults in local inference — **STRONGEST**

A silent-failure class: the model works, it just gets quietly dumber, and users blame the weights.

**Live GitHub issue volume (2026-08-31):**

| Query | Total |
|---|---|
| `repo:ggml-org/llama.cpp "chat template" in:title created:>2026-01-01` | **54** |
| `repo:ggml-org/llama.cpp jinja in:title created:>2026-01-01` | **80** |
| `repo:vllm-project/vllm template in:title state:open created:>2026-03-01` | **31** |
| `repo:ollama/ollama "chat template" in:title created:>2026-01-01` | **10** |

Representative open issues, all verified live:
- [llama.cpp #27129](https://github.com/ggml-org/llama.cpp/issues/27129) (2026-08-15) — "server **silently drops the tools array** when the chat template has no tool support (--jinja)"
- [llama.cpp #27134](https://github.com/ggml-org/llama.cpp/issues/27134) (2026-08-15) — "regression — assistant reply misfiled into reasoning_content (content empty)"
- [llama.cpp #27367](https://github.com/ggml-org/llama.cpp/issues/27367) (2026-08-19) — "HTTP 500 when a system message appears mid-conversation (strict chat templates, e.g. Qwen3.x)"
- [llama.cpp #26781](https://github.com/ggml-org/llama.cpp/issues/26781) (2026-08-09) — "enable_thinking forced true in jinja/caps.cpp capability probe **leaks into non-DeepSeek templates**"
- [ollama #18082](https://github.com/ollama/ollama/issues/18082) (2026-08-27) — "GLM chat template emits orphaned closing think tag — **reasoning leaks into message.content**"
- [vllm #53284](https://github.com/vllm-project/vllm/issues/53284) (2026-08-21) — "`--reasoning-parser qwen3` returns the whole answer as `reasoning` (content=null)"
- [vllm #53820](https://github.com/vllm-project/vllm/issues/53820) (2026-08-26) — "MiMo-V2.5 chat template is auto-detected as string, reordering multimodal content"

**HN, "Why your local LLM feels dumber than it is"** — 509 points, 207 comments, 2026-08-22 — [item?id=49402232](https://news.ycombinator.com/item?id=49402232). The highest-signal comment (`anotherCodder`) is effectively a product spec written by a user who has no tool:

> "most of the time when a local model feels dumb **its not the quant, its the chat template**. a lot of gguf mints just drop the template from the metadata and the runtime silently falls back to chatml. model still talks fine so nobody notices, it just gets noticeably dumber. got burned by this myself serving qwen, **now i grep the gguf for the template tokens before i blame anything else**. second place is sampling, people run whatever defaults their ui ships instead of what the vendor recommends and then compare that to benchmark numbers that were run greedy or with the official settings"

Same thread:
> "It took him two hours of passing errors to Claude for the endpoint to start working... **Claude messed up sampling parameters**, it was an absolute pain to watch" — `big-chungus4`

> "People who use Ollama generally don't always clearly understand what quantization they use... so people end up saying 'I tried running Qwen 3.8 27b locally and it was dumb' while Ollama would default to a Q4 version" — `embedding-shape`

**HN, "The local LLM ecosystem doesn't need Ollama"** — 648 points, 207 comments, 2026-04-16 — [item?id=47788385](https://news.ycombinator.com/item?id=47788385):

> "This creates a recurring pattern on r/LocalLLaMA: new model launches, people try it through Ollama, **it's broken or slow or has botched chat templates, and the model gets blamed instead of the runtime**."

> "**Jinja is not always losslessly convertible to the Go template syntax expected by Ollama.** This means that some models simply cannot work correctly with Ollama. Sometimes the effects of this incompatibility are **subtle and unpredictable**." — `derrikcurran`

> "I remember people complaining model X is 'dumb' simply because Ollama capped the context size to a ridiculously small number by default." — `kgeist`. Still live: Ollama "defaults to 4K if less than 24GB VRAM" (`petu`, citing https://docs.ollama.com/context-length).

**Ecosystem-wide incident, May 2026.** Every Gemma 4 GGUF shipped with a Jinja template producing malformed `<start_of_turn>` / `<end_of_turn>` markers. Bartowski *and* Unsloth re-uploaded all four official sizes. r/LocalLLaMA thread (u/jacek2023, 2026-05-04) reached ~395 upvotes / 115 comments in 24h. Sources: [openaitoolshub](https://www.openaitoolshub.org/en/blog/gemma-4-gguf-chat-template-fix), [aiproductivity.ai](https://aiproductivity.ai/news/gemma-4-gguf-chat-template-fix/). Prior instances on HF: [unsloth/Qwen3-30B-A3B-GGUF #2 "UPDATED FIXED!! Template problem?"](https://huggingface.co/unsloth/Qwen3-30B-A3B-GGUF/discussions/2), [#13 "The chat template is still broken"](https://huggingface.co/unsloth/Qwen3-30B-A3B-GGUF/discussions/13), [unsloth/gpt-oss-20b-GGUF #2](https://huggingface.co/unsloth/gpt-oss-20b-GGUF/discussions/2).

**Blast radius (live HF API):** `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` **12,760,676** downloads/30d; `unsloth/Qwen3.8-27B-GGUF` 8,839,153; `ornith-ai/Ornith-1.0-9B-GGUF` 4,402,172; `lmstudio-community/Qwen3.8-27B-GGUF` 2,275,982. The top of the GGUF distribution is dominated by **third-party re-quantizers** — precisely where template drift is introduced.

**Nobody has measured the failure rate.** A live search returned explicitly: *"the search results do not contain a specific survey with percentage breakdowns of how many models on HuggingFace have broken chat templates."* That headline number is unclaimed.

#### 1.2 GPU memory-budget accounting in serving engines — **VERY STRONG**

Not one bug — a recurring 2026 class where an allocation is invisible to the budgeter, so the engine's auto-sizing knob silently lies. All issues verified open on 2026-08-31:

- [SGLang #35201](https://github.com/sgl-project/sglang/issues/35201) (open, 2026-08-17, 0 comments) — "DeepSeek-V4 indexer's context-proportional logits allocation is unaccounted by mem_fraction_static." Per-layer fp32 logits are "**invisible to `mem_fraction_static`** — no part of the memory budgeter accounts for it — so any sufficiently long prefill deterministically OOMs mid-request, on every TP rank simultaneously."
- [vLLM #44740](https://github.com/vllm-project/vllm/issues/44740) (open, 2026-06-06, 4 comments) — "Negative CUDA graph memory estimation (-35 GiB) with MTP speculative decoding leads to severe [over-allocation]". The profiler "artificially inflate[s] the available KV cache pool." Workaround: drop `--gpu-memory-utilization` 0.8 → 0.55.
- [vLLM #44209](https://github.com/vllm-project/vllm/issues/44209) (open, 2026-06-01, 2 comments) — "Non-deterministic KV-cache reservation on hybrid GDN model (Qwen3.6) → CUDA-graph capture OOM." Non-determinism "**across byte-for-byte identical cold boots**"; capture OOM occurs *after* `/health` returns 200, giving "a **silent crash-loop of a container that already looked healthy**."
- [SGLang #35777](https://github.com/sgl-project/sglang/issues/35777) (open, 2026-08-21) — "Qwen3.8-27B NVFP4 on RTX 5090: cookbook mem-fraction OOMs at decode-graph capture (~5GB)". **The vendor's own recommended values cannot boot on the hardware.**
- SGLang: **40 issues/PRs** with `mem-fraction-static` in the title, including [#37130](https://github.com/sgl-project/sglang/pull/37130) (2026-08-30) "Remove silent x0.85 mem_fraction_static derate."

**Upgrade churn compounds it:** [vLLM #53241](https://github.com/vllm-project/vllm/issues/53241) (open, 2026-08-21) "performance degradation 0.26 vs 0.27 for Qwen3.5 122B on 4xrtx 3090"; #45938 throughput regression 0.19.1→0.21.0; #50718 (2026-08-02) "Significant TTFT degradation and poor QPS scaling with Rust frontend on vLLM 0.25.1."

**Demand proof:** [`noonghunna/club-3090`](https://github.com/noonghunna/club-3090) — **2,131 stars, created 2026-04-28, pushed 2026-08-27** (verified live). Its entire value is hand-curated working configs, measured VRAM budgets and TPS. A community resorted to a *markdown recipe book* because no tool answers "what config actually boots."

#### 1.3 Hugging Face repo-level supply chain — **STRONG, incident-driven**

The attack surface moved from serialized weights to repo Python, and the scanners did not follow.

- **[Open-OSS/privacy-filter, 2026-05-07](https://www.hiddenlayer.com/research/malware-found-in-trending-hugging-face-repository-open-oss-privacy-filter)** (verified by direct fetch): a typosquat of OpenAI's Privacy Filter "reached the **#1 trending position on Hugging Face with approximately 244K downloads and 667 likes in under 18 hours**." Delivery: "The **loader.py** script first runs decoy code (a **DummyModel** class, with fake training output, and a synthetic dataset) to look like a real loader." Payload was PowerShell fetched from jsonkeeper.com → Rust infostealer. **The malware was never in the weights.** (That weights/pickle scanners would therefore not have caught it is my inference from the delivery mechanism, not a claim the vendor makes — the writeup does not address detection.)
- **Aug 2026:** three high-severity CVEs in HF `diffusers` bypass `trust_remote_code` entirely — [thehackernews](https://thehackernews.com/2026/08/hugging-face-diffusers-flaws-could-let.html). Maintainer unease is on record and dated: [diffusers discussion #12033](https://github.com/huggingface/diffusers/discussions/12033) (2025-07-31), where maintainers questioned whether offering the capability remains justified; the proposed fix was an opt-out env var.
- **Pickle scanners are known-weak:** four 2025 CVEs in picklescan (CVE-2025-1716/1889/1944/1945). A July 2026 "ShadowPickle" preprint reportedly reaches ~63% evasion across ten scanners — **UNVERIFIED** (secondary reporting only; I did not read the preprint).

**The defenders are stalled (verified live):**

| Project | Stars | Last push | Latest release |
|---|---|---|---|
| `protectai/modelscan` | 766 | **2026-02-18** | **v0.8.8 @ 2026-02-18** (~6 months stale) |
| `sigstore/model-transparency` | 243 | 2026-08-24 | **v1.1.1 @ 2025-10-10** (~10 months, no release) |
| `mmaitre314/picklescan` | 422 | 2026-08-30 | active, but blacklist-based by design |

modelscan's open issues include four identical un-triaged `[BUG] Security Vulnerability` reports with **0 comments each** (#364, #367, #368, #369).

### TIER 2 — Real but partly served

#### 1.4 Quantization/backend divergence is unmeasurable by practitioners

The source article behind the 509-point thread ([Level1Techs, user `thr3e`, Aug 2026](https://forum.level1techs.com/t/why-your-local-llm-feels-dumber-than-it-is/253917)) measured, on a 27,525-token tool-calling prompt:
- **NVIDIA NVFP4 showed ~50% token disagreement by 88k context** vs BF16.
- "**Both the NVFP4 and AWQ W4A16 failed to properly close their tool calls.**"
- INT8 W8A16 beat first-party FP8 and NVIDIA's FP4 release.
- Int8 KV-cache "eventually managed to recover"; **Int4 KV-cache "did not."**
- FlashAttention 2 "uses a structure where rounding does not commute with rescaling," causing divergence across H200 / B200 / SM120 **despite identical source**.

HN corroboration (`throwdbaaway`): "NVFP4 and AWQ W4A16 are generally regarded as low quality quants... perhaps the lesson here is **'don't use vllm at home'**?" Practitioners cope with folklore instead of measurement (`walrus01`): "Don't quantize your KV cache... Don't run quantizations worse than the best available Q8."

Literature agrees there is no framework: GGUF "lacks official documentation on the implementations of quantization strategies beyond inspecting specific pull requests"; new quantizers arrive "via GitHub issues and pull requests rather than formal algorithmic descriptions, resulting in practical guidance being dominated by anecdotal advice and perplexity measurements with **no unified experimental framework**" (arXiv 2601.14277).

#### 1.5 "Will it fit / how fast on MY hardware?" (consumer/local)

- HN 2026-08-28, 137 pts / 99 c: "Run Qwen3.8 27B locally: real numbers from my Mac Studio" — [49479951](https://news.ycombinator.com/item?id=49479951). People hand-publish hardware numbers because no tool produces them.
- Every VRAM calculator is tiny: `hlpun/Train-in-Silence` 101★, `jaeseok614/llm-gpu-checker-ko` 41★, `mshojaei77/vram-calculator` 24★, `changh95/vram-calculator` 10★, `pochenai/llm-inference-calculator` 9★, `Leon-Sander/KV-Cache-Calculator` 0★. Live search `will model fit gpu memory estimate llm` → **zero repos**.
- **Honest counter-evidence:** "Show HN: Quant Picker – which GGUF file fits your model and machine" (2026-06-13) got **20 points, 0 comments** — [48516202](https://news.ycombinator.com/item?id=48516202). The need is real; the web-calculator framing failed.

#### 1.6 Eval reproducibility — real but *unattended*

- [lighteval #1363](https://github.com/huggingface/lighteval/issues/1363) (2026-08-29): sample cache "doc.id collides across evaluation splits… **silently serving one split's answers for another split's questions**." [#1364](https://github.com/huggingface/lighteval/issues/1364): "weights moving under the same revision name **silently reuse the old responses**." [#1329](https://github.com/huggingface/lighteval/issues/1329): a scorer "ignored word order in every release up to 0.3.252."
- [lm-eval #3958](https://github.com/EleutherAI/lm-evaluation-harness/issues/3958) (2026-07-28, open) "Failed to reproduce Qwen3.5-4B on ceval-valid"; #3383 same for Qwen3-0.6B/GSM8K.
- [lm-eval #3967](https://github.com/EleutherAI/lm-evaluation-harness/issues/3967) (2026-07-30) proposes "opt-in pre-registration for eval claims (lock threshold + task-config hash before the run)" — and received **0 comments**.
- ["LLM Olympiad: Why Model Evaluation Needs a Sealed Exam"](https://arxiv.org/abs/2603.23292) (2026-03-24): scores reflect "benchmark-chasing, hidden evaluation choices, or accidental exposure to test content."

**Caveat that keeps this in Tier 2:** nearly every eval issue above has **0–1 comments**. Diffuse, unattended pain = low competition *and* low proven willingness to adopt a fix.

#### 1.7 GGUF format gaps — an explicit, on-the-record invitation

HN "What's in a GGUF, besides the weights – and what's still missing?" 195 pts / 58 c, 2026-05-14 — [48138332](https://news.ycombinator.com/item?id=48138332). GGUF's designer (`Philpax`) participates:
> "I intentionally left space for the computation graph to be included in the GGUF spec in the hopes that this would be picked up by someone... **it would need a cheerleader very familiar with the current state of the GGML IR.**"
> "I regret that the projection models ended up separate... Hoping that someone will shepherd the cause of merging the two; I think I'm too out of the loop to do it this time around."

`theapadayo`: "the biggest thing still missing is an actual way to define the model architecture outside of being hard coded into the current build... **Having proper, vendor validated support for day 1 is what is the difference between people thinking a model is amazing vs horrible.**"

Genuine and invited — but it is *standards work* requiring ggml-org buy-in. Low absorption resistance (they own the spec), high difficulty.

### TIER 3 — NEGATIVE RESULTS (searched hard, found little or nothing)

These are honest negatives. Negative results were an explicit deliverable, and several of these areas look attractive from the outside.

| Area | Evidence actually found | Verdict |
|---|---|---|
| **Dataset deduplication** | HN, stories since 2025-01 with >15 pts: **exactly one** — "Show HN: SemHash" (19 pts, 6 c, 2025-01-12). `MinishLab/semhash` 963★ with **1 open issue** (a `py.typed` request). `ChenghaoMou/text-dedup` 764★ with **0 open issues**. `google-research/deduplicate-text-datasets` 1,270★ **archived** since 2024-07-30. These are *finished tools nobody is straining against*. | **DUD** |
| **Benchmark decontamination** | `decontamination in:title state:open created:>2025-09-01` → 61 results, **nearly all agent-generated bot spam in single-user repos** (one account accounts for 5 of the top 6). No practitioner conversation. | **DUD** (see honorable mention in §6) |
| **Dataset provenance / EU AI Act compliance tooling** | Art. 53(1)(d) training-data summaries mandatory since Aug 2025; AI Office enforcement powers began **2026-08-02**. A Trinity College Dublin/Mozilla study (ACM FAccT 2026) found only **4 of 7** major providers filled the template. **As of 2026-08-07, zero fines or investigations opened.** Best HN hit: "Crovia Spider — Forensic crawler exposing compliance gaps in LAION-5B" (2025-12-06) — **2 points, 0 comments**. | **DUD** — regulation on paper, no enforcement pressure, no tool-buying |
| **Experiment tracking / prompt+model versioning** | `repo:mlflow/mlflow is:issue reproducib created:>2026-01-01` → **TOTAL 0**. HN "mlflow" 2026 hits are essentially all *"Who wants to be hired" résumé keyword lists*. Incumbents large, funded, committing daily: langfuse 33,944★, mlflow 27,740★, opik 21,700★, dvc 15,849★, wandb 11,244★, aim 6,245★, zenml 5,569★. Consolidating further: `iterative/dvc` now redirects to `treeverse/dvc` — [lakeFS acquired DVC 2025-11-18](https://lakefs.io/blog/celebration-shared-vision-lakefs-dvc/). | **SATURATED. AVOID.** |
| **Fine-tuning tooling** | Repos `fine-tuning training created:>2025-06-01 stars:>1200` → **exactly one, and it is NVIDIA's** (`NVIDIA-NeMo/Nemotron` 2,002★). Incumbents: unsloth 75,278★, LLaMA-Factory 74,450★, verl 23,206★, peft 21,609★, trl 19,181★, axolotl 12,427★. **No new entrant has broken in for 14 months.** | **CONSOLIDATED. AVOID.** |
| **New model-eval infrastructure** | Repos `evaluation benchmark llm created:>2025-06-01 stars:>1000` → only novelty *benchmarks* (a Chinese fortune-telling benchmark; an agent-coding benchmark). **Zero new eval infrastructure above 1,000★ in 14 months.** | **MOSTLY DUD** (one narrow exception, §6 #7) |
| **Model signing / AIBOM / watermarking** | `sigstore/model-transparency` **243★, no release since 2025-10-10**. `manifest-cyber/aibom` 46★. `facebookresearch/videoseal` 763★. AIBOM adoption "remains limited... not widely adopted due to limited awareness and lack of mature, easy-to-use tools." No practitioner pain threads found. | **DUD** — note this is the *opposite* conclusion from §1.3; see the distinction below |
| **Cost-per-token measurement for self-hosted serving** | `org:vllm-project "cost per token"` → 1 irrelevant hit. | **DUD** |
| **Generic RAG frameworks / chunkers** | See §1.8. | **AVOID — receding market** |

**Important distinction inside "provenance":** *weights signing, watermarking and AIBOM generation are duds* — compliance-driven, no demonstrated developer demand. *Repo-level executable-surface auditing is not* — it has a dated, high-profile incident and stalled defenders (§1.3). Do not collapse these into one area; the first is theory, the second is an active exploit path.

#### 1.8 Special negative: RAG is deconsolidating

"Ask HN: How are you doing RAG locally?" — 413 pts, 156 comments, 2026-01-14 — [46616529](https://news.ycombinator.com/item?id=46616529). The dominant answers *reject vector infrastructure*:

> "**Don't use a vector database for code, embeddings are slow and bad for code.** Code likes bm25+trigram." — `CuriouslyC`
> "running gpt-oss 20B in a while loop with access to ripgrep works pretty dang well." — `postalcoder`
> "I'm using SQLite FTS5... This took about **one hour** to set up and works very well." — `esperent`
> "**BM25/tf-idf and N grams have always been extremely difficult to beat baselines**... This is why embeddings still have not led to a 'ChatGPT' moment in information retrieval." — `Der_Einzige`

Corroborated: "RAG Is Simpler Than You Think" (511 pts, 216 c, 2026-08-26); "We replaced RAG with a virtual filesystem for our AI documentation assistant" (411 pts, 2026-04-02).

**Building a chunker or RAG framework in 2026 is building into a receding tide.**

---

## 2. CONSOLIDATED VS FRAGMENTED — live map

All figures 2026-08-31.

### Local runtimes — consolidated at the core, empty in the quality layer

| Repo | Stars | Last push | Open issues | Read |
|---|---|---|---|---|
| ollama/ollama | 179,799 | 2026-08-29 | 3,852 | Corporate, fast, **reputationally weak** (two 648-pt HN pile-ons) |
| ggml-org/llama.cpp | 126,411 | 2026-08-30 | 2,309 | The substrate. Build *around*, never against |
| janhq/jan | 44,271 | 2026-08-29 | 499 | Desktop layer |
| ml-explore/mlx | 28,228 | 2026-08-30 | 124 | **Apple, fast — do not compete** |
| mozilla-ai/llamafile | 25,796 | 2026-08-26 | 212 | Slowing |
| kvcache-ai/ktransformers | 19,331 | 2026-08-28 | 508 | Active |
| LostRuins/koboldcpp | 11,584 | 2026-08-30 | 507 | Healthy niche |
| ikawrakow/ik_llama.cpp | 3,153 | 2026-08-28 | 101 | Quality-quant fork, respected |
| containers/ramalama | 3,026 | 2026-08-31 | 113 | Red Hat |
| nomic-ai/gpt4all | 77,389 | **2025-05-27** | 772 | **DEAD** — 15 months stale, 77k stars stranded |

### Apple Silicon serving — fragmented gold rush, crowded, closing

| Repo | Stars | Created | Last push |
|---|---|---|---|
| jundot/omlx | 21,063 | 2026-02-13 | 2026-08-29 |
| drumih/turbo-fieldfare | 6,511 | 2026-07-17 | 2026-08-29 |
| raullenchai/Rapid-MLX | 3,599 | 2026-02-25 | 2026-08-31 |
| waybarrios/vllm-mlx | 1,554 | 2025-12-06 | 2026-08-30 |
| ARahim3/mlx-tune | 1,391 | 2026-01-03 | 2026-06-23 |
| ddalcu/mlx-serve | 968 | 2026-02-17 | 2026-08-31 |

Six credible entrants in nine months, all alive. Rewarding but crowded, and Apple's MLX sits upstream of all of it.

### Datacenter serving — corporate-controlled, fast-moving. **AVOID the engines.**

| Repo | Stars | Last push | Open issues | Controlled by |
|---|---|---|---|---|
| vllm-project/vllm | 90,525 | 2026-08-31 | **7,212** | PyTorch Foundation / Red Hat / heavy corp |
| BerriAI/litellm | 57,620 | 2026-08-31 | **4,893** | Commercial |
| sgl-project/sglang | 32,941 | 2026-08-31 | **4,973** | LMSYS / corp |
| NVIDIA/TensorRT-LLM | 14,507 | 2026-08-31 | 1,406 | **NVIDIA** |
| InternLM/lmdeploy | 8,035 | 2026-08-28 | 607 | Shanghai AI Lab |
| ai-dynamo/dynamo | 7,922 | 2026-08-31 | 1,343 | **NVIDIA** |
| vllm-project/aibrix | 5,046 | 2026-08-30 | — | ByteDance |
| llm-d/llm-d | 4,338 | 2026-08-30 | 236 | Red Hat/IBM/Google |
| vllm-project/production-stack | 2,538 | 2026-08-29 | 204 | vLLM org |
| huggingface/text-generation-inference | 10,890 | **2026-03-21** | 324 | **ARCHIVED — HF abandoned it** |

Four corporate projects fighting over the orchestration layer. Open-issue counts of 7,212 and 4,973 are not opportunity — they are a firehose. **But the operator-tooling layer *outside* the engine is genuinely empty.**

### Fine-tuning — consolidated. AVOID.
unsloth 75,278 · LlamaFactory 74,450 · verl 23,206 · peft 21,609 · trl 19,181 · axolotl 12,427 · OpenRLHF 9,960 · torchtune 5,801 · mergekit 7,324 (**slowing, push 2026-06-17**) · nanotron 2,805 (**slowing, push 2026-05-26**).

### Vector/retrieval — consolidated AND receding
ragflow 89,677 · llama_index 51,925 · milvus 45,885 · faiss 40,825 · qdrant 34,275 · chroma 29,183 · haystack 26,366 · pgvector 22,828 · weaviate 16,760 · lancedb 11,314 · vespa 7,071. Plus `RyanCodrai/turbovec` **16,554★ created 2026-03-26** (1,434 forks). Soft spots: `vibrantlabsai/ragas` 15,547★ **stale since 2026-02-24**; `AnswerDotAI/rerankers` 1,631★ stale since 2025-12-20.

### Document parsing — consolidated by Microsoft and IBM. AVOID.
markitdown 177,212 · ragflow 89,677 · MinerU 78,819 · docling 65,767 · marker 39,405 · unstructured 15,363.

### Data tooling — fragmented *and quiet* (the bad kind)
huggingface/datasets 21,880 · data-juicer 6,951 · Daft 5,733 · argilla 5,089 · distilabel 3,382 · datatrove 3,312 · NVIDIA-NeMo/Curator 1,740 · streaming 1,554 · dolma 1,538 · dclm 1,468 (**stale, 2025-09-09**) · semhash 963 · text-dedup 764. Every live fast-mover is corporate (HF ×3, NVIDIA, Alibaba, Eventual).

---

## 3. THE "BORING INFRASTRUCTURE" ANGLE — highest priority

The thesis is empirically confirmed here. Live proof points:

- **`mostlygeek/llama-swap`** — 5,526★. One annoyance ("swap models behind one OpenAI-compatible port"), solved sharply, by an individual.
- **`noonghunna/club-3090`** — 2,131★ in four months. It is *a markdown file of working configs*. Not even code.
- **`drumih/turbo-fieldfare`** — 6,511★ in **six weeks**: "Gemma 4 26B-A4B inference in ~2 GB of RAM." HN 919 points.
- **`FareedKhan-dev/kimi-k3-in-c`** — 6,836★ in **four weeks**: "2.78-trillion-parameter Kimi K3 on a single CPU in 8.24 GB of RAM."
- **`raullenchai/Rapid-MLX`** — 3,599★, README headline: "**4.2x faster than Ollama, 0.08s cached TTFT.**"
- **`RightNow-AI/picolm`** — 1,923★: "Run a 1B LLM on a $10 board with 256MB RAM." (Cautionary: **last push 2026-02-22**, three days after launch. The number bought attention, not a project.)

**Pattern: one narrow scope + one striking, verifiable number + reproducible on the reader's own hardware. Every breakout has a number in its one-line description. None is a framework.**

### Candidate B1 — `ggufdoctor`: cross-runtime model-artifact linter
One CLI that opens any GGUF (or safetensors repo) and reports everything that will silently degrade output: missing/mangled chat template, template disagreeing with upstream `tokenizer_config.json`, absent `generation_config` sampling params, wrong BOS/EOS/pad tokens, missing tool-call support, quant type vs reported quality.

**Competitors, all live-checked:** `CHKDSKLabs/l-bom` **3★**, `mitanuriel/gguf_analyzer` **2★**, `rbehzadan/gguf-info` **0★**, `ycros/model-templater` **0★**, `pxlcrtiv/hf-hub-lint` **0★**. Searches `gguf chat template validate` and `chat template test harness llm` → **zero repos each**. Greenfield.

**README number (unclaimed):** *"I scanned the 1,000 most-downloaded GGUF repos on Hugging Face. N% ship a chat template that does not match upstream. M% ship no sampling defaults at all."* Data is free via the HF API; the top repos pull 12.7M downloads/month.

### Candidate B2 — `preflight`: GPU memory-budget reconciler
Predict the *actual* post-boot KV-cache pool for `(model, GPU, flags)`, then **diff the prediction against what the engine really allocated**, naming the unaccounted consumer (CUDA-graph capture reserve, indexer logits, spec-decode drafter). Not a VRAM calculator — a *reconciler against engine reality*, and cross-engine (vLLM + SGLang).

**Competitors:** 92 repos found, **none above 101★**, all static estimators. `gpu memory profiler vllm oom debug` → **TOTAL 0**.

**README number:** *"On 12 model/GPU pairs, `--gpu-memory-utilization` overshot the true safe ceiling by a median of N GB; 4 of 12 crash-looped after passing /health."* Directly reproducible from vLLM #44209/#44740 and SGLang #35777.

### Candidate B3 — `hf-audit`: repo-level executable-surface scanner
Scan a Hugging Face *repo*, not its weights. Flag every executable surface: `loader.py` / arbitrary top-level `.py`, `auto_map` in `config.json`, custom `modeling_*.py`, network calls at import time, `trust_remote_code` requirement — plus hygiene signals (age vs download ratio, model card copied verbatim, typosquat distance to a known-org name).

**Competitors:** search `huggingface model repository scanner trust_remote_code security` → **zero results**. modelscan (766★, stale) and picklescan (422★) scan serialized files only.

**README number:** *"Scanned the top 1,000 most-downloaded HF models — N require `trust_remote_code`, N ship Python that makes an outbound network call at import time, N are typosquat-distance ≤2 from a major lab org."* In the direct slipstream of a #1-trending, 244K-download compromise four months old.

### Candidate B4 — `quantdiff`: token-level divergence measurement
Two artifacts (or one model, two backends) + a prompt set → token-level divergence, first-divergence position, tool-call-closure failure rate, greedy-token disagreement. Packages the methodology that reached 509 HN points and was never turned into a tool.

**Competitors:** `llm quantization compare perplexity cli` → **zero repos**; `gguf quantization quality benchmark kld` → **zero repos**. AngelSlim (1,584★) compresses, does not compare.

### Candidate B5 — `samplerc`: vendor-correct sampling defaults registry
Curated, versioned registry of each model's officially recommended sampling params, emitted in llama.cpp / vLLM / Ollama / LM Studio / OpenAI-API form. Search `sampling parameters llm defaults` → **zero repos**. Very low difficulty, **low durability alone** — ship as a `ggufdoctor` module, not standalone.

### Anti-candidates — do not build
- **Thin orchestration over llama.cpp.** Precedent: llama.cpp shipped native **router mode in December 2025** (`--models-dir`/`--models-max`, LRU eviction), directly absorbing `llama-swap`'s core function ([glukhov.org](https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/), [runaihome](https://runaihome.com/blog/llama-server-router-mode-multi-model-setup-2026/)).
- **Coarse serving-config recommenders.** vLLM merged [`--performance-mode {balanced,interactivity,throughput}`](https://github.com/vllm-project/vllm/pull/34936) in Feb 2026 and ships `benchmarks/auto_tune`. Already absorbed. (Note the presets are themselves buggy — [#37587](https://github.com/vllm-project/vllm/issues/37587), `--performance-mode throughput` → `cudaErrorIllegalAddress` — which is precisely why the *adversarial reconciler* survives where the *recommender* does not.)

---

## 4. TRACTION EVIDENCE — 2025–2026 non-agent AI OSS

| Repo | Stars | Created | Last push | Driver |
|---|---|---|---|---|
| jundot/omlx | 21,063 | 2026-02-13 | 2026-08-29 | Apple Silicon serving, continuous batching + SSD caching |
| RyanCodrai/turbovec | 16,554 (1,434 forks) | 2026-03-26 | 2026-08-21 | Rust impl of Google's TurboQuant vector index |
| GeeeekExplorer/nano-vllm | 15,236 | 2025-06-09 | 2026-04-26 | Pedagogical minimal vLLM |
| RunanywhereAI/runanywhere-sdks | 10,281 | 2025-07-22 | 2026-08-31 | Local-AI toolkit |
| FareedKhan-dev/kimi-k3-in-c | 6,836 | **2026-08-01** | 2026-08-26 | "2.78T params, single CPU, 8.24 GB RAM" |
| drumih/turbo-fieldfare | 6,511 | **2026-07-17** | 2026-08-29 | "26B in ~2 GB RAM on any M-series Mac" (HN 919 pts) |
| cactus-compute/cactus | 5,957 | 2025-04-23 | 2026-08-26 | On-device mobile inference |
| mostlygeek/llama-swap | 5,526 | 2024-10-04 | 2026-08-30 | One-annoyance model swapping |
| vllm-project/semantic-router | 5,431 | 2025-08-26 | 2026-08-31 | Mixture-of-models routing |
| skyzh/tiny-llm | 4,531 | 2025-04-19 | 2026-08-30 | Teaching repo |
| raullenchai/Rapid-MLX | 3,599 | 2026-02-25 | 2026-08-31 | "4.2x faster than Ollama" |
| noonghunna/club-3090 | 2,131 | 2026-04-28 | 2026-08-27 | **Curated working configs — a markdown file** |
| RightNow-AI/picolm | 1,923 | 2026-02-19 | **2026-02-22** | "1B LLM on a $10 board" — spiked, then abandoned |

**Is there still room? Yes, but only in specific shapes.** Two repos created within the last eight weeks cleared 6,500 stars each. The space is **not** consolidated at the tool level.

- Room exists in **local/on-device inference, quantization, and operator tooling**.
- Room does **not** exist in fine-tuning (one new entrant in 14 months, NVIDIA's), eval infra (zero), experiment tracking (zero), dedup (zero), or signing/AIBOM (zero).
- `club-3090` is the most instructive datapoint in this report: **2,131 stars for curated, verified numbers with no code at all.** The scarce asset is trustworthy measurement, not software.

---

## 5. DURABILITY — what gets absorbed, what survives

### Obviously going to be absorbed — do not build here

| Thing | Absorber | Evidence |
|---|---|---|
| Model swapping/routing over llama.cpp | **llama.cpp itself** | Router mode shipped Dec 2025 |
| Serving config recommendation / autotuning | **vLLM** | `--performance-mode` merged Feb 2026; `benchmarks/auto_tune` ships |
| Routing / scheduling / autoscaling | **NVIDIA, Red Hat, ByteDance, vLLM org** | Dynamo, llm-d, aibrix, production-stack already fighting over it |
| Apple Silicon inference kernels | **Apple (MLX, 28,228★, pushed 2026-08-30)** | Ollama already switched to MLX on Apple Silicon (HN 648 pts, 2026-03-31) |
| Quantization *algorithms* | **NVIDIA / vLLM / Unsloth** | TensorRT-LLM, llm-compressor, Unsloth Dynamic 3.0 |
| Serialized-weights scanning, safetensors hardening | **Hugging Face** | Durably theirs — do not compete |
| Dataset curation/dedup pipelines | **HF (datasets, datatrove), NVIDIA (NeMo Curator)** | HF owns the data layer; NVIDIA owns the GPU-speed story (37h CPU → 3h GPU on RedPajama) |
| AIBOM / SBOM generation | **Snyk / JFrog / Palo Alto**, once EU enforcement bites | Commercial security vendors |
| Document parsing | **Microsoft (177k★), IBM (65.7k★)** | Already absorbed |
| Inference serving frontends | **Nobody holds it — HF archived TGI 2026-03-21** | Bad neighborhood regardless |

### Durable — and the reason is structural, not technical

**The protected position is neutrality: a tool whose product is *grading the ecosystem* cannot be shipped by a participant in it.**

1. **Cross-runtime correctness/conformance checking (B1, B4).** llama.cpp will not ship a tool flagging Ollama's Go-template lossiness. Ollama will not ship a tool saying its own 4K default is wrong. NVIDIA will never ship the tool whose headline is "NVFP4 diverges from BF16 on ~50% of tokens." HF will not grade its own uploaders.
2. **Adversarial, cross-engine, cross-version reconciliation (B2).** vLLM will never ship a tool whose headline is "our memory budgeter is wrong by N GB," and will never validate SGLang.
3. **Repo-level reputation auditing (B3).** HF is structurally slow to *judge repos it hosts*, because that means labelling its own users' uploads as suspicious. An outside CLI that ranks and shames is exactly what an incumbent hub cannot ship.
4. **Curated measurement corpora.** `club-3090`'s 2,131 stars in four months prove verified numbers are themselves the durable asset.

### Genuinely at risk
`ggufdoctor` could be partly absorbed if llama.cpp added `llama-lint`. **Mitigation: cover safetensors + HF + Ollama + vLLM from day one**, so no single runtime's built-in can replace it. This is a real risk, not a hypothetical one — see the llama-swap precedent.

---

## 6. TOP 7 OPPORTUNITIES, RANKED

### 1. `ggufdoctor` — cross-runtime model-artifact linter
- **Problem:** Local models are silently degraded by broken/missing chat templates and absent sampling defaults, and users blame the weights instead of the packaging.
- **Evidence:** [HN 49402232, 509 pts](https://news.ycombinator.com/item?id=49402232) — *"its not the quant, its the chat template… now i grep the gguf for the template tokens before i blame anything else"*; 54 chat-template + 80 jinja issues in llama.cpp in 2026; [llama.cpp #27129](https://github.com/ggml-org/llama.cpp/issues/27129); [ecosystem-wide Gemma 4 re-upload, May 2026](https://www.openaitoolshub.org/en/blog/gemma-4-gguf-chat-template-fix).
- **Nearest solution / insufficiency:** `l-bom` 3★, `gguf_analyzer` 2★, `gguf-info` 0★ — all read metadata; **none validates the template against upstream or checks sampling defaults**. `gguf chat template validate` → zero repos.
- **Absorption resistance:** HIGH (neutrality moat; mitigate llama-lint risk by going multi-runtime).
- **Difficulty:** LOW–MODERATE.
- **Striking number:** **YES, and unclaimed** — *"N% of the 1,000 most-downloaded GGUF repos ship a chat template that disagrees with upstream."*

### 2. `preflight` — GPU memory-budget reconciler for vLLM/SGLang
- **Problem:** Serving engines' memory auto-sizing silently lies, because real allocations are invisible to the budgeter — producing OOM crash-loops in containers that already returned healthy.
- **Evidence:** [SGLang #35201](https://github.com/sgl-project/sglang/issues/35201) (open, 2026-08-17) allocation "**invisible to `mem_fraction_static`**"; [vLLM #44740](https://github.com/vllm-project/vllm/issues/44740) (open) "-35 GiB" estimate inflating the KV pool; [vLLM #44209](https://github.com/vllm-project/vllm/issues/44209) (open) "**silent crash-loop of a container that already looked healthy**"; [SGLang #35777](https://github.com/sgl-project/sglang/issues/35777) — vendor's own recommended values cannot boot on an RTX 5090. Demand proof: [club-3090](https://github.com/noonghunna/club-3090), **2,131★ in 4 months for a markdown recipe book**.
- **Nearest solution / insufficiency:** 92 static VRAM calculators, **none above 101★**; `gpu memory profiler vllm oom debug` → zero repos. vLLM's own `--performance-mode` is a *recommender*, not a reconciler, and is itself buggy ([#37587](https://github.com/vllm-project/vllm/issues/37587)).
- **Absorption resistance:** HIGH (adversarial + cross-engine; vLLM cannot ship "our budgeter is wrong").
- **Difficulty:** MODERATE — needs real GPU access across several model/GPU pairs. This is the main cost.
- **Striking number:** **YES** — *"`--gpu-memory-utilization` overshot the safe ceiling by a median of N GB across 12 pairs; 4 crash-looped after passing /health."*

### 3. `hf-audit` — Hugging Face repo executable-surface scanner
- **Problem:** Model-repo attacks have moved from serialized weights to repo Python, and every deployed scanner still only inspects serialized files.
- **Evidence:** [Open-OSS/privacy-filter, 2026-05-07](https://www.hiddenlayer.com/research/malware-found-in-trending-hugging-face-repository-open-oss-privacy-filter) — "#1 trending… **approximately 244K downloads and 667 likes in under 18 hours**", delivered via `loader.py` with a `DummyModel` decoy; [three diffusers CVEs bypassing `trust_remote_code`, Aug 2026](https://thehackernews.com/2026/08/hugging-face-diffusers-flaws-could-let.html); [diffusers #12033](https://github.com/huggingface/diffusers/discussions/12033) maintainers questioning the feature.
- **Nearest solution / insufficiency:** `protectai/modelscan` 766★ **no release since 2026-02-18**, with four un-triaged 0-comment security bug reports; `picklescan` 422★ blacklist-based; `sigstore/model-transparency` 243★ **no release since 2025-10-10**. Search for a repo-level scanner → **zero results**.
- **Absorption resistance:** HIGH — HF cannot ship a tool that publicly ranks its own users' uploads as suspicious.
- **Difficulty:** LOW–MODERATE (static analysis + HF API; no GPU needed).
- **Striking number:** **YES** — *"Of the top 1,000 HF models by downloads, N require `trust_remote_code` and N execute outbound network calls at import."*

### 4. `quantdiff` — token-level quantization/backend divergence
- **Problem:** Nobody can measure what a given quant or attention backend actually cost them on their own workload, so choices are made by folklore.
- **Evidence:** [Level1Techs, Aug 2026](https://forum.level1techs.com/t/why-your-local-llm-feels-dumber-than-it-is/253917) — NVFP4 ~50% token disagreement by 88k context; NVFP4 and AWQ W4A16 "failed to properly close their tool calls"; arXiv 2601.14277 — "no unified experimental framework."
- **Nearest solution / insufficiency:** llama.cpp perplexity/KLD scripts; AngelSlim 1,584★ compresses but does not compare. Comparison-CLI searches → **zero repos**.
- **Absorption resistance:** MODERATE–HIGH (NVIDIA/vLLM structurally disinclined).
- **Difficulty:** MODERATE — statistical rigor is the hard part *and* the moat.
- **Striking number:** YES — generalize the published 50%-divergence result into one command.

### 5. `willitfit` — hardware-truthful local capacity planning
- **Problem:** No reliable way to know which quant fits and how fast it runs on *your* specific machine.
- **Evidence:** [HN 49479951, 137 pts, 2026-08-28](https://news.ycombinator.com/item?id=49479951) "real numbers from my Mac Studio"; turbo-fieldfare's measured **83 ms/token SSD read on M2 vs 12 ms on M5 Pro**; all calculators ≤101★.
- **Nearest solution / insufficiency:** Web calculators you type numbers into. **[Quant Picker got 20 points and 0 comments](https://news.ycombinator.com/item?id=48516202)** — the web-calculator framing demonstrably fails. Differentiator must be *measuring the actual machine*, SSD read speed included.
- **Absorption resistance:** MODERATE–HIGH.
- **Difficulty:** LOW.
- **Striking number:** MODERATE — "predicts tok/s within X% across N machines" is credible but less visceral. **Weakest demand evidence of the top five; consider shipping as a `ggufdoctor` subcommand.**

### 6. Apple Silicon memory-hierarchy inference (weight streaming/offload)
- **Problem:** Models whose weights exceed RAM are unrunnable on the machines most developers actually own.
- **Evidence:** [HN 49098510, 919 pts](https://news.ycombinator.com/item?id=49098510) — turbo-fieldfare, 6,511★ in six weeks; author's measurements: 40% expert reuse next-token, I/O cut 166→88 ms/token; **0.50 tok/s (mmap) vs 4 tok/s (pread)** on M2, because the OS cannot know which experts come next.
- **Nearest solution / insufficiency:** llama.cpp mmap — reactive paging, measurably 8× slower here.
- **Absorption resistance:** **LOW–MODERATE — Apple/MLX and llama.cpp will move here.** Highest traction, lowest durability.
- **Difficulty:** HIGH (Metal/Swift kernel work).
- **Striking number:** YES, proven — but six Apple Silicon servers launched in nine months. Crowded.

### 7. Eval run-manifest hasher
- **Problem:** Benchmark numbers cannot be compared because harness version, prompt template, few-shot seed, tokenizer and backend go unrecorded.
- **Evidence:** [lm-eval #3958](https://github.com/EleutherAI/lm-evaluation-harness/issues/3958) "Failed to reproduce Qwen3.5-4B on ceval-valid"; [lighteval #1363](https://github.com/huggingface/lighteval/issues/1363) cache "**silently serving one split's answers for another split's questions**"; ["LLM Olympiad" arXiv 2603.23292](https://arxiv.org/abs/2603.23292).
- **Nearest solution / insufficiency:** lm-eval-harness (13,833★) is a harness, not a reproducibility checker. `eval reproducibility hash config lm-eval` → **TOTAL 0**.
- **Absorption resistance:** MODERATE.
- **Difficulty:** MODERATE.
- **Striking number:** POSSIBLE — "reproduced N model-card claims; M differed by >2 points."
- **Ranked last, honestly:** [lm-eval #3967](https://github.com/EleutherAI/lm-evaluation-harness/issues/3967) proposed exactly this and got **0 comments**, and **no new eval infrastructure above 1,000★ has appeared in 14 months.** Low competition *and* low proven demand.

### Honorable mentions — considered and rejected
- **GGUF compute-graph / mmproj consolidation.** Explicitly invited by the format's designer ([HN 48138332](https://news.ycombinator.com/item?id=48138332)), which is rare and valuable. Rejected: ggml-org owns the spec (low absorption resistance), it requires deep GGML IR expertise and maintainer buy-in (high difficulty), and it has no striking number.
- **`decontam` CLI.** Genuinely unbuilt — `benchmark decontamination cli tool` → zero results; sole existing repo is 1★. Rejected: §1 found the surrounding discussion to be bot spam, i.e. no demand. Only viable if the *measurement* is the product: "N% of the top 1,000 HF datasets contain verbatim spans from MMLU/GSM8K/HumanEval."

---

## 7. Recommendation

**Build #1 (`ggufdoctor`), lead with the survey, and fold #5 (`samplerc`) in as a module and #4 (`quantdiff`) in as the second release.** It is the only candidate that is simultaneously: heavily evidenced by primary sources, technically greenfield (every competitor ≤3★), cheap for one person with no GPU budget, structurally protected by neutrality, and carrying an unclaimed headline number the ecosystem will immediately feel.

**If GPU access is available, #2 (`preflight`) is the stronger commercial position** — the pain is more expensive, the users are operators rather than hobbyists, and `club-3090`'s 2,131 stars for a markdown file prove the demand. It costs more to build.

**#3 (`hf-audit`) is the best risk-adjusted third** — low difficulty, no GPU, a dated high-profile incident, and incumbents that have visibly stopped shipping.

**Avoid entirely:** fine-tuning, experiment tracking, dataset dedup, decontamination, model signing/AIBOM/watermarking, generic RAG and chunking, document parsing, serving engines themselves, and serving orchestration/autoscaling. Each is either consolidated, corporate-controlled and fast-moving, or shows no demonstrated practitioner demand.
