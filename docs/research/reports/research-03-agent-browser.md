# Technical Due Diligence: "Token-Efficient Agent Browser" (`agent-browser test localhost:3000`)

**Date of research:** 2026-08-31. All star counts, commit dates and npm figures verified live on this date via `api.github.com`, `gh api`, and `api.npmjs.org`. Funding figures come from secondary press/aggregator sources and are labeled accordingly.

**Verdict up front: SKIP. Confidence: high (~90%).** The proposed product exists, is named `agent-browser`, is published by Vercel Labs under Apache-2.0, has **41,585 GitHub stars** and **1.36M npm downloads/week**, and already ships every feature in the proposal plus visual diffing, auth vaults, HAR capture, axe-core audits and an MCP mode. See §1.1.

---

## 0. The single most important finding

The exact project — same name, same pitch, same architecture — shipped in January 2026 from Vercel Labs.

```
vercel-labs/agent-browser | stars: 41,585 | created: 2026-01-11 | pushed: 2026-08-31
description: "Browser automation CLI for AI agents"
npm "agent-browser": 1,360,414 downloads last week
72 commits since 2026-06-01
```
Source: https://github.com/vercel-labs/agent-browser (verified via `gh api repos/vercel-labs/agent-browser`, 2026-08-31)

The npm package name `agent-browser` is taken. The GitHub org-level mindshare is taken. The idea is not just occupied — it is occupied by a well-resourced infra vendor shipping daily.

Additionally, **Microsoft itself has abandoned the MCP-snapshot approach for coding agents** and now ships `@playwright/cli` (840,825 downloads/week) whose README states verbatim:

> "**Token-efficient**. Does not force page data into LLM."
> "Modern **coding agents** increasingly favor CLI–based workflows exposed as SKILLs over MCP because CLI invocations are more token-efficient: they avoid loading large tool schemas and verbose accessibility trees into the model context…"

Source: https://github.com/microsoft/playwright-cli/blob/main/README.md (fetched 2026-08-31)

That is the proposal's entire thesis, published by Microsoft, as the official recommendation.

---

## 1. Competitive census (all figures verified 2026-08-31)

### 1.1 Direct competitors — token-efficient browser CLIs/MCPs for coding agents

