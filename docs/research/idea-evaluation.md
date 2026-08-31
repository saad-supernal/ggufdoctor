# How ggufdoctor was chosen

Record of the evaluation that preceded this project, 2026-08-31. Kept because
the *rejected* options and the reasons are the expensive part — without this,
a future session re-proposes them.

Full agent reports are in `reports/`. All figures were verified live that day;
treat them as dated, and note that star counts in this ecosystem are
demonstrably manipulable (one repo gained 102k stars in nine days).

## Ideas evaluated and rejected

| Idea | Verdict |
|---|---|
| `agent-workspace` — one `.agent/` dir + CLI syncing CLAUDE.md / AGENTS.md / .cursor / .codex | **Dead.** AGENTS.md won (~70k repos, Linux Foundation governance). Agent Plugins 1.0 — half the proposed spec — shipped 2026-08-06 backed by Amazon, Cursor, Microsoft, OpenAI, Vercel. The `.agent/` idea was already filed as agents.md#71 in Sept 2025 with no maintainer response in 11 months. Twelve sync tools died in 12 months; two survived. Every Show HN in the category scored 1–2 points. |
| `awesome-agent-skills` — 20 production-grade skills, paid tiers | **Dead.** Name taken (33k★). All ten proposed skills exist first-party (Supabase's postgres skill alone has 378k installs). No payout rail anywhere — GitHub, Vercel, ClawHub and Anthropic all made distribution free by design. A 20-skill bundle consumes most of a user's trigger budget; benchmarks show ≤3 modules outperform larger ones, so the product would degrade the buyer's agent. |
| `agent-browser` — token-efficient browser QA harness | **Dead.** Exists under the same name: `vercel-labs/agent-browser`, 41.6k★, 1.36M npm/week, strict superset. 26 repos share the pitch; the best has 175★. Token efficiency was already solved three times over (disk-offloaded snapshots, delta snapshots, `playwright-cli`). |
| Spend enforcement for agents | **Dead on arrival.** `claude --max-budget-usd` already ships. Dropped at the user's direction before the kill-research completed. |
| Trigger/adherence eval harness | **Absorbed mid-evaluation.** `claude plugin eval` ships `--ablation with-without` with `tool_used: Skill` as an explicit plugin-fired indicator — precisely the proposed product, first-party, for Claude Code. |

## The pattern

Every rejected idea was a layer over a cost the platforms are actively driving
to zero. Claude Code absorbed roughly one category per month for 18 months;
Agent Teams shipped in February and Vibe Kanban (28k★, YC-backed, paid tier)
was dead nine weeks later.

**Operating rule adopted:** if a single vendor can ship it as a flag, it is
disqualified. Verify against the actual CLI before recommending — two
recommendations in this evaluation were killed by one `--help` invocation each.

## Why a GGUF template linter survived

- **Verified empty.** Zero results on GitHub for GGUF/chat-template linting
  across five query variants.
- **Measured pain.** 15.1% of comparable top-downloaded GGUF chat models render
  different prompt text than upstream; 30.8% weighted by downloads. See
  `README.md` and `2026-08-31-survey-raw.json`.
- **Neutrality moat.** Hugging Face cannot publicly rank the quality of its own
  users' uploads; llama.cpp and Ollama will not ship the tool that says their
  engines disagree. The value comes from not being any of them.
- **Fits the builder.** Infra/CLI plus AI/ML, no GPU required, narrow contract,
  low maintenance surface.

## The other live candidates, if this one dies

Ranked, from the same research:

1. **Agent credential broker.** Category tops out at 9★. Strongest structural
   moat found anywhere in the study: a vendor cannot ship the component whose
   job is withholding credentials from its own agent. Weakness: enterprise-shaped,
   thin day-one solo value.
2. **Cross-vendor record/replay for agents.** Emptiest agent-domain square
   (best entrant 1.4k★, then 270, then 30). A paper proves F=1.0 replay with a
   98.3% latency cut; its reference implementation has 30★.
3. **Provenance and pinning for MCP servers / skills.** Not scanning — scanning
   is proven invalid (scanner agreement κ ≈ 0.045–0.082; 24.3% of malicious
   verdicts had zero scanner signal, caught by provenance instead).
4. **Contribution path.** MCP's spec repo merges 78% of PRs from outsiders,
   6.6h median for outsiders vs 125h for insiders, written ladder, no CLA.
   `mcp/conformance` has 121 open issues and 38 contributors ever; `mcp/mcpb`
   is abandoned. Stars are farmable now; adjudicated roles are not.

Avoid entirely: Ollama, LiteLLM, Langfuse, Opik, mem0, Temporal — CLA-gated
with staff-only merges. Maximum apparent need, no actual path.
