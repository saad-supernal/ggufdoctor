# Technical Due Diligence: "Unified Agent Configuration" (`.agent/` + `agent sync` CLI)

**Date of research:** 2026-08-31. All star counts, commit counts, and issue counts were pulled live from the GitHub API on this date via authenticated `gh api`. npm download figures pulled live from `api.npmjs.org` (last 30 days).

**Verdict up front:** The premise is largely obsolete. Convergence has happened at the format layer (AGENTS.md, SKILL.md, Agent Plugins 1.0), the sync-tool niche has consolidated to two well-funded-by-attention survivors with ~1.25M combined monthly npm downloads, and the one remaining pain point (Claude Code) is a single-vendor holdout that Anthropic has publicly signalled it will address. **Recommendation: do not build. Contribute instead.** Confidence: high (~85%).

---

## 1. PRIOR ART CENSUS

### 1a. Dedicated sync/generate tools — the direct competitors

| Project | Stars | Commits (90d) | Open issues | License | Maintainer | npm dl/mo | Status |
|---|---:|---:|---:|---|---|---:|---|
| [dyoshikawa/rulesync](https://github.com/dyoshikawa/rulesync) | **1,363** | **2,023** | 76 | MIT | solo (dyoshikawa) | **1,061,402** | **ALIVE — category leader** |
| [intellectronica/ruler](https://github.com/intellectronica/ruler) | **2,901** | 126 | 9 | MIT | solo (Eleanor Berger) | **192,541** | **ALIVE — #2** |
| [PanisHandsome/ai-rules-sync](https://github.com/PanisHandsome/ai-rules-sync) | 118 | 1 | 0 | MIT | solo | — | barely alive |
| [yelmuratoff/agent_sync](https://github.com/yelmuratoff/agent_sync) | 14 | 109 | 1 | GPL-3.0 | solo | — | alive, tiny |
| [spxrogers/agentsync](https://github.com/spxrogers/agentsync) | 10 | 87 | 22 | MIT | solo | — | alive, tiny |
| [lbb00/ai-rules-sync](https://github.com/lbb00/ai-rules-sync) | 37 | 11 | 2 | Unlicense | solo | — | alive, tiny |
| [cortesi/agentsmd](https://github.com/cortesi/agentsmd) | 9 | 2 | 0 | MIT | solo | — | marginal |
| [FutureExcited/vibe-rules](https://github.com/FutureExcited/vibe-rules) | 529 | **0** (last push 2025-08-21) | 12 | MIT | solo | 57,420 (residual) | **DEAD** |
| [botingw/rulebook-ai](https://github.com/botingw/rulebook-ai) | 603 | **0** (last push 2025-10-03) | 23 | MIT | solo | — | **DEAD** |
| [steipete/agent-rules](https://github.com/steipete/agent-rules) | 5,696 | 0 | 0 | MIT | solo (Peter Steinberger) | — | **ARCHIVED** |
| [gabimoncha/cursor-rules-cli](https://github.com/gabimoncha/cursor-rules-cli) | 50 | 0 | 1 | MIT | solo | — | **DEAD** |
| [mitkury/airul](https://github.com/mitkury/airul) | 34 | 0 | 0 | MIT | solo | 238 | **DEAD** |
| [airulefy/Airulefy](https://github.com/airulefy/Airulefy) | 33 | 0 | 5 | MIT | solo | — | **DEAD** |
| [hcastro/cursor2claude](https://github.com/hcastro/cursor2claude) | 25 | 0 | 3 | MIT | solo | — | **DEAD** |
| [intellectronica/claude-agentsmd](https://github.com/intellectronica/claude-agentsmd) | 18 | 0 | 0 | CC0 | solo | — | **DEAD** (author folded it into ruler) |
| [Ratler/airuler](https://github.com/Ratler/airuler) | 16 | 0 | 5 | MIT | solo | — | **DEAD** |
| [upamune/airulesync](https://github.com/upamune/airulesync) | 8 | 0 | 0 | MIT | solo | — | **ARCHIVED** |
| [weykon/agent-hooks](https://github.com/weykon/agent-hooks) | 6 | 0 | 0 | MIT | solo | — | **DEAD** |
| [lastmile-ai/aiconfig](https://github.com/lastmile-ai/aiconfig) | 1,087 | 0 (last push 2026-02-10) | 165 | MIT | company (LastMile AI) | — | **DEAD** — and unrelated (prompt-as-config for apps, not agent rules) |

**Key structural finding:** a 2025 wave of ~12 sync tools existed. As of Aug 2026, **all of them are dead or archived except two**. This is a consolidated, not an empty, market. Death was not from lack of stars (vibe-rules had 529, rulebook-ai 603, agent-rules 5,696) — it was from the maintenance treadmill (see §3).

### 1b. Standards & spec layer

| Project | Stars | Commits (90d) | Open issues | License | Governance |
|---|---:|---:|---:|---|---|
| [agentsmd/agents.md](https://github.com/agentsmd/agents.md) | **23,997** | 1 (spec is stable) | 169 | MIT | **Linux Foundation / Agentic AI Foundation** |
| [agentplugins/agent-plugins-spec](https://github.com/agentplugins/agent-plugins-spec) | **1,189** | 79 | 13 | — | Multi-vendor charter (Amazon, Cursor, Microsoft, OpenAI, Vercel, +Google) |
| [anthropics/skills](https://github.com/anthropics/skills) | 172,653 | 15 | 1,190 | none | Anthropic (Agent Skills open standard) |

### 1c. Adjacent — workflow/method frameworks (NOT direct competitors, but they occupy the `.agent/`-shaped mindshare)

| Project | Stars | Commits (90d) | Open issues | License | Status |
|---|---:|---:|---:|---|---|
| [github/spec-kit](https://github.com/github/spec-kit) | **132,359** | 822 | 335 | MIT | ALIVE (GitHub/Microsoft) |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) (formerly `claude-flow`) | 69,858 | 731 | 870 | MIT | ALIVE — **note: renamed** |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | 52,481 | 179 | 33 | custom | ALIVE |
| [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master) | 28,036 | **0** (last push 2026-04-28) | 212 | custom | **DORMANT/DEAD** |
| [SuperClaude-Org/SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework) | 23,851 | 2 | 73 | MIT | **DYING** |
| [buildermethods/agent-os](https://github.com/buildermethods/agent-os) | 5,350 | 1 | 2 | MIT | near-dormant |
| [udecode/dotai](https://github.com/udecode/dotai) | 1,153 | 28 | 0 | **none** | alive |

### 1d. Harnesses (the sync targets themselves)

| Project | Stars | Commits (90d) | Open issues | Status |
|---|---:|---:|---:|---|
| [anomalyco/opencode](https://github.com/anomalyco/opencode) (formerly `sst/opencode`) | **202,605** | 1,953 | 5,635 | ALIVE — **note: moved org** |
| [cline/cline](https://github.com/cline/cline) | 67,189 | 1,153 | 1,153 | ALIVE |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | 48,613 | **0** (last push 2026-05-22) | 1,837 | **DORMANT** |
| [continuedev/continue](https://github.com/continuedev/continue) | 35,705 | 24 | 947 | slowing sharply |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | 32,568 | 3 | 447 | official OpenAI CC↔Codex bridge |
| [Kilo-Org/kilocode](https://github.com/Kilo-Org/kilocode) | 27,090 | 7,298 | 569 | very active |
| [RooCodeInc/Roo-Code](https://github.com/RooCodeInc/Roo-Code) | 24,319 | 0 | 1,034 | **ARCHIVED / EOL** (successor: Zoo Code) |

> Sanity note for anyone with 2025-era priors: `sst/opencode` → `anomalyco/opencode`; `ruvnet/claude-flow` → `ruvnet/ruflo`; Roo Code is EOL; Aider and Task Master have gone quiet. Do not cite stale names.

---

## 2. HAS THE PROBLEM BEEN SOLVED BY CONVERGENCE?

**Yes — substantially. This is the single most important finding.**

### 2a. AGENTS.md adoption is decisive

- **70,144 non-fork GitHub repositories** contain an `AGENTS.md` (live GitHub code search, `filename:AGENTS.md`, 2026-08-31). agents.md itself claims "over 60k open-source projects."
- Governance moved to a neutral body: the **Linux Foundation announced the Agentic AI Foundation (AAIF) on 2025-12-09**, anchored by three donated projects — **Anthropic's MCP, Block's goose, and OpenAI's AGENTS.md**. AAIF launched with **150+ member organisations**, described as the fastest-growing foundation in LF history. ([Linux Foundation press release](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation), [OpenAI](https://openai.com/index/agentic-ai-foundation/), [aaif.io](https://aaif.io/))
- Tools listed on [agents.md](https://agents.md/) as natively reading it (23): **Codex, Jules, Factory, Aider, goose, opencode, Zed, Warp, VS Code, Devin, UiPath, Junie (JetBrains), Amp, Cursor, RooCode, Gemini CLI, Kilo Code, Phoenix, Semgrep, GitHub Copilot Coding Agent, Ona, Windsurf, Augment Code.**

### 2b. Claude Code is the ONE holdout — verified, and it is a narrow, closing gap

Official Anthropic documentation states unambiguously ([code.claude.com/docs/en/memory](https://code.claude.com/docs/en/memory)):

> "Claude Code reads `CLAUDE.md`, not `AGENTS.md`. If your repository already uses `AGENTS.md` for other coding agents, create a `CLAUDE.md` that imports it..."

So: **UNVERIFIED-as-false is the widely-repeated claim that Claude Code "reads AGENTS.md as a fallback." It does not.** Blog posts asserting Claude Code supports AGENTS.md natively (e.g. codersera, buildbetter) are **wrong**; the primary source contradicts them.

**But the workarounds are first-party, documented, and now automated:**
1. `CLAUDE.md` containing `@AGENTS.md` (one-line import) — the officially recommended pattern.
2. `ln -s AGENTS.md CLAUDE.md` — officially documented.
3. **`/init` with `CLAUDE_CODE_NEW_INIT=1` reads `AGENTS.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`, `.devin/rules/`, `.windsurf/rules/` or `.windsurfrules`, and `.clinerules`** and folds them into the generated CLAUDE.md.
4. **`/import` (Claude Code v2.1.213+)** — "brings a supported coding agent's configuration into Claude Code, which appends a one-time copy of instruction files such as `AGENTS.md` to the matching `CLAUDE.md` and **carries over MCP servers, commands, subagents, and skills.**"

**Item 4 is Anthropic shipping the proposed product's import path as a built-in command.** It is one-shot rather than continuous, but it removes the bulk of the value proposition.

**Issue [#6235](https://github.com/anthropics/claude-code/issues/6235) status (live API, 2026-08-31):** `state: closed`, `state_reason: completed`, updated 2026-08-29. **5,088 👍 / 6,548 total reactions / 387 comments** — the most-reacted issue on the tracker. It was closed with a Claude-generated comment pointing at the `@AGENTS.md` import, which the community read as a brush-off. Duplicates remain open: [#78977](https://github.com/anthropics/claude-code/issues/78977), [#31005](https://github.com/anthropics/claude-code/issues/31005) (22 comments), [#34235](https://github.com/anthropics/claude-code/issues/34235) (14 comments), [#89825](https://github.com/anthropics/claude-code/issues/89825).

**Forward-looking signal:** an Anthropic engineer (@trq212) stated publicly, quoted in the #6235 thread on 2026-08-26:
> "We are working on making Claude Code more hackable, which will include being able to easily use Agents.MD or make other system prompt modifications."

**A sync tool whose flagship job is "make Claude Code see your AGENTS.md" is building on a fault line that the vendor has announced it will close.**

### 2c. Skills convergence: also solved

- **Agent Skills** is an open standard (`SKILL.md`): created at Anthropic Sept 2025, shipped Oct 2025, **published as a spec Dec 2025**. Roughly **40–44 products** support it, including Codex CLI, Gemini CLI, GitHub Copilot, Cursor (since v2.4, 2026-01-22), Goose, Cline.
- **Codex CLI 0.147.0 (2026-08-07)** shipped the ability to import Cursor-managed skills — three vendors, one `SKILL.md`.
- **`.agents/skills/` has emerged as the shared cross-vendor directory.**

### 2d. Agent Plugins 1.0 — the killer datapoint

**Released 2026-08-06**, three weeks before this research. [agentplugins/agent-plugins-spec](https://github.com/agentplugins/agent-plugins-spec), 1,189 stars, 79 commits/90d.

- A plugin is **a directory with `plugin.json`, an optional `skills/` folder, and an optional `mcp.json`.**
- **Core Maintainers: Amazon, Cursor, Microsoft, OpenAI, Vercel** (Google joining, represented by Kevin Hou). Charter forbids any single vendor holding a majority of seats.
- **Launch clients: ChatGPT, Codex, Cursor, GitHub Copilot, Kiro, VS Code.** GitHub shipped support in VS Code, Copilot CLI and the Copilot app on [2026-08-12](https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app/).

**This is a vendor-neutral, industry-backed version of roughly half of the proposed `.agent/` directory — shipped, with six launch clients, three weeks ago.** Building a competing bespoke `.agent/` layout now means competing with Amazon+Microsoft+OpenAI+Cursor+Vercel+Google.

**Explicitly out of scope in v1.0.0:** permission model, sandboxing, signature verification, secrets. Also **not covered**: rules/instructions files, subagents, hooks, memory, commands. (See §4 — this is where the remaining gaps live.)

### 2e. The `.agent/` directory idea specifically was already proposed — and ignored

[agentsmd/agents.md#71](https://github.com/agentsmd/agents.md/issues/71), "Proposal: Standardize a `.agent` Directory for Comprehensive Project Context," opened **2025-09-25** by @haoranba. Proposed `AGENT.md` + `spec/` + `wiki/` + `links/`. **Still open, no maintainer response, no labels, no assignee, 11 months later.** Related open proposals: [#179](https://github.com/agentsmd/agents.md/issues/179) (standardized `.agents/rules/` format), [#185](https://github.com/agentsmd/agents.md/issues/185) (different content to different agents), [#184](https://github.com/agentsmd/agents.md/issues/184) (Agent Specification).

The AGENTS.md maintainers have deliberately kept the standard minimal — plain Markdown, schema-free. They are not going to bless a directory structure. That is simultaneously the gap *and* the reason nobody has filled it: the neutral body with the authority to standardize it has chosen not to.

**Blunt convergence verdict: the "sync" thesis has lost most of its value.** The format war is over. What remains is (a) one vendor holdout with documented one-line workarounds and an announced fix, and (b) the long tail of *non-instruction* config (permissions, hooks, subagents) that no standard covers.

---

## 3. LIMITATIONS OF WHAT EXISTS

### rulesync (1,363★, 2,023 commits/90d, 76 open issues, 1.06M npm dl/mo)

The dominant tool. Syncs six feature categories — **rules, ignore (deprecated), mcp, commands, subagents, skills** — plus hooks, permissions and checks for select tools, across **40+ targets**.

Reading its open issue list is the most instructive artefact in this entire research. The issues are almost entirely **per-adapter semantic mismatch bugs**, which is exactly the failure mode the proposed product would inherit:

- `#2831` — "command-capable adapters other than the four command-only ones ignore the all-tools `*` category"
- `#2829` — "Hermes `command_allowlist` takes allow rules from every category while deny is read from bash and webfetch only"
- `#2830` — "deepagents-cli writes an allow that a restriction covers, while the other command-only adapters withhold it"
- `#2825` — "A deny under the all-tools `*` category escapes the shadowed-rule warning"
- `#2790` — "Muse Code upstream updates: **hooks and permissions still blocked on unpublished schemas**"
- `#2796` — "Shared JSONC configs lose the user's comments on write-back"
- `#2797` — "`rulesync import --features permissions` replaces the canonical file instead of merging per category"
- `#2749` — "Factory Droid: the DESIGN.md design-guidelines channel is never emitted"

Documented caveats from its README: the `ignore` feature is **deprecated** in favour of permissions; plugin packaging targets are **excluded from `--targets "*"`**; **Kiro had to be split** into `kiro-cli` and `kiro-ide` because their config formats diverged; **Roo Code is EOL** and users must migrate to Zoo Code.

It is also carrying a permanent tracking backlog of *new* targets to support: `#2762` Crush, `#2761` Continue, `#2760` CodeBuddy. **The treadmill never stops.** 2,023 commits in 90 days (~22/day) for a solo maintainer is the cost of staying in this business — and it is why the other twelve tools died.

### ruler (2,901★, 126 commits/90d, 9 open issues, 193k npm dl/mo)

More stars, far fewer commits, tighter scope. Supports 30+ agents; syncs rules, MCP servers (via `ruler.toml`), `.gitignore` management, plus **experimental** skills and subagents.

Stated limitations, verbatim from its own docs:
- **"All agents currently receive identical concatenated rules; agent-specific guidance requires manual sections in rule files."** — i.e. it does not solve per-tool semantic differentiation at all.
- Skills support "only propagates to agents with native support"; subagents are experimental, "behavior may change," and **disabled by default**.
- Nested mode is experimental.
- Subagent directories are **atomically replaced — manual edits are overwritten on every apply.**
- Windsurf, RooCode, Aider have no native subagent support to target.
- No explicit revert for subagents.

Open feature requests reveal the real user asks: `#392` "allow **per-agent** skills propagation instead of global `--skills`/`--no-skills`", `#678` "generic custom frontmatter for **harness-specific** subagent configuration", `#399` env-var substitution in TOML, `#319` merge global + local configs.

### Community sentiment (HN, verified threads)

HN thread [49367350](https://news.ycombinator.com/item?id=49367350) "Feature Request: Support AGENTS.md" (2026-08-19, **378 points, 220 comments**) is the best sentiment sample. Representative positions:

- **The dominant view is that the problem is trivial**: "My Claude.md has one line that says to read agents.md, **this is a bit of a nothingburger**" (chomp). "You can save a tool call by just making it a symlink" (eigenspace). "a simple symlink from AGENTS.md -> CLAUDE.md works well enough" (verdverm).
- **The minority pro-tooling view names the real residue**: "But it's not just claude.md. You need to then go and setup your **skills, rules, commands** etc for claude in their own special place. Sure it's small, but **it adds up**" (Jcampuzano2). "Also the skills are different. it's quite annoying!" (wilg).
- **A genuine failure mode of indirection**: "Having a CLAUDE.md that just says 'Read AGENTS.md' resulted in **Claude randomly not following the rules**" (superfrank). This is a real, under-tooled problem — but it is an *adherence* problem, not a sync problem, and a sync tool cannot fix it.
- **A counterargument to full unification**: "CLAUDE.md can still hold Claude specific rules... my instructions have lot of stuff specific to Claude — how subagent works, how async tool calling works, quirks of WebFetch etc. **All this has zero value for other agents**" (Mart-Bogdan). Unification is not universally desired.
- Much of the thread is anti-Anthropic sentiment rather than demand for tooling.

**Market-interest signal — this is damning.** Every `rulesync` Show HN has flatlined: [44382989](https://news.ycombinator.com/item?id=44382989) (1 pt), [44480341](https://news.ycombinator.com/item?id=44480341) (1 pt), [44612918](https://news.ycombinator.com/item?id=44612918) (2 pts), [48051242](https://news.ycombinator.com/item?id=48051242) (1 pt, 1 comment), [49193083](https://news.ycombinator.com/item?id=49193083) (1 pt). Meanwhile a fresh "Show HN: Manage coding norms across your AI agents" ([49503387](https://news.ycombinator.com/item?id=49503387), 2026-08-30) got **1 point**. And "Ask HN: How are teams sharing AI/agent setups internally?" ([49330900](https://news.ycombinator.com/item?id=49330900), 2026-08-17) got **zero comments**.

**Interpretation:** rulesync's 1M monthly npm downloads prove the tool is *used* (largely in CI), but the community has **zero appetite for discussing another one**. This is a solved-enough problem that nobody wants to read about it. That is the worst possible launch environment for a new entrant.

---

## 4. GENUINE UNSOLVED GAPS

These are real, but note that each comes with a reason nobody has solved it.

**Gap 1 — Instruction *adherence* verification, not distribution.** Every tool guarantees files are *identical*; none verifies the rules are *followed* or still *correct*. Anthropic's own docs concede "there's no guarantee of strict compliance" and that CLAUDE.md is "context, not enforced configuration." @superfrank's HN report — indirection via `@AGENTS.md` degrades rule-following — is measurable and untooled. The only product spotted attacking this is **Blume** (desktop app, detects behavioural drift and proposes fixes; UNVERIFIED — could not confirm repo/traction). Related: HN [46809708](https://news.ycombinator.com/item?id=46809708) "AGENTS.md outperforms skills in our agent evals" (524 pts) and [47034087](https://news.ycombinator.com/item?id=47034087) "Evaluating AGENTS.md: are they helpful for coding agents?" (232 pts) — both far more upvoted than any sync tool. **Why unsolved:** requires an eval harness per agent and a ground-truth signal; it is an ML-eval problem, not a codegen problem. **Difficulty: high.** **This is the most interesting gap in the space and it is *not* a sync tool.**

**Gap 2 — Permissions / hooks / sandbox policy portability.** Agent Plugins 1.0 explicitly excludes permission model, sandboxing, signatures and secrets. AGENTS.md excludes them. rulesync's open issues (`#2831`, `#2829`, `#2830`, `#2825`, `#2790`) show its permission translation is materially broken across adapters and **blocked on unpublished vendor schemas**. Hooks are the least portable primitive of all — `weykon/agent-hooks`, the only tool that tried, is dead at 6 stars. **Why unsolved:** the semantics genuinely differ (Claude Code's `PreToolUse` has no Cursor equivalent), vendors don't publish schemas, and getting it wrong is a *security* failure, not a cosmetic one. **Difficulty: very high, and partly impossible** — you cannot faithfully translate a deny-rule into a harness with no deny concept, and silently degrading a security control is worse than not syncing it.

**Gap 3 — Per-agent differentiation from a shared source.** Both leaders fail here identically. Ruler: "All agents currently receive identical concatenated rules." rulesync ships everything everywhere. But Mart-Bogdan's point stands — Claude-specific subagent/WebFetch guidance is noise in Codex, and vice versa. This is [agents.md#185](https://github.com/agentsmd/agents.md/issues/185) (open since 2026-05-13) and [ruler#678](https://github.com/intellectronica/ruler/issues/678) / [ruler#392](https://github.com/intellectronica/ruler/issues/392). **Why unsolved:** needs a conditional/templating layer, which every maintainer resists because it turns a plain-Markdown file into a programming language. **Difficulty: medium — the most tractable gap, and it is a PR to ruler, not a product.**

**Gap 4 — Team/org-level distribution across many repos.** All existing tools are single-repo. There is no good answer for "50 repos, one org standard, versioned, with staged rollout and per-repo override." rulesync has a `pull` command and a GitHub Action, but the article note that "pull-based distribution keeps files identical, but it cannot tell you whether the rules themselves are still correct" is the honest assessment. Ask HN [49330900](https://news.ycombinator.com/item?id=49330900) asked this exact question and got **zero replies**. **Why unsolved:** it is a distribution/policy problem needing org buy-in; and Anthropic already ships managed-policy CLAUDE.md via MDM for the enterprise case. **Difficulty: medium.** **The zero replies suggest the demand is not there yet.**

**Gap 5 — Memory portability.** Claude Code auto-memory lives in `~/.claude/projects/<project>/memory/` with a `MEMORY.md` index; it is explicitly **machine-local and not shared across machines**. No standard exists, no tool syncs it, no other vendor has a comparable primitive to sync *to*. **Why unsolved:** there is nothing to be portable *with* — it is a single-vendor feature. **Difficulty: low technically, but the addressable market is one product.** The proposed `.agent/memory/` folder is, on this evidence, the weakest part of the pitch.

---

## 5. VERDICT

### Is this a legitimate opportunity in Aug 2026?

**No. Skip building it.** Confidence: **high (~85%)**.

Five independent lines of evidence:

1. **The format war is over and you lost the timing by ~12 months.** AGENTS.md: 70,144 repos, 23+ native tools, Linux Foundation governance. SKILL.md: ~44 products, `.agents/skills/` as the shared directory. Agent Plugins 1.0 (`plugin.json` + `skills/` + `mcp.json`): six launch clients, six of the largest vendors as maintainers, shipped 2026-08-06.

2. **Your differentiating target has a first-party answer.** The one holdout is Claude Code, and Anthropic ships `@AGENTS.md` import, symlink support, `/init` that reads five competitors' rule formats, and **`/import` (v2.1.213+) that carries over MCP servers, commands, subagents and skills**. An Anthropic engineer has publicly said easy AGENTS.md use is coming. Build a business on that gap and you are betting against the vendor's stated roadmap.

3. **The category already consolidated, and the losers had more stars than you'll start with.** Twelve dedicated sync tools died in 12 months, including ones at 529, 603 and 5,696 stars. Two survived. **rulesync does ~22 commits/day** to stay alive. You would be entering a market where the price of admission is a full-time adapter-maintenance treadmill against 40+ moving vendor targets — several of which (`#2790`) have **unpublished schemas** you cannot support at any effort level.

4. **Nobody wants to talk about it.** Five rulesync Show HNs at 1–2 points each. A brand-new competing Show HN at 1 point (2026-08-30). An Ask HN on exactly this problem with zero replies. On the biggest relevant HN thread the top-voted framing is **"this is a bit of a nothingburger."** You cannot get distribution for a tool the community considers solved by `ln -s`.

5. **The `.agent/` directory idea specifically has been sitting rejected-by-silence for 11 months** ([agents.md#71](https://github.com/agentsmd/agents.md/issues/71)). The neutral body that could bless it has deliberately chosen minimalism.

### The strongest argument AGAINST building it

**You would be building a translation layer over an actively converging standard — which means your product's total addressable value shrinks every month by design, while your maintenance cost grows every month with each new harness.** rulesync's 76 open issues are almost all "adapter X's permission semantics differ from adapter Y's"; that backlog is not a bug list, it is the permanent shape of the work. And the specific residual pain your product monetises (Claude Code ≠ AGENTS.md) is a **single vendor decision away from evaporating** — one that Anthropic has already publicly signalled. You would ship into a market whose incumbents can't get 2 upvotes and whose users' preferred solution is a symlink.

### The strongest argument FOR (steelman, for completeness)

rulesync's **1,061,402 npm downloads/month** and ruler's **192,541** are not noise — a million-download-a-month category is real, and it is served by exactly two solo maintainers with a combined 85 open issues and one of them (rulesync) is a one-person 22-commit-a-day treadmill with obvious bus-factor risk. If either burns out, the category is undefended. But note: this is an argument for *acquiring or contributing to* the incumbents, not for starting from zero.

### Recommendation: CONTRIBUTE, and pick the specific PR

**Primary target: [intellectronica/ruler](https://github.com/intellectronica/ruler)** — 2,901 stars, 193k npm downloads/month, only **9 open issues**, 126 commits/90d, MIT, clean scope. It is the healthiest project with the most room. rulesync is too fast-moving to join usefully; ruler is receptive and under-resourced.

**Ship this, in order:**

1. **[ruler#678](https://github.com/intellectronica/ruler/issues/678) + [ruler#392](https://github.com/intellectronica/ruler/issues/392) — per-agent differentiation.** Ruler's own docs admit "all agents currently receive identical concatenated rules." Add `agents:` frontmatter to `.ruler/*.md` (and per-agent `--skills` propagation) so one source can emit Claude-specific and Codex-specific sections. This is **Gap 3**, the most tractable real gap, it is explicitly requested by users, and it is the single highest-leverage change in the category. Medium difficulty, days-to-weeks of work.
2. **Agent Plugins 1.0 as a first-class ruler target.** Emit `plugin.json` + `skills/` + `mcp.json` from `.ruler/`. Six launch clients, zero tools currently bridge `.ruler/` to it. This rides the standard instead of competing with it.
3. **A `ruler doctor` / drift-detection command** — verify generated files still match source, report divergence, exit non-zero in CI. Addresses the drift complaint directly with a fraction of the surface area of a new product.

**If you want to build something new anyway, build Gap 1, not the sync tool.** An *adherence* checker — does the agent actually follow the rules in this file, per harness, measured — is genuinely unsolved, is what the HN crowd actually upvotes (524 and 232 points for AGENTS.md eval posts vs. 1 point for sync tools), and is defensible in a way that a file-format translator can never be. It also complements rather than competes with rulesync/ruler. Difficulty is high and it is a different company than the one proposed.

**Do not build `.agent/` + `agent sync`.**

---

## Citations

**Primary sources (live API / official docs):**
- GitHub REST API `repos/*`, `repos/*/commits?since=`, `repos/*/issues`, `search/code` — all figures pulled 2026-08-31 via authenticated `gh api`
- npm registry API `api.npmjs.org/downloads/point/last-month/*` — pulled 2026-08-31
- Claude Code memory docs: https://code.claude.com/docs/en/memory
- anthropics/claude-code#6235: https://github.com/anthropics/claude-code/issues/6235
- agentsmd/agents.md#71: https://github.com/agentsmd/agents.md/issues/71
- https://agents.md/
- https://github.com/agentplugins/agent-plugins-spec
- https://github.com/dyoshikawa/rulesync
- https://github.com/intellectronica/ruler

**Standards / announcements:**
- https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation
- https://openai.com/index/agentic-ai-foundation/
- https://aaif.io/
- https://github.blog/changelog/2026-08-12-agent-plugins-1-0-in-vs-code-copilot-cli-and-the-copilot-app/
- https://developers.googleblog.com/agent-plugins-package-your-skills-tools-and-more/

**Community threads:**
- https://news.ycombinator.com/item?id=49367350 (Feature Request: Support AGENTS.md — 378 pts, 220 comments)
- https://news.ycombinator.com/item?id=46809708 (AGENTS.md outperforms skills in our agent evals — 524 pts)
- https://news.ycombinator.com/item?id=47034087 (Evaluating AGENTS.md — 232 pts)
- https://news.ycombinator.com/item?id=44957443 (AGENTS.md launch — 837 pts)
- https://news.ycombinator.com/item?id=48051242, 49193083, 44382989, 44480341, 44612918 (rulesync Show HNs, 1–2 pts each)
- https://news.ycombinator.com/item?id=49503387, 49330900

**Secondary / analysis (lower confidence, used for orientation only):**
- https://codex.danielvaughan.com/2026/05/05/agent-skills-open-standard-portable-skills-codex-cli-cross-agent/
- https://www.digitalapplied.com/blog/agent-plugins-1-0-open-standard-portable-ai-skills
- https://mcp.directory/blog/cross-agent-skills-cursor-codex-cline-antigravity-gemini-mastra-portability
- https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026

**Explicitly flagged UNVERIFIED:**
- "Blume" drift-detection desktop app — mentioned in one secondary source; no repo or traction confirmed
- Exact Agent Plugins launch-client list (from secondary sources; the spec repo README did not enumerate clients)
- Google's formal accession as Agent Plugins Core Maintainer (announced via Google Developers Blog, not confirmed in spec repo MAINTAINERS.md)
- Claims in several SEO blogs that Claude Code "natively reads AGENTS.md" — **verified FALSE** against official docs