| Project | URL | Stars | Last push | 90d commits | What it does | Context/token strategy |
|---|---|---:|---|---:|---|---|
| **vercel-labs/agent-browser** | github.com/vercel-labs/agent-browser | **41,585** | 2026-08-31 | 72 | Rust CLI + Node daemon. Snapshot w/ `@e1` refs, click/fill/type, console, network requests + HAR, screenshots (+`--annotate`), **screenshot & snapshot diffing**, auth vault/profile reuse/session persistence, axe-core a11y audits, React render + Web Vitals, tabs/frames/dialogs, batch mode, streaming preview dashboard, **and an MCP mode with tiered tool profiles**. Integrations for Browserbase, Browserless, Browser Use, Kernel, AgentCore, iOS Simulator. | CLI = zero tool-schema overhead. Compact a11y snapshot with refs; `-c` compact mode; `--max-output`; successful action returns `Done`. Third-party claim: ~200–400 tokens/page. |
| **microsoft/playwright-cli** (`@playwright/cli`) | github.com/microsoft/playwright-cli | 12,970 | 2026-08-27 | — | Playwright actions as a CLI + Claude Skills. Microsoft's official answer for coding agents. | Writes snapshots to disk as compact YAML; agent greps/reads only what it needs. Explicitly markets "does not force page data into LLM." |
| **microsoft/playwright-mcp** | github.com/microsoft/playwright-mcp | 36,636 | 2026-08-28 | 23 | The reference browser MCP. 24 tools. | Filtered a11y snapshot w/ refs; **delta snapshots** (shipped Oct 2025); `--snapshot-mode=none`; snapshot-to-file. Tool schemas measured at **4,024 tokens across 24 tools** (PR #1714, 2026-08-16). npm 5.88M/wk. |
| **ChromeDevTools/chrome-devtools-mcp** | github.com/ChromeDevTools/chrome-devtools-mcp | **50,219** | 2026-08-30 | 100+ | Google first-party. Structured console (**with source-mapped stack traces**), network analysis, performance traces + insights, screenshots, Puppeteer-driven actions with auto-waiting. Also ships a CLI. | Structured/typed payloads, uid-based element refs, performance-insight summarization rather than raw traces. npm 3.29M/wk. README documents first-party install paths for Claude Code, Codex, Cursor, Copilot, Gemini CLI, Devin, Factory, Windsurf, JetBrains, opencode, Qoder, Katalon, Antigravity. |
| **browser-use/browser-harness** | github.com/browser-use/browser-harness | **17,256** | 2026-08-30 | 100+ | "Self-healing harness that enables LLMs to complete any task." HN Show, 2026-04-24, 134 pts / 66 comments. | Self-healing + compressed state. |

### 1.2 Agent frameworks / browser-driving libraries

| Project | URL | Stars | Last push | 90d commits | Funding | Notes |
|---|---|---:|---|---:|---|---|
| browser-use/browser-use | github.com/browser-use/browser-use | **111,750** | 2026-08-30 | 100+ | $17M seed, Mar 2025, led by Felicis (per Tracxn / browser-use.com/posts/seed-round) | The category-defining OSS agent-browser library. |
| puppeteer/puppeteer | github.com/puppeteer/puppeteer | 95,528 | 2026-08-30 | — | Google | Substrate. |
| microsoft/playwright | github.com/microsoft/playwright | 95,395 | 2026-08-30 | — | Microsoft | Substrate. 87.5M npm/wk. Ships **Test Agents** (planner/generator/healer) since 1.56. |
| browserbase/stagehand | github.com/browserbase/stagehand | 24,101 | 2026-08-30 | 100+ | (Browserbase) | AI-native Playwright wrapper: `act`/`extract`/`observe`. npm 1.40M/wk. |
| Skyvern-AI/skyvern | github.com/Skyvern-AI/skyvern | 22,885 | 2026-08-31 | 100+ | $2.7M, latest round Dec 2025 (Tracxn) | LLM + vision workflow automation. |
| browser-use/web-ui | github.com/browser-use/web-ui | 16,303 | **2026-05-15** | — | — | Stale ~3.5 months. |
| web-infra-dev/midscene | github.com/web-infra-dev/midscene | 14,738 | 2026-08-28 | 100+ | ByteDance-backed OSS | Vision+DOM UI automation & assertions, YAML scripts, report viewer. |
| browseros-ai/BrowserOS | github.com/browseros-ai/BrowserOS | 13,407 | 2026-08-30 | — | — | Open-source agentic *browser* (Atlas/Comet/Dia alternative). Different category. |
| lightpanda-io/browser | github.com/lightpanda-io/browser | 34,319 | 2026-08-31 | — | — | Zig headless browser built for AI/automation. Infra layer, not a harness. |
| AgentDeskAI/browser-tools-mcp | github.com/AgentDeskAI/browser-tools-mcp | 7,304 | 2026-08-12 | — | — | "Monitor browser logs from Cursor" — the 2025 version of this idea; growth stalled. |
| steel-dev/steel-browser | github.com/steel-dev/steel-browser | 7,566 | **2026-08-25** | **13** | $17M total (StartupHub.ai) | Slowing: 13 commits in 90 days. Markets "reduces LLM token usage by up to 80%". |
| nottelabs/notte | github.com/nottelabs/notte | 1,999 | 2026-08-30 | 50 | $2.5M pre-seed led by 4DX (Vestbee) | Browser infra + web automation for agents. |
| tinyfish-io/agentql | github.com/tinyfish-io/agentql | 1,454 | 2026-08-26 | 16 | (TinyFish) | Query language for web elements. Low activity. |

### 1.3 Commercial cloud browser infrastructure (the "AgentBrowser Cloud" tier)

| Company | Funding (secondary sources) | Entry price / browser-hour |
|---|---|---|
| Browserbase | **$67.5M total; $40M Series B (2025) led by Notable Capital; ~$300M valuation** | Free / $20 Dev / $99 Startup; overage **$0.10–$0.12/browser-hour** |
| Browser Use Cloud | $17M seed | **$0.02/hour**; $29 Dev (25 concurrent) → $999 Scaleup (500 concurrent) |
| Steel.dev | ~$17M total | $29/mo → 290 hrs; $499/mo → 9,980 hrs |
| Hyperbrowser | **UNVERIFIED** — no credible funding figure found | ~$30/mo, 30,000 credits, ~$0.10/hr equivalent |
| Anchor Browser | $6M seed led by Blumberg Capital (Oct/Nov 2025) | — |
| Cloudflare Browser Rendering, Kernel, Browserless, AgentCore | — | Commodity |

**Implication:** browser-hours are a commodity at **$0.02–$0.12/hour**, sold by companies with $17M–$67M of capital and their own datacenter economics. `agent-browser` already integrates with five of them as backends. A solo builder entering here competes on price against funded infra with zero differentiation.

### 1.4 Agentic QA startups (the "verification loop" tier)

| Company | Funding (secondary) | Position |
|---|---|---|
| QA Wolf | **$57M total; $36M Series B led by Scale VP (Jul 2024)** | Managed E2E service; reported contracts $60k–$250k+/yr |
| Momentic | **$18.7M total; $15M Series A, Standard Capital, Nov 2025**; YC | AI-native E2E authoring/execution |
| Meticulous | ~$4M seed | Records real sessions → replays as visual-regression tests |
| Octomind | $4.8M seed (Cherry Ventures, ROI Ventures) | URL-in → auto-generated Playwright E2E |
| **Canary (YC W26)** | YC | Launch HN 2026-03-19, 58 pts. Reads the PR diff → generates & runs flow tests against preview envs → comments on PR with recordings |
| **Propolis (YC X25)** | YC | Launch HN 2025-10-30, 116 pts. Autonomous QA "swarms"; exports to Playwright |
| Autify, Reflect, Ranger, Spur, kodefreeze, revyl, broxhq/qpilot | various/unknown | Crowded long tail |

### 1.5 First-party agent-native browser tooling (free, bundled, zero-install)

This is the most under-appreciated part of the landscape.

- **Claude Code built-in browser** — shipped ~6–10 July 2026 as a tabbed browser pane in the desktop app (Cmd+Shift+B). *Directly observable in this session:* the harness exposes `preview_start` (launches the dev server from `.claude/launch.json`), `navigate`, `read_page` (a11y tree with `ref_N` handles), `find`, `read_console_messages`, `read_network_requests`, `computer` (click/type/screenshot/scroll), and `resize_window` (mobile/tablet/desktop + `prefers-color-scheme`). That is `agent-browser test localhost:3000`, already inside the agent, for free.
- **Google Antigravity Browser Subagent** — a dedicated Chromium subagent that clicks through the app during the build loop, screenshots, and records verification videos.
- **Cursor** browser integration; **Claude in Chrome** extension.
- **Playwright Test Agents** (planner / generator / **healer**) — self-healing selectors, first-party, free, since Playwright 1.56.

### 1.6 The thin-wrapper graveyard — the most damning evidence

A GitHub search for `token+efficient+browser+mcp in:name,description` returns **26 repositories**. Every one is a version of the proposal. Stars, verified 2026-08-31:

| Repo | Stars | Created | Pitch |
|---|---:|---|---|
| TickTockBent/charlotte | **175** | 2026-02-13 | "Token-efficient browser MCP server — structured web pages for AI agents, **not raw accessibility dumps**" |
| magentic/flowlens-mcp-server | 110 | 2025-10-04 | MCP giving coding agents browser context (**stale: last push 2026-05-17**) |
| OpenEvident/vindicate | 48 | 2026-08-14 | Local-first Playwright toolkit for Cursor/Claude Code |
| tontoko/fast-playwright-mcp | 40 | 2025-08-04 | "FAST Playwright MCP" |
| lourencomaciel/sift-gateway | 31 | 2026-02-08 | Offloads oversized MCP output out of context |
| mehmetnadir/cdpilot | 29 | 2026-08-25 | Zero-dep browser CLI, 70+ commands, 10 test assertions |
| JuliusBrussee/caveman-browse | 19 | — | "compressed accessibility snapshots, uid actions" |
| drisplabs/browser-mcp | 15 | — | "semantic page snapshots and stable element refs" |
| BDuba/pinchtab-mcp-wrapper | 15 | — | token-efficient browser MCP |
| ArkNill/browsegrab | 8 | — | a11y tree + MarkGrab |
| DimitriBouriez/navagent-mcp | 5 | — | "Ultra-light MCP browser navigation" |
| Silbercue/public-browser | 3 | — | direct CDP, a11y-tree refs |
| **atreasureboy/agent-browser** | **2** | 2026-08-11 | *literally the same name and pitch* |

`charlotte` is the best-executed instance — the exact positioning, 6 months old, actively developed (100+ commits/90d) — and it has **175 stars**. That is the realistic ceiling for a solo builder with this idea, not because the builder is bad, but because the slot is filled.

Also relevant: `browser-use/vibetest-use` (Vibetest MCP, "automated QA testing using Browser-Use agents") got to **827 stars** and then **died — last push 2025-09-02**, nearly a year stale, despite being published by the 111k-star browser-use org.

---

## 2. Is token efficiency already solved? — **Yes, three times over.**

### 2.1 The problem was real, and is well documented

Verified GitHub issues on `microsoft/playwright-mcp`:

- **#1131** (2025-10-14) "Playwright mcp 20k token wait-for?" — user pastes the client warning verbatim:
  > `playwright - Wait for (MCP)(time: 3)` → `⚠ Large MCP response (~20.7k tokens), this can fill up context quickly`

  Maintainer **pavelfeldman**: "It returns a snapshot, so that the LLM could determine whether it waited enough." Commenter **thoraxe**: *"If I waited 3 seconds and that wasn't enough and now wait for another 3 seconds I just burned 40k tokens that I didn't need to burn."*
- **#1274** (2025-12-19) "Large responses consuming context windows" — 7 comments, multiple users, "affecting me and my team also". One user's fork reports a single snapshot at **2,847 lines / 156.2 KB**.
- **#1329** (2026-01-23) "On very large pages, the snapshot can fill the entire context."
- **#1573** (2026-04-27) "token efficiency to reduce API costs and latency" — maintainer's entire reply: **"nope"**.

### 2.2 Primary measurement I performed

I drove the Playwright MCP against **news.ycombinator.com** — about as simple a page as exists on the web — on 2026-08-31:

```
1,002 lines | 47,596 bytes | ≈11,900 tokens (bytes/4)
```
The tree is dominated by waste: nested `table`/`rowgroup`/`row`/`cell` scaffolding, `generic` nodes, and `[ref=eN]` handles minted for non-interactive elements. A checkout page would be several times larger. **So the raw problem is real.**

**But — critically — the snapshot never entered my context.** Current playwright-mcp wrote it to `.playwright-mcp/page-2026-08-31T01-49-46-238Z.yml` and handed the agent a file link. The acute failure mode has already been fixed upstream.

### 2.3 Every mitigation the proposal offers already shipped

| Mitigation | Who shipped it | When |
|---|---|---|
| Snapshot written to file, agent reads selectively | microsoft/playwright-mcp | current default |
| **Delta snapshots** (only what changed) | microsoft/playwright-mcp | Oct 2025 (per #1131) |
| `--snapshot-mode=none` | microsoft/playwright-mcp | — |
| Compact mode, `--max-output`, scoped snapshots | vercel-labs/agent-browser | shipped |
| CLI (zero tool-schema overhead) | microsoft/playwright-cli, vercel-labs/agent-browser | 2026 |
| Tiered MCP tool profiles (`core`/`network`/`state`/`debug`/`all`) | vercel-labs/agent-browser | shipped |
| Structured console + **source-mapped** stack traces | ChromeDevTools/chrome-devtools-mcp | shipped |
| Generic MCP output offloading | sift-gateway, and Claude Code's own MCP output caps | shipped |

### 2.4 Published benchmark numbers

- Independent benchmark (ytyng.com, 2026): a 10-step login-flow task cost **~114,000 tokens via Playwright MCP vs ~27,000 via Playwright CLI** — a ~4x reduction. Author's recommendation: *"use agent-browser as the default choice for everyday browser automation, supplementing with Playwright CLI for complex operations."*
- Playwright MCP tool schemas: **4,024 tokens across 24 tools**, measured 2026-08-16 (PR #1714), median across a 57-server sweep being 2,636 — i.e. playwright-mcp's schema overhead is already *disciplined*, not bloated.
- agent-browser: ~200–400 tokens/page (vendor-adjacent claim, third-party repetition — treat as directional).
- Steel.dev markets "up to 80% token reduction"; various wrappers claim 78%, 90%, 93%.

### 2.5 Conclusion on Q2

**"Smaller structured state" is not a differentiator; it is table stakes that four separate first-party vendors already ship.** The proposed JSON blob (`{"page","interactive","errors"}`) is a strictly *weaker* representation than what agent-browser already returns, because it discards hierarchy and text content the agent needs for anything beyond a smoke test. And per Q1, this is a **200-line wrapper** — literally 26 such wrappers exist on GitHub, none above 175 stars.

The competitive frame is not "us vs. playwright-mcp." It is "us vs. a Rust binary from Vercel with 41k stars, plus Microsoft's official CLI, plus Google's DevTools MCP, plus the browser already built into Claude Code."

---

## 3. What coding agents actually lack (the real gaps)

Sourced from HN threads and GitHub issues, not speculation.

**HN 45642911** — "Show HN: Playwright Skill for Claude Code – Less context than playwright-MCP" (2025-10-20, 189 pts, 45 comments):

1. **Auth is the wall, not tokens.** *siva7*: "beyond basic kindergarten stuff playwright (with AI) falls quickly apart. **Have some OAuth? Good luck** configuring playwright for your exact setup."
2. **Synthesis across signals is the wall.** Same comment: "Need to **synthesize all information available from logs and visuals** to debug something? Good luck."
3. **Death spirals.** *boredtofears*: "I get so many LLM death spirals with playwright… it gets hung up on things like not finding the active playwright window or being able to identify elements."
4. **The hard part is sequences, not snapshots.** *nikisweeting*: "BrowserBase and Browser-Use exist specifically because this is a harder problem than it looks. Any approach will work for the first couple actions; the hard parts are **long strings of actions that depend on the results of previous actions**, compressing the context and knowing what to send, and having your tools work across all the edge cases (date pickers, file upload fields, cross-origin iframes)."
5. **The baseline is brutally high.** *simonw*: he just prompts Claude Code to start a server and drive Playwright directly — *"This works really well even without adding an extra skill."* And: *"one of the hardest parts of skill development is figuring out what to put in the skill that produces better results than the model acting alone."*
6. **MCP schema overhead is what people actually resent.** *yomismoaqui*: "Taking into account all the tools crap that the Playwright MCP puts in your context window…"
7. **Nothing survives the session.** *cadamsdotcom*: make the Playwright script a permanent part of the codebase so it runs in CI — i.e. the missing piece is **persistence and promotion into a suite**, not the drive layer.
8. **Data privacy.** *Rooster61*: "There's no way I'd be able to use this in any kind of real application where data privacy is a constraint."

**HN 47441629** — Launch HN: Canary (YC W26) (2026-03-19, 58 pts):

9. **The agent games its own assertions.** *ashgam*: "there has been instance of **Claude already patching the test scripts instead of fixing the bugs** to make the tests pass." This is the deepest gap in the whole space and nobody has solved it.
10. **Flake-free promotion is the actual moat.** *pastescreenshot*: "If Canary catches a real regression, how often can that check be **promoted into a stable long-lived regression test without turning into a flaky, environment-coupled browser script**? That conversion rate feels closer to the real moat than the generation demo."
11. **The value is infrastructure, not the drive layer.** Canary's founder, asked how they differ from Claude Code + GitHub: "You also need infrastructure to execute the tests — **browser fleets, ephemeral environments, data seeding**."
12. **Shift-left favors the incumbent.** *Bnjoroge*: "you probably wanna shift a lot of the code verification as left as possible… **claude/codex are well positioned to do the local review**." The local loop — precisely where `agent-browser test localhost:3000` lives — is the first-party agents' home turf.
13. **No moat, generally.** *monkpit*: "Isn't the last point the case with every AI startup? Nobody has a moat and it's tough to build one because the playing field is so level."

**HN 45677406 / Propolis Launch HN (2025-10-30, 116 pts):**

14. **Test data / state pollution across parallel runs** — Propolis called this "one of our biggest challenges."
15. **Side-channel verification** — email OTP, SMS, MFA. Multiple commenters raised it; Propolis only supports email, only for paying customers.
16. **"Broken UI" detection is genuinely unsolved.** *cloudflare728* (an ML engineer): "I tried and mostly failed to build a broken UI detector in my previous company… I tried by taking long screenshot… finding diff between 2 images. It kind of worked but not satisfactorily."
17. **Build-your-own pressure.** *webprofusion*: "You can already pretty much do this using the standard agent tools and a set of test prompts… The pricing sounds quite enterprisey, the risk there is that people will tend towards building their own."

**Ranked list of what is genuinely unmet:**

| Gap | Solved by anyone? |
|---|---|
| Agent edits the assertion instead of fixing the bug | **No.** Nobody. |
| Regression → durable, non-flaky, checked-in test (promotion) | **Barely.** Playwright Healer + Canary's cascade are partial. |
| OAuth/SSO/MFA + email/SMS OTP side-channels | Partial (agent-browser auth vault; Propolis paid email) |
| Test-data seeding & state isolation across parallel runs | **No** OSS answer; commercial-only |
| "Is this UI visually broken?" without a baseline | **No.** VLM opinions are unreliable on dense UI |
| Runtime error → source file attribution | **Yes** — chrome-devtools-mcp ships source-mapped stack traces |
| Token efficiency | **Yes**, comprehensively (§2) |
| Flaky waits | Largely — auto-waiting in Puppeteer/Playwright/agent-browser |
| Visual diff | **Yes** — `agent-browser diff screenshot --baseline` |
| CI integration | **Yes** — Playwright, QA Wolf, Canary, Octomind |

Note that **token efficiency, the proposal's stated differentiator, ranks dead last on the list of real problems.**

---

## 4. Moat and business

### 4.1 Distribution is the moat, and it is entirely spoken for

`chrome-devtools-mcp`'s README carries first-party install instructions for Claude Code, Codex, Cursor, Copilot/VS Code, Gemini CLI, Devin, Factory, Windsurf, JetBrains, opencode, Qoder, Katalon, Antigravity, IBM Bob, Command Code. Google ships the install path *inside every agent*. A solo project cannot buy that.

Meanwhile the agents themselves are absorbing the function: Claude Code has a built-in browser pane (July 2026), Antigravity has a Browser Subagent, Cursor has browser integration. The category is being **commoditized into the harness**, which is the classic terminal state for a tool of this shape.

### 4.2 What happened to thin wrappers: they capped at ~200 stars or died

See §1.6. The distribution is stark — the median "token-efficient browser MCP" repo has **single-digit to low-double-digit stars**; the best has 175; the one with real backing (`vibetest-use`, 827 stars, from the 111k-star browser-use org) has been **abandoned for ~12 months**. There is no example of a thin browser wrapper crossing into a business.

### 4.3 The cloud business is fully occupied and already commoditized

- Parallel sessions / browser-hours: **$0.02–$0.12/hr** from Browserbase ($67.5M), Browser Use ($17M), Steel ($17M), Hyperbrowser, Anchor ($6M), Cloudflare, Kernel, Browserless, AgentCore.
- CI + recordings + PR comments: QA Wolf ($57M), Momentic ($18.7M), Canary (YC W26), Propolis (YC X25), Octomind, Meticulous, Autify, Reflect, Ranger.
- Vercel's `agent-browser` already **integrates with Browserbase, Browserless, Browser Use, Kernel, and AgentCore as backends** — the OSS layer has already federated to the funded infra layer. There is no gap between the two to insert a new one.

A solo builder here would be selling undifferentiated compute at a lower price than five funded competitors, with no cost advantage.

### 4.4 The strongest argument *against* the project (steelmanned)

> The proposal's differentiator is a *performance property* (fewer tokens), not a *capability*. Performance properties are the easiest thing in software for a well-resourced incumbent to copy, and in this case they didn't even have to copy — Microsoft, Google, and Vercel each independently shipped the same optimization within a twelve-month window, because it was the obvious next move once anyone measured a snapshot. Meanwhile the token cost that motivated the whole idea is falling on its own: context windows grow, prompt caching amortizes repeated snapshots, and the harness now writes large tool outputs to disk automatically. The proposal is optimizing a metric whose importance is *decreasing* while its competitors optimize capabilities whose importance is increasing. And the *name* is taken by a 41.5k-star Vercel repo with 1.36M weekly downloads.

I could not construct a serious counter-argument to this.

---

## 5. Verdict

### **SKIP as proposed. Confidence: high (~90%).**

The project is dominated on every axis simultaneously:
- **Product:** `vercel-labs/agent-browser` ships a strict superset (adds visual diff, auth vault, HAR, axe-core, React profiling, MCP mode, five cloud backends).
- **Name:** taken, on both GitHub and npm.
- **Thesis:** Microsoft's own `playwright-cli` README argues the proposal's thesis, as Microsoft's official position.
- **Distribution:** Google ships install paths inside every coding agent; Anthropic and Google ship browsers *inside the agent*.
- **Precedent:** 26 identical OSS wrappers exist; ceiling observed is 175 stars.
- **Business:** browser-hours commoditized to $0.02/hr by five funded vendors; agentic QA has ~$100M+ deployed across QA Wolf, Momentic, Canary, Propolis, Meticulous, Octomind.
- **Motivating problem:** already fixed upstream (file-offload, delta snapshots, CLI mode) and structurally shrinking.

### If you insist on building in this space

Do **not** build a browser driver. Build a thin layer *on top of* `agent-browser` or `playwright-cli` targeting the one gap nobody has closed:

**"The agent cheats its own tests."** A verification harness where the assertion contract is (a) written before the fix, (b) stored outside the agent's writable tree or content-hash-pinned so edits are detected and rejected, (c) executed by a process the agent does not control, and (d) reported as a signed pass/fail the agent cannot forge. Adjacent and equally open: **promotion** — turning a caught regression into a durable, non-flaky checked-in test, which *pastescreenshot* correctly identified as "closer to the real moat than the generation demo."

Even this is a hard sell: Playwright's Healer and Canary are circling it, and it is a *workflow/trust* product, not an infrastructure one — meaning it is a feature that Anthropic or Google could ship into the harness in a quarter. Realistic framing: a well-regarded OSS project of a few thousand stars and a strong portfolio piece, not a company. Confidence that this narrower wedge is *viable as a business*: low (~25%).

### Best alternative use of the effort

**Contribute, don't compete.** `vercel-labs/agent-browser` has 72 commits in 90 days and no assertion/test-runner mode, no CI mode, and no exit-code-based pass/fail suite — the one genuine hole in an otherwise complete README. A `agent-browser test` subcommand contributed upstream reaches 1.36M weekly installs on day one; the same code in a new repo reaches 175 stars in six months. The evidence in §1.6 is unambiguous about which of those two outcomes is the default.

---

## Appendix: verification methods

- Star counts, push dates, creation dates, 90-day commit counts: `gh api repos/{owner}/{repo}` and `gh api repos/{o}/{r}/commits?since=2026-06-01`, run 2026-08-31. Commit counts shown as "100" are capped by `per_page=100` and mean ≥100.
- npm weekly downloads: `api.npmjs.org/downloads/point/last-week/{pkg}`, 2026-08-31.
- Wrapper census: `api.github.com/search/repositories?q=token+efficient+browser+mcp+in:name,description&sort=stars`.
- HN threads: `hn.algolia.com/api/v1/items/{id}` — full comment trees retrieved, quotes verbatim.
- GitHub issues: `api.github.com/repos/microsoft/playwright-mcp/issues/{n}` plus `/comments`.
- Snapshot size: drove Playwright MCP against news.ycombinator.com and measured the emitted `.yml` with `wc -lc`.
- Funding figures: secondary sources (Tracxn, PitchBook summaries, StartupHub, Vestbee, Blumberg Capital, press). **Not** verified against primary filings. Hyperbrowser funding is **UNVERIFIED**.

### Side effect to note
The Playwright MCP measurement in §2.2 caused the MCP server to write `/Users/saad/Silvergrain/Agent Tools/.playwright-mcp/page-2026-08-31T01-49-46-238Z.yml` (47.6 KB). It was created by the tool, not authored by me, and was left in place rather than deleted per the no-deletion constraint. It is safe to remove.
