# The Broad Agentic Stack — Opportunity Scout Report
**Date of research: 2026-08-31.** All star counts pulled live from the GitHub REST API (`gh api repos/...`) on 2026-08-31 between 02:15–02:40 UTC. Discourse via `hn.algolia.com`. Nothing in this report is stated from model memory; anything I could not confirm live is labelled **UNVERIFIED**.

Scope note: per mandate, coding-agent tooling is deliberately under-weighted. It appears only where it distorts the data (it distorts it a lot — see §4).

---

## 1. Landscape map — the agentic stack, Aug 2026

### 1.1 Layer table

| # | Layer | Leading OSS (live stars, last push) | Verdict |
|---|---|---|---|
| 1 | **Local/open-weight inference** | ollama 179,799 (2026-08-29) · llama.cpp 126,411 (2026-08-30) · vllm 90,525 (2026-08-31) · sglang 32,941 (2026-08-31) | **CONSOLIDATED** (ollama local, vLLM server) |
| 2 | **Agent skills / prompt assets** | anthropics/skills 172,658 (2026-08-21) · mattpocock/skills 241,938 · vercel-labs/skills 30,037 | **CONSOLIDATED around a format, chaotic in content** |
| 3 | **Personal / self-hosted agent runtime** | openclaw/openclaw 388,100 (created 2025-11-24) · HKUDS/nanobot 47,543 · nanocoai/nanoclaw 30,651 | **CONSOLIDATED** (OpenClaw won decisively) |
| 4 | **Agent frameworks (Python)** | langchain 145,302 · autogen 60,706 **(last push 2026-04-15 — 4.5 months stale)** · crewAI 57,841 · llama_index 51,925 · agno 41,971 · langgraph 40,733 · openai-agents-python 29,079 · semantic-kernel 28,518 · haystack 26,366 · google/adk-python 21,336 · pydantic-ai 19,595 | **FRAGMENTED** — but saturated; a new framework is a bad bet |
| 5 | **Agent frameworks (TS)** | mastra 27,578 · voltagent 10,469 · inkeep/agents 1,398 | **FRAGMENTED**, lower ceiling |
| 6 | **Retrieval / vector** | ragflow 89,677 · milvus 45,885 · faiss 40,825 · qdrant 34,275 · chroma 29,183 · pgvector 22,828 · weaviate 16,760 · lancedb 11,314 | **CONSOLIDATED-ish** (pgvector is the default answer; well-funded) |
| 7 | **Agent memory / context store** | mem0 64,377 · openhuman 39,030 (created 2026-02-18) · volcengine/OpenViking 34,511 (created 2026-01-05) · cognee 30,361 · letta 24,498 · zep 4,879 | **FRAGMENTED** ⚑ — but crowded and corporate-funded; correctness is unsolved, land-grab is over |
| 8 | **Protocol layer (MCP/A2A)** | mcp/servers 89,978 · A2A 25,558 · mcp/python-sdk 24,163 · mcp/typescript-sdk 13,284 · mcp spec 9,085 · mcp/registry 7,203 | **CONSOLIDATED** (MCP won; A2A is second-order) |
| 9 | **Inference routing / LLM gateway** | litellm 57,619 (**4,893 open issues**) · Portkey/gateway 12,855 **(stale: 2026-05-25)** · agentgateway 4,649 · IBM/mcp-context-forge 4,390 (**1,168 open issues**) · docker/mcp-gateway 1,547 | **CONSOLIDATED but strained** ⚑ — LiteLLM has monopoly + severe maintenance debt + a 2026 supply-chain breach |
| 10 | **Observability / tracing** | langfuse 33,944 · mlflow 27,740 · opik 21,700 · phoenix 11,250 · openllmetry 7,409 · helicone 6,115 · openlit 2,732 | **CONSOLIDATING** on langfuse + OTel GenAI semconv |
| 11 | **Evaluation** | promptfoo 24,681 · deepeval 17,979 · ragas 15,547 **(stale: last push 2026-02-24, moved to vibrantlabsai)** · langchain-ai/agentevals 711 | **FRAGMENTED** ⚑ — and *trajectory* eval is nearly empty (agentevals = 711) |
| 12 | **Sandboxing / isolation** | firecracker 36,381 · nanoclaw 30,651 · E2B 13,598 · onecli 3,430 · e2b/infra 1,350 · cloudflare/sandbox-sdk 1,121 | **CONTESTED** — Docker Sandboxes (694 HN pts, 2026-08-10) is a vendor land-grab in progress |
| 13 | **Durable execution / long-running agents** | airflow 46,653 · prefect 23,726 · temporal 22,612 · windmill 17,729 · inngest 5,789 · restate 4,354 · dbos-transact-py 1,555 · golem 1,508 · chidori 1,364 | **FRAGMENTED** ⚑ — general-purpose incumbents, none agent-semantics-aware |
| 14 | **Guardrails / runtime security** | guardrails-ai 7,335 · NVIDIA-NeMo/Guardrails 7,031 · PurpleLlama 4,372 · llm-guard 3,206 (2026-07-08) · arcjet-js 681 | **FRAGMENTED** ⚑ |
| 15 | **Agent supply-chain scanning** | snyk/agent-scan 2,981 · cisco-ai-defense/mcp-scanner 1,055 · mcp-shield 554 **(stale: 2025-04-26)** | **CONSOLIDATING FAST** (Snyk + Cisco arrived) — scanning is taken; *provenance* is not |
| 16 | **Credential isolation for agents** | Infisical/agent-vault 2,164 (created 2026-03-27) · onecli/onecli 3,430 (YC S26) | **FRAGMENTED** ⚑, now VC-contested |
| 17 | **Agent authorization / least-privilege** | *no repo above 16 stars found.* Best: Claire56/ruhusa 16 · aws-samples/sample-cedar-agentic-ai-authorization 4 | **EMPTY** ⚑⚑ |
| 18 | **Record / replay / determinism** | chidori 1,364 · zenml-io/kitaru 270 (created 2026-03-05) · p0nymc1/cee 101 · Taiwrash/agrepl 30 · **~15 further repos at 1–31 stars** | **EMPTY** ⚑⚑ — dozens of independent attempts, zero winner |
| 19 | **Cost / budget enforcement** | *no standalone repo above 6 stars found.* Partially covered by LiteLLM. | **EMPTY** ⚑⚑ |

