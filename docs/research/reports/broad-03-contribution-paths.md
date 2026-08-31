# Becoming a Recognized Contributor in AI/Agentic Open Source

**Research date: 2026-08-31.** All numbers pulled live from the GitHub REST API (`gh api`), raw file fetches of GOVERNANCE/CONTRIBUTING docs, project blogs, and HN. Nothing here is stated from model memory. Items I could not confirm are marked **UNVERIFIED**.

---

## 0. Method and its limits

- **Stars / issues / push dates**: `GET /repos/{owner}/{repo}`, fetched 2026-08-31 ~02:20 UTC.
- **Openness proxy**: last 100 *closed* PRs per repo, filtered to merged, bucketed by `author_association`, plus median time-to-merge (TTM) computed separately for insiders (`MEMBER`/`OWNER`/`COLLABORATOR`) and outsiders (`CONTRIBUTOR`/`NONE`).
- **Critical caveat**: `author_association: CONTRIBUTOR` means "has had a PR merged before, not a public org member." It does **not** mean "not an employee." I therefore resolved the actual GitHub profile `company` field for every unique merged-PR author in the top candidates. This changed the conclusion for several projects (LiteLLM, MCP TypeScript SDK, Ollama all look open by association and are not).
- **Sampling window varies wildly**: 100 closed PRs covers 2 days in llama.cpp and 202 days in the MCP TypeScript SDK. Compare the `span` column, not raw counts.
- **Contributor totals** come from the `Link: rel="last"` header on `/contributors?per_page=1`. GitHub truncates this list around 500, so ~450 should be read as "450+".
- Search-API results were rate-limited (30/min); a few cells are missing rather than guessed.

### Corrections to stale assumptions

Several projects moved or died since early 2026. Verified live:

| Assumption | Live reality (2026-08-31) |
|---|---|
| `block/goose` | Redirects to **`aaif-goose/goose`** — moved to the Agentic AI Foundation org (created 2026-03-25) |
| `sst/opencode` | Redirects to **`anomalyco/opencode`** — 202,616 stars |
| `All-Hands-AI/OpenHands` | Redirects to **`OpenHands/OpenHands`** |
| `RooCodeInc/Roo-Code` | **ARCHIVED** |
| `huggingface/text-generation-inference` | **ARCHIVED** (last push 2026-03-21) |
| `microsoft/autogen` | Last push **2026-04-15** — 4.5 months idle |
| `Aider-AI/aider` | Last push **2026-05-22** — 3 months idle |
| `Portkey-AI/gateway` | Last push **2026-05-25** — 3 months idle |

The Agentic AI Foundation (`github.com/aaif`, org created 2025-11-14) is real and is a **directed fund of the Linux Foundation**. It has 17 repos, mostly working groups.

---

## 1. The target list — live vitals

Sorted by strategic relevance, not stars.

