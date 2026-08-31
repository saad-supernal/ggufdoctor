# Technical Due Diligence: The Agent Skills Ecosystem, Aug 2026
## Evaluating "a production-grade Skills library / private skill registry"

**Research date:** 2026-08-31
**All star counts, install counts and dates below were fetched LIVE on 2026-08-31** via the GitHub REST API (`gh api`, authenticated) and the skills.sh public search API. Nothing is stated from model memory. Anything not directly verified is labelled **UNVERIFIED**.

**Bottom line up front:** The idea as specified — a curated 20-skill "awesome-agent-skills" pack with a $29/$99 paid tier — is **saturated on every axis simultaneously**: the content is supplied free by first-party vendors, the curation layer is supplied free by 250k-star repos, the distribution layer is owned by GitHub and Vercel, and the exact $29/$99 private-registry price points are already occupied by live products. **Verdict: SKIP the content play. The only defensible wedge is skill evaluation / trigger-regression testing, which is a genuinely unfilled gap but is a small, hard, infrastructure business — not a content business.**

---

## 1. STATE OF THE SKILLS PRIMITIVE

### 1.1 The spec is real, open, and vendor-neutral

Agent Skills is no longer an Anthropic feature. It is an **open standard with its own governance body**.

- The spec lives at **https://agentskills.io/specification**, published as an open standard on **2025-12-18** and stewarded through the **Agentic AI Foundation**. ([announcement](https://claude.com/blog/organization-skills-and-directory))
- The spec repo is **`agentskills/agentskills`** — **24,882 stars**, 1,862 forks, **Apache-2.0**, created 2025-12-16, last pushed 2026-08-09. Homepage: agentskills.io.
- Required frontmatter is only two fields: `name` (≤64 chars, lowercase/hyphens, must match parent dir) and `description` (≤1024 chars). Optional: `license`, `compatibility`, `metadata`, `allowed-tools` (experimental).
- Directory convention: `SKILL.md` + optional `scripts/`, `references/`, `assets/`.
- There is an official reference validator: `skills-ref validate ./my-skill`.
- Progressive disclosure is formalised: metadata (~100 tokens) always loaded; body (<5000 tokens recommended) on activation; `scripts/`/`references/` on demand. Spec advises keeping `SKILL.md` **under 500 lines**.

### 1.2 The format has CONVERGED, not fragmented

This is the single most important finding for the thesis. There is no format war to arbitrage.

The **agentskills.io Client Showcase** (fetched live) lists **46 agent products** implementing the format:

> Junie (JetBrains), ZeroClaw, Gemini CLI (Google), Autohand Code CLI, OpenCode, OpenHands, Mux (Coder), **Cursor**, **Amp**, Letta, Firebender, Goose (Block), **GitHub Copilot**, **VS Code**, **Claude Code**, **Claude**, **ChatGPT & Codex (OpenAI)**, Piebald, Factory, pi, Databricks Genie Code, Agentman, TRAE (ByteDance), Spring AI, Roo Code, Mistral AI Vibe, Command Code, Ona, VT Code, Qodo, Laravel Boost, Emdash, Snowflake Cortex Code, Kiro (AWS), Workshop, Google AI Edge Gallery, nanobot, fast-agent, bub, Tabnine, Vita, Superconductor, Deep Code, Pulumi Neo, Hermes Agent (Nous Research), OpenClaw.

Every question in the brief resolves to "yes":

| Vendor | Skills support | Path |
|---|---|---|
| Anthropic / Claude Code | Native | `.claude/skills/`, `.agents/skills/` |
| OpenAI Codex + ChatGPT | Native (docs at developers.openai.com/codex/skills) | `.agents/skills/`, `~/.codex/skills/` |
| Cursor | Native | `.cursor/skills/`, `.agents/skills/` |
| GitHub Copilot | Native (shipped ~Apr 2026) | `.github/skills/`, `.claude/skills/`, `.agents/skills/` |
| Gemini CLI | Native | `.agents/skills/` |
| Amp | Native | `.agents/skills/` |

Per the **AI Harness Engineering Compatibility Matrix, dated 2026-08-26**, `.agents/skills/*/SKILL.md` is "the broadest shared skill path among these products," and Copilot / Claude Code / Codex / Cursor all read it natively.

**Implication:** a cross-vendor compatibility layer or "one format to rule them all" product has no market. That job is done.

### 1.3 Official registries/marketplaces already exist — and they are free

| Registry | Operator | Scale (verified 2026-08-31) | Monetized? |
|---|---|---|---|
| **skills.sh** | **Vercel** (`vercel-labs/skills`, 30,036 stars, MIT) | Leaderboard shows **1,332,357 skills** all-time. `npx skills add <owner/repo>`. Lists 21+ compatible agents. | No pricing tier found — free |
| **`gh skill`** | **GitHub** (GitHub CLI v2.90.0+, shipped **2026-04-16**) | install / search / update / publish, `--pin` to tag or commit SHA, records source git tree SHA in `SKILL.md` frontmatter as portable provenance | Free, bundled with gh |
| **ClawHub** (clawhub.ai) | OpenClaw (`openclaw/clawhub`, 9,376 stars, MIT) | 13,000+ community skills (UNVERIFIED count); signed manifests, moderated releases, version history, `/audit` endpoint | **"ClawHub doesn't have paid listings. Everything in the registry is free."** |
| **anthropics/claude-plugins-official** | Anthropic | **35,619 stars**; marketplace.json lists **291 plugins** (AWS, Azure, Atlassian, Auth0, Apollo, Canva, Box, Databricks, Figma, Snowflake…) | Free |
| **claude.com/connectors** skills directory | Anthropic, launched 2025-12-18 | Partner-built. Launch partners: Atlassian, Canva, Cloudflare, Figma, Notion, Sentry, Vercel, Zapier | **No revenue share for skill authors** |

`gh skill` carries an explicit disclaimer that matters for the security thesis:

> "Skills are installed at your own discretion. They are not verified by GitHub and may contain prompt injections, hidden instructions, or malicious scripts."

**Anthropic has also shipped org-level skill management** for Team and Enterprise plans: admins provision skills centrally from Organization settings → Skills; admin-provisioned skills are enabled by default for all users. This directly overlaps the proposed "private internal skills" tier for any org already on a Claude Team/Enterprise plan.

---

## 2. PRIOR ART CENSUS

