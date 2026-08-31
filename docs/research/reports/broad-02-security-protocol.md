# Agent Security, Identity, and the Protocol Layer — Open-Source Opportunity Assessment

**Research date:** 2026-08-31. All GitHub stars and dates verified live via authenticated `gh api` on 2026-08-31. All claims sourced; UNVERIFIED labels applied where a claim could not be traced to a primary source.

---

## 0. Executive summary

The protocol layer settled faster than expected. MCP is under the Linux Foundation's Agentic AI Foundation, shipped a major spec revision on 2026-07-28, and A2A hit v1.0 in March 2026. **Transport, discovery, and OAuth mechanics are standardized. Trust, identity federation, provenance, and risk semantics are not** — they sit in a queue of open SEPs, some nine months stale.

The most important verified finding in this report is that **detection-based defense is empirically dead, and the evidence is stronger than the brief suggested.** Two independent large-scale studies (67,453 skills; 37,288 runtime MCP servers) show security scanners agree at chance-corrected rates of κ ≤ 0.082 and Jaccard ≤ 15.66%, with 45.53% precision and 24.17% recall. This is not "scanners need tuning." This is "the signal is not there."

The corollary is the opportunity: if you cannot *detect* a malicious agent action, you must *constrain* it. Constraint mechanisms — capability attenuation, credential brokering, egress mediation, signed provenance — are architectural, not statistical, and they are where the open ground is.

But the honest counterweight: **vendors are absorbing the constraint layer aggressively at the single-agent-single-harness scope.** Claude Code ships native sandboxing with an egress-proxy allowlist. The durable opportunities are therefore all at the *cross-vendor, cross-agent, multi-principal* scope, which is precisely the scope a single vendor cannot own — and also the scope that smells most like enterprise sales.

---

## 1. Protocol layer state

### 1.1 MCP governance

| Fact | Value | Source |
|---|---|---|
| Governing body | Agentic AI Foundation (AAIF), under Linux Foundation | [LF press release](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation) |
| Announced | 2025-12-09 | ibid. |
| Inaugural projects | MCP (Anthropic), goose (Block), AGENTS.md (OpenAI) | ibid. |
| Platinum members | AWS, Anthropic, Block, Bloomberg, Cloudflare, Google, Microsoft, OpenAI | ibid. |
| Gold members incl. | Cisco, Datadog, Docker, IBM, Okta, Oracle, Runlayer, Salesforce, SAP, Tetrate | ibid. |
| Silver members incl. | Eve Security, Solo.io, Stacklok, WorkOS, Pydantic, Obot.ai | ibid. |
| MCP technical governance | Unchanged: Lead → Core → Maintainers → Contributors, via SEP process | AAIF/MCP docs |
| A2A in AAIF? | **No.** A2A is a separate Linux Foundation project (donated by Google, June 2025) | LF press releases |

Note the member list: **the security vendors are already inside the tent** (Okta, Cisco, Datadog, Stacklok, Eve Security, Runlayer, WorkOS). This is a meaningful signal for opportunity assessment — the vendor-neutral foundation is not vendor-free.

### 1.2 MCP spec: 2026-07-28 release

Primary source: [blog.modelcontextprotocol.io/posts/2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/)

| Change | Detail | Security relevance |
|---|---|---|
| Stateless core | `initialize`/`initialized` handshake and `Mcp-Session-Id` removed; each request self-describing via `_meta` | Removes session-fixation surface; shifts state to app layer |
| Multi Round-Trip Requests (MRTR) | `resultType: "input_required"`; client retries with `inputResponses` | Replaces server-initiated requests over open streams |
| Header-based routing | `Mcp-Method`, `Mcp-Name` HTTP headers required | **Explicitly designed so gateways and WAFs can route/meter without parsing JSON bodies** — the spec now assumes a mediation layer exists |
| Cacheable list results | `ttlMs`, `cacheScope` on `tools/list` etc. | Cache poisoning becomes a consideration |
| Authorization hardening | RFC 9207 issuer validation; DCR deprecated in favor of CIMD; credentials bound to issuing AS; `application_type` support | Closes real OAuth bugs |
| Enterprise-Managed Authorization (EMA) | Central IT control over which servers employees may connect to | Direct response to enterprise procurement blockers |
| Extensions framework | Tasks moved to `io.modelcontextprotocol/tasks` | |
| Deprecations | Roots, Sampling, Logging (12-month offramp); HTTP+SSE transport (1-year) | |

**The header-based-routing change is the single most commercially significant line in the spec.** MCP has formally conceded that a proxy sits between client and server, and has made that proxy's job cheap. That is a standards body building a road for a product category.

### 1.3 A2A

| Fact | Value |
|---|---|
| Governance | Linux Foundation (donated by Google Cloud, June 2025) |
| Version | v1.0, released 2026-03-12 |
| Key security feature | Signed Agent Cards — JWS (RFC 7515) + JCS canonicalization (RFC 8785) for domain verification |
| Adoption | 150+ organizations; production use at IBM, Cisco, SAP, ServiceNow; integrated in Google/Microsoft/AWS platforms |
| SDKs | Python, JS, Java, Go, .NET (Apache 2.0) |

A2A solved *agent identity attestation* (signed cards) before MCP solved *server identity attestation*. Worth noting: MCP's equivalent, SEP-3140 "Signed Capability Declarations," is still open with 0 reactions.

### 1.4 Agent identity / auth standards — the mess

| Effort | Body | Status | Note |
|---|---|---|---|
| WIMSE | IETF | WG active | Workload identity for service-to-service |
| `draft-reece-wimse-cross-org-delegation-00` | IETF | Individual draft | Cross-org delegated, attenuated, principal-bound authority — **explicitly an open problem** |
| `draft-klrc-aiagent-auth-00` | IETF | Individual draft | Maps SPIFFE/WIMSE/OAuth/OpenID SSF to agents; goal is to find gaps *before* inventing new protocols |
| AIMS (Agent Identity Management System) | Industry (AWS, Zscaler, Ping, Defakto) | Published 2026-03-02 | 9-layer stack mapping existing standards |
| AuthZEN | OpenID Foundation | Active; Identiverse 2026 track on agent-era authz | |
| SPIFFE/SPIRE | CNCF | Mature (spiffe 1,838★ / spire 2,505★) | The de facto substrate everyone maps onto |

**Verdict on identity: standardized in pieces, unstandardized as a whole.** SPIFFE gives you workload identity. OAuth gives you delegation for a *single* hop. Nothing standard expresses "user U authorized agent A, which sub-delegated to agent B, to perform action X on resource R for the next 90 seconds, and here is the verifiable chain." Every IETF draft above is an individual draft, not a WG document. That is a 2–4 year road.

### 1.5 What is still missing from MCP — evidence from open SEPs

Queried live via `gh api` on 2026-08-31 against `modelcontextprotocol/modelcontextprotocol` (9,085★, 137 open issues):