| Project | Stars | Open iss. | Last push | Contribs | Governance host |
|---|---:|---:|---|---:|---|
| ollama/ollama | 179,799 | 3,852 | 2026-08-29 | 451+ | Ollama Inc. |
| anomalyco/opencode | 202,616 | 5,599 | 2026-08-31 | — | Anomaly (corp) |
| open-webui/open-webui | 150,443 | 238 | 2026-08-31 | — | corp |
| langchain-ai/langchain | 145,302 | 430 | 2026-08-30 | — | LangChain Inc. |
| ggml-org/llama.cpp | 126,411 | 2,309 | 2026-08-30 | 445+ | ggml.ai (BDFL) |
| vllm-project/vllm | 90,525 | 7,211 | 2026-08-31 | 453+ | LF / PyTorch Fdn |
| modelcontextprotocol/servers | 89,978 | 512 | 2026-08-30 | — | LF (MCP) |
| OpenHands/OpenHands | 85,686 | 606 | 2026-08-31 | — | All Hands AI |
| cline/cline | 67,189 | 1,153 | 2026-08-30 | — | corp |
| mem0ai/mem0 | 64,377 | 706 | 2026-08-28 | — | Mem0 (corp) |
| microsoft/autogen | 60,706 | 1,000 | **2026-04-15** | — | Microsoft (idle) |
| crewAIInc/crewAI | 57,841 | 769 | 2026-08-28 | — | corp |
| BerriAI/litellm | 57,619 | **4,893** | 2026-08-31 | 375+ | BerriAI (corp) |
| **aaif-goose/goose** | 53,704 | 234 | 2026-08-31 | 449+ | **AAIF / LF** |
| run-llama/llama_index | 51,925 | 673 | 2026-08-29 | — | corp |
| Aider-AI/aider | 48,614 | 1,837 | **2026-05-22** | — | idle |
| ray-project/ray | 43,660 | 3,547 | 2026-08-31 | 71 committers | LF / Anyscale |
| langchain-ai/langgraph | 40,733 | 729 | 2026-08-30 | — | LangChain Inc. |
| qdrant/qdrant | 34,275 | 704 | 2026-08-30 | — | Qdrant GmbH |
| langfuse/langfuse | 33,944 | 863 | 2026-08-30 | — | Langfuse GmbH |
| sgl-project/sglang | 32,941 | 4,973 | 2026-08-31 | 451+ | LMSYS/RadixArk |
| chroma-core/chroma | 29,183 | 817 | 2026-08-30 | — | Chroma Inc. |
| openai/openai-agents-python | 29,079 | 38 | 2026-08-28 | — | OpenAI |
| deepset-ai/haystack | 26,366 | 122 | 2026-08-30 | — | deepset |
| **agentskills/agentskills** | 24,882 | 74 | 2026-08-09 | **41** | Anthropic |
| modelcontextprotocol/python-sdk | 24,163 | 391 | 2026-08-28 | — | LF (MCP) |
| temporalio/temporal | 22,612 | 933 | 2026-08-31 | — | Temporal Inc. |
| comet-ml/opik | 21,700 | 222 | 2026-08-31 | — | Comet ML |
| google/adk-python | 21,336 | 516 | 2026-08-31 | — | Google |
| pydantic/pydantic-ai | 19,595 | 772 | 2026-08-31 | — | Pydantic Inc. |
| weaviate/weaviate | 16,760 | 692 | 2026-08-30 | — | corp |
| NVIDIA/TensorRT-LLM | 14,507 | 1,411 | 2026-08-31 | — | NVIDIA |
| modelcontextprotocol/typescript-sdk | 13,284 | 596 | 2026-08-30 | 164 | LF (MCP) |
| Arize-ai/phoenix | 11,250 | 923 | 2026-08-29 | — | Arize AI |
| modelcontextprotocol/inspector | 10,793 | 25 | 2026-08-30 | — | LF (MCP) |
| **modelcontextprotocol/modelcontextprotocol** | 9,085 | 137 | 2026-08-30 | — | **LF (MCP)** |
| traceloop/openllmetry | 7,409 | 660 | 2026-08-10 | — | corp |
| modelcontextprotocol/registry | 7,203 | 157 | 2026-08-26 | — | LF (MCP) |
| modelcontextprotocol/go-sdk | 5,039 | 93 | 2026-08-28 | — | LF (MCP) |
| modelcontextprotocol/csharp-sdk | 4,500 | 165 | 2026-08-27 | — | LF (MCP) |
| restatedev/restate | 4,354 | 429 | 2026-08-28 | — | Restate (corp) |
| modelcontextprotocol/rust-sdk | 3,855 | 56 | 2026-08-30 | — | LF (MCP) |
| modelcontextprotocol/java-sdk | 3,675 | 299 | 2026-08-28 | 78 | LF (MCP) |
| **modelcontextprotocol/ext-apps** | 2,774 | 209 | 2026-08-12 | — | LF (MCP) |
| **modelcontextprotocol/mcpb** | 2,092 | 97 | **2026-04-22** | **18** | LF (MCP) |
| modelcontextprotocol/php-sdk | 1,594 | 69 | 2026-08-29 | 49 | LF (MCP) |
| **modelcontextprotocol/swift-sdk** | 1,480 | 103 | **2026-04-29** | **18** | LF (MCP) |
| modelcontextprotocol/kotlin-sdk | 1,445 | 81 | 2026-08-24 | 55 | LF (MCP) |
| **modelcontextprotocol/conformance** | **111** | **121** | 2026-08-27 | **38** | LF (MCP) |
| aaif/* working groups | 3–56 | 1–39 | 2026-08 | tiny | **AAIF / LF** |

---

## 2. The openness test

### 2a. Quantitative: merged-PR composition and time-to-merge

`out%` = share of merged PRs from non-org-members. `span` = calendar days covered by the sample. `uniqOut` = distinct outsider authors in the window.

| Project | n | span | out% | medTTM out | medTTM in | uniqAuth | uniqOut |
|---|---:|---:|---:|---:|---:|---:|---:|
| ggml-org/llama.cpp | 58 | 2d | 70% | 51.3h | 9.4h | **39** | **33** |
| vllm-project/vllm | 48 | 0d | 68% | 61.6h | 7.4h | **29** | **20** |
| ray-project/ray | 63 | 8d | 82% | 170.0h | 74.0h | 37 | 31 |
| sgl-project/sglang | 41 | 1d | 29% | 437.1h | 14.2h | 26 | 12 |
| temporalio/temporal | 62 | 5d | 96% | 71.1h | 687.4h | 20 | 19 |
| comet-ml/opik | 84 | 5d | 61% | 42.5h | 14.0h | 24 | 17 |
| Arize-ai/phoenix | 72 | 4d | 45% | 25.6h | 2.2h | 18 | 17 |
| aaif-goose/goose | 61 | 6d | 21% | 101.4h | 73.8h | 22 | 12 |
| agentskills/agentskills | 51 | 65d | 45% | 43.2h | 23.4h | 22 | 21 |
| mcp/modelcontextprotocol | 69 | 83d | 78% | **6.6h** | 125.5h | 35 | 28 |
| mcp/conformance | 78 | 54d | 41% | 169.3h | 0.4h | 20 | 17 |
| mcp/rust-sdk | 82 | 33d | 74% | 12.3h | 43.5h | 19 | 18 |
| mcp/go-sdk | 76 | 42d | 90% | 21.6h | 2.3h | 23 | 22 |
| mcp/registry | 47 | 56d | 61% | 42.4h | 0.5h | 10 | 8 |
| langfuse/langfuse | 86 | 3d | 65% | 1.6h | 1.4h | 13 | 9 |
| ollama/ollama | 46 | 8d | 30% | 4.8h | 3.2h | **7** | **4** |
| BerriAI/litellm | 52 | 0d | "100%" | 3.9h | — | **10** | 10 |
| mcp/typescript-sdk | 61 | **202d** | "100%" | 1.6h | — | **10** | 10 |
| mcp/inspector | 90 | 14d | 1% | 730.3h | 4.8h | **3** | 1 |
| NVIDIA/TensorRT-LLM | 27 | 2d | 7% | 260.4h | 87.1h | 20 | 2 |

### 2b. Qualitative: who actually merged (profile `company` resolution)

This is where the association field lies. Three examples:

- **BerriAI/litellm — 100% "CONTRIBUTOR", actually 100% staff.** The 10 unique merge authors over the sampled window: `mateo-berri`, `ryan-crabbe-berri`, `tin-berri`, `yassin-berriai`, `yucheng-berri`, `yuneng-berri`, `devin-ai-integration[bot]`, plus 2 genuine outsiders. The company suffix is in the handles. Meanwhile the repo carries **4,893 open issues**. Verdict: **closed**, and the openness metric is an artifact.
- **modelcontextprotocol/typescript-sdk — "100% CONTRIBUTOR", 10 authors over 202 days**, of whom 2 are bots and the humans include `felixweinberger` (Anthropic) and `maxisbey` (Anthropic). ~6 human authors in 7 months against **294 open PRs, 150 of them older than 3 months**. Verdict: **narrow funnel + drowning backlog**, not open.
- **ollama/ollama — 7 unique merge authors in 8 days**, of whom `dhiltgen`, `drifkin`, `jessegross`, `hoyyeva`, `ParthSareen` are Ollama staff. Verdict: **closed**.

Contrast with genuinely open projects:

- **llama.cpp**: 39 distinct merge authors in a *2-day* window, mostly unaffiliated individuals plus NVIDIA (`jeffbolznv`, `ruixiang63`), Qualcomm (`wanghqc`), HuggingFace (`allozaur`, `ngxson`, `ggerganov`), AMD (`slojosic-amd`), unsloth (`danielhanchen`), and two Shanghai Jiao Tong students. Highest outsider throughput measured.
- **vLLM**: 29 authors in a *single day* spanning BAAI, Inferact, Mistral, Huawei, Confluent, NVIDIA, Red Hat, AMD, DaoCloud, SJTU, plus unaffiliated individuals. Genuinely multi-vendor.
- **SGLang**: multi-vendor (Alibaba Cloud, XPENG, NVIDIA, Meta, AMD, Intel, Tongji) but insider-dominated at merge time (29 COLLABORATOR vs 12 CONTRIBUTOR) and outsider TTM is **437h ≈ 18 days** vs 14h for insiders — a **31× insider advantage**, the worst ratio measured among otherwise-open projects.
- **agentskills**: 22 authors from Continue, Pulumi, Vercel, JetBrains, Apache/OceanBase, Qodo, Snowflake, Anthropic — and only **41 total contributors ever**. Unusually multi-vendor for its size.

### 2c. Documented ladders and legal gating

Sourced from live GOVERNANCE/CONTRIBUTING fetches.

| Project | Written ladder? | RFC open to outsiders? | CLA/DCO | Control |
|---|---|---|---|---|
| **MCP** | **Yes — full contributor ladder** ([contributor-ladder.mdx](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/community/contributor-ladder.mdx), implements SEP-2148) | **Yes — SEP process**, plus Working Groups + Interest Groups | **Neither**; "no contributor will be required to assign copyrights" | LF; BDFL-topped (Lead Maintainers are Anthropic-origin) |
| **vLLM** | **Yes, with numeric criteria** ([committers.md](https://github.com/vllm-project/vllm/blob/main/docs/governance/committers.md)) | Yes, RFC issue template | DCO, no CLA | LF-adjacent; Red Hat/Berkeley heavy but multi-vendor |
| **goose** | **Yes** ([GOVERNANCE.md](https://github.com/aaif-goose/goose/blob/main/GOVERNANCE.md)) — "merit-based and tied to individual contributions, not employer affiliation" | Issue + 1-week community review; no RFC repo | None found | **AAIF / LF** (moved off Block) |
| Ray | Process yes, **criteria not published** | REP repo, but needs a committer shepherd | None | LF; Anyscale-concentrated |
| SGLang | Roles named, **no promotion criteria**; nomination = "ping Lianmin/Ying in Slack" | No | None | LMSYS/RadixArk |
| llama.cpp | 3 tiers named in CONTRIBUTING, **no criteria**; self-add to CODEOWNERS | No | None | BDFL (ggerganov) |
| agentskills | No | Discussions only; "not accepting code contributions" to Reference Library | None | **Anthropic** |
| ollama | **None at all** | No | None | Ollama Inc. |
| opencode | No; "must go through a design review with the core team… PRs that ignore these guardrails will likely be closed" | No | None found | Anomaly |
| pydantic-ai | No. "A maintainer needs to agree on the approach and assign the issue to you before you open a PR. Unassigned PRs may be auto-closed" | No | None | Pydantic Inc. |
| OpenHands | No CONTRIBUTING, no GOVERNANCE at root; SDK repo lists **3** maintainers | No | None | All Hands AI |
| langfuse, litellm, opik, phoenix, mem0, temporal | **No ladder, no maintainer list** | No | **CLA required** (all six) | Single-vendor |

**The cleanest single predictor found: a copyright-assigning CLA plus no published maintainer list ⇒ the project is closed in practice.** Every project in the bottom row has both. Foundation-hosted projects (MCP, vLLM, goose, Ray) uniformly have DCO-or-nothing *and* a public roster.

Two extra gating patterns worth flagging:
- **mem0**: PRs must link an issue carrying the `accepted` label or a bot auto-closes them, plus a `.github/VOUCHED.td` allowlist maintainers edit with `!vouch @you` / `!denounce`. Explicit gatekeeping machinery.
- **Arize phoenix**: "An open issue is not an invitation to submit a PR… please wait for explicit confirmation from a maintainer."

**AAIF caveat**: the foundation's own Technical Committee is *not* meritocratic — [charter.md](https://github.com/aaif/technical-committee/blob/main/governance/charter.md) states "Each Platinum Member of AAIF may appoint one representative to the TC." Foundation-level seats are corporate-apportioned; the *project*-level ladders (goose, MCP) are where merit operates.

---

## 3. The under-resourced test

Ranked by (downstream usage) ÷ (maintainer capacity).

| Project | Users signal | Capacity signal | Backlog | Verdict |
|---|---|---|---|---|
| **modelcontextprotocol/swift-sdk** | 1,480 ★, official MCP SDK | **18 contributors; last commit 2026-04-29 (4 months)** | 103 open issues; **open PRs from 2025-04-04**, i.e. **16 months unmerged** | **Effectively abandoned. Highest takeover leverage.** |
| **modelcontextprotocol/mcpb** | 2,092 ★, MCP Bundles packaging format | **18 contributors; last commit 2026-04-22** | 97 open issues | **Abandoned; CLI/packaging-shaped** |
| **modelcontextprotocol/conformance** | The official cross-SDK conformance harness; gates SDK "Tier" status | **38 contributors total** | **121 open issues**, mostly outsider-filed and unassigned | **Under-resourced and strategically central** |
| **modelcontextprotocol/typescript-sdk** | 13,284 ★, 164 contributors | **~6 human merge authors / 202 days** | **294 open PRs (150 >3mo); 302 open issues (145 >6mo)** | Drowning; narrow merge funnel |
| modelcontextprotocol/python-sdk | 24,163 ★ | small | 185 open PRs (102 >3mo), 206 open issues | Drowning |
| modelcontextprotocol/java-sdk | 3,675 ★ | 78 contributors | **299 open issues** | Stretched |
| **ollama/ollama** | **179,799 ★** — enormous install base | **~5 staff merge authors** | **1,395 open PRs (819 >3mo); 2,457 open issues (1,711 >6mo); 1 "help wanted"** | Huge backlog but **closed** — do not invest |
| sgl-project/sglang | 32,941 ★, production inference | insider-dominated merges | **4,153 open PRs (843 >3mo)**; 50 good-first-issue | Overloaded, semi-open |
| vllm-project/vllm | 90,525 ★ | 57 active committers | **4,975 open PRs (1,531 >3mo); 2,237 open issues; 34 help-wanted; 23 good-first-issue** | Overloaded **and** open — best combination |
| llama.cpp | 126,411 ★ | 445+ contributors, ~23 CODEOWNERS | 1,447 open PRs (817 >3mo); 864 open issues; **27 help-wanted, 17 good-first-issue** | Busy but healthy and open |
| **aaif/wg-\*** | LF working groups defining agentic standards | **1–3 active people per WG** | 1–39 open issues each | **Wide open; institutional standing available now** |

### Maintainers publicly signalling capacity limits (direct quotes)

- **David Soria Parra, MCP Lead Maintainer** — [2026 MCP Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/), 2026-03-09: *"Right now, every SEP requires full Core Maintainer review, regardless of domain. That's a bottleneck."* And: *"Maintainer bandwidth is finite, and we'd rather be transparent about where it's going."* And an explicit open invitation: *"A dedicated Enterprise WG does not yet exist. If you work in enterprise infrastructure and want to lead or join one, the Working Groups page explains how to get started."*
- **Kevin Luu (@khluu), vLLM CI committer** — [Keeping vLLM Production Quality](https://vllm.ai/blog/2026-07-16-keeping-vllm-production-quality), 2026-07-16: *"In June 2026, vLLM merged 1,918 commits into main — 64 a day on average, on par with other big OSS projects like PyTorch or Kubernetes."* … *"If any of these problems sound like your kind of fun … come say hi in #sig-ci on the vLLM Slack."*
- **Robert Shaw (@robertgshaw2-redhat), vLLM committer** — [issue #31689](https://github.com/vllm-project/vllm/issues/31689), 2026-01-04: *"WARNING: this is a significant undertaking and will be scrutinized heavily for code quality. The PR author should reach out to @robertgshaw2-redhat in slack to discuss design and on-going progress during the PR creation. Thanks in advance for any help!!!"*
- **SGLang** [.github/MAINTAINER.md](https://github.com/sgl-project/sglang/blob/main/.github/MAINTAINER.md) — an explicit, unusual on-ramp: *"If you or someone you know would like to donate machines for CI, they can serve as the CI oncalls for their machines."*

**UNVERIFIED**: no maintainer in vLLM / SGLang / llama.cpp was found using the word "burnout." The evidence above is capacity/bottleneck language, not burnout claims. Generic OSS burnout discourse exists ([OpenJSF, 2026-06-21](https://openjsf.org/blog/burnout-is-real-for-open-source-maintainers), HN 48620462; [Godot "drowning in AI-generated PRs"](https://news.ycombinator.com/item?id=47251385), 2026-03-04) but is not AI-infra-specific.

---

## 4. High-leverage work types — what actually got people promoted

Verified promotions with dates and evidence.

### What worked

**(a) Kernel/perf work with measured wins — vLLM's dominant path.**
- **Wentao Ye (@yewentao256)**: first merged PR 2025-06-05, [#19233 "[Perf] Vectorize static/dynamic INT8 quant kernels"](https://github.com/vllm-project/vllm/pull/19233) — VEC_SIZE=16 vectorization removing a global-memory pass, PR body carrying before/after gsm8k parity and H100 throughput benchmarks, plus a new `benchmarks/kernels/bench_int8_gemm.py`. Now a committer for "Kernels and performance" with 417 merged PRs.
- **Yongye Zhu (@zyongye)**: first PR 2025-08-06, [#22330 "[gpt-oss] flashinfer attention sink init"](https://github.com/vllm-project/vllm/pull/22330) → committer, "MoE kernels and quantization."

**(b) Building a missing subsystem — the fastest path observed.**
- **Bugen Zhao (@BugenZhao)**, ex-RisingWave database engineer: first merged vLLM PR 2026-04-21 ([#40460](https://github.com/vllm-project/vllm/pull/40460)); made **Rust frontend code owner** via [PR #44047](https://github.com/vllm-project/vllm/pull/44047), merged 2026-05-30. **39 days from first PR to owning a subsystem.** He brought a transferable systems skill (Rust) into a project that lacked it.

**(c) Hardware/backend enablement — reliably rewarded.**
- **Doug Lehr (@dllehr-amd)** self-added as AMD/ROCm owner taking `/csrc/rocm` and ROCm attention/MLA/fused_moe backends ([PR #42772](https://github.com/vllm-project/vllm/pull/42772), 2026-05-20). **@iboiko-habana** added for Intel Gaudi HPU ([#52726](https://github.com/vllm-project/vllm/pull/52726), 2026-08-20). SGLang's named external CI oncalls follow the same pattern: @saienduri (AMD), @mingfeima + @DiweiSun (Intel), @iforgetmyname (Ascend NPU).

**(d) Spec/protocol work — the dominant path in MCP.**
- **Kurtis Van Gent (@kurtisvg)**, Google Cloud: made Core Maintainer in the [January 2026 update](https://blog.modelcontextprotocol.io/posts/2026-01-22-core-maintainer-update/) specifically for *driving the Transport Working Group*; then authored merged [SEP-2575 "Make MCP Stateless"](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575).
- **Den Delimarsky (@localden)** → **Lead Maintainer** ([April 2026 update](https://blog.modelcontextprotocol.io/posts/2026-04-08-maintainer-update/)), credited for the authorization spec, RFC 8707 resource indicators, SEP-835/1024/2350, leading the 2025-11-25 spec release — **and for building a [contribution tracker](https://localden.github.io/mcp-repo-data-tracker/) for maintainers**, i.e. tooling that reduced maintainer load.
- **Clare Liguori (@clareliguori)**, AWS → Core Maintainer, April 2026.
- **Luca Chang (@LucaButBoring)**, AWS: authored merged [SEP-2663 Tasks Extension](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2663).
- **Ido Salomon (@idosal) / Liad Yosef (@liady)**: built the third-party MCP-UI project, now co-Leads of the **official MCP Apps WG**. External project → spec ownership.

**(e) Sustained tooling/triage on one repo until you own it — the outsider classic.**
- **Cliff Hall (@cliffhall)**, an independent consultant at Futurescale. First PR to `modelcontextprotocol/inspector` was [#169, 2025-03-07, "Removing all the hype from the ping button"](https://github.com/modelcontextprotocol/inspector/pull/169) — a trivial UI tweak. He is now the repo's **#1 contributor (1,479 contributions)** and a **WG Lead + Maintainer** on the Inspector V2 working group, whose charter PR he authored ([#2555](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2555)). This is the single most encouraging trajectory in the dataset: no employer sponsorship, trivial first PR, ~18 months to WG lead.
- **Ola Hungerford (@olaservo)**, Nordstrom: first inspector PR [#135, 2025-01-27](https://github.com/modelcontextprotocol/inspector/pull/135) ("Add server startup logging"); now #2 contributor and Lead of **two** WGs (Inspector V2, Skills-over-MCP).
- **goose**: [PR #5675](https://github.com/aaif-goose/goose/pull/5675) (2025-11-11) promoted **@Abhijay007** and **@The-Best-Codes** to maintainer. Their prior work was unglamorous CLI/desktop polish — recipe-list dedup, quick launcher, fuzzy file search, Windows `download_cli.ps1`, OpenRouter model fetch in `goose configure`, a hermit "text file busy" fix on Linux. **@codefromthecrypt** (Adrian Cole, Netflix, Zipkin creator) added 2025-11-19 ([#5815](https://github.com/aaif-goose/goose/pull/5815)).

**(f) Docs/spec-clarity — works only in young spec repos.**
- **Jonathan Hefner (@jonathanhefner)**, Vercel: top contributor to `agentskills/agentskills` with **91 contributions vs 10 for the next-highest**, and now visibly *merging* others' PRs despite Anthropic owning the repo. His work is metadata/frontmatter clarification and consolidating agent guidance. Shows that in a 41-contributor spec repo, docs work does convert to de facto maintainership.

### What does not work

- **Docs PRs to large mature projects.** Not one vLLM committer promotion in the sampled set was earned through documentation.
- **Volume of trivial PRs.** vLLM's stated bar is explicitly qualitative and includes *reviewing*: *"Submitted approximately 30+ PRs of substantial quality and scope; Provided high-quality reviews of approximately 10+ substantial external contributor PRs."* Reviewing others is half the criterion and is the part most outsiders skip.
- **Contributing to CLA-gated single-vendor repos.** No promotion path exists to find.
- **Authoring a SEP and walking away.** There are 30+ open SEPs, many stalled for months (see §5). Authorship alone is cheap; shepherding to Final is what got people promoted.

---

## 5. Concrete opportunities (12)

Ordered by leverage-per-effort for a backend/infra/CLI + AI/ML builder.

| # | Project & gap | Why it matters | Why still open | Effort |
|---|---|---|---|---|
| 1 | **`modelcontextprotocol/conformance`** — 121 open issues, only 38 contributors ever. Concrete: [#451 "Expose expected-vs-emitted check coverage per scenario"](https://github.com/modelcontextprotocol/conformance/issues/451), [#467 "Prevent false greens when a negative check rejects for the wrong reason"](https://github.com/modelcontextprotocol/conformance/issues/467), [#430 "WARNING severity is inconsistent between client and server runners"](https://github.com/modelcontextprotocol/conformance/issues/430), [#460 "Shift config of known-sdks.ts to SDK-side config file"](https://github.com/modelcontextprotocol/conformance/issues/460) | This harness **gates every MCP SDK's Tier status** — it is the referee for the whole ecosystem. A TypeScript CLI (`npx @modelcontextprotocol/conformance`). Infrastructure-shaped, measurable, high-visibility to all SDK maintainers. | Tiny team; conformance work is unglamorous; outsider TTM is 169h so it needs patience but PRs *do* merge (17 distinct outsiders merged in 54 days, from Google, Stytch, Hitachi, OpenAI, pydantic) | Med |
| 2 | **`modelcontextprotocol/swift-sdk`** — official SDK, **last commit 2026-04-29**, 18 contributors, 103 open issues, outsider PRs open since **2025-04-04** (e.g. [#64 StdioTransport for Windows](https://github.com/modelcontextprotocol/swift-sdk/pull/64), [#101 legacy SSE client transport](https://github.com/modelcontextprotocol/swift-sdk/pull/101)) | An **official** LF-hosted SDK, effectively unmaintained, with 1,480 stars of downstream users. Reviving it is a visible rescue, and MCP has a written ladder to climb afterwards. | Nobody has stepped up; Swift is outside the core team's skill set | Med–High |
| 3 | **`modelcontextprotocol/mcpb`** (MCP Bundles) — **last commit 2026-04-22**, 18 contributors, 97 open issues, 2,092 stars | The **packaging/distribution format** for MCP servers — squarely CLI/infra-shaped, the exact profile requested. Packaging formats become load-bearing ecosystem infrastructure. | Stalled after the Anthropic staff who drove it moved on | Med |
| 4 | **Lead the MCP Enterprise Working Group — it does not exist yet.** The Lead Maintainer publicly asked for someone: *"A dedicated Enterprise WG does not yet exist. If you work in enterprise infrastructure and want to lead or join one, the Working Groups page explains how to get started."* ([2026 roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)) | WG Lead is a **named, public role** in a Linux Foundation project, and §4 shows WG leadership is the fastest route to Core Maintainer (Van Gent, Hungerford, Hall, Salomon/Yosef all took it) | It requires someone to write a charter and run meetings — organizational work most engineers avoid | Med (sustained) |
| 5 | **vLLM [#33872](https://github.com/vllm-project/vllm/issues/33872) — kernel-abstraction migration**, a community help-wanted issue with a **per-scheme migration table**; and [#31689 "Clean up GPTQ + AWQ Quantization"](https://github.com/vllm-project/vllm/issues/31689) | Robert Shaw wrote an explicit onboarding ramp with a checklist. Kernel/quantization work is *the* documented promotion path (Ye, Zhu). Wins are measurable in throughput. | Explicitly flagged as "a significant undertaking… scrutinized heavily for code quality" — high bar deters people | High |
| 6 | **vLLM [#32335 "Extract KV-Cache update from all attention backends"](https://github.com/vllm-project/vllm/issues/32335)** — 54 comments, help-wanted + good-first-issue, open since 2026-01-14; related [#33267](https://github.com/vllm-project/vllm/issues/33267) | Cross-cutting refactor touching every attention backend — exactly the kind of subsystem work that earns CODEOWNER status. 54 comments = high maintainer attention. | Long-lived, coordination-heavy, spans many backends | High |
| 7 | **vLLM [#39428 "[torch.compile] E2E correctness testing for fusions"](https://github.com/vllm-project/vllm/issues/39428)** and [#39479 config-hashing refactor follow-ups](https://github.com/vllm-project/vllm/issues/39479) | **Test-infrastructure** work in the compile stack. Correctness harnesses are chronically under-owned and give a durable ownership claim; CI/testing is a named committer specialty (@khluu, @Harry-Chen) | Testing work is low-status relative to kernels, so it stays open | Med |
| 8 | **vLLM CI / #sig-ci** — Kevin Luu's open invitation, against **4,975 open PRs and 13M CI job-minutes/month** | CI ownership is a documented promotion category in vLLM's committer roster (@vadiklyutiy, @Harry-Chen). Direct maintainer-pain relief = fastest gratitude. | Thankless, on-call-flavoured | Med (sustained) |
| 9 | **SGLang CI oncall via hardware donation** — [.github/MAINTAINER.md](https://github.com/sgl-project/sglang/blob/main/.github/MAINTAINER.md): *"If you or someone you know would like to donate machines for CI, they can serve as the CI oncalls for their machines."* Backlog: **4,153 open PRs**, 50 good-first-issues | A **written, non-competitive path to a named role** in a 33k-star inference engine. Almost nobody exploits it. | Requires hardware/cloud budget rather than skill — an unusual and therefore uncrowded barrier | Low skill / Med cost |
| 10 | **llama.cpp [#10453 "ggml: add ANE backend"](https://github.com/ggml-org/llama.cpp/issues/10453)** (Apple Neural Engine, help-wanted, open since 2024-11) and [#6758 "ggml: add GPU support for Mamba models"](https://github.com/ggml-org/llama.cpp/issues/6758) (39 comments) | Backend enablement is the #1 promotion category ecosystem-wide, and llama.cpp is the **most open project measured** (39 merge authors in 2 days; self-nominate by adding yourself to CODEOWNERS). Perf wins are trivially measurable. | Genuinely hard low-level work; ANE is poorly documented by Apple | High |
| 11 | **Shepherd a stalled MCP SEP to Final.** 30+ open SEPs, many stalled months — e.g. [SEP-2998 Partial Tool Results (streaming tool output)](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2998), [SEP-2694 Resumable Task Event Streams](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2694), [SEP-2692 Stdio process lifetime](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2692), [SEP-2633 Standard client config format `mcp.json`](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2633) | The spec repo has the **best outsider TTM measured (6.6h median, vs 125h for insiders)** and 78% outsider merges. Pair a SEP with a reference implementation *plus* conformance tests (opportunity #1) and it becomes very hard to ignore. | The Lead Maintainer named the cause himself: *"every SEP requires full Core Maintainer review… That's a bottleneck."* Authors write and abandon; shepherding is the scarce act. | Med–High |
| 12 | **AAIF working groups — `aaif/wg-observability-and-traceability`** (17 open issues, ~2 active people), `wg-workflows-and-process-integration` (8), `wg-security-and-privacy` (14) | Linux Foundation standards bodies for agentic AI, currently driven by **one to three individuals each** (@narko4u, @91pavan, @mzagar). Institutional standing — a foundation WG role — available at near-zero competition right now. | Created only in 2026; almost nobody knows they exist; star counts (3–56) make them invisible to status-seekers | Low–Med |

**Note on #12's ceiling**: AAIF's Technical Committee seats are reserved for Platinum Members, so WG participation grants standing and visibility but not a TC seat.

---

## 6. Honest comparison — contribute vs. build

### The new-repo premise is false — and *why* it is false changes the argument

The brief's premise was that "the star ceiling has fallen — nothing created after May 2026 has cleared 15k stars." **Checked live on 2026-08-31, this is false by roughly an order of magnitude.**

`created:>2026-05-01 stars:>15000` returns **19 repos**. The top of that cohort:

| Repo | Stars | Created | Age |
|---|---:|---|---|
| `deepseek-ai/deepseek-harness` | **204,899** | 2026-08-13 | **18 days** |
| `DietrichGebert/ponytail` | 117,288 | 2026-06-12 | 2.6 mo |
| `odysseus-dev/odysseus` | 86,587 | 2026-05-31 | 3.0 mo |
| `zhaoxuya520/reverse-skill` | 32,088 | 2026-05-13 | 3.6 mo |
| `BigPizzaV3/CodexPlusPlus` | 29,924 | 2026-05-06 | 3.8 mo |
| `xai-org/grok-build` | 26,264 | 2026-07-14 | 1.5 mo |

Cohort comparison, repos above 20k stars: **2024-H1 → 71; 2025-H1 → 72; 2026 (8 months, partial) → 125.** The age confound runs *against* the premise, not for it — correcting for it would widen the 2026 lead. Restricting to agent/AI keywords does not rescue the claim either (`alibaba/open-code-review` 21,674; `PrimeIntellect-ai/prime-agent` 19,278; `microsoft/SkillOpt` 16,504, all post-May-2026).

**But the corrected fact argues for the contribution path more strongly than the original premise did.** The reason is what those numbers now represent. 2026 HN discourse is not about a falling ceiling — it is about stars decoupling from merit:

- ["GitHub's fake star economy"](https://news.ycombinator.com/item?id=47831621) — **810 points, 377 comments**, 2026-04-20.
- ["90% of Claude-linked output going to GitHub repos with <2 stars"](https://news.ycombinator.com/item?id=47521157) — 337 points, 2026-03-25. The long tail is now effectively infinite.
- ["AI slop is killing online communities"](https://news.ycombinator.com/item?id=48053203) — 834 points, 2026-05-07.
- ["OpenClaw surpasses React to become the most-starred software project on GitHub"](https://news.ycombinator.com/item?id=47217812) — 291 points, 2026-03-02; a repo created 2025-11-24 now at 388,100 stars.

And the cohort list itself is the evidence: several of the top post-May-2026 repos (`DietrichGebert/ponytail`, `zhaoxuya520/reverse-skill`, `affaan-m/ECC` at 244,747) are not projects anyone in this ecosystem can name. A 200k-star repo that nobody has heard of is a measurement failure, not an achievement.

**So the real 2026 dynamic is not "you can't get stars." It is "stars no longer prove anything."** Star counts have become cheap and noisy at exactly the moment when verifiable, adjudicated roles — a committer row in a Linux Foundation project, a WG lead line in MAINTAINERS.md, an authored SEP marked Final — have not. Those cannot be farmed, because a human maintainer has to vote you in. **Star inflation devalues the build path's currency while leaving the contribution path's currency intact.** That is a stronger argument for contributing than a falling ceiling would have been.

### Verdict: **Contribute — with a specific shape. Do not start a general-purpose new repo.**

The reasoning:

**1. The ladders are real, written, and currently being climbed — with measured latency in weeks, not years.** This is the strongest finding. MCP, vLLM, and goose all publish promotion criteria, and I found dated PRs promoting outsiders throughout 2026: vLLM's [#51300](https://github.com/vllm-project/vllm/pull/51300) added ~15 committers in a single 2026-08-06 commit. **@BugenZhao went from first merged PR to owning the Rust frontend in 39 days.** No new repo produces comparable recognition in 39 days.

**2. Recognition transfers to a person, not a repo — and is adjudicated, not farmed.** vLLM's governance doc states it directly: *"No one buys their way into governance. Committer status belongs to individuals, not companies."* In a year when 125 repos crossed 20k stars and an 810-point HN investigation documented a fake-star economy, a role that required existing maintainers to vote for you is the scarcer and more credible signal. A committer row in a Linux Foundation project is legible to employers and durable; a 3k-star repo decays the moment you stop pushing, and a 30k-star repo no longer proves much.

**3. Slot scarcity favours the contributor path right now.** The ecosystem's structural bottleneck in 2026 is **maintainer review capacity, not more projects.** vLLM has 4,975 open PRs; SGLang 4,153; MCP's Lead Maintainer named SEP review as *the* bottleneck. Supplying scarce capacity is rewarded; adding another repo to a saturated field is not.

**4. The specific skill profile maps onto the highest-paid gaps.** Backend/infra/CLI + AI/ML is exactly what opportunities #1, #2, #3, #5–#10 need, and it is *rarer* in these projects than ML-research skill. @BugenZhao's leverage was a database engineer's Rust competence entering a Python-heavy project. Conformance suites, packaging formats, CI, and test harnesses are all under-owned precisely because they are infra work in ML-researcher communities.

**Conditions under which building still wins:**
- **Build an adjacent tool, not a competitor.** The two highest-status outsider stories both did this: Salomon/Yosef built MCP-UI externally and were absorbed as **official MCP Apps WG co-leads**; Den Delimarsky built a maintainer contribution tracker and made **Lead Maintainer**. A small tool that solves a maintainer's problem is a contribution vector wearing a repo's clothes — it captures both paths' upside. This is the single best play available.
- **Build if you have a genuine architectural thesis** the incumbents cannot adopt without breaking compatibility. Absent that, you are competing for attention against 200k-star incumbents.
- **Never build to farm stars.** The projects reviewed here reward reviewing others' PRs (vLLM literally counts it), shepherding, and unglamorous maintenance — none of which a personal repo exercises.

**What to avoid, concretely:** do not invest in **Ollama** (179k stars, 2,457 open issues, 1,711 older than 6 months, ~5 staff merge authors, **1** help-wanted label, no governance doc) — the backlog looks like opportunity and is actually a wall. The same applies to every CLA-gated single-vendor project: **LiteLLM, Langfuse, Opik, Phoenix, mem0, Temporal**. LiteLLM in particular has 4,893 open issues and merges almost exclusively BerriAI staff — maximum apparent need, zero actual path.

### Recommended sequencing (3–6 months)

1. **Weeks 1–4 — pick one lane and prove competence.** `modelcontextprotocol/conformance` (#1) is the best single entry: tiny contributor base (38), CLI-shaped, TypeScript, 121 unassigned issues, and its output is the referee every SDK is measured against. Ship 3–5 substantive PRs.
2. **Weeks 2–8 — start reviewing others' PRs in the same repo.** This is half of vLLM's written criterion and the step almost everyone skips. It is also what got the goose maintainers promoted.
3. **Months 2–4 — take an owned surface.** Either revive `swift-sdk` or `mcpb` (#2/#3), or pair a stalled SEP with a reference implementation *and* conformance tests (#11 × #1). The combination is what makes a SEP unignorable.
4. **Months 3–6 — take a named role.** Propose or join the Enterprise WG (#4), or an AAIF WG (#12). Named roles are what convert work into recognition.
5. **Run one high-bar technical thread in parallel** — vLLM #33872 or #32335 (#5/#6) — for the harder credential, accepting that it may not land inside 6 months.

Hedge: keep any personal tooling you build small, adjacent, and aimed at a maintainer's pain, so it can be absorbed rather than compete.

---

## Appendix: confidence and gaps

**High confidence**: all star/issue/push/contributor counts (direct API, timestamped); merged-PR composition and TTM within the sampled windows; author company fields; presence/absence of GOVERNANCE, CONTRIBUTING, CLA, maintainer lists; the promotion PRs and blog posts cited in §4 (each links to a specific PR diff or dated post).

**Medium confidence**: "corporate-controlled" verdicts for projects lacking governance docs — inferred from CLA presence, absent maintainer lists, and merge-author affiliation, not from a company statement. Effort estimates in §5 are my judgement.

**Premise correction**: the brief's stated premise (no post-May-2026 repo above 15k stars) was tested and is false; 19 such repos exist, topping out at 204,899. The verdict in §6 does not rest on it — it rests on star *credibility* collapsing, which is independently evidenced by 2026 HN discourse.

**Explicitly UNVERIFIED**:
- Historical star counts at matched age for the 2024/2025 cohorts. The `stargazers` endpoint with the `star+json` media type returned 404 in this environment, so per-star timestamps were unavailable and like-for-like 3-month comparisons could not be reconstructed. The 2026 figures are direct measurements at known ages; the baselines are current totals at 14–32 months.
- Whether the top post-May-2026 star gainers are organically starred. Their obscurity plus the documented fake-star economy makes them suspect, but no per-repo forensic check was run.
- Absence of CLA bots for sglang, llama.cpp, ollama, chroma, opencode, qdrant, OpenHands, pydantic-ai — docs and workflow files were checked, live PR checks were not.
- Ray's actual committer criteria (TSC-internal, unpublished).
- No maintainer in vLLM/SGLang/llama.cpp was found using the word "burnout"; §3 quotes capacity language instead. Do not read burnout claims into it.
- A vLLM Semantic Router blog listing ~16 additional new committers was seen only as a search snippet and not opened.
- First-PR dates missing for several vLLM committers (@vadiklyutiy, @shen-shanshan, @tomeras91, @orozery).
- "Inferact" and "RadixArk" appear repeatedly as employers of vLLM and SGLang committers respectively and are almost certainly the projects' commercial entities, but I did not confirm this.
- `agentskills` last push is 2026-08-09 (3 weeks) — slower than peers; whether this signals a slowdown or normal cadence for a spec repo is unconfirmed.
- Search-API rate limits blocked stale-PR counts for a few repos; those cells are absent rather than estimated.