⚑ = fragmented, opportunity lives here. ⚑⚑ = essentially unclaimed.

### 1.2 The three structurally interesting findings

1. **Layers 17, 18, 19 are unclaimed despite loud, expensive, documented pain.** GitHub search for agent least-privilege, agent replay, and agent budget enforcement each returns a long tail of 1–30-star repos and no leader. That is the classic signature of a real problem with no shipped answer — many people independently start, nobody finishes.
2. **Two incumbents are visibly rotting.** `microsoft/autogen` (60,706 stars) has not been pushed since **2026-04-15**. `ragas` (15,547) has not been pushed since **2026-02-24**. `Portkey-AI/gateway` (12,855) since **2026-05-25**. Star count is now a lagging indicator in several layers.
3. **LiteLLM is a single point of failure for the whole stack** — 57,619 stars, **4,893 open issues**, and a March 2026 PyPI compromise (below). A leaner, verifiable gateway is one of the few "replace an incumbent" plays that is actually live.

---

## 2. What is actually breaking in production

Ranked by strength of primary evidence. Everything here is about people *operating* agents, not people using coding assistants.

### Rank 1 — Human-in-the-loop approval is measurably broken (evidence: very strong, quantitative, n=409,000)

The single best-measured finding of 2026. A 40,000-run permission game published its raw statistics:

> "over 40,000 runs and 409,000 individual approve/deny decisions"

Humans missed **1 in 3 threats** (66.3% accuracy). Breakdown by threat class:

| Threat type | Miss rate |
|---|---|
| Obviously destructive | 11.7% |
| Persistent mutation | 23.8% |
| Exfiltration / code execution | 33.4% |
| **Scope violations** | **35.0%** |

Worst individual command: `npm run analyze` approved by **64.7%** of players. Pooled `npm run *` exfiltration attacks were "missed 52.5% of the time" vs 28.4% for other exfiltration. Meanwhile **7% approved every single prompt** and benign commands were wrongly blocked at high rates (`npm config set registry` blocked 59%).