| SEP | Title | Created | Last updated | 👍 | Comments | Status |
|---|---|---|---|---|---|---|
| 2640 | Skills Extension | 2026-04-23 | 2026-08-29 | 86 | 33 | Open |
| 1488 | securitySchemes in Tool Metadata for Mixed-Auth Servers | 2025-09-18 | 2026-08-17 | 16 | 36 | **Open 11 months** |
| 2127 | MCP Server Cards — HTTP Server Discovery | — | — | 13 | — | Open |
| 1933 | **Workload Identity Federation** | 2025-12-05 | 2026-08-24 | 9 | 39 | **Open 9 months** |
| 1932 | **DPoP Profile for MCP** | 2025-12-05 | 2026-08-22 | 4 | 25 | **Open 9 months** |
| 1913 | **Trust and Sensitivity Annotations** | 2025-11-27 | 2026-08-24 | 1 | 42 | **Open 9 months, most-debated** |
| 2793 | **Tool Risk Metadata** | 2026-05-26 | 2026-07-29 | 1 | 6 | Open, stalling |
| 3140 | **Signed Capability Declarations & Trustworthy Trust Labels** | 2026-07-27 | 2026-08-26 | 0 | 15 | Open, new |
| 2448 | MCP server execution telemetry | — | — | 4 | — | Open |
| 1984 | Comprehensive Tool Annotations for Governance | — | — | 1 | — | Open |

**This table is the core finding of Section 1.** Every single trust primitive — workload identity federation, proof-of-possession tokens, sensitivity labels, risk metadata, signed capabilities — is *proposed but not standardized*, and the oldest have been debated for nine to eleven months with 25–42 comments and no resolution. High comment counts with low reaction counts is the signature of contested design, not neglect.

The spec standardized the *plumbing* (transport, OAuth mechanics, routing) and left the *semantics of trust* to implementations. That is the gap.

---

## 2. The real security problems: what is actually happening

### 2.1 The detection-failure result — VERIFIED, with a correction

The brief attributed "scanner agreement κ 0.01–0.18" to Trail of Bits. **This is misattributed, and the real numbers are worse (i.e. stronger evidence).** Two separate bodies of work exist:

**(a) ClawHub Security Signals** — arXiv [2606.01494](https://arxiv.org/abs/2606.01494), Koc, Erichsen, Tomlinson, Rivera, Appel, Paz; submitted 2026-05-31. Dataset: **67,453** public agent-skill versions. Three scanner families: VirusTotal, static heuristic analysis, NVIDIA SkillSpector.

Verified by extracting Table 4 from the PDF directly:

| Scanner pair | Jaccard (raw agreement) | Cohen's κ |
|---|---|---|
| VirusTotal ∩ Static | 0.065 | 0.054 |
| VirusTotal ∩ SkillSpector | 0.094 | 0.045 |
| Static ∩ SkillSpector | 0.104 | **0.082** |

Joint positive patterns: only **0.69%** of skills flagged by all three; **81.9%** of flagged skills flagged by exactly one scanner; 47.22% flagged by none.

The structural finding is sharper than the headline: disagreement is **structured by attack surface**, not random. SkillSpector (semantic agentic-risk) is positive on 75.3% of *suspicious* rows but only **6.8%** of *malicious* rows. VirusTotal is positive on **72.8%** of malicious rows. Quoting the paper: "The tooling that catches a credential-stealer is not the tooling that catches an over-privileged, under-disclosed automation skill." And: **24.3% of malicious verdicts had no positive scanner signal of any kind** — the registry reached "malicious" from provenance, metadata, and moderation context alone.

> Author conclusion (verbatim from abstract): "These results show that agent-skill security requires layered governance, not single-scanner allow/block decisions."

**(b) MCPZoo / "Rethinking MCP Security"** — arXiv [2607.11086](https://arxiv.org/html/2607.11086v1). Dataset: **37,288** unique runtime-capable MCP servers (of 64,611 collected). Eight scanners: Agent-Scan (Snyk), A.I.G (Tencent), MCP-Scanner (Cisco AI Defense), MCPScan (Ant Group), MCPSafetyScanner, mcp-gateway (Lasso), nova-proximity, mcp-armor.

| Metric | Value |
|---|---|
| Risk rate spread across scanners | **0.54%** (MCPSafetyScanner) → **80.04%** (MCPScan) |
| Flagged risky by ≥1 scanner | 96.89% |
| Average Jaccard similarity | **15.66%** |
| Category-specific similarity | 3.36–5.98% |
| Best pairwise overlap | 47.80% |
| **Mean precision (manual validation)** | **45.53%** (range 10.40%–96.88%) |
| **Recall vs CVE ground truth** | **24.17%** |

> Author conclusion: reframe from "MCP servers are unsafe" to "**current MCP security scanners are not yet reliable enough to support ecosystem-level security claims**"; treat outputs as "potential risks rather than confirmed vulnerabilities."

**(c) Trail of Bits** — ["The sorry state of skill distribution"](https://blog.trailofbits.com/2026/06/03/the-sorry-state-of-skill-distribution/), 2026-06-03; corroborated by [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-agent-skill-scanner-bypass-20260610-csa/), 2026-06-10. This is a *qualitative bypass* study, not a kappa study. Four constructed malicious skills vs ClawHub (VirusTotal + guard model), Cisco skill-scanner, and skills.sh (Gen Agent Trust Hub, Socket, Snyk):

| Attack | Mechanism | Result |
|---|---|---|
| Padding | 100,000 newlines before payload | Scanner truncated file, missed payload |
| .docx extraction | Executable instructions inside XML archive | Evaded pattern matching |
| Python bytecode poisoning | Malicious `.pyc`, benign source (xz-utils pattern) | Evaded source analysis |
| Prompt injection | "Corporate registry" framing to LLM analyzer | Convinced LLM the redirect was legitimate |

"No single scanner caught all four malicious skills. Some caught none." Socket produced no Critical/High alerts under any condition *including against unobfuscated malicious skills*. Three of four attacks took under an hour to build. ToB's recommendation: "Don't outsource trust to a scanner" — instead curated repos, org-managed plugins, version pinning, least-privilege execution.

**Synthesis.** Three independent teams, two methodologies (statistical agreement + adversarial bypass), three datasets, same conclusion. The scanning approach fails for a structural reason: **a static scanner gives the adversary unlimited offline attempts against a fixed oracle.** No amount of model improvement fixes an unlimited-retry game. This is the strongest empirically-grounded architectural claim in the whole space.

**Correction to record:** the κ figure is 0.045–0.082 (ClawHub, n=67,453), not 0.01–0.18, and it is not Trail of Bits.

### 2.2 Real incidents — actually happening, not theoretical

| Date | Incident | Evidence class | Detail |
|---|---|---|---|
| 2025-09-25 | **postmark-mcp** npm backdoor | **Confirmed in-the-wild** | First confirmed malicious MCP server. Silently BCC'd every sent email to attacker domain. ~1,643 downloads / ~1,500 weekly active installs; est. 3,000–15,000 corporate emails/day exfiltrated for >1 week. Inherited pre-authorized corporate API keys. |
| 2025-11 | Google Antigravity data exfil via indirect prompt injection | Confirmed | HN 768 points, 215 comments — largest agent-security discussion found |
| 2025-08 | GitHub Copilot RCE via prompt injection (CVE-2025-53773) | CVE | |
| 2026-01→02 | **30+ CVEs filed against MCP servers/clients/infra in 60 days** | CVE wave | Includes CVSS 9.6 RCE in a package with ~500k downloads |
| 2026-02 | **Moltbook** platform DB misconfiguration | Confirmed breach | 1.5M agent keys exposed in plaintext |
| 2026-03 | **TeamPCP** supply-chain campaign vs LiteLLM | Confirmed | Harvested SSH keys, cloud creds, LLM API keys, DB passwords; est. 500,000 corporate identities affected |
| 2026-06-03 | **Agentjacking** (Tenet Security) | Confirmed, disclosed | Fake Sentry error events injected via *public DSN*; Sentry MCP server feeds them to coding agent as real bugs; agent reads `.env`/`~/.aws/config` and exfiltrates. 2,388 orgs found exposed; 100+ agents acted on injected errors in controlled testing; a ~$250B Fortune 100 company's agent executed the payload. **Sentry declined to fix at the root, calling it "technically not defensible."** |
| 2026-07-20→24 | **Pillar Security sandbox-escape series** | Confirmed, multi-vendor | Escapes/boundary bypasses reproduced across Cursor, Codex, Gemini CLI, Antigravity. Claude Code shipped 4 consecutive releases in 5 days closing symlinked working dirs, git redirection out of worktree, leftover worktrees, unprompted network egress. Cursor workspace-hook escape = **CVE-2026-48124**, patched in 3.0.0. |
| 2026 | Claude Code OAuth token theft via MCP hijacking (Mitiga) | Disclosed research | Silent redirect of MCP traffic → OAuth token interception → persistent access to connected SaaS |
| 2026-03-10 | Windsurf CVE-2026-30615 | CVE | Attacker-controlled HTML → modifies local MCP config → registers malicious STDIO server → arbitrary command exec, **no user interaction** |
| — | OX Security: MCP STDIO command injection | Systemic | STDIO transport passes params to host shell unsanitized; reported to affect Cursor, VS Code, Windsurf, Claude Code, Gemini-CLI |

**Theoretical vs real:** prompt injection, malicious MCP servers, tool poisoning, supply-chain compromise of the agent tool ecosystem, credential theft, confused deputy, and sandbox escape are **all now confirmed in the wild or in credible reproduced research**. What remains largely theoretical: multi-agent collusion, agent-to-agent worm propagation at scale, and model-weight-level backdoors triggered by tool context. The brief's framing that we should separate real from theoretical is answered bluntly — **almost everything on the list is real now**.

Supporting aggregate stats (secondary sources, treat as directional): HackerOne logged a **540% surge** in prompt-injection reports; Trend Micro found **492 MCP servers exposed to the open internet with zero authentication**; **47–53%** of orgs report an AI agent exceeding permissions or causing an incident; **82%** of enterprises have agents/workflows their security teams did not know existed; **53%** of MCP servers rely on long-lived static secrets and only **8.5%** use OAuth. *(These are vendor/blog aggregates; I could not trace each to a primary methodology — treat as UNVERIFIED in precise magnitude, directionally consistent with the confirmed incidents above.)*

### 2.3 The alternative architecture

Since detection fails, the field has converged on constraint. The canonical statements:

- **Lethal trifecta** (Simon Willison, 2025-06-16): private data + untrusted content + exfiltration vector = exploitable. Remove any one leg.
- **Agents Rule of Two** (Meta AI, Nov 2025): an agent session may satisfy at most two of {processes untrusted input, accesses sensitive data, changes state / communicates externally}. Meta's framing is explicitly interim — "until robustness research allows us to reliably detect and refuse prompt injection." Meta also floats **declarative Rule-of-Two configuration in tool calls** so a call deterministically succeeds, fails, or escalates to approval. *No such declaration exists in the MCP spec today* — cf. stalled SEP-1913 / SEP-2793.
- **Revocable capabilities** — "Lingering Authority," arXiv [2606.22504](https://arxiv.org/abs/2606.22504). Names the failure mode precisely: *"Coding agents often receive broad tool access for an entire task, even when a resource is needed only for one subgoal. We call this gap lingering authority."* Their PORTICO reference monitor implements request→grant→invoke with automatic expiry; rejects 10/10 post-closure capability reuses vs 0/10 for the non-revoking baseline. Small-scale, but the framing is right.
- **Credential brokering** — SANS, Kenneth G. Hartman, 2026-05-15. CB4A: agents never hold real credentials; they get short-lived (seconds–minutes), narrowly-scoped, **agent-identity-bound** proxy tokens that cannot be replayed. Split Policy Decision Point (decides, holds no creds) from Credential Delivery Point (mints, cannot decide). Built on SPIFFE + OAuth 2.0 + canary credentials.
- **Layered governance / provenance** — the ClawHub conclusion; and note that 24.3% of that registry's malicious verdicts came from *provenance and moderation context with zero scanner signal*. Provenance outperformed scanning on the hardest cases.
- **NSA/CISA** published a Cybersecurity Information Sheet on MCP security, 2026-06-02 (`media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF`). **UNVERIFIED CONTENT** — the URL returned HTTP 403 to automated fetch; existence confirmed via search indexing only. Worth a manual read; a US-government MCP guidance document is a strong procurement lever.

**The architectural consensus, stated plainly:** you cannot classify your way out. You must (1) restrict what the agent *can* do (capabilities, attenuation, expiry), (2) mediate what leaves (egress), (3) never let the agent hold the real credential (brokering), (4) know where the code came from (provenance), and (5) produce evidence afterward (attestable audit).

---

## 3. Category census — live GitHub data (verified 2026-08-31)

### 3.1 MCP gateways / proxies — **CONSOLIDATED (and foundation-captured)**

| Repo | ★ | Last push | Note |
|---|---|---|---|
| **agentgateway/agentgateway** | **4,649** | 2026-08-30 | **Linux Foundation project** (donated by Solo.io, Aug 2025). 228 contributor pages. Full MCP + A2A. Created 2025-03-18. |
| octelium/octelium | 4,030 | 2026-08-30 | General zero-trust access platform, not agent-specific |
| AmoyLab/Unla | 2,215 | 2026-08-27 | API→MCP conversion gateway |
| stacklok/toolhive | 2,056 | 2026-08-30 | Enterprise MCP server runtime/management; Stacklok is AAIF Silver |
| docker/mcp-gateway | 1,547 | 2026-08-26 | Docker official |
| agentic-community/mcp-gateway-registry | 886 | 2026-08-28 | |
| microsoft/mcp-gateway | 805 | 2026-08-25 | Microsoft official |
| TheLunarCompany/lunar | 484 | 2026-08-30 | |
| lasso-security/mcp-gateway | 384 | **2026-01-22** | **Stale 7 months** |

**Flag: CONSOLIDATED and CLOSED.** The winner (agentgateway) is inside the Linux Foundation, backed by Solo.io, has ~228 contributors, and the MCP spec itself added `Mcp-Method`/`Mcp-Name` headers to make gateway routing cheap. Microsoft and Docker both ship official gateways. HN corroborates saturation: MCP-gateway Show HNs cluster at 3–14 points. Do not enter here.

### 3.2 Agent sandboxes — **CONSOLIDATED at the primitive layer, ACTIVE at integration, and BEING ABSORBED**

| Repo | ★ | Last push | Layer |
|---|---|---|---|
| firecracker-microvm/firecracker | 36,381 | 2026-08-28 | Primitive (microVM) |
| google/gvisor | 19,197 | 2026-08-30 | Primitive (syscall interposition) |
| e2b-dev/E2B | 13,599 | 2026-08-28 | Commercial-OSS sandbox platform |
| microsandbox/microsandbox | 8,024 | 2026-08-31 | Self-hosted microVM |
| **anthropic-experimental/sandbox-runtime** | **5,093** | 2026-08-28 | **Vendor absorption** |
| dagger/container-use | 4,028 | 2026-08-17 | |
| kubernetes-sigs/agent-sandbox | 3,685 | 2026-08-30 | K8s SIG — upstream capture |
| earendil-works/gondolin | 2,067 | 2026-07-06 | Linux microVM + TS control plane |
| cloudflare/sandbox-sdk | 1,121 | 2026-08-28 | Vendor |
| superhq-ai/shuru | 848 | 2026-08-05 | macOS/Linux local microVM |
| BitMiracle-AI/Dormice | 937 | 2026-08-14 | E2B-compatible self-hosted |
| buildkite/cleanroom | 65 | 2026-08-29 | Policy-controlled microVM |

**Flag: DO NOT ENTER.** Firecracker/gVisor own the primitive. Kubernetes SIG owns the orchestration. Anthropic ships `sandbox-runtime` (5,093★) and Claude Code has native sandboxing since v2.1.0 **including an egress-proxy allowlist with `allowedDomains` and `strictAllowlist`**. HN interest is high (Tilde.run 205p, OneCLI Launch HN 88p, "A deep dive on agent sandboxes" 68p) but that reflects a crowded, well-funded race, not an opening. Note also "Ask HN: Why are so many rolling out their own AI/LLM agent sandboxing solutions" (32p, 18c, 2026-01-20) — fragmentation exists, but every major vendor is resolving it in-house.

**Important nuance:** sandboxes are consolidated but *not correct*. Pillar Security reproduced escapes across Cursor, Codex, Gemini CLI, and Antigravity; the CBSE class (write an artifact that a trusted component outside the sandbox later executes) defeats process/container/OS isolation entirely. So the *isolation primitive* is solved and captured; the *trust-handoff boundary* is neither. That distinction matters for Section 6.

### 3.3 MCP security scanners — **GRAVEYARD, CONFIRMED**

| Repo | ★ | Last push |
|---|---|---|
| invariantlabs-ai/mcp-scan | 2,981 | 2026-08-28 |
| Synvoya/codeinspectus | 44 | 2026-08-25 |
| sidhpurwala-huzaifa/mcp-security-scanner | 21 | 2026-07-13 |
| aws-samples/sample-mcp-security-scanner | 15 | 2026-05-13 |
| DMontgomery40/mcp-security-scanner | 12 | 2026-03-23 |
| Helixar-AI/sentinel | 10 | 2026-04-22 |
| alexandriashai/mcp-guardian | 6 | 2026-07-29 |
| badchars/mcp-security-scanner | 5 | 2026-08-12 |

HN evidence (Algolia, stories since June 2025):

| Points | Date | Title |
|---|---|---|
| 168 | 2025-10-27 | MCP-Scanner – Scan MCP Servers for vulnerabilities |
| 5 | 2025-11-06 | Open-source MCP Security scanner |
| 3 | 2025-12-13 | MCP Security Scanner |
| 3 | 2026-01-07 | Cisco MCP Scanner Behavioural Code Scanning |
| 3 | 2026-03-08 | Show HN: Golf Scanner |
| 2 | 2026-03-06 | Show HN: MCPSec – OWASP MCP Top Scanner |
| 1 | 2026-03-09 | Show HN: Sentinel – OSS MCP security scanner |
| 1 | 2025-11-11 | MCP Security Scanner |
| 1 | 2025-12-03 | Scanner MCP |

**Flag: DEAD — and the brief's diagnosis needs refining.** The parent research said "~15 near-identical Show HNs at 1–5 points"; confirmed. But the correct causal story is not "the category is oversubscribed." It is **the approach is empirically invalid** (Section 2.1): κ ≤ 0.082, precision 45.53%, recall 24.17%, and 3-of-4 adversarial bypasses buildable in under an hour. One exception proves the rule: invariantlabs-ai/mcp-scan at 2,981★ succeeded by *pivoting* — its description now reads "Security scanner for AI agents, MCP servers **and agent skills**," and its adjacent work is Toxic Flow Analysis (dataflow reachability), which is a constraint/analysis technique, not a signature matcher.

So: **the scanning approach is dead; the underlying need — "should I trust this artifact?" — is unmet and now demonstrably unmeetable by classification.** That need routes to provenance and capability restriction instead.

### 3.4 Egress / network policy for agents — **THINLY POPULATED, PARTIALLY ABSORBED**

| Repo | ★ | Last push | Note |
|---|---|---|---|
| qpoint-io/qtap | 1,457 | 2026-08-25 | eBPF pre-encryption traffic capture (general, not agent-specific) |
| step-security/harden-runner | 1,258 | 2026-08-30 | CI/CD egress EDR — the closest *proven* analogue |
| **luckyPipewrench/pipelock** | **824** | 2026-08-31 | Created 2026-02-08. "AI agent firewall for MCP security and agent egress… emits mediator-signed action receipts: verifiable audit evidence from outside the agent." |
| FootprintAI/Containarium | 276 | 2026-08-30 | eBPF egress policy + SSH-native isolation |
| michaelneale/agent-seatbelt-sandbox | 58 | 2026-02-11 | macOS native sandbox to stop egress |

**Flag: CONTESTED, NOT EMPTY, AND ABSORPTION IS ACTIVE.** Claude Code already ships an egress allowlist proxy. But note the mechanism: Anthropic's docs describe network isolation via **a local HTTP proxy, not kernel blocking** — "well-behaved HTTP clients route through a localhost proxy." A non-well-behaved process (raw socket, DNS tunneling, a subprocess that ignores `HTTP_PROXY`) is not covered. That is a real, verifiable gap in the absorbed implementation. `harden-runner` proves the eBPF-based version of this is a viable OSS category (1,258★ in CI/CD). pipelock at 824★ in under 7 months is the fastest-growing thing in this census and is already staking the combined egress+receipts claim.

### 3.5 Policy / authorization engines — **CONSOLIDATED (generic), EMPTY (agent-specific)**

| Repo | ★ | Last push |
|---|---|---|
| open-policy-agent/opa | 12,179 | 2026-08-28 |
| authzed/spicedb | 7,002 | 2026-08-28 |
| openfga/openfga | 5,679 | 2026-08-28 |
| ory/keto | 5,392 | 2026-08-24 |
| cerbos/cerbos | 4,563 | 2026-08-31 |
| cedar-policy/cedar | 1,701 | 2026-08-28 |
| permitio/permit-mcp | 3 | **2025-05-05** (abandoned) |

**Flag: the engines are consolidated; the agent binding is empty.** OPA/Cedar/OpenFGA/SpiceDB are mature and will not be displaced. But the gap between them and an agent tool call is enormous and unbridged: nobody has a standard way to express "this `tools/call` carries untrusted-derived arguments, on behalf of principal U via delegation chain U→A→B, touching sensitivity class S." The 3★ abandoned `permitio/permit-mcp` is the tombstone for the naive version of this. The *hard* version — deriving the policy inputs (taint, provenance, delegation depth, sensitivity) rather than just evaluating them — is untouched.

### 3.6 Secret brokers for agents — **EMPTY**

| Repo | ★ | Last push |
|---|---|---|
| Infisical/infisical | 29,036 | 2026-08-30 |
| hashicorp/vault | 36,190 | 2026-08-28 |
| openbao/openbao | 7,214 | 2026-08-28 |
| spiffe/spire | 2,505 | 2026-08-29 |
| spiffe/spiffe | 1,838 | 2026-08-27 |
| tashian/tsm | 9 | 2026-05-31 |
| cswink267/agent-vault | 1 | 2026-08-08 |
| dennisMeeQ/clavum / mizrahidaniel/agent-secrets-vault | 0 / 0 | 2026-02 |

**Flag: STRIKINGLY EMPTY.** Vault/OpenBao/Infisical are mature *human and service-account* secret stores. SPIFFE/SPIRE is mature *workload identity*. The agent-specific broker — the CB4A architecture SANS described in May 2026 — has **no credible OSS implementation**: the entire agent-secrets-vault cohort is 9★, 1★, 0★, 0★. Meanwhile the incident record is dominated by exactly this failure: postmark-mcp inherited pre-authorized corporate API keys; Moltbook leaked 1.5M agent keys in plaintext; TeamPCP harvested ~500k identities' credentials from an AI gateway; Agentjacking's payload was literally "read `.env` and `~/.aws/config`." **The most-exploited weakness has the emptiest tooling category in this census.**

### 3.7 Audit / provenance / attestation — **EMPTY, EARLY MOVER PRESENT**

No established OSS incumbent. `pipelock` (824★) is the only project found staking "mediator-signed action receipts… verifiable audit evidence from outside the agent." Adjacent primitives are mature (Sigstore, in-toto, JWS/JCS — the latter two already used by A2A v1.0 signed Agent Cards). MCP-side: SEP-2448 (execution telemetry, 4👍) and SEP-3140 (signed capability declarations, 0👍) are both open and unadopted.

Academic support: [Trustworthy MCP Registry blueprint](https://doi.org/10.3390/fi18050243) proposes RFC 8615 discovery + Sigstore keyless signing + JCS/JWS runtime message signing, and identifies the precise unsolved problem: *"an unverified registry in which servers can dynamically mutate their capabilities during a live session, without any mechanism for a client to verify that the update was authorized by the original software publisher."* Note also that Sigstore alone is insufficient here — its transparency log records **who signed, not which registry distributed**, so identical signatures appear regardless of distribution path.

### 3.8 Registries — **CONSOLIDATED**

`modelcontextprotocol/registry` 7,203★ (official, AAIF); `punkpeye/awesome-mcp-servers` 93,367★; `modelcontextprotocol/servers` 89,978★; Solo.io contributed `agentregistry` to CNCF in March 2026. Closed.

### 3.9 Census summary

| Category | Leader | ★ | Verdict |
|---|---|---|---|
| MCP gateways/proxies | agentgateway (LF) | 4,649 | **Consolidated + foundation-captured** — closed |
| Sandbox primitives | Firecracker / gVisor | 36,381 / 19,197 | **Consolidated** — closed |
| Agent sandbox integration | K8s SIG / Anthropic / E2B | 3,685 / 5,093 / 13,599 | **Being absorbed** — closed |
| MCP security scanners | mcp-scan (pivoted) | 2,981; rest ≤44 | **Dead approach** — invalid, not merely crowded |
| Registries | modelcontextprotocol/registry | 7,203 | **Consolidated** — closed |
| Egress / network policy | pipelock / harden-runner | 824 / 1,258 | **Contested, partially absorbed** — narrow opening |
| Policy engines (generic) | OPA | 12,179 | **Consolidated** — closed |
| Policy *inputs* for agent tool calls | — | — | **EMPTY** |
| Secret brokers for agents | — (best: 9★) | — | **EMPTY** |
| Audit / provenance / receipts | pipelock only | 824 | **NEAR-EMPTY** |
| Cross-agent delegation identity | — (IETF individual drafts) | — | **EMPTY** |

---

## 4. The enterprise gap

### 4.1 Compliance timing — the forcing function just weakened

| Instrument | Date | Status |
|---|---|---|
| EU AI Act — general application + Art. 50 transparency | **2026-08-02** | **In force now.** Not deferred. |
| EU AI Act — Annex III high-risk (hiring, credit, education, critical infra) | was 2026-08-02 → **2027-12-02** | **Deferred** by Digital Omnibus, Regulation (EU) 2026/1744, OJ 2026-07-24, in force 2026-07-27 |
| EU AI Act — Annex I embedded high-risk (medical devices, machinery, toys) | → **2028-08-02** | Deferred |
| NIST COSAiS — SP 800-53 control overlays incl. single-agent and multi-agent | announced mid-2025 | **Still in development as of 2026** |
| NIST Cyber AI Profile (CSF 2.0) | Dec 2025 | Released |
| OWASP Top 10 for Agentic Applications (ASI01–ASI10) | 2025-12-09 | Released; 100+ contributors. Prompt injection maps to 6 of 10 categories. |
| NSA/CISA MCP Security CSI | 2026-06-02 | Exists (fetch 403 — content UNVERIFIED) |

**This is a material negative for the "compliance will force purchases" thesis.** The hard high-risk obligations slipped 16 months. The most technically prescriptive artifact (COSAiS agentic overlays) is unfinished. What remains live on 2026-08-02 is Art. 50 transparency, which is a disclosure duty — not an agent-security-controls duty.

Implication: **do not build for a 2026 compliance deadline.** Build for the incident-driven demand that is already real (Section 2.2) and let compliance arrive in late 2027 as a tailwind.

### 4.2 What practitioners say is missing

From practitioner and buyer-side writeups (secondary sources; directional):

- **Delegation-chain accountability.** "When an orchestrator agent delegates to a sub-agent which calls an API which modifies a database, the accountability chain spans multiple layers" — traditional models break when agents authenticate on behalf of users who don't know the specific actions taken. Maps exactly to the IETF cross-org-delegation gap (§1.4) and stalled SEP-1933.
- **Evidentiary audit trails.** Defined as chronological, **tamper-resistant** records of every input, reasoning step, LLM call, tool execution, and output. Note "tamper-resistant" — that is a cryptographic requirement, not a logging requirement, and it is exactly what nobody ships.
- **Procurement has become the gate.** By mid-2026 enterprise checklists reportedly demand kill switches, evidentiary audit trails, human-in-the-loop boundaries, model change control, outcome SLAs, and ISO/IEC 42001 or SOC 2 attestations as *gating conditions*.
- **Shadow agents.** 82% of enterprises reportedly have agents/workflows security teams didn't know existed. Discovery/inventory is unsolved — though this is where gateways (consolidated) naturally win.
- **MCP's own answer:** EMA (Enterprise-Managed Authorization) landed in the 2026-07-28 spec *specifically* because "organisations couldn't adopt MCP without central IT control over which servers employees connect to." The spec authors are documenting the procurement blocker in the changelog.

### 4.3 Is the gap OSS-shaped?

**Partly.** The honest split:

- **OSS-shaped:** the *mechanism* — brokers, mediators, capability monitors, receipt formats, signing schemes. These need to be inspectable and vendor-neutral to be trusted at all; a closed-source thing that holds all your agent credentials is a harder sell than an open one. Auditors accept open mechanisms.
- **NOT OSS-shaped:** the *evidence product* — the SOC 2 / ISO 42001 attestation package, the auditor relationship, the dashboard the CISO shows the board. This is where the money is and it is enterprise sales.

The viable shape is therefore **open mechanism + open format, with the aggregation/attestation layer as the commercial surface** — the harden-runner / Sigstore pattern, not the pure-OSS-tool pattern.

---

## 5. Durability analysis: what gets absorbed

**The absorption rule this space follows:** *a vendor will absorb any control that protects its own agent from its own users' mistakes, inside its own process boundary. A vendor will not absorb any control whose value depends on being trusted by a party that does not trust the vendor.*

| Layer | Absorption risk | Evidence | Reasoning |
|---|---|---|---|
| Process/FS sandboxing | **Absorbed** | Claude Code native sandbox v2.1.0+; `anthropic-experimental/sandbox-runtime` 5,093★; K8s SIG agent-sandbox 3,685★ | Table stakes for a coding agent. Every harness ships it. |
| Basic egress allowlist | **Absorbed (single-harness)** | Claude Code `allowedDomains` / `strictAllowlist` / custom proxy | Same. |
| Tool approval prompts | **Absorbed** | Every harness | UX-level; belongs in the harness. |
| MCP gateway/routing | **Absorbed by foundation** | agentgateway is an LF project; spec added routing headers *for gateways* | Worse than vendor absorption — standardized and given away. |
| Registries | **Absorbed by foundation** | official MCP registry 7,203★; agentregistry→CNCF | Same. |
| Scanning | **N/A — approach invalid** | κ≤0.082; precision 45.53% | Nothing to absorb. |
| **Cross-vendor credential brokering** | **LOW** | Category empty at 9★ | A broker's whole value is that it sits *outside* and *above* every agent vendor, holding credentials none of them may see. Anthropic cannot ship the thing that withholds credentials from Claude; OpenAI cannot ship the neutral broker for Anthropic's agents. Multi-vendor by construction. |
| **Attestable action receipts / provenance** | **LOW** | pipelock only; SEP-3140 unadopted; ClawHub found provenance beat scanning | Evidence signed by the party being audited is worth less. Vendor-neutrality is the *product*. Same reason Sigstore is not "GitHub Signing." |
| **Cross-org delegation chains** | **LOW** | All IETF individual drafts; SEP-1933 open 9mo | Inherently multi-party. No single vendor can define how *their* agent proves authority to *someone else's* system. |
| **Trust-handoff / artifact-consumption boundary** | **MEDIUM** | Pillar CBSE series; Claude Code shipped 4 fixes in 5 days | Vendors patch instances fast, but the *class* spans the boundary between sandbox and every downstream consumer (CI, git, editor, next agent). Cross-tool by nature. Medium because vendors are actively working it. |
| **Policy inputs (taint/provenance/sensitivity derivation)** | **MEDIUM-LOW** | SEP-1913 open 9mo, 42 comments, unresolved; SEP-2793 stalling | If the spec eventually standardizes annotations, part of this becomes free. But *deriving* taint at runtime is not something an annotation gives you. |

**The generalization:** absorption tracks the trust boundary, not the technical difficulty. Anything valuable *because it is neutral* is safe. Anything valuable *because it is convenient* is gone within two releases.

---

## 6. Verdict: ranked opportunities

### #1 — Agent credential broker (CB4A implementation)

**Problem.** Agents hold long-lived, broadly-scoped bearer credentials. Every major 2026 incident monetized exactly this: postmark-mcp inherited pre-authorized corporate API keys; Moltbook leaked 1.5M agent keys in plaintext; TeamPCP harvested ~500k identities from an AI gateway; Agentjacking's payload read `.env` and `~/.aws/config`. Reportedly 53% of MCP servers use long-lived static secrets, 8.5% use OAuth *(magnitude UNVERIFIED)*.

**What to build.** SANS's CB4A: split PDP (decides, holds nothing) from CDP (mints, decides nothing). Agents receive seconds-to-minutes proxy tokens, narrowly scoped, **bound to agent cryptographic identity** (SPIFFE), non-replayable. Add canary credentials for compromise detection. Sit in front of MCP servers and tool calls; agents never see a real secret.

**Evidence.** SANS blueprint (Hartman, 2026-05-15) with no implementation. IETF `draft-klrc-aiagent-auth-00` and AIMS both map SPIFFE+OAuth to agents but ship nothing. Incident record above.

**Nearest competitor.** Vault (36,190★) / OpenBao (7,214★) / Infisical (29,036★) — human & service-account stores, wrong lifecycle. SPIRE (2,505★) — identity, not brokering. Agent-specific: `tashian/tsm` 9★, `agent-vault` 1★, two 0★ repos. **Effectively no competitor.**

**Absorption resistance: HIGH.** Structural: the broker's function is to withhold credentials from the agent. A vendor cannot credibly ship the component whose job is to not trust that vendor's agent. Multi-vendor by construction.

**Difficulty: MEDIUM-HIGH.** Building on SPIFFE/OAuth is well-trodden; the hard parts are per-provider token-exchange adapters (AWS STS, GitHub App tokens, Google, Slack…) and being on the hot path without wrecking latency. Adapter breadth is the real cost and also the moat.

**Risk.** Okta, WorkOS, Aembit, and Runlayer are all AAIF members working this space commercially. You will be racing funded incumbents into an enterprise buyer. Being the *open reference implementation* is the defensible position, not being the product.

---

### #2 — Attestable action receipts (verifiable agent audit)

**Problem.** Enterprise procurement now gates on "evidentiary, tamper-resistant audit trails" and delegation-chain accountability. What exists is application logging written by the agent being audited — worthless as evidence. Nobody can answer "prove this agent was authorized to do that, and prove the log wasn't edited."

**What to build.** A signed-receipt format + reference mediator. Every tool call produces a receipt signed **outside the agent process**, chaining: principal → delegation path → tool + arguments hash → provenance of the artifact that triggered it → policy decision → outcome. Reuse JWS + JCS (already blessed by A2A v1.0 signed Agent Cards) and Sigstore. Ship the *format spec* first, the mediator second — the format is the durable asset.

**Evidence.** ClawHub's most underrated result: **24.3% of malicious verdicts had no positive scanner signal at all** — reached via provenance and moderation context. Provenance beat detection on the hardest cases in a 67,453-sample study. MCP SEP-2448 (telemetry) and SEP-3140 (signed capability declarations) both open and unadopted. Trustworthy-MCP-Registry blueprint names the exact hole. Buyer-side governance writeups list tamper-resistant trails as a gating condition.

**Nearest competitor.** `pipelock` (824★, created 2026-02-08) already advertises "mediator-signed action receipts: verifiable audit evidence from outside the agent." **This is a real, fast-moving early mover and the single biggest competitive risk in this report.** Otherwise: generic observability (SigNoz 31,974★, MLflow 27,740★) which does telemetry, not evidence.

**Absorption resistance: HIGH.** Evidence signed by the audited party is worth less than evidence signed by a neutral one — the same logic that made Sigstore a foundation project rather than a GitHub feature. Also cross-vendor: a receipt chain spanning Claude Code → an MCP server → a sub-agent cannot be signed by any one vendor.

**Difficulty: MEDIUM.** Cryptography is off-the-shelf. The genuinely hard part is *semantic*: capturing delegation and data provenance faithfully enough that the receipt means something. Getting adopted as a format is harder than building it.

---

### #3 — Revocable capability monitor for agent tool access

**Problem.** "Lingering authority" (arXiv 2606.22504): agents get broad tool access for a whole task when a resource was needed for one subgoal, and the grant never closes. Combined with the Pillar CBSE finding — that isolation is bypassed at the *artifact handoff*, not the process boundary — the right unit of control is the capability and its expiry, not the container.

**What to build.** A reference monitor implementing request→grant→invoke→**auto-revoke** for tool capabilities, with attenuation (a sub-agent can only receive a subset of its parent's authority) and per-subgoal scoping. Effectively the enforcement engine for Meta's Rule of Two and Willison's trifecta, made deterministic and declarative.

**Evidence.** PORTICO rejects 10/10 post-closure capability reuses vs 0/10 for a non-revoking baseline (small-n, research prototype). Meta explicitly proposes declarative Rule-of-Two configuration in tool calls — *and MCP has no such field*. SEP-1913 (Trust & Sensitivity Annotations) has been open 9 months with 42 comments; SEP-2793 (Tool Risk Metadata) is stalling at 6 comments. Detection failure (§2.1) makes constraint the only remaining path.

**Nearest competitor.** OPA (12,179★), Cedar (1,701★), OpenFGA (5,679★), Cerbos (4,563★) — mature *evaluators*, but nothing produces the agent-specific *inputs* (taint, delegation depth, subgoal scope, sensitivity class). `permitio/permit-mcp` at 3★, last pushed 2025-05-05, is the tombstone for the naive attempt. **Do not rebuild an engine — build the input derivation and bind to Cedar/OPA.**

**Absorption resistance: MEDIUM.** If MCP eventually merges SEP-1913/2793, annotations become free and part of your value evaporates. Hedge by making the project the *reference implementation* of those SEPs and participating in them — nine months of deadlock says there is time, and an implementation is the standard argument that usually breaks deadlocks.

**Difficulty: HIGH.** Runtime taint tracking across an LLM boundary is genuinely unsolved research. Scope tightly: start with *provenance of tool-call arguments* (did this string originate in untrusted content?), which is tractable and directly implements the trifecta.

---

### #4 — eBPF-level agent egress mediation

**Problem.** Egress control is the last leg of the lethal trifecta and the cheapest to enforce deterministically. Claude Code ships an allowlist — but via **a localhost HTTP proxy, not kernel blocking**, covering only "well-behaved HTTP clients." Raw sockets, DNS tunneling, and subprocesses ignoring `HTTP_PROXY` are out of scope. Agents spawn arbitrary subprocesses by design, so "well-behaved" is an assumption an attacker chooses to violate.

**What to build.** Kernel-level (eBPF) egress policy for agent processes and their descendants: per-process-tree DNS+IP+SNI policy, full attempt logging, deny-by-default, with policy expressed in terms of agent identity rather than IP. Explicitly the `harden-runner` model, ported from CI runners to agent runtimes.

**Evidence.** `step-security/harden-runner` at 1,258★ proves the pattern works commercially in CI/CD. `qpoint-io/qtap` 1,457★ proves eBPF traffic capture has an audience. Pillar's series shows Claude Code shipped an "unprompted network egress" fix on 2026-07-24 — i.e. the absorbed version was leaking weeks ago. Every exfiltration incident in §2.2 terminated in an outbound request.

**Nearest competitor.** pipelock (824★) covers HTTP/MCP/A2A/WebSocket *mediated* traffic — same limitation as Anthropic's, one layer up. Containarium (276★) does eBPF egress but bundles it with a whole SSH-native runtime. **The pure "eBPF egress for agents" slot is open.**

**Absorption resistance: MEDIUM-LOW.** This is the weakest entry on the list. Vendors are actively shipping egress control and will improve it. Your differentiator — kernel enforcement covering non-cooperating subprocesses, multi-vendor, one policy across Claude Code + Codex + Cursor + CI — is real but narrow, and a determined vendor could close it. **Best pursued as a component of #2 (receipts need a trustworthy egress record) rather than as a standalone product.**

**Difficulty: MEDIUM.** eBPF is well-understood; portability is the tax — Linux is fine, macOS has no eBPF (Network Extension framework instead), and macOS is where a huge share of coding agents actually run.

---

### #5 — Curated, provenance-verified distribution for MCP servers and skills

**Problem.** Scanning provably fails (§2.1). Trail of Bits' own recommendation after breaking every scanner was *curation*: curated repos, org-managed plugins, version pinning, controlled approval. The postmark-mcp incident showed the deeper issue — pulling a package from a registry does not remove it from running environments; installs kept exfiltrating until manually found.

**What to build.** Not another registry (consolidated). A **verification and pinning layer over the existing one**: Sigstore-backed publisher provenance, JCS/JWS signing of capability declarations, cryptographic detection of mid-session capability mutation (the exact hole named in the Trustworthy-MCP-Registry paper), lockfile-style pinning, and org-scoped allowlists with an approval workflow.

**Evidence.** Trustworthy MCP Registry blueprint (RFC 8615 + Sigstore + JCS/JWS) — a published architecture with no implementation. SEP-3140 open at 0👍. Trail of Bits' curated-repos recommendation. ClawHub: provenance caught 24.3% of malicious cases that *no scanner* caught. Trail of Bits' original 2025 insight, still unaddressed: a scanner checks the version at install time; the attack ships in the update.

**Nearest competitor.** `trailofbits/mcp-context-protector` (223★, last push **2026-04-14 — 4.5 months stale**) does config-change detection and pin-on-approval; it is the right idea, apparently under-maintained, and only 223★. `stacklok/toolhive` (2,056★) does enterprise MCP server management and is the most likely to grow into this. Sigstore/in-toto are the substrate.

**Absorption resistance: MEDIUM.** The AAIF registry could add signing — but note Sigstore's documented limit: its log records *who signed, not which registry distributed*, so a registry feature alone is insufficient. And the org-scoped curation/approval workflow is a customer-side concern the registry has no reason to own.

**Difficulty: MEDIUM-LOW.** Every primitive exists. This is integration and workflow, not research. **Lowest-difficulty, highest-certainty entry on the list** — and the one most likely to be genuinely useful within a quarter.

---

### 6.1 Ranked summary

| # | Opportunity | Category state | Nearest competitor | Absorption resistance | Difficulty |
|---|---|---|---|---|---|
| 1 | Agent credential broker (CB4A) | **Empty** (best 9★) | none credible | **HIGH** | Med-High |
| 2 | Attestable action receipts | **Near-empty** | pipelock 824★ ⚠ | **HIGH** | Medium |
| 3 | Revocable capability monitor | **Empty** (inputs) | permit-mcp 3★ dead | Medium | **High** |
| 4 | eBPF agent egress | Contested | pipelock 824★; harden-runner 1,258★ | Med-Low | Medium |
| 5 | Provenance-verified distribution | Near-empty | mcp-context-protector 223★ (stale) | Medium | **Med-Low** |

### 6.2 The honest answer

The brief asked me to say plainly if the answer is "solved or enterprise sales." It is **neither, but closer to enterprise sales than a small team would like.**

Three things are true simultaneously:

1. **The obvious categories are gone.** Gateways, sandboxes, registries, and scanners are consolidated, foundation-captured, vendor-absorbed, or empirically invalid. A small team entering any of them loses.

2. **The non-obvious categories are genuinely, verifiably empty** — and it is not because nobody wants them. It is because they are *hard in a specific way*: they require being trusted by parties who do not trust each other, which means adoption is a standards-and-integration problem, not a code problem. The 9★ ceiling on agent credential brokers next to a 500,000-identity credential-harvesting incident is the single most striking number in this report.

3. **The buyer is an enterprise security team, and the EU AI Act deferral just removed the 2026 deadline.** Demand is now incident-driven rather than calendar-driven, which is less predictable but arguably more real — Agentjacking hit a $250B company's agents and Sentry declined to fix it, which is exactly the situation that makes a security team buy something.

**What this means for a small team.** The realistic play is not "build an OSS product and monetize it." It is **own the format/mechanism, and let the mechanism be the standard.** #2 (receipt format) and #1 (broker) are both shaped like Sigstore: an open mechanism nobody can absorb because neutrality is the point, with the commercial surface in aggregation and attestation rather than in the mechanism itself. #5 is the pragmatic first ship — lowest difficulty, real users immediately, and it produces exactly the provenance data that #2 needs as input.

**The strongest single recommendation:** start with **#5 to get users and provenance data**, design **#2's receipt format** from what that data actually shows, and treat **#1** as the eventual centre of gravity. Do not start with #3 (research risk) or #4 (absorption risk) standalone.

**And a caution:** pipelock (824★, seven months old, still pushing daily) is already executing an overlapping thesis across #2 and #4. Any plan here should start by reading its code and deciding whether to compete, complement, or contribute.

---

## Appendix: verification notes

- All GitHub figures retrieved 2026-08-31 via authenticated `gh api` and `gh search repos`.
- ClawHub κ values (0.045 / 0.054 / 0.082) and Jaccard values (0.065 / 0.094 / 0.104) extracted directly from Table 4 of the arXiv PDF via `pdftotext`, not from a secondary summary.
- **Corrected from brief:** the scanner-agreement result is arXiv 2606.01494 (Koc et al., 2026-05-31), not Trail of Bits; κ ≤ 0.082, not 0.01–0.18. Trail of Bits' contribution is a separate qualitative bypass study (2026-06-03).
- **UNVERIFIED:** NSA/CISA MCP CSI content (HTTP 403 to automated fetch; existence confirmed via search indexing only). Aggregate industry statistics in §2.2 final paragraph (HackerOne 540%, Trend Micro 492 exposed servers, 47–53% incident rate, 82% shadow agents, 53%/8.5% secrets split) are from vendor blogs without traceable methodology — directionally consistent with confirmed incidents, but magnitudes should not be quoted as fact.
- `open-edison/open-edison` (named in prior research) returned 404 — repo does not exist at that path.

### Primary sources

- [MCP 2026-07-28 spec release](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [LF: Agentic AI Foundation formation](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)
- [LF: A2A one-year adoption](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- [LF: agentgateway project](https://www.linuxfoundation.org/press/linux-foundation-welcomes-agentgateway-project-to-accelerate-ai-agent-adoption-while-maintaining-security-observability-and-governance)
- [arXiv 2606.01494 — ClawHub Security Signals](https://arxiv.org/abs/2606.01494)
- [arXiv 2607.11086 — Rethinking MCP Security (MCPZoo)](https://arxiv.org/html/2607.11086v1)
- [arXiv 2606.22504 — Lingering Authority / PORTICO](https://arxiv.org/abs/2606.22504)
- [Trail of Bits — The sorry state of skill distribution](https://blog.trailofbits.com/2026/06/03/the-sorry-state-of-skill-distribution/)
- [CSA — AI Agent Skill Scanners: Bypassed Across the Board](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-agent-skill-scanner-bypass-20260610-csa/)
- [CSA — AI Coding Agent Sandbox Escapes: The Trust Handoff Flaw](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-coding-agent-sandbox-escapes-20260722-c/)
- [Pillar Security — The Week of Sandbox Escapes](https://www.pillar.security/blog/the-week-of-sandbox-escapes)
- [Simon Willison — The lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
- [Meta AI — Agents Rule of Two](https://ai.meta.com/blog/practical-ai-agent-security/)
- [SANS — Your AI Agent Is an Easily Confused Deputy (CB4A)](https://www.sans.org/blog/your-ai-agent-easily-confused-deputy-why-cloud-security-needs-credential-broker)
- [Snyk — Malicious MCP server on npm: postmark-mcp](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/)
- [Tenet Security — Agentjacking](https://tenetsecurity.ai/blog/agentjacking-coding-agents-with-fake-sentry-errors/)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [Claude Code sandboxing docs](https://code.claude.com/docs/en/sandboxing)
- [Trustworthy MCP Registry blueprint (Future Internet)](https://doi.org/10.3390/fi18050243)
- [IETF draft-reece-wimse-cross-org-delegation-00](https://datatracker.ietf.org/doc/html/draft-reece-wimse-cross-org-delegation-00)
- [IETF draft-klrc-aiagent-auth-00](https://www.ietf.org/archive/id/draft-klrc-aiagent-auth-00.html)
- [Holland & Knight — EU AI Act Aug 2026 deadline](https://www.hklaw.com/en/insights/publications/2026/04/us-companies-face-eu-ai-acts-possible-august-2026-compliance-deadline)
- MCP SEPs verified live: [#1913](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1913), [#1933](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1933), [#1932](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1932), [#2793](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/2793), [#3140](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3140), [#1488](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1488)