All figures fetched live 2026-08-31 via authenticated `gh api`. "Pushed" = last push to default branch.

### 2.1 Skill / agent collections

| Repo | Stars | Forks | Last push | Created | License | What it actually is |
|---|---:|---:|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | **279,694** | 25,072 | 2026-08-29 | 2025-10-09 | MIT | 14 methodology skills + **full test suite + 10 harness plugin manifests**. The quality leader. |
| [mattpocock/skills](https://github.com/mattpocock/skills) | **241,914** | 20,572 | 2026-08-24 | 2026-02-03 | MIT | 37 skills, median 3.4KB. Genuinely well-engineered. 738k installs on skills.sh. |
| [anthropics/skills](https://github.com/anthropics/skills) | **172,652** | 20,510 | 2026-08-21 | 2025-09-22 | Apache-2.0 / source-available | 19 skills, 417 files, **198 script files**. Heavily scripted. |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | **53,249** | 4,638 | 2026-08-31 | 2025-04-19 | NOASSERTION | Link list |
| [VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills) | **52,271** | 5,011 | 2026-08-29 | 2026-01-25 | MIT | Link list (0 SKILL.md files in repo) |
| [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) | **45,709** | 6,687 | 2026-08-30 | 2026-01-14 | MIT | **6,603 SKILL.md paths → only 2,097 unique names / 2,366 unique blobs (~64% duplication)**. Mega-aggregator. |
| [wshobson/agents](https://github.com/wshobson/agents) | **39,278** | 4,190 | 2026-08-31 | 2025-07-24 | MIT | Pivoted to "Multi-harness agentic plugin marketplace for Claude Code, Codex, Cursor, OpenCode, Copilot, Antigravity" |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | **38,455** | 4,854 | 2026-08-31 | 2025-06-11 | MIT | **432 SKILL.md files**, published by GitHub itself |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | **35,619** | 3,973 | 2026-08-29 | 2025-11-20 | — | 291 official plugins |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | **30,651** | 2,726 | 2026-08-28 | 2025-12-08 | none | 9 skills; `vercel-react-best-practices` alone has **676,562 installs** |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | **30,456** | 3,456 | 2026-08-30 | 2025-07-04 | MIT | CLI + aitmpl.com |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) | **30,036** | 2,575 | 2026-08-18 | 2026-01-14 | MIT | The `npx skills` tool / skills.sh |
| [openai/skills](https://github.com/openai/skills) | **25,285** | 1,717 | 2026-07-14 | 2025-11-25 | — | "Skills Catalog for Codex" |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | **24,882** | 1,862 | 2026-08-09 | 2025-12-16 | Apache-2.0 | The spec itself |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | **24,754** | 2,866 | 2026-08-12 | 2025-07-30 | MIT | 100+ subagents |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | **14,901** | 1,919 | 2026-04-28 | 2025-10-16 | none | Link list; **stale ~4 months** |
| [BehiSecc/awesome-claude-skills](https://github.com/BehiSecc/awesome-claude-skills) | **10,073** | 1,484 | 2026-08-02 | 2025-10-17 | none | Link list |
| [openclaw/clawhub](https://github.com/openclaw/clawhub) | **9,376** | 1,459 | 2026-08-31 | 2026-01-03 | MIT | Registry backend |
| [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) | **3,913** | 474 | 2026-08-27 | 2026-03-29 | NOASSERTION | Harness/evals/observability list |
| [supabase/agent-skills](https://github.com/supabase/agent-skills) | **2,564** | 200 | 2026-08-12 | 2026-01-16 | MIT | 2 skills; `supabase-postgres-best-practices` = **378,417 installs** |
| [langchain-ai/langchain-skills](https://github.com/langchain-ai/langchain-skills) | **1,186** | 90 | 2026-08-29 | 2026-01-22 | none | 22 skills |
| [getsentry/skills](https://github.com/getsentry/skills) | **963** | 50 | 2026-08-25 | 2026-01-05 | Apache-2.0 | **27 skills**, incl. `security-review` (14,901 installs) |
| [karanb192/awesome-claude-skills](https://github.com/karanb192/awesome-claude-skills) | **502** | 230 | 2026-08-05 | 2025-10-21 | MIT | "50+ verified" list |
| [Karanjot786/agent-skills-cli](https://github.com/Karanjot786/agent-skills-cli) | **178** | 19 | 2026-05-17 | 2026-01-04 | MIT | Cross-agent sync CLI |
| [Chat2AnyLLM/awesome-claude-skills](https://github.com/Chat2AnyLLM/awesome-claude-skills) | **147** | 35 | 2026-08-31 | 2025-12-23 | none | Link list |
| [adewale/skill-eval-harness](https://github.com/adewale/skill-eval-harness) | **72** | 5 | 2026-08-31 | 2026-06-09 | MIT | **Eval harness — the un-won space** |
| [itgoyo/awesome-claude-code-skills](https://github.com/itgoyo/awesome-claude-code-skills) | **40** | 17 | 2026-04-13 | 2026-04-13 | none | Dead |

**Monetization column, summarized: essentially nobody monetizes the content directly.** The one exception found is `obra/superpowers`, whose README routes enterprise interest to a **services** business (`sales@primeradiant.com`) while the skills stay MIT, and whose only funding channel is GitHub Sponsors (`.github/FUNDING.yml → github: [obra]`).

### 2.2 The killer competitive finding: every proposed skill already exists, published first-party

I queried the live skills.sh search API for each of the 10 proposed skills. **All 10 have existing implementations, and the strongest ones come from the vendor who owns the technology:**

| Proposed skill | Already exists as | Installs |
|---|---|---:|
| postgres-performance | `supabase/agent-skills/supabase-postgres-best-practices` | **378,417** |
| | `planetscale/database-skills/postgres` | 7,145 |
| fastapi-review | `fastapi/fastapi/fastapi` (in the FastAPI repo itself) | 8,633 |
| react-accessibility | `microsoft/vscode/accessibility` | 2,670 |
| | `jakubkrehel/skills/better-accessibility` | 10,724 |
| playwright-debugger | `voidmatcha/e2e-skills/playwright-debugger` | 133 |
| security-review | `getsentry/skills/security-review` | **14,901** |
| | `github/awesome-copilot/security-review` | 4,924 |
| docker-debugger | `shubhamsaboo/awesome-llm-apps/debugger`, `langchain-ai/langchain-skills` | 3,244 |
| github-issue-triage | `code-yeongyu/oh-my-openagent/github-issue-triage` | 1,306 |
| dependency-upgrader | `github/awesome-copilot/dotnet-upgrade` | 10,297 |
| | `callstackincubator/agent-skills/upgrading-react-native` | 9,095 |
| production-incident | `useai-pro/openclaw-skills-security/incident-responder`, `spencerpauly/awesome-cursor-skills/incident-response` | 432 / 2,000+ |
| api-migration | `auth0/agent-skills/auth0-migration` | 693 |

The dominant distribution pattern is **first-party vendor skills**: Supabase, PlanetScale, FastAPI, Microsoft, Sentry, GitHub, LangChain, Auth0, Vercel, Laravel, Pulumi, Snowflake, Databricks all ship their own. This is a structural moat a third party cannot cross: Supabase knows Postgres better than you, ships it free, and updates it with the product.

### 2.3 Enterprise / private registry vendors (the "$99 tier" competitors)

| Product | Who | Positioning | Pricing (live) |
|---|---|---|---|
| **JFrog Agent Skills Registry** | JFrog | Announced at **NVIDIA GTC 2026**. "Every skill is automatically versioned, scanned for malicious intent, cryptographically signed, and access-controlled." Approval workflows. NVIDIA NemoClaw Ready. | Contact sales |
| **SkillReg** (skillreg.dev) | Kairia | "The private registry for AI agent skills." Version history, access control, **50+ built-in security scanning rules**, approval workflows, audit logs, usage analytics, desktop app + CLI. Live, self-serve. | **Free $0 (10 skills/5 members) · Team $29/mo (100 skills/25 members) · Enterprise $99/mo (unlimited)** |
| **SkillRepo** (skillrepo.dev) | SkillRepo LLC | "Open distribution layer." **A–F security grading** on every published skill, team libraries scoped per repo, publisher analytics. Live. | Free publishing; **Team from $8/seat/mo**, 14-day trial |
| **skillscatalog.ai** | — | "The Trust Registry", enterprise page | UNVERIFIED |
| **Anthropic org skills** | Anthropic | Central admin provisioning for Team/Enterprise plans | Bundled in plan |
| **Claude Code enterprise plugin distribution** | Anthropic | Signed manifest at gateway, **Ed25519 signature + per-file SHA-256**, device sync | Bundled (UNVERIFIED detail) |

**SkillReg's price card is literally $29 Team / $99 Enterprise** — the exact tiers in the proposal, already shipped by an operating company with a security-scanning moat.

---

## 3. THE QUALITY GAP — WHAT "PRODUCTION-GRADE" ACTUALLY HAS TO BEAT

I read source files rather than READMEs. Measurements from the GitHub trees API.

### 3.1 The bar at the top is much higher than "polished markdown"

**`obra/superpowers` (279,694 stars) is not a prompt collection. It is an engineered product.** Full-tree analysis (195 blobs):

- **14 skills**, `SKILL.md` sizes 2,305B–32,339B, mean 9,898B.
- **41 shell scripts, 10 JS, 6 Python, 2 TS.**
- **A real test suite** — roughly 50 test files under `tests/`, including:
  - `tests/explicit-skill-requests/` with **prompt fixtures** (`please-use-brainstorming.txt`, `use-systematic-debugging.txt`, `skip-formalities.txt`, `claude-suggested-it.txt`…) plus `run-multiturn-test.sh`, `run-extended-multiturn-test.sh`, `run-haiku-test.sh` — i.e. **automated skill-triggering regression tests across models**.
  - `tests/claude-code/analyze-token-usage.py` — context-cost measurement.
  - Harness-specific conformance tests: `tests/codex/`, `tests/opencode/`, `tests/kimi/`, `tests/devin/`, `tests/hermes/`, `tests/pi/`, `tests/antigravity/`.
- **Ten harness plugin manifests shipped in-repo**: `.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`, `.devin-plugin/`, `.hermes-plugin/`, `.kimi-plugin/`, `.opencode/`, `.pi/extensions/`, `.agents/plugins/marketplace.json`, `gemini-extension.json`.
- Pre-commit config, shell linting, automated version bumping, session-start hooks.

That is the actual bar. It is MIT-licensed and free.

**`anthropics/skills`**: 417 blobs, **198 script-ish files**, mean `SKILL.md` 12,916B (largest: `claude-api` at 75,707B). Ships its own eval tooling: `skills/skill-creator/scripts/run_eval.py`, `eval-viewer/generate_review.py`, plus `mcp-builder/scripts/evaluation.py`.

**`mattpocock/skills`**: 37 skills, median 3,388B, max 11,908B. Small but sharp. Its free `code-review` skill spawns **two parallel sub-agents** (Standards axis and Spec axis) to avoid context pollution, then aggregates — and carries an embedded **twelve-item Fowler code-smell baseline from _Refactoring_ ch.3**, each written as *what it is → how to fix*, with two governing rules ("The repo overrides", "Always a judgement call"). It also handles failure ordering explicitly:

> "Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents."

This is precisely the "production-grade code-review skill" the proposal intends to sell. It is free, MIT, and backed by a creator whose repo has **241,914 stars** and **738,211 installs**.

### 3.2 The bar at the bottom is genuinely awful — but that's not where the money is

The mega-aggregators are padded with machine-generated filler. The thinnest file in `sickn33/agentic-awesome-skills` (45,709 stars), at 634 bytes, reads in its entirety:

```markdown
---
name: cc-skill-strategic-compact
description: "Development skill from everything-claude-code"
risk: none
source: community
date_added: "2026-02-27"
---

# cc-skill-strategic-compact

Development skill skill.

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.
```

"Development skill skill." — template output with the name never substituted, and a "When to Use" section that refers to an overview that does not exist. And its **6,603 SKILL.md paths collapse to 2,097 unique names / 2,366 unique blobs** — the repo triple-counts by mirroring every skill into `skills/`, `plugins/agentic-awesome-skills/`, and `plugins/agentic-awesome-skills-claude/`.

Ecosystem-wide quantification of the same rot, from an analysis of **55,315 public skills** (antoinebuteau.com, **2026-05-30**):

- **26.4% have no description at all**; **44.1% are missing a description or have one under 20 tokens** — which makes routing ambiguous by construction.
- Of 15,107 classified paragraphs across 90 skills, only **38.5% are actionable rules**; 40.7% is background, 12.9% examples, 7.6% templates.
- 100 SkillHub skills bundled **505 reference files totalling 1.67M tokens**.

### 3.3 What this means

The quality distribution is **bimodal**, not a smooth gradient with a gap in the middle:

- **Bottom:** tens of thousands of auto-generated slop skills. Free, worthless, and nobody will pay to have them replaced because nobody installed them in the first place.
- **Top:** superpowers, mattpocock, anthropics/skills, and first-party vendor skills. Free, MIT, actively maintained, better resourced than a solo pack, and — for the vendor skills — authored by the people who wrote the underlying technology.

**There is no under-served middle to sell into.** "Production-grade" would have to mean *beating superpowers' test rig and Supabase's Postgres knowledge simultaneously* — and then charging $29 for what both give away.

---

## 4. MONETIZATION EVIDENCE

Short version: **I could not find a single verified instance of anyone making meaningful money selling skill *content*.** Every large distribution channel is deliberately free. The money that does exist in this ecosystem is in **infrastructure, enterprise governance, and services** — and in **using a free skill as the funnel for a paid service**.

### 4.1 Every major channel is free by design

| Channel | Monetization |
|---|---|
| **skills.sh** (Vercel) | No paid tier found. Free. It is developer-relations for Vercel. |
| **`gh skill`** (GitHub) | Free, bundled in GitHub CLI. |
| **ClawHub** | *"ClawHub doesn't have paid listings. Everything in the registry is free."* |
| **Anthropic skills directory** (claude.com/connectors) | Partner-built. **No revenue share for skill authors.** |
| **anthropics/claude-plugins-official** | 291 plugins, free. |
| **anthropics/skills** | Apache-2.0 / source-available. Free. |
| **github/awesome-copilot** | 432 skills, MIT. Free. |
| **First-party vendor skills** (Supabase, Sentry, FastAPI, Auth0, LangChain, Laravel, Pulumi, Snowflake, Databricks, PlanetScale, Microsoft) | Free — they are marketing for the underlying product. |
| **Trail of Bits** (`trailofbits/skills`, 6,919★) | CC-BY-SA-4.0. Free. A top security consultancy gives away its `semgrep` and `codeql` skills. |

**Anthropic does not sell skills and has built no author-payout rail.** That is the single most important structural fact: the platform owner has chosen "skills are free capability distribution," the same way it treats documentation.

### 4.2 The one paid content marketplace found — and how thin the evidence is

**Agensi** (agensi.io) is the only skill marketplace I found that takes payments and pays creators. Everything known about it comes from **its own marketing content**:

- Claims "Creators earn 80% of sales" (a different page in the same content-marketing cluster claims a **70/30** split — the copy is internally inconsistent, which is itself a signal).
- Claims "Agensi Pro" at **$9/mo** for "live MCP access to the full catalog"; individual skills claimed at **$3–5**; claims an "8-point scan on every submission"; claims "200+" skills.
- **No sales figures, no transaction volume, no customer names, no testimonials.** The comparison articles ranking Agensi #1 are published by Agensi.

For calibration: **$3–5 per skill** against 200+ listings is a hobby-scale business even at implausibly good conversion. And the same article concedes the other six marketplaces it lists are all free.

A widely-shared Medium post claiming ClawHub builders make **"$600–$20,000/month"** is **UNVERIFIED and contradicted by ClawHub's own stated policy that all listings are free**. Treat it as SEO fabrication.

### 4.3 What people *actually* get paid for

Four working models, all verified, none of which is "sell a skills pack":

**(a) Enterprise governance infrastructure — real money, real vendors.**
- **JFrog Agent Skills Registry** — announced at NVIDIA GTC 2026; versioning, malicious-intent scanning, cryptographic signing, access control, approval workflows; "NVIDIA NemoClaw Ready." Contact-sales pricing.
- **SkillReg** (skillreg.dev, a Kairia product) — live, self-serve, with pricing verified directly from the page's schema.org JSON-LD: **Free $0 / Team $29 / Enterprise $99**. Ships versioning, permissions, approval workflows, **50+ built-in security scanning rules**, analytics, a desktop app and `@skillreg/cli` for CI.
- **SkillRepo** (skillrepo.dev, SkillRepo LLC) — live; **A–F security grading** on every published skill, per-repo team libraries, publisher analytics; **from $8/seat/month**, free publishing.
- Plus Google Skill Registry (Gemini Enterprise), Chainguard, TrueFoundry.

**Note the collision:** SkillReg's price card is **exactly $29 / $99** — the proposal's own tiers — shipped by an operating company with a security-scanning and governance moat the proposal does not have.

**(b) Services and support on top of free content.** The #1 repo in the ecosystem does this: `obra/superpowers` (279,694★) is MIT, its only funding channel is GitHub Sponsors (`.github/FUNDING.yml → github: [obra]`), and its README routes enterprise demand to a consultancy:

> "If you're using Superpowers in enterprise and could benefit from commercial support, additional tooling, or managed spending, please don't hesitate to drop us a line at sales@primeradiant.com."

For scale reference, AI consulting rates in 2026 run **$150–$500/hour**, with mid-market engagements at **$50k–$150k** plus **$10k–$25k/month** ongoing. One such engagement exceeds what a $29 pack would earn in years.

**(c) The skill as a free funnel to a paid service.** Visible right on ClawHub's front page: `fetcher-sh`'s Google News API and App Store API skills are free to install and **"pay-per-call in USDC via x402"**; `genmedia-labs` ships free `ai-music` / `video-edit` skills that bill through RunComfy. The skill is the distribution wrapper; the API is the product. This is the only *content-adjacent* model with an obvious revenue mechanism.

**(d) Reputation → audience → other income.** `mattpocock/skills` (241,914★, 738,211 installs) is MIT and free; Matt Pocock monetizes courses. Same shape at Vercel/Supabase/Sentry: skills are marketing.

### 4.4 The failed precedent

**PromptBase** — the canonical "sell prompt content" marketplace — is still operating but **declining**, taking a **20% commission**. Similarweb/Semrush show month-over-month traffic decreases (**−13.6%** Oct→Nov 2025, **−5.75%** in Sept 2025). It never became infrastructure, and its decline tracks exactly the thing that kills prompt-content businesses: the models got better at generating the content than the marketplace was at curating it.

The 2026 version of that dynamic is already visible: **`anthropics/skill-creator` has 367,122 installs** — the most-installed non-meta skill in Anthropic's own catalog is *the one that writes skills for you*. When the marginal cost of generating a skill approaches zero and the platform ships the generator for free, selling the artifact is a losing position.

### 4.5 Counter-evidence summary

- Guides on monetizing skills concede the structural problem: selling via Gumroad/Lemon Squeezy "requires handling every part of the buyer experience with **no agent-native discovery**, and works best **if you already drive traffic**." No revenue figures exist in any of them.
- No VC round for a skill-*content* company was found. Funding in this space went to **registries and governance** (JFrog is a public company; the OpenClaw ecosystem ended with **OpenAI hiring Peter Steinberger and moving OpenClaw into a foundation**, per [Forbes, 2026-02-16](https://www.forbes.com/sites/ronschmelzer/2026/02/16/openai-hires-openclaw-creator-peter-steinberger-and-sets-up-foundation/)).
- Even *curation* by a maximally credible brand underperforms: **`trailofbits/skills-curated` has 496 stars** and 31 skills, last pushed 2026-07-14 — against **6,919 stars** for the same firm's *authored* `trailofbits/skills`. Curation earns roughly 7% of the attention that authorship does, even when Trail of Bits is the one recommending curation as the security remedy.

---

## 5. DEMAND SIGNALS AND COMPLAINTS

### 5.0 Do skills even work? Mixed, and the biggest registry operator says "often no"

**Positive:** **SkillsBench** ([arXiv 2602.12670](https://arxiv.org/abs/2602.12670), submitted 2026-02-13, rev. 2026-06-14; Xiangyi Li et al., 77 authors) — 87 tasks × 8 domains × 18 model-harness configs with deterministic verifiers. Curated skills lifted average pass rate **33.9% → 50.5%** (+16.6pp). Crucially for this proposal: **"Focused Skills with at most three modules outperform larger or exhaustive bundles"** — an argument against selling a 20-skill bundle. The same benchmark scores 47,150 public skills at an average **6.2/12**.

**Negative, and from the operator of the largest registry:** Vercel's own eval, ["AGENTS.md outperforms Skills in our agent evals"](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals), **2026-01-27**, Jude Gao:

| Configuration | Pass rate |
|---|---|
| Baseline (no docs) | 53% |
| Skill, default | 53% (**+0pp**) |
| Skill + explicit instruction to use it | 79% |
| **8KB docs index in AGENTS.md** | **100%** |

> "In 56% of eval cases, the skill was never invoked."
> "A compressed 8KB docs index embedded directly in `AGENTS.md` achieved a 100% pass rate, while skills maxed out at 79%."
> "For general framework knowledge, passive context currently outperforms on-demand retrieval."

Vercel runs skills.sh and still tells framework maintainers to ship AGENTS.md instead of a skill. That is the most damaging single data point for a business selling framework/domain knowledge as skills.

### 5.1 Ranked complaints (with citations)

**#1 — Skills don't trigger.** The dominant complaint across evals, papers, GitHub issues and HN.
- Anthropic's own harness cannot measure it: [anthropics/skills#556](https://github.com/anthropics/skills/issues/556), opened **2026-03-07**, still open — *"run_eval.py: claude -p never triggers skills/commands (0% trigger rate across all queries)."* Independent reproductions in-thread report **0% recall across 2 skills / 60 queries** and *"0% recall across ALL 5 iterations, ALL queries, ALL description variants."* Partially root-caused to a worker-UUID race (PR #794); not closed.
- HN, `testfrequency` 2026-01-21 ([46699530](https://news.ycombinator.com/item?id=46699530)): *"I wish I knew why my skills are never called… Every time I call Claude out it tells me it knows and chose to ignore it."*
- HN, `rudedogg` ([46700528](https://news.ycombinator.com/item?id=46700528)): *"I'm having issues with the LLMs ignoring the skills content… it's put a damper in my dream of constraining them with well crafted skills."*
- Steve Kinney, [2026-03-17](https://stevekinney.com/writing/agent-skills): *"If three skills all use 'review' in their descriptions, the model is essentially guessing."* And *"Composition is not deterministic. Two runs of the same prompt can trigger different skill combinations."*

**#2 — Context bloat and the trigger-slot ceiling.** Progressive disclosure does not save you: descriptions are always resident.
- ["@skills: Attention is all you have"](https://arxiv.org/abs/2608.12610), **2026-08-12**: *"There are 56,804 public agent skills today… once installed, a skill's description remains in the system prompt, competing for **fewer than 100 reliable trigger slots**."*
- ["Skills and the discovery ceiling"](https://cdelgado70.github.io/2026/05/06/skills-and-the-discovery-ceiling.html), 2026-05-06: Claude Code caps the skills index at ~1% of context (~8,000 chars ≈ a **32-skill ceiling**) before descriptions truncate.
- [anthropics/skills#1486](https://github.com/anthropics/skills/issues/1486), 2026-07-27: *"`claude-api` skill consumes context to the point unusable. 320k tokens of context is outrageously expensive $3.50 in api costs just to load the skill."*
- HN, `gwerbin` ([48017124](https://news.ycombinator.com/item?id=48017124)): *"Even having too many skills can be an issue because the list of skill names and their descriptions all end up in the context."*

**This is fatal to the product shape specifically proposed.** A "free tier of 20 skills" plus a paid "complete pack" is asking a user to spend most of a ~32-slot budget on one vendor's bundle.

**#3 — Trust and security.** Well documented, with real incidents.
- **Snyk ToxicSkills**, 2026-02-05 (arXiv [2605.28588](https://arxiv.org/abs/2605.28588)): 3,984 skills from ClawHub + skills.sh — **13.4% critical**, **36.8% at least one flaw**, **76 confirmed malicious payloads**, 91% of malicious ones pairing code payload + prompt injection. *"The barrier to publishing a new agent skill on ClawHub? A `SKILL.md` Markdown file and a GitHub account that's one week old. No code signing. No security review. No sandbox by default."*
- ["Agent Skills in the Wild"](https://arxiv.org/abs/2601.10338), 2026-01-15: 31,132 skills, **26.1% contain ≥1 vulnerability**, 5.2% likely malicious intent.
- **The #1 downloaded skill on ClawHub was macOS infostealer malware** — [1Password, 2026-02-02](https://1password.com/blog/from-magic-to-malware-how-openclaws-agent-skills-become-an-attack-surface); HN 334 pts / 151 comments. Targeted browser cookies, saved credentials, dev tokens, SSH keys, cloud credentials.
- The registry operator's own position, quoted on HN ([46898615](https://news.ycombinator.com/item?id=46898615)): *"There's about 1 Million things people want me to do, I don't have a magical team that verifies user generated content. Can shut it down or people us their brain when finding skills."*
- A **1.7 million aggregate install** malware campaign on skills.sh (fake "Paperclip"/"Browser Use" skills reached #8 trending, Jul 2 – Aug 2 2026) — [Zenity Labs / mbgsec, 2026-08-06](https://www.mbgsec.com/posts/2026-08-06-attackers-target-agents-via-the-skill-supply-chain/). It abused progressive disclosure itself, hiding the payload in a conditionally-loaded secondary file.
- A live compromise caught in an HN thread on a front-paged skills repo, 2026-08-04 ([49171370](https://news.ycombinator.com/item?id=49171370)): *"DO NOT INSTALL THIS VIA NPX OR OPEN THIS REPO IN VSCODE. This repo has been infected by malware… The payload looks like it will fingerprint your system and try to exfil your GitHub tokens… AWS credentials… K8s secrets."*

**#4 — Slop, no quality signal, discovery at 1.3M scale.**
- skills.sh indexes **1,332,357 skills** (verified live 2026-08-31). The **top skill in the entire ecosystem is `find-skills`** (3,179,550 installs) — a meta-skill whose only job is finding other skills.
- Analysis of **55,315 public skills** ([antoinebuteau.com, 2026-05-30](https://www.antoinebuteau.com/skill-bloat-is-the-new-context-tax/)): **26.4% have no description at all**; **44.1% missing or under 20 tokens**; only **38.5% of skill paragraphs are actionable rules**.
- Star-farming is rampant — [OSS Insight](https://ossinsight.io/blog/agent-skills-explosion-2026): "250,000 GitHub stars in 10 weeks"; one repo hit **102,235 stars in ~9 days**. HN, `consumer51` ([48016405](https://news.ycombinator.com/item?id=48016405)): *"I no longer trust gh stars, can anyone chime in?"*
- **Install counts are gameable too** — HN, `pixl97` ([46898615](https://news.ycombinator.com/item?id=46898615)): *"UI is perfect for 'vote' manipulation… download your own plugin hundreds of times to get it to the top. Make it look popular. No way to share to other that the plugin is risky."* **Caveat: treat every install number in this report, including those I fetched, as directionally useful but manipulable.**

**#5 — Versioning / dependency management.** Open and unresolved.
- [vercel-labs/skills#283](https://github.com/vercel-labs/skills/issues/283) (+54), [#549](https://github.com/vercel-labs/skills/issues/549) (+46, `npm ci` equivalent), [#11 "[RFC] Versioning"](https://github.com/vercel-labs/skills/issues/11) (+27, **open since day 2 of the repo, still arguing 8 months later**).
- HN, `theahura` ([46722059](https://news.ycombinator.com/item?id=46722059)): *"You need versioning, linking between skills, an easy install client...basically a full package manager, which this is not."*
- Partially solved by `gh skill --pin <tag|sha>` + tree-SHA provenance in frontmatter. `skills-lock.json` has near-zero adoption.

**#6 — Silent breakage; no eval harness.** [Aerospike, 2026-03-31](https://aerospike.com/blog/agent-skills-guide/): *"The biggest problem with agent skills is that they fail without saying so. There is no error, no stack trace, and no signal that anything went wrong, just a skill that should have run and did not."* Named failure modes include truncation (*"the affected skills go quiet with no way to tell from the outside"*) and frontmatter corruption by an autoformatter rewrapping a description.
- OpenAI acknowledges it officially ([developers.openai.com/blog/eval-skills](https://developers.openai.com/blog/eval-skills)): *"a regression slips in: the skill doesn't trigger, it skips a required step, or it leaves extra files behind"* — but ships **guidance, not a harness** (only `codex exec --json --output-schema`).
- Cross-harness regression is its own problem: *"A SKILL.md change that passes Claude Code can silently break in Codex."*
- Maintenance is the emerging frame: the GitSkills dataset found **~3.8M SKILL.md occurrences across 282,000+ GitHub repos** (July 2026) — *"Someone has to notice when they become outdated."*

**#7 — Team / private distribution.** [vercel-labs/skills#381](https://github.com/vercel-labs/skills/issues/381) — *"Official support for private skills"* — is the **single most-upvoted issue in that repo at +78**, opened 2026-02-17, still open, called *"a top priority"* by a maintainer on 2026-02-18. [anthropics/skills#228](https://github.com/anthropics/skills/issues/228) (2026-01-13): *"Currently users must download the .skill file, send it via Slack/Teams, and have colleagues manually navigate to Settings > Capabilities to upload."*
- HN, `jillesvangurp`, 2026-08-04 ([49170811](https://news.ycombinator.com/item?id=49170811)): *"none of the major AI tool providers are really focusing much on team use of their stuff… A central repository of company skills is merely our way of improvising a solution."*

**#8 — No CI / reproducibility.** HN, `clamshelldev`, 2026-08-04 ([49170833](https://news.ycombinator.com/item?id=49170833)): *"For a central skills repository I would also record the exact rules revision in each run or generated artifact. Otherwise a failed run becomes hard to reproduce… It would be useful if each skill declared which claims are advisory and which are backed by a command the agent can execute and verify."* And the recurring counter-argument: *"move anything mechanically checkable into tests, linters, or build gates. More rules in context are not enforcement."*

### 5.2 Is the infrastructure gap already being filled?

Mostly yes — with one glaring, well-evidenced exception.

**Already filled (do not build here):**
- **Distribution / install / pinning:** `gh skill` (GitHub CLI v2.90+, 2026-04-16), `npx skills` (Vercel), ClawHub.
- **Validation:** `claude plugin validate --strict` (GA); `skills-ref validate`; linters [mgechev/skills-best-practices](https://github.com/mgechev/skills-best-practices) (2,241★), [modiqo/skillspec](https://github.com/modiqo/skillspec) (739★), [agent-sh/agnix](https://github.com/agent-sh/agnix) (400★).
- **Private / enterprise registries:** JFrog Agent Skills Registry, SkillReg ($29/$99), SkillRepo ($8/seat), Google Skill Registry (Gemini Enterprise), Chainguard, TrueFoundry, plus Anthropic's own org provisioning.
- **Context-cost controls:** `disableBundledSkills`, `skillOverrides`, `skillListingBudgetFraction` (GA); `/skill-doctor` (early access) reports per-skill 7-day token usage, never-invoked warnings, and name/trigger collisions.
- **Eval harness:** `claude plugin eval` (early access, org-gated) is a real harness — `evals/` cases, graders (`regex`, `tool_used`, `tool_order`, `file_exists`, `llm`, `baseline`), with/without baseline arms, sandboxed runs, `--threshold` / `--max-cost-usd` and exit codes for CI.

**Loudly funded but demonstrably broken — security scanning.** Despite heavy investment (NVIDIA SkillSpector 15,324★; Snyk agent-scan 2,981★; Cisco skill-scanner 2,472★; Socket/Snyk wired into skills.sh), four independent 2026 studies find scanning does not work:
1. **Mastro (June 2026)** — 5 scanners × 3,084 skills: **63.9% conflicting verdicts**; 14.2% had one scanner say CRITICAL and another SAFE; **Cohen's κ 0.01–0.18** (chance-level agreement).
2. **[Trail of Bits, 2026-06-03](https://blog.trailofbits.com/2026/06/03/the-sorry-state-of-skill-distribution/)** — built 4 malicious skills, **3 of 4 in under an hour**. Verdict: **"No amount of scanning or LLM analysis can reliably detect malicious content in agent skills."**
3. **CSA, 2026-06-10** — five products defeated across three platforms: *"No single scanner caught all four malicious skills. Some caught none."*
4. **[Gecko Security, 2026-03-11](https://www.gecko.security/blog/rce-in-your-test-suite-ai-agent-skills-bypass-skill-scanners)** — payload in a `*.test.ts` executed by Jest/Vitest on `npm test`; bypasses Snyk, Cisco and VirusTotal because all three analyze only SKILL.md and agent-invoked scripts. *"The agent is not needed. The repo is."*
- Live proof: a fake skill reached **26,000+ users** with no malicious code in the bundle at all (it pointed at a typosquatted domain, swapped later) — all three scanners tested marked it safe ([CSO Online, 2026-06-24](https://www.csoonline.com/article/4188840/)).

**The genuinely unfilled gap:** an *independent, cross-harness, open* skill **evaluation and trigger-regression** harness. The leading OSS attempt, [adewale/skill-eval-harness](https://github.com/adewale/skill-eval-harness), has **72 stars** (created 2026-06-09). Anthropic's is org-gated early access and its shipped `run_eval.py` has a 6-month-old 0%-trigger bug. OpenAI ships guidance only. `obra/superpowers` had to build its own bespoke rig.

### 5.3 The name is taken

`gh search repos "awesome-agent-skills"` (live, 2026-08-31):

| Repo | Stars | Last push |
|---|---:|---|
| **VoltAgent/awesome-agent-skills** | **33,396** | 2026-08-29 | "1000+ agent skills from official dev teams and the community, compatible with Claude Code…" |
| heilcheng/awesome-agent-skills | 6,157 | 2026-04-05 |
| libukai/awesome-agent-skills | 5,028 | 2026-08-05 |
| gamedev-skills/awesome-gamedev-agent-skills | 761 | 2026-08-24 |
| skillmatic-ai/awesome-agent-skills | 665 | 2026-05-14 |
| JackyST0/awesome-agent-skills | 629 | 2026-08-24 |
| kodustech/awesome-agent-skills | 98 | 2026-08-14 |

Even the *vertical* variants are taken and better-scoped than the proposal (e.g. `gamedev-skills/awesome-gamedev-agent-skills` — 67 game-dev skills across Godot/Unity/Unreal/Phaser/three.js/Bevy; `RKiding/Awesome-finance-skills` at 2,825★; `new-silvermoon/awesome-android-agent-skills` at 946★).

---

## 6. VERDICT

### 6.1 Blunt answer

**The content play is dead on arrival. Skip it. Confidence: high (~90%).**

**The infrastructure play is alive but mostly claimed. One sub-slice — cross-harness skill evaluation and trigger-regression testing — is genuinely open. Confidence that it is open: medium-high (~70%). Confidence that it is a *good business*: low (~25%).**

### 6.2 Why the content play fails — five independent kill-shots

Any one of these would be a serious problem. All five are true simultaneously.

1. **First-party vendors own the domains.** All ten proposed skills already exist, and the highest-installed versions are published by the companies that build the technology: `supabase/agent-skills/supabase-postgres-best-practices` (**378,417 installs**), `getsentry/skills/security-review` (**14,901**), `fastapi/fastapi` (in the FastAPI repo itself), `microsoft/vscode/accessibility`, `github/awesome-copilot` (**432 skills**), `auth0/agent-skills`, `langchain-ai/langchain-skills`. You cannot out-Postgres Supabase, and they charge $0 and update with the product.

2. **The free quality bar is already above "production-grade."** `obra/superpowers` (**279,694★**, MIT) ships automated **skill-triggering regression tests across models** (`tests/explicit-skill-requests/` with prompt fixtures + multi-turn + Haiku runs), token-usage analysis, harness conformance suites for eight runtimes, pre-commit hooks and shell linting. `mattpocock/skills` (**241,914★**, MIT) gives away a `code-review` skill with parallel Standards/Spec sub-agents and an embedded twelve-item Fowler smell baseline. `anthropics/skills` ships **198 script files**. A solo 20-skill pack does not beat this, let alone at $29.

3. **The distribution economics are inverted.** The channels are free and vendor-run (`gh skill`, `npx skills`, ClawHub, Anthropic's directory), and **Anthropic has built no author-payout rail at all**. The only paid content marketplace found (Agensi) has zero verifiable sales and internally inconsistent marketing. PromptBase, the precedent, is in decline at a 20% take rate.

4. **The context budget makes a 20-skill bundle actively harmful.** Descriptions are permanently resident; Claude Code caps the skills index around **~1% of context (~32 skills)**; the research framing is **"fewer than 100 reliable trigger slots"** against **56,804+ public skills**. SkillsBench found **"Focused Skills with at most three modules outperform larger or exhaustive bundles."** Selling someone a 20-skill pack sells them most of their trigger budget — and self-generated / "comprehensive" skills scored *negative* in that benchmark.

5. **The generator is free and shipped by the platform.** `anthropics/skill-creator` has **367,122 installs**. Anthropic's most-installed catalog skill is the one that writes skills. Marginal cost of supply → 0.

Two smaller nails: the **repo name is taken** by `VoltAgent/awesome-agent-skills` at **33,396 stars** with "1000+ skills," and the **$29/$99 price points are already occupied** by SkillReg, live, with a governance and security-scanning moat.

### 6.3 The strongest argument AGAINST — the one to take seriously

Not saturation. This:

> **Vercel — which operates skills.sh, the largest skills registry on earth — published its own eval concluding that an 8KB docs index in `AGENTS.md` beats skills outright: 100% pass rate vs 79% for a skill with explicit instructions, vs 53% baseline. Default skills scored 53% — identical to no documentation at all — because "in 56% of eval cases, the skill was never invoked."**

The proposed product is *domain knowledge packaged as skills*. Vercel's finding is that for exactly that use case — general framework/domain knowledge — the skill wrapper is the wrong container, and passive context wins. The registry operator's own recommendation to framework maintainers is to ship AGENTS.md instead.

So the risk is not "someone else built this already." It is: **the entire product category may be an inferior delivery mechanism for the thing being sold**, and the company with the most data on the subject has said so publicly.

Second-order version of the same argument: skills are a **context-management strategy, not a capability**. As Steve Kinney puts it, *"Skills don't give you new capability — they give you consistency."* Consistency is worth something to a team with a codified process. It is not worth $29 to an individual who can ask their agent to write the same skill in 30 seconds.

### 6.4 Where the real opportunity is — infrastructure, and one specific slice of it

Mapping the seven infrastructure candidates against what already exists:

| Candidate | Status | Verdict |
|---|---|---|
| Registry / discovery | GitHub (`gh skill`), Vercel (skills.sh, 1.33M skills), ClawHub | **Taken.** Don't. |
| Cross-vendor format bridge | Spec converged; `.agents/skills/` read natively by Copilot/Claude Code/Codex/Cursor/Gemini/Amp; 46 clients | **No market.** |
| Team / private distribution | JFrog, SkillReg ($29/$99), SkillRepo ($8/seat), Google Skill Registry, Anthropic org provisioning; and repo-committed `.agents/skills/` is free and solves 80% | **Crowded**, and the free default is good enough for most teams. |
| Security scanning | Heavily funded (NVIDIA 15,324★, Snyk, Cisco) and **independently proven not to work** — four 2026 studies, Cohen's κ 0.01–0.18 between scanners, Trail of Bits: *"No amount of scanning or LLM analysis can reliably detect malicious content in agent skills."* | **Contested and possibly unsolvable.** Entering here means competing with NVIDIA and Snyk on a problem they have not solved. |
| Versioning / lockfiles | `gh skill --pin` + tree-SHA provenance covers pinning; `skills-lock.json` has near-zero adoption; vercel-labs/skills#11 open 8 months | **Half-open, but it's Vercel's and GitHub's to close.** |
| Curation / quality signal | Trail of Bits recommends curation — but their own curated repo has **496 stars** vs 6,919 for their authored one | **Weak demand.** Curation is not what people install. |
| **Skill evaluation / trigger-regression testing** | Leading OSS harness has **72 stars**. Anthropic's `claude plugin eval` is **org-gated early access** and its shipped `run_eval.py` has an open 0%-trigger bug since **2026-03-07**. OpenAI ships *guidance only*. `obra/superpowers` had to build a bespoke rig. Cross-harness regression (*"passes Claude Code, silently breaks in Codex"*) is unowned. | **GENUINELY OPEN.** |

**The three sharpest gaps, ranked:**

1. **Trigger reliability measurement.** The #1 complaint in every venue, quantified by the registry operator at **56% never invoked**, and the platform vendors' own tooling cannot measure it. An open, cross-harness harness that answers "does my skill fire, on which phrasings, on which models, and did that regress?" is the one thing nobody has shipped well.
2. **Context-budget accounting.** With a ~32-skill practical ceiling and skills costing measurable tokens every turn, "what is this skill costing me, and is it earning it?" is unowned outside Anthropic's early-access `/skill-doctor`.
3. **Maintenance / staleness at scale.** ~3.8M SKILL.md occurrences across 282,000+ repos; skills fail silently and nobody notices when they go stale.

**But be honest about why this is still a bad business:** all three are *developer tools for a free artifact*. The buyers are the same people who won't pay $29 for content. Anthropic, GitHub and Vercel each have an obvious incentive to absorb the winner into their free tier — Anthropic is already ~80% of the way there with `claude plugin eval` and `/skill-doctor`. This is a "build it open, earn reputation, monetize via consulting" play — precisely the `obra/superpowers` → `sales@primeradiant.com` pattern — not a $29/$99 SaaS.

### 6.5 Recommendation

- **SKIP** the paid skills library. Do not build `awesome-agent-skills`.
- **CONTRIBUTE** if the goal is reputation: publish 3–5 genuinely excellent, *narrow* skills (SkillsBench: ≤3 modules beats bundles) into an existing high-traffic channel, MIT-licensed, with real evals attached. This is the cheapest path to credibility and costs weeks, not quarters.
- **BUILD only** if the appetite is for open-source infrastructure with a services business behind it: a cross-harness **skill trigger-regression + context-cost harness**. Ship it free, expect Anthropic to compete, and monetize the enterprise engagements it generates.
- **Do not** enter security scanning, registries, or format bridging.

### 6.6 Caveats and confidence

- **Install and star counts in this ecosystem are manipulable.** HN commenters describe both star-farming (one repo gained 102,235 stars in ~9 days) and install-count gaming (*"download your own plugin hundreds of times to get it to the top"*). I fetched every number live from the GitHub API and the skills.sh API, but the underlying metrics are not audited. Directional, not precise.
- **Reddit was not directly reachable** from this environment; Reddit-attributed sentiment is second-hand and marked UNVERIFIED.
- **Agensi's revenue-share terms are self-reported and internally inconsistent** (70/30 in one place, 80% in another); no sales data exists.
- ClawHub's "13,000+ skills", skillscatalog.ai's offering, and the Ed25519 enterprise plugin-distribution detail are **UNVERIFIED**.
- The Medium claim of ClawHub builders earning "$600–$20,000/month" is **UNVERIFIED and contradicted** by ClawHub's stated free-listings policy.
- Star counts moved fast in this ecosystem; all figures are a 2026-08-31 snapshot.