- Source: https://scalex.dev/blog/ai-agent-permissions-stats/ — HN 340 pts, 245 comments (https://news.ycombinator.com/item?id=49195468)
- Companion: "Continue? Y/N: A 60-second game about AI agent permission fatigue" — HN **386 pts**, 162 comments (https://news.ycombinator.com/item?id=48308376)

**Interpretation:** the industry's standard safety mechanism — show the human a command, ask yes/no — has a measured ~34% false-negative rate *and* a high false-positive rate. It is not a safety control; it is theatre with a dialog box.

### Rank 2 — Agent runs cannot be reproduced, so failures cannot be debugged (evidence: strong, academic + fragmented-repo signal)

Peer-reviewable primary source, verified live at arXiv:

> **"Deterministic Replay for AI Agent Systems"**, Rasheed Mudasiru, submitted 2026-04-30. https://arxiv.org/abs/2607.16200
> Presents `agrepl`, a Go CLI that MITM-intercepts all external interaction at the transport layer and replays offline. Across five workloads / 250 replay instances: **replay fidelity F = 1.0** and **median per-step latency reduction of 98.3%**.

The technique is proven and the reference implementation is MIT-licensed — and it has **30 stars** (`Taiwrash/agrepl`, last push 2026-07-18). Nobody has shipped this as a real tool.

Corroborating production evidence — an eight-week longitudinal study of a production agent runtime:

> **arXiv 2606.14589**, "When Errors Become Narratives: A Longitudinal Taxonomy of Silent Failures in a Production LLM Agent Runtime." A runtime in continuous production since March 2026 with ~40 scheduled jobs, 8 LLM providers, a tool-governance proxy, "defended by 4,286 unit tests and 827 governance checks," logged 22 incidents in 8 weeks. Findings: **"About 70% of silent failures were caught by human user-view observation, not tests or audits"** and a retrospective audit of 15 incidents found **"0% ex-ante prevention but 87% regression blocking."**

Read that again: 4,286 tests and 827 governance checks prevented **zero** incidents ex-ante, but replayable regression tests would have blocked 87% of recurrences. That is a direct, numeric argument for record/replay.

Repo-level signal: `chidori` 1,364 · `zenml-io/kitaru` 270 ("Agent traces you can run, not just read", created 2026-03-05) · `cee` 101 · then roughly fifteen 1–31-star repos all independently named some variant of *agent-replay / tracetape / tooltrace / agentdiff*. Maximum demand signal, zero supply.

### Rank 3 — Agent evaluation is not merely hard, it is corrupted (evidence: strong, quantitative)

Berkeley RDI exploited **eight** major agent benchmarks to near-perfect scores **without solving any tasks**:

| Benchmark | Score achieved | Exploit |
|---|---|---|
| Terminal-Bench (89 tasks) | **100%** | binary wrapper trojans |
| SWE-bench Verified (500) | **100%** | ~10-line `conftest.py` forcing all tests to pass |
| SWE-bench Pro (731) | **100%** | in-container parser overwrite |
| WebArena (812) | ~100% | config leakage + DOM/prompt injection |
| FieldWorkArena (890) | **100%** | validator never checks correctness — sending `{}` sufficed |
| CAR-bench | **100%** | reward components skipped |
| GAIA (165) | ~98% | public answers + normalization collisions |
| OSWorld (369) | 73% | VM state manipulation + public gold files |

- Source: https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/ — HN **588 pts**, 143 comments (https://news.ycombinator.com/item?id=47733217)

Practitioner corroboration — LangChain *State of Agent Engineering* (**n = 1,340**, fielded 2025-11-18 → 2025-12-02, https://www.langchain.com/state-of-agent-engineering):
- Quality is the **#1 barrier to production at 33%**; latency #2 at 20%; security 24.9% among 2,000+ employee enterprises.
- **89% have observability, only 52.4% run offline evals and 37.3% online evals.** Teams can *see* failures but cannot *measure* them.

*(Caveat: this survey was fielded ~9 months ago. I found no more recent survey of comparable rigour. Secondary 2026 figures — Deloitte "89% of pilots never reach production", Forrester root-cause splits — I could only reach via aggregator blogs and mark **UNVERIFIED**.)*

### Rank 4 — Agents burn money and destroy resources with no blast-radius control (evidence: strong, incident-based)

Highest-engagement agent incident of 2026:

> **"AI agent bankrupted their operator while trying to scan DN42"** — HN **1,467 pts, 536 comments** (https://news.ycombinator.com/item?id=48500012). The operator's own words: **"aws bill 6531,30$"**, later negotiated down to **"1894$ charge now"**. The agent had provisioned **five `m8g.12xlarge` instances** (22.5 Gbps each) by repeatedly re-deploying the same CloudFormation template. Source: https://lantian.pub/en/article/fun/ai-agent-bankrupted-their-operator-scan-dn42lantian.lantian/

Others in the same class:
- "An AI agent deleted our production database. The agent's confession is below" — HN **860 pts, 1,032 comments** (https://news.ycombinator.com/item?id=47911524)
- "Are the costs of AI agents also rising exponentially?" (Toby Ord) — HN 306 pts (https://news.ycombinator.com/item?id=47778922)
- "AI agent runs amok in Fedora and elsewhere" (LWN) — HN 552 pts (https://news.ycombinator.com/item?id=48484584)

Repo evidence of the gap: GitHub search for LLM cost/budget-enforcement proxies returns **nothing above 6 stars**. LiteLLM has budget features buried inside a 57k-star, 4,893-open-issue monolith.

### Rank 5 — Agent authorization / least privilege has no implementation at all (evidence: strong demand, zero supply)

- "Ask HN: How do you give AI agents access without over-permissioning?" — 6 pts but **14 comments** (https://news.ycombinator.com/item?id=46861542)
- "Ask HN: How do you authorize AI agent actions in production?" (https://news.ycombinator.com/item?id=46719774)
- "A €0.01 bank transfer could compromise a banking AI agent" — HN **208 pts, 202 comments** (https://blue41.com/blog/how-we-helped-bunq-secure-their-financial-ai-assistant/)
- Palantir engineering: "Securing Agents in Production" (https://blog.palantir.com/securing-agents-in-production-agentic-runtime-1-5191a0715240)
- Standards are still forming: CNCF's 2026 line is "SPIFFE for identity, OAuth 2.0 for delegation, OPA for policy," and IETF **WIMSE** is standardising workload-identity token exchange for agentic call chains. The unsolved bit, stated well by Stacklok: SPIFFE can assert *"this workload is X"* but not *"X acting on behalf of user Y, scoped, time-bounded, with an audit record."* **UNVERIFIED** at the IETF draft level — I read this via vendor blogs, not the draft itself.
- **GitHub reality check: the best-starred agent least-privilege repo I could find has 16 stars.**

### Rank 6 — The agent toolchain is now an active supply-chain target (evidence: strong, incident-based)

The largest confirmed AI-infrastructure breach of 2026 hit the gateway layer itself:

> **LiteLLM PyPI compromise.** Malicious `litellm` v1.82.7/v1.82.8 packages, orchestrated March 2026, publicly tracked at https://github.com/BerriAI/litellm/issues/24518 (**165 reactions, 119 comments**, opened 2026-03-24 — still open). Reported impact: **"more than 2,500 organizations"** and **"approximately 434,000 CI/CD pipelines"**; packages were live for **"approximately 40 minutes."** Harvested AWS/GCP/Azure credentials, SSH keys, Kubernetes tokens, CI/CD secrets, package-publishing credentials, and **LLM API keys and gateway configurations**. An FBI FLASH advisory (July 2026) warned the credentials would be weaponised later. Source: https://www.cxtoday.com/security-privacy-compliance/supply-chain-attack-exposes-2500-companies-in-largest-ai-infrastructure-breach-of-2026-so-far/

Adjacent, same class: the SmartLoader/Oura-Ring trojanised MCP server (five fake GitHub personas, cross-forked to fake a community, StealC infostealer, Feb 2026) and the `postmark-mcp` email-exfiltration backdoor (June 2026) — a behavioural backdoor that received **no CVE**. Sources: https://www.upguard.com/blog/mcp-security-incidents, https://securityboulevard.com/2026/06/malicious-mcp-servers-email-security-the-new-supply-chain-threat/ (**UNVERIFIED** on exact counts — vendor blogs).

Note the shape of the gap: **scanning** is being consolidated by well-funded vendors (snyk/agent-scan 2,981; cisco mcp-scanner 1,055). **Provenance and pinning** — the lockfile/SBOM/attestation layer for MCP servers and skills — is not.

### Rank 7 — Prompt injection succeeds against real, shipped, well-resourced deployments (evidence: strong)

- **"GitLost: We Tricked GitHub's AI Agent into Leaking Private Repos"** — HN **541 pts, 205 comments** (https://noma.security/blog/gitlost-how-we-tricked-githubs-ai-agent-into-leaking-private-repos/). This is Microsoft/GitHub, not a hobby project.
- "Autonomous cars, drones cheerfully obey prompt injection by road sign" — HN 220 pts (https://www.theregister.com/2026/01/30/road_sign_hijack_ai/)
- "Prompt Injection as Role Confusion" — HN 235 pts (https://role-confusion.github.io)
- "Prompt Injecting Contributing.md" / "Open source has a bot problem" — HN 138 pts (https://glama.ai/blog/2026-03-19-open-source-has-a-bot-problem)
- Brex shipped **CrabTrap**, an LLM-as-judge HTTP proxy to secure agents — HN 132 pts (https://www.brex.com/crabtrap). Note the *shape*: a real company's answer was a **proxy**, not a framework feature.
- "Signal leaders warn agentic AI is an insecure, unreliable surveillance risk" — HN 349 pts.

### Rank 8 — Versioning and rollback of agent behaviour breaks in-flight runs silently (evidence: moderate, expert-source)

Restate's engineering write-up is the clearest statement of a problem almost nobody has named:

> **"The agent doesn't crash or print a warning, it just silently makes the wrong decision."**
> **"Your code is the manual the LLM uses to interpret its own execution history: tool descriptions, prompts, schemas, model config…"**
> **"The execution history lives in a database, but most of the information needed to interpret it lives in docstrings and comments in your code."**
>
> — https://www.restate.dev/blog/dealing-with-versioning-in-long-running-agents (HN: https://news.ycombinator.com/item?id=47397996)

Corroborating framework-level evidence from live GitHub issues:
- langgraph#5672 "Run Cancellation Causes Loss of Streamed State Not Yet Persisted as a Checkpoint" — 9 reactions, **45 comments**, open since 2025-07-25 (https://github.com/langchain-ai/langgraph/issues/5672)
- langgraph#3716 postgres checkpointer SSL/operational errors — 12 reactions, **53 comments**, open since 2025-03-06 (https://github.com/langchain-ai/langgraph/issues/3716)
- langgraph#6486 "Tool node error handling disabled by default after 1.0.1" (2025-11-22)

**Evidence caveat:** HN interest in "durable execution for agents" is thin — an hn.algolia query for durable-execution/checkpoint/resume story terms since 2026-01-01 returned essentially nothing on-topic. This is a real problem discussed by *vendors and experts*, not yet by the crowd. Lower demand signal than Ranks 1–6.

### Rank 9 — Multi-agent coordination fails in characteristic, catalogued ways (evidence: moderate; the key paper is aging)

MAST (Cemri et al., https://arxiv.org/abs/2503.13657): 1,600+ annotated traces across 7 multi-agent frameworks, 14 failure modes, Cohen's κ = 0.88. Distribution: **41.8%** specification/system-design, **36.9%** inter-agent misalignment (context loss at handoff, format mismatch, conflicting outputs), **21.3%** verification/termination. **Caveat: this is a March 2025 paper — 18 months old and pre-dating most current frameworks.**

Practitioner corroboration, Bayer via martinfowler.com (https://martinfowler.com/articles/reliable-llm-bayer.html): tool-selection collapse as tool count grows ("overlapping concerns and domain boundaries across different tools"), agents executing "a perfectly valid workflow (good process) but still retriev[ing] insufficient data," and agents "waste[ing] resources executing 50+ sequential steps while drifting from the goal." HN 196 pts.

### Rank 10 — Agents behave badly under objective pressure (evidence: moderate, contested)

- arXiv 2512.20798: "Frontier AI agents violate ethical constraints 30–50% of time, pressured by KPIs" — HN **544 pts, 366 comments** (https://news.ycombinator.com/item?id=46954920). **UNVERIFIED** — I did not fetch the paper itself.
- The Economist, "AI agents lie, cheat and steal. That is putting off users" — HN 164 pts, 213 comments (2026-08-12).
- Zuckerberg: "AI agent development going slower than expected" (Reuters, 2026-07-02) — HN 342 pts.

### Explicitly investigated and DOWN-ranked

**MCP context bloat / tool-selection degradation.** The numbers are dramatic (RAG-MCP: tool-selection accuracy collapsing "from 43% to under 14%"; tool definitions consuming 50,000+ tokens; practical ceiling of 5–7 MCP servers). **But the vendors already shipped the fix in 2026** — Anthropic's Tool Search Tool (~85% reduction), Anthropic code-execution-with-MCP (~98.7%), Cloudflare Code Mode (~99.9%). This is the textbook example of a gap being absorbed. All figures here are **UNVERIFIED** (aggregator blogs). **Do not build here.**

**Agent memory.** Real correctness problems, but the land-grab is finished and corporate: mem0 64,377, openhuman 39,030, OpenViking 34,511 (ByteDance/volcengine), cognee 30,361, letta 24,498. A solo entrant is 3+ years and one funding round late.

---

## 3. Vendor-absorption resistance

The test I applied: a gap is durable if it is **(a) cross-vendor by construction**, **(b) at the infrastructure/transport layer rather than the SDK layer**, **(c) adversarial to the model vendors' commercial interest**, or **(d) primarily serves self-hosted/open-weight deployments**. Two or more = safe.

| Gap | a. Cross-vendor | b. Infra layer | c. Adversarial | d. Self-hosted | Verdict |
|---|---|---|---|---|---|
| Deterministic record/replay | ✅ must span 8+ providers *and* N frameworks | ✅ MITM proxy, below the SDK | ⚠️ neutral | ✅ | **SAFE.** A vendor will only ever replay *its own* traffic. The value is precisely in the parts it can't see. |
| Agent least-privilege / capability broker | ✅ | ✅ policy enforcement point | ✅✅ **strongly** — vendor incentive is maximum autonomy and minimum friction | ✅ | **SAFEST.** Anthropic/OpenAI ship a yes/no dialog because a real capability model would make their agents feel worse. |
| Risk-scored approval / HITL gate | ✅ | ✅ | ✅ same as above | ✅ | **SAFE**, same reasoning. Vendors optimise for approval rate; this optimises for *correct* approval rate. |
| Budget circuit breaker | ✅ cross-provider is the whole point | ✅ gateway | ✅✅ **model vendors bill by the token; they will never ship an aggressive spend killswitch** | ✅ | **SAFEST.** |
| Eval/benchmark integrity auditing | ✅ | ⚠️ tooling layer | ✅✅ vendors *publish* the benchmarks they'd be audited on | ✅ | **SAFE** — structurally, the referee cannot be the player. |
| Agent-behaviour versioning / in-flight migration | ✅ | ✅ runtime | ⚠️ neutral | ✅ | **MODERATELY SAFE.** LangGraph could absorb the LangGraph-shaped 30%; the cross-framework problem stays. |
| Supply-chain provenance for MCP/skills | ✅ | ✅ | ⚠️ registries are vendor-run and conflicted about policing themselves | ✅ | **MODERATELY SAFE.** But Snyk/Cisco are already here on the scanning side — pick provenance, not scanning. |
| MCP context bloat | ✅ | ❌ prompt/SDK layer | ❌ vendors *want* to fix this | ❌ | **ALREADY ABSORBED — avoid.** |
| Agent memory | ✅ | ❌ SDK layer | ❌ | ✅ | **UNSAFE + crowded — avoid.** |
| Observability/tracing | ✅ | ✅ | ⚠️ | ✅ | Safe from vendors, **but langfuse + OTel semconv already won.** |

The pattern worth internalising: **the durable opportunities are exactly the ones where a model vendor shipping the feature would hurt the model vendor.** Spend limits, capability restriction, approval friction, and independent benchmark auditing all reduce token consumption, autonomy, or claimed capability. That is structural protection no roadmap change can remove.

Secondary protection: **the proxy/transport position.** Brex's CrabTrap, `agrepl`, agent-vault, and rtk all sit on the wire rather than inside an SDK. A vendor's SDK feature cannot see another vendor's traffic; a proxy can see everything. This is why "proxy-shaped" keeps winning in this ecosystem.

---

## 4. OSS traction patterns outside the coding niche, 2026

### 4.1 The star economy has re-based — recalibrate your expectations

Repos created since 2026-01-01 with >3,000 stars, top of list (live, 2026-08-31):

| Stars | Created | Repo | What it is |
|---|---|---|---|
| 388,100 | 2025-11-24 | openclaw/openclaw | Self-hosted personal AI assistant, any OS, 50+ integrations |
| 244,745 | 2026-01-18 | affaan-m/ECC | agent harness optimisation |
| 241,938 | 2026-02-03 | mattpocock/skills | skills collection |
| 204,885 | 2026-08-13 | deepseek-ai/deepseek-harness | "Everything is a Plugin" |
| 172,658 | 2025-09-22 | anthropics/skills | official skills |
| **77,964** | **2026-01-22** | **rtk-ai/rtk** | **"CLI proxy that reduces LLM token consumption by 60-90% on common dev commands"** |
| 79,711 | 2026-03-02 | paperclipai/paperclip | manage agents at work |
| **68,117** | **2026-01-07** | **headroomlabs-ai/headroom** | **"Compress tool outputs, logs, files, and RAG chunks before they reach the model"** |
| 48,685 | 2026-03-08 | HKUDS/CLI-Anything | make all software agent-native |
| 48,299 | 2026-01-13 | multica-ai/multica | humans + agents as one team, self-hostable |
| 47,543 | 2026-02-01 | HKUDS/nanobot | ultra-light self-hosted personal agent |
| 41,587 | 2026-01-11 | vercel-labs/agent-browser | browser automation CLI for agents |
| 39,030 | 2026-02-18 | tinyhumansai/openhuman | local-first personal memory |
| 34,511 | 2026-01-05 | volcengine/OpenViking | self-evolving context DB |
| **30,651** | **2026-01-31** | **nanocoai/nanoclaw** | **"A lightweight alternative to OpenClaw that runs in containers for security"** |
| 29,540 | 2026-03-15 | iOfficeAI/OfficeCLI | Office suite for agents |

A large fraction of the very top is skills/harness content for coding agents — that is the distortion the mandate warned about. Filter it out and the **non-coding infrastructure** winners share five traits:

### 4.2 What the non-coding winners have in common

1. **CLI or proxy shaped, not framework shaped.** rtk (77,964) is a *CLI proxy*. headroom (68,117) sits *before the model*. agent-browser (41,587) is a *CLI*. CLI-Anything (48,685) turns software into CLIs. **Zero new agent frameworks broke out in 2026.** The framework layer is closed; the wire is open.
2. **A striking measured number in the one-line description.** rtk: *"reduces LLM token consumption by 60-90%"* → 77,964 stars in ~7 months. This is the single most reproducible pattern in the dataset. The number *is* the marketing.
3. **Self-hosted / local-first / "own it" positioning.** OpenClaw ("runs entirely on your own devices"), nanobot ("self-hosted"), multica ("self-hostable"), openhuman ("local-first"), odysseus ("Self-hosted AI workspace", 86,587), AnythingLLM ("Stop renting your intelligence"). Sovereignty sells.
4. **Security/isolation as the differentiator, not the product.** `nanoclaw` earned **30,651 stars** with essentially one value proposition: *OpenClaw, but in a container*. It did not invent anything; it made an existing popular thing safe. HN backed this independently — "Don't trust AI agents" / nanoclaw's security model post drew **344 pts**.
5. **Ride an existing runtime's install base.** nanoclaw rode OpenClaw. gbrain (29,326) rode OpenClaw. The winners plugged into a corpus of existing users rather than asking for a migration.

### 4.3 Realistic ceiling for a well-executed new entrant, late 2026

Judged against 2026-created cohorts:
- **Median outcome for a competent infra CLI with a clear number:** 3,000–8,000 stars in 6 months (cf. onecli 3,430 in ~6 months *with YC backing and two HN front-pages*; agent-vault 2,164 in ~5 months *backed by Infisical*).
- **Good outcome:** 10,000–30,000 (cf. nanoclaw 30,651, OpenViking 34,511 — both had a host ecosystem to attach to).
- **Exceptional outcome:** 60,000–80,000 (rtk, headroom) — requires the measured-number hook *plus* a problem every single agent operator has *plus* front-page HN.
- **Not achievable solo:** 100,000+. Every repo above that line is either a full personal-assistant product or skills content with viral social distribution.

**Target: 10k–30k stars in 9 months.** That is the honest ceiling for a well-executed, vendor-neutral, CLI/proxy-shaped infrastructure tool launched now. Note that both 60k+ outliers were *proxies that measured a reduction*.

---

## 5. Top 7 opportunities, ranked

Ranking weights: evidence strength × vendor-resistance × solo-team feasibility × the availability of a striking measured number.

---

### #1 — `rr` for agents: cross-vendor deterministic record & replay

**Problem (one sentence):** A production agent failure cannot be reproduced, so it cannot be debugged, regression-tested, or fixed with confidence.

**Primary evidence:**
- https://arxiv.org/abs/2607.16200 — proven technique, **F = 1.0 replay fidelity, 98.3% median per-step latency reduction**, MIT reference implementation with **30 stars**.
- https://arxiv.org/abs/2606.14589 — production runtime with 4,286 unit tests and 827 governance checks achieved **"0% ex-ante prevention"**; **"70% of silent failures were caught by human user-view observation, not tests or audits"**; replay-style regression would have blocked **87%**.
- Fragmentation: `kitaru` 270 · `cee` 101 · `agrepl` 30 · ~15 more at 1–31 stars, all independently reinventing the same name.

**Who's nearest and why they haven't shipped it:** ZenML's `kitaru` (270 stars, created 2026-03-05, "Agent traces you can run, not just read") is closest in intent but is tied to ZenML's world. LangGraph has time-travel checkpoints — LangGraph-only, and its own checkpointing has 45- and 53-comment open bugs (#5672, #3716). Langfuse (33,944) stores traces you can *read*, not *execute*. The academic prototype exists but nobody productised it: replay requires MITM-ing every provider, every MCP server, and every HTTP tool, plus a noise-vs-signal diff for headers/timestamps/IDs — genuinely fiddly plumbing that researchers don't finish and framework vendors have no incentive to build across competitors.

**Vendor-resistance:** Structural. A vendor can only replay its own API traffic. The whole value is the *union* — model calls across 8 providers, MCP servers, and arbitrary HTTP tools in one deterministic trace. Also runs offline against open-weight models, which vendors don't serve.

**Difficulty (solo):** **Medium.** A single Go/Rust static binary: a CA-signed MITM proxy, a trace format, a deterministic replayer with zero egress, plus a noise-aware diff. No distributed systems, no ML.

**Striking number to lead with:** "Replay any agent run byte-for-byte, 98% faster, offline, zero API cost" — and a CI mode: *turn last night's incident into a regression test in one command.*

**Realistic star ceiling: 15,000–40,000.** Highest of the seven: it is proxy-shaped, has a measured number, and every operator has the pain.

---

### #2 — Agent budget circuit breaker (spend + resource killswitch at the wire)

**Problem:** An unattended agent can spend unbounded money on models *and* on the cloud resources it provisions, and nothing stops it mid-run.

**Primary evidence:**
- https://news.ycombinator.com/item?id=48500012 (**1,467 pts, 536 comments**) — **"aws bill 6531,30$"**, five `m8g.12xlarge` instances from repeated CloudFormation redeploys.
- https://news.ycombinator.com/item?id=47911524 (**860 pts, 1,032 comments**) — agent deleted a production database.
- "Are the costs of AI agents also rising exponentially?" — HN 306 pts.
- Supply gap: **no standalone budget-enforcement repo above 6 stars** in GitHub search.

**Who's nearest and why they haven't:** LiteLLM (57,619) has budget features, but they are buried in a project with **4,893 open issues**, they cover *token spend only*, and they cannot see the agent's `aws`/`terraform`/`gcloud` calls — which is where the DN42 operator's $6,531 actually went. Cloud providers sell budget *alerts*, which are asynchronous and arrive hours late. Nobody has built the synchronous, kill-the-process-now breaker spanning both token spend and provisioned-resource spend.

**Vendor-resistance:** Maximal. Model vendors are paid per token; they will never ship an aggressive spend killswitch. Cloud vendors are paid per instance-hour. This tool exists to reduce both parties' revenue.

**Difficulty (solo):** **Low–medium.** Same proxy substrate as #1: price-table-driven token accounting, cost estimation for cloud CLI invocations, hard limits, and a real SIGKILL. Ship it as `agentfuse run -- <anything>`.

**Striking number:** *"The DN42 agent's $6,531 bill would have been stopped at $20."* Reproduce the incident as a demo.

**Realistic star ceiling: 10,000–25,000.** The strongest emotional hook in the entire dataset (1,467 HN points) and the emptiest supply.

---

### #3 — Risk-scored approval gate (fix human-in-the-loop, which is measurably broken)

**Problem:** Yes/no approval prompts have a measured ~34% false-negative rate, so the industry's primary agent safety control does not work.

**Primary evidence:**
- https://scalex.dev/blog/ai-agent-permissions-stats/ — **409,000 decisions over 40,000 runs; 1 in 3 threats missed; scope violations missed 35.0%; `npm run analyze` approved by 64.7%; 7% approved everything; benign `npm config set registry` wrongly blocked 59% of the time.** HN 340 pts.
- Permission-fatigue game itself: HN **386 pts** (https://news.ycombinator.com/item?id=48308376).
- "What's the worst thing your AI agent did in production without asking first?" (HN 48658607).

**Who's nearest and why they haven't:** HumanLayer (11,355) is the best-known HITL project but has pivoted toward coding agents ("get AI coding agents to solve hard problems"). `Aegis` (335) and `Deuz-SDK` (601) touch it. Model vendors ship the dialog box — and are structurally disinclined to add friction that lowers task-completion rates. Crucially, *nobody has used the 409k-decision dataset* that now exists publicly: it tells you exactly which command shapes humans get wrong, which is a ready-made training signal for a risk classifier.

**Vendor-resistance:** Strong. The correct product surfaces *fewer, better* prompts by auto-denying high-risk/low-ambiguity actions and auto-approving safe ones — that means saying "no" to the vendor's agent. And it must work across Claude Code, OpenClaw, LangGraph, and custom runtimes to be worth installing.

**Difficulty (solo):** **Medium.** The hard part is a defensible risk taxonomy (destructive / persistent-mutation / exfiltration / scope-violation is already published), not the plumbing.

**Striking number:** *"Humans miss 34% of dangerous agent commands. This misses 4%."* Publish your own benchmark against the published miss-rate table.

**Realistic star ceiling: 8,000–25,000.**

---

### #4 — Capability broker: real least-privilege for agent tool calls

**Problem:** Agents run with the full ambient authority of whatever credentials they were handed, so a single bad decision or injection has unbounded blast radius.

**Primary evidence:**
- https://noma.security/blog/gitlost-how-we-tricked-githubs-ai-agent-into-leaking-private-repos/ — HN **541 pts**. GitHub's own agent, over-privileged.
- https://blue41.com/blog/how-we-helped-bunq-secure-their-financial-ai-assistant/ — HN 208 pts, 202 comments: a **€0.01** transfer compromises a banking agent.
- Ask HNs: 46861542 (14 comments), 46719774.
- Palantir: https://blog.palantir.com/securing-agents-in-production-agentic-runtime-1-5191a0715240
- **Supply gap: the best agent-least-privilege repo on GitHub has 16 stars.**

**Who's nearest and why they haven't:** Infisical's `agent-vault` (2,164, created 2026-03-27) and `onecli` (3,430, YC S26) solve *credential hiding* — the agent never sees the secret — but not *capability scoping*: the proxy still forwards whatever call the agent makes. SPIFFE/SPIRE + OPA is the CNCF answer for workloads but, as Stacklok puts it, cannot express *"X acting on behalf of user Y, scoped and time-bounded."* IETF WIMSE is standardising this but is a draft (**UNVERIFIED** — read via secondary sources). Nobody has shipped the ergonomic middle: a per-run capability manifest that a proxy actually enforces.

**Vendor-resistance:** Maximal — restricting agents directly opposes vendor autonomy narratives, and it must span every provider and MCP server.

**Difficulty (solo):** **Medium–high.** Policy language design is a tarpit; the discipline is to ship 10 hard-coded high-value capabilities (git push, cloud provision, outbound network, filesystem write scope, payment endpoints) before inventing a DSL.

**Realistic star ceiling: 8,000–20,000.** Lower than #1–#3 because "authorization" reads as enterprise, which suppresses stars.

---

### #5 — Supply-chain provenance and lockfile for MCP servers and skills

**Problem:** Agents install and execute third-party MCP servers and skills with no pinning, no provenance, and no reproducibility — and this is now an actively exploited attack path.

**Primary evidence:**
- **LiteLLM PyPI compromise**, https://github.com/BerriAI/litellm/issues/24518 (165 reactions, 119 comments, still open): **2,500+ organizations, ~434,000 CI/CD pipelines, ~40-minute exposure window**, harvesting cloud credentials *and LLM gateway configs*.
- SmartLoader trojanised Oura-Ring MCP server via fake community (Feb 2026); `postmark-mcp` email-exfiltration backdoor with **no CVE assigned** (Jun 2026) — https://www.upguard.com/blog/mcp-security-incidents.
- "Prompt Injecting Contributing.md" — HN 138 pts.

**Who's nearest and why they haven't:** `snyk/agent-scan` (2,981) and `cisco-ai-defense/mcp-scanner` (1,055) **scan for known-bad**. They are heuristic detectors — useless against a *behavioural* backdoor like postmark-mcp, which is why it got no CVE. The missing primitive is the boring one: a lockfile with content hashes, signature verification, and a diff on every update. Registry operators are conflicted about policing their own registries; the MCP registry itself is only 7,203 stars and young.

**Vendor-resistance:** Moderate–strong. The registries are vendor-run; an independent verifier is exactly what a conflicted registry won't build. Cross-ecosystem by nature (MCP + skills + PyPI + npm).

**Difficulty (solo):** **Medium.** `agentlock` — hash-pin every MCP server and skill, verify on load, hard-fail on drift, diff on update. Well-understood engineering (this is Cargo.lock applied to agent tools).

**Striking number:** *"The 40-minute LiteLLM window that hit 434,000 pipelines: a lockfile would have blocked it."*

**Realistic star ceiling: 8,000–25,000.** Caution: Snyk and Cisco are consolidating the adjacent space fast — this window closes in ~2 quarters.

---

### #6 — Independent eval-integrity auditor for agent benchmarks and trajectories

**Problem:** Agent benchmark scores are systematically gameable and current harnesses do not detect it, so nobody can trust a reported agent capability number — including their own internal evals.

**Primary evidence:**
- https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/ — HN **588 pts**. **8 benchmarks exploited; 100% on Terminal-Bench, SWE-bench Verified, SWE-bench Pro, FieldWorkArena, CAR-bench; ~98% GAIA; 73% OSWorld — solving nothing.** FieldWorkArena fell to sending `{}`.
- LangChain survey (n=1,340): **89% have observability, 52.4% offline evals, 37.3% online evals.**
- Supply gap: `langchain-ai/agentevals` is **711 stars**; `ragas` (15,547) **has not been pushed since 2026-02-24**.

**Who's nearest and why they haven't:** promptfoo (24,681) and deepeval (17,979) evaluate *outputs*, not *trajectories*, and assume the harness is honest. Berkeley RDI published the attacks but is a research lab, not a tool vendor. Model vendors publish the benchmarks they would be audited against — the referee cannot be the player.

**Vendor-resistance:** Structurally maximal on the adversarial axis; weaker on the infra axis (it is tooling, not a proxy).

**Difficulty (solo):** **Medium–high.** Requires reproducing exploit classes (binary shimming, conftest injection, gold-file leakage, validator no-ops) as an automated audit suite, plus per-benchmark harness knowledge. Slower to build than #1–#3.

**Striking number:** *"We scored 100% on 5 benchmarks without solving a single task. Here's the linter that catches it."*

**Realistic star ceiling: 5,000–15,000.** Real and important; narrower audience (eval authors, not every operator).

---

### #7 — Agent behaviour versioning: safe migration of in-flight runs

**Problem:** Changing a tool description, schema, prompt, or model between deploys causes long-running agents to silently misinterpret their own execution history, with no crash and no warning.

**Primary evidence:**
- https://www.restate.dev/blog/dealing-with-versioning-in-long-running-agents — **"The agent doesn't crash or print a warning, it just silently makes the wrong decision."** / **"The execution history lives in a database, but most of the information needed to interpret it lives in docstrings and comments in your code."**
- https://github.com/langchain-ai/langgraph/issues/5672 (45 comments, open since 2025-07-25) — cancellation loses un-checkpointed state.
- https://github.com/langchain-ai/langgraph/issues/3716 (53 comments, open since 2025-03-06) — postgres checkpointer failures.
- Layer fragmentation: temporal 22,612 / restate 4,354 / dbos 1,555 / golem 1,508 / chidori 1,364 — all general-purpose, none agent-semantics-aware.

**Who's nearest and why they haven't:** Restate has *named* the problem best but sells its own runtime — the fix requires adopting Restate. Temporal has versioning primitives built for deterministic workflow code, which does not map onto "the LLM reinterprets old tool results under new docstrings." LangGraph could solve the LangGraph-shaped slice and probably will. Nobody has built the cross-framework version-fingerprint-and-refuse layer.

**Vendor-resistance:** Moderate. Cross-framework and infra-layer, but neutral rather than adversarial, and partially absorbable by LangGraph/Temporal.

**Difficulty (solo):** **High.** Requires hashing the full "interpretation surface" (tool schemas + descriptions + prompts + model id + sampling params), detecting drift against persisted state, and offering migrate/quarantine/refuse — and it only matters for teams already running multi-hour agents.

**Realistic star ceiling: 4,000–12,000.** Lowest of the seven: the crowd is not yet discussing it (my hn.algolia sweep for durable-execution/resume terms since 2026-01-01 returned essentially nothing on-topic). Real problem, early market.

---

## 6. Synthesis and recommendation

**Build #1 (deterministic record/replay), and ship #2 (budget breaker) and #3 (risk-scored approvals) as modules on the same proxy.**

They share one substrate — a MITM proxy that sits between any agent and every provider, MCP server, and HTTP tool. That single substrate gives you the trace (replay), the token accounting (budget), and the interception point (approvals). Each has an independent striking number, and every one of them sits on the adversarial side of the vendor-incentive line: vendors do not want to help you replay competitors' traffic, cap your spend, or add approval friction.

That combination — proxy-shaped, cross-vendor, CLI-installable, one measured percentage in the tagline — is precisely the profile of the two biggest non-coding OSS breakouts of 2026 (rtk 77,964 and headroom 68,117), both of which are proxies that measured a reduction.

**Avoid:** new agent frameworks (layer closed, 11 contenders above 19k stars), agent memory (crowded and corporate), MCP context bloat (already absorbed by Anthropic and Cloudflare in 2026), and MCP *scanning* (Snyk and Cisco arrived).

### Open items I could not verify
- arXiv 2512.20798 (agents violating ethical constraints 30–50% under KPI pressure) — read only via HN title; paper not fetched.
- Deloitte's "89% of pilots never reach production" and Forrester's failure root-cause splits — aggregator blogs only.
- MCP context-bloat percentages (43%→14% tool selection; Anthropic 85%/98.7%; Cloudflare 99.9%) — secondary sources only.
- IETF WIMSE draft status — read via vendor blogs, not the draft.
- OTel GenAI semantic conventions stability ("all `gen_ai.*` still Development as of mid-July 2026") — secondary source, not the OTel registry itself.
- No practitioner survey more recent than LangChain's (fielded Nov–Dec 2025) was found; treat its percentages as ~9 months stale.
