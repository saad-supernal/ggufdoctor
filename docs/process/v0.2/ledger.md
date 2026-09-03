# SDD ledger — plan: docs/superpowers/plans/2026-09-03-ggufdoctor-v0.2.md
Spec: docs/superpowers/specs/2026-08-31-ggufdoctor-design.md + docs/superpowers/specs/2026-09-03-ggufdoctor-v0.2-amendments.md (amendments win). Evidence: docs/research/2026-09-03-engine-spike.md.
Branch: feat/v0.2 (from main b45223b). Plan committed at 1617f43.

Ruling R1: workspace is the repo checkout on branch feat/v0.2, not a separate git worktree — same arrangement v0.1 used; nothing else is being developed in this checkout — cost if wrong: none beyond discipline.

## Pre-flight scan (2026-09-03)
| pair / task | produces vs consumes | found |
|---|---|---|
| T1↔T2 | module exports gd_alloc/gd_free/gd_render/gd_out_len/_initialize/memory; manifest build_tag/commit; result keys ok/text/stage/error/caps/normalized | consistent |
| T2↔T5 | RenderResult.extra {caps, normalized} | consistent |
| T2↔T6 | LlamaCppEngine.available/unavailable_reason/commit/backend used by registry+reports | consistent |
| T4↔T5 | Fixture.tier; is_tool_fixture = "tools" in context → with_tools, tool_roundtrip | consistent |
| T4↔T6 | both edit tests/test_checks_sanity.py (T4 reconciles real-template sets; T6 Step 0 changes CHAT_TPL) | sequential, no conflict |
| T5↔T6 | X_IDS, run_cross_engine_checks, ctx.stats["engines_agreed_fixtures"] | consistent |
| T6↔T7 | both edit cli.py, different functions | sequential |
| T7↔T8 | sidecar keys repo/revision/license/gated/architecture/bos_token/eos_token/base_model/upstream_saved | consistent |
| T8↔T9 | TEMPLATES glob over tests/data/templates | consistent |
| T9↔T10 | both edit pyproject (markers vs version) and ci.yml (different jobs) | sequential |
| T1↔T10 | build.sh --out DIR; ENV GGUFDOCTOR_ENGINE_WASM from T2 | consistent |
| T1 self | tests check manifest+sha; build.sh writes manifest; shim exports match | consistent |
| T2 self | tests vs code: error prefixes compile:/raise:/render:/engine:unavailable:/render:wasm: | consistent |
| T3 self | rows are the spike's measured values | consistent |
| T4 self | S003 extended bucket collapses by error string → two findings in the test | consistent (fixed in self-review) |
| T5 self | _x002(fx, ok_engine, failing, ok_result, failing_engine) call sites match | consistent; risk: llama.cpp support for `is not none` in a test template — implementer verifies |
| T6 self | registry monkeypatch of module-global _construct; families_run insert after S | consistent |
| T7 self | save happens after tpl read, before filters; upstream after why=="ok" | consistent |
| T9 self | marker deselected by default; downloads only under -m conformance | consistent with global constraint |
| T11 self | survey figure recorded with corpus version | consistent |
Scan clean; no rulings needed beyond R1.

## Progress
Task 1: dispatched (implementer sonnet, BASE 1617f43)
Task 1: review clean (sonnet). ⚠️ build.sh download branch not exercised locally → covered by Task 10's engine-build CI job on ubuntu; ⚠️ wheel ships engine_data → Task 10 wheel check. Module is 721,494 bytes (spike estimate 672 KB; caps+normaliser added).
Task 1: minor (deferred): report miscounts sha256 entries (19 vs 20); build.sh curl|tar lacks pipefail (POSIX sh, plan-mandated text).
Task 1: complete (commits 1617f43..7579f48, review clean)
Task 2: dispatched (implementer haiku, BASE 7579f48)
Task 2: review (sonnet) — 2 Important, both plan-mandated (brief code lets render() raise: json.dumps outside try; result["text"] unguarded).
Ruling R2: the global constraint "engines never raise from render" wins over the plan's sample code — fix both (json.dumps inside the try; missing "text" → render: error), add a test with a non-serializable context — cost if wrong: none; strictly more defensive.
Task 2: minor (deferred): unused pytest import in test_engine_llamacpp.py (fixed in round 1 as it's in the touched file); wasmtime re-imported locally in two methods.
Task 2: fix round 1/5 (3 addressed, 0 open — json.dumps inside try; text guarded; unused import; commits 531c0ac..db78ca5)
Task 2: complete (commits 7579f48..db78ca5, review clean after 1 fix round)
Task 3: dispatched (implementer haiku, BASE db78ca5)
Task 3: complete (commits db78ca5..1aa4da3, review clean)
Task 4: dispatched (implementer sonnet, BASE 1aa4da3)
Task 4: review (sonnet) — 1 Important: Mistral tool_roundtrip justification comment states an invented mechanism (raise fires at loop.index0==0 on the system message, not a "four-turn desync"). Extra file tests/test_report.py corpus literal 1→2 judged minimal mechanical consequence.
Task 4: minor (deferred): legacy real-template tests assert (id, severity) pairs without fixtures (predates v0.2; consider tightening in final review or Task 8).
Task 4: fix round 1/5 (2 addressed, 0 open — Mistral/Llama-3 comment mechanisms corrected; commits 0e72147..8706b17)
Task 4: complete (commits 1aa4da3..8706b17, review clean after 1 fix round)
Task 5: dispatched (implementer sonnet, BASE 8706b17)
Task 5: review (opus) — deviations (a) character-level _signature collapse key and (b) _explained_by_normaliser re-render both judged real fixes to brief defects; approved. 1 Important (plan-mandated): an unavailable llama.cpp engine left in ctx.engines would surface as a collapsed X002 ERROR instead of a recorded gap.
Ruling R3: the declined-vs-unavailable distinction lives in the CLI/registry (Task 6: unavailable engines are dropped from ctx.engines and X_IDS recorded there; a declined --engines subset never calls run_cross_engine_checks). cross_engine keeps its single-engine X_IDS append (a library caller with one engine gets a recorded gap) AND gains a defensive guard: any `engine:unavailable:` result records X_IDS once and emits no X finding — cost if wrong: one redundant guard.
Task 5: minor (deferred): _diff 40-line cap does not bound single-line renders (add a char budget in final review if cheap); _signature grouping is heuristic (same class as existing collapse); non-content normaliser rewrites (tool_calls arguments, reasoning_content) are not mirrored by _flatten_typed_content — latent, conservative direction; documented in fix round.
Task 5: fix round 1/5 (4 addressed, 0 open — unavailable-engine guard + test; _x002 kwargs; stage in X002 messages; docstring; commits 0398840..491609e)
Task 5: complete (commits 8706b17..491609e, review clean after 1 fix round)
Task 6: dispatched (implementer sonnet, BASE 491609e)
Task 6: review (sonnet) — 1 Important: with `--engines jinja2` plus a failed upstream, human.py's "note: X family skipped" fires although X was declined (ALL_FAMILIES now has X; skipped computed from families_run alone). Step 0 CHAT_TPL deviation (join parts with "\n") and _model() default-metadata change judged legitimate corrections of unsatisfiable brief text.
Ruling R4: the "family skipped" note lists only genuine gaps — R when upstream_gap is set, X when coverage.engines_unavailable is non-empty; a declined X is never listed. No new Coverage field — cost if wrong: none (narrower note).
Task 6: minor (deferred): pre-existing CLI tests pass token metadata that _model() now defaults; comments stale.
Task 6: fix round 1/5 (2 addressed, 0 open — _skipped_families gated on real gaps + 2 tests; CHAT_TPL per-family justification block; commits 5074412..8cc85cf)
Task 6: complete (commits 491609e..8cc85cf, review clean after 1 fix round)
Task 7: dispatched (implementer sonnet, BASE 8cc85cf)
Task 7: review clean (sonnet). Deviation accepted — Ruling R5: templates of repos excluded as non_chat_architecture / non_chat_pipeline_tag are not saved by --save-templates (save sits after those returns), which matches the brief's own test and avoids an ungated base_model_of call; cost if wrong: a corpus builder that skips ASR/TTS/embedding repos' templates, which are not chat templates anyway.
Task 7: minor (deferred): os.makedirs per repo; add a comment at the save call site explaining the skip.
Task 7: complete (commits 8cc85cf..5572cd3, review clean)
Task 8: dispatched (implementer opus, BASE 5572cd3)
Task 8: implementer DONE_WITH_CONCERNS (4b73aa5). Correctness concerns addressed before review:
Ruling R6: test_real_templates.run() must not fabricate a two-token vocab — use tokens=[], bos/eos ids None; S004/S005/S006 are then recorded as not evaluated (S004 already skips on empty vocab), and the pinned sets cover S003/S007/S008 + X — six artefact S004 ERRORs on working models were the false-positive shape the project exists to avoid — cost if wrong: S004–S006 uncovered on real templates until a vocab source exists (HF metadata has none).
Ruling R7: in cross_engine, a divergence explained by the normaliser is classified before the whitespace-only test (cause outranks magnitude; INFO < WARN) — cost if wrong: a few whitespace-only diffs reported at INFO with the normaliser named instead of WARN.
Ruling R8: HfClient.model_info requests expand[]=sha so --save-templates can record `revision`; vendored sidecars get revision backfilled only where a re-fetch is byte-identical to the vendored template — cost if wrong: one extra field in an API call already made.
Task 8: real X002 ERROR on rippertnt/HyperCLOVAX tool_roundtrip (jinja2 raises on null content; llama.cpp emits an empty assistant turn and drops the tool call) — true positive, kept.
Task 8: R6-R8 applied (commits 4b73aa5..f502387); spec/kickoff amended for R7 (controller docs commit)
Task 8: review clean (opus) — all 15 pinned findings traced to template text; R6/R7/R8 verified.
Task 8: minor (deferred): mudler comment cites wrong codepoints (U+3008/9 not U+2329/A); R7 test has one decorative literal-vs-literal assertion; SOURCES.md should say `other` licences need reading before redistribution beyond test data; scaffold test could assert each slug has a SOURCES.md row.
Task 8: complete (commits 5572cd3..f502387; controller docs commit 5296831 for R7; review clean)
Task 9: dispatched (implementer opus, BASE 5296831)
Task 9: implementer DONE_WITH_CONCERNS (6db84b2): first conformance run 26/100 pairs diverged; four shim gaps ported (enable_thinking defaults true and is always defined; add_generation_prompt set only when true; caps_apply_preserve_reasoning / reasoning_effort; null content → ""), module rebuilt 724,963 bytes sha 830e8722…; harness handles assistant prefill (--no-prefill-assistant) and preserve_reasoning symmetrically; one (slug, fixture) skip for chat.cpp's Gemma-4 tool_responses rewrite; final 99/100 byte-equal + 1 reasoned skip.
Ruling R9: llama.cpp's implicit `enable_thinking = true` default is a runtime default, not a template defect. In cross_engine, when jinja2 and llama.cpp differ on a fixture that does not set `enable_thinking`, re-render jinja2 with `enable_thinking: True` added; if that matches llama.cpp's text, classify as X001 INFO "explained by llama.cpp's implicit enable_thinking default" (same shape as the normaliser explanation; tool fixtures included). Rationale: 4 of 10 popular templates would otherwise carry X001/X005 ERROR for a divergence every llama-server user gets by default — the false-positive shape. Cost if wrong: a real runtime-default divergence reported at INFO rather than ERROR; it is still reported and named.
Task 9: R9 applied (8514b7a); module rebuilt 724,955 bytes sha 20140194…; `normalized` no longer set by the null-content conversion.
Ruling R10 (to apply in the review fix round): explanations compose — when neither the normaliser flatten nor the enable_thinking default alone reproduces llama.cpp's text but both applied together do, classify X001 INFO with explained_by listing both causes. Cost if wrong: two typed_content divergences on popular templates reported at INFO rather than ERROR; still reported and named.
Task 9: review (opus) — ports verified faithful against pinned chat.cpp/server-context.cpp; 1 Important: conformance harness injects preserve_reasoning=true on both sides (a third resolution route), so the product reports agreement on two corpus templates that fork on it under a default llama-server; minors: stale-skip detection only in both-rendered case; add_generation_prompt absent-key not defaulted to true; non-bool add_generation_prompt truthiness; null-content coercion has no explanation class (deferred).
Ruling R11: llama.cpp defaults preserve_reasoning=true when unspecified (common/arg.cpp:963-966 at the pin) and the server applies it only when caps.supports_preserve_reasoning (server-context.cpp:1493-1497). The shim mirrors both: after caps_get, if the context lacks preserve_reasoning and caps say supported, set it true. The harness stops injecting it on either side. Cost if wrong: our engine follows llama.cpp's default rather than a bare template render — which is the engine's stated contract.
Ruling R12: the checks-layer explanation generalises to runtime defaults — re-render jinja2 with the llama.cpp defaults the context lacks (enable_thinking=True, preserve_reasoning=True); explained_by="runtime_defaults" with evidence["defaults"] naming the keys; R10 composition: flatten + defaults together → explained_by="normaliser+runtime_defaults". Cost if wrong: INFO instead of ERROR on runtime-default forks; still reported and named.
Task 9: fix round 1 applied (23d7a6a): R10/R11/R12 in; conformance 10/10 without harness injection; LuffyTheFox fork now reported (X001 ERROR multiturn); module 725,251 bytes sha 3445df65…
Ruling R11a (amends R11): server-context.cpp:1493-1512 is a logging block — llama.cpp passes preserve_reasoning=true to the template unconditionally when unspecified (arg.cpp:963-966). The shim mirrors that exactly: default it true whenever absent, no caps gate. Cost if wrong: none observable (templates that ignore the variable are unaffected).
Ruling R12a (amends R12): RUNTIME_DEFAULTS for the jinja2 explanation re-render must include what caps_apply_preserve_reasoning expands preserve_reasoning into (caps.cpp:22-27): preserve_thinking=True, clear_thinking=False, truncate_history_thinking=False, drop_thinking=False, plus preserve_reasoning=True and enable_thinking=True. Cost if wrong: INFO instead of ERROR on preserve-reasoning forks; still reported and named.
Task 9: LiquidAI preserve-reasoning branch unexercised — corpus has no fixture with assistant reasoning_content (deferred: v0.3 corpus candidate).
Task 9: fix round 2 applied (7a0b88f); module 725,239 bytes sha 4de88e68…; conformance 10/10
Task 9: fix rounds 1-2/5 re-reviewed together (5 items addressed, 0 open; commits 8514b7a..7a0b88f)
Task 9: minor (deferred): tests/test_real_templates.py:115-119 comment still names _explained_by_thinking_default / "enable_thinking_default" (renamed to runtime_defaults) — fix in the final review wave.
Task 9: complete (commits 5296831..7a0b88f, review clean after 2 fix rounds; conformance 10/10, 99/100 pairs byte-equal + 1 reasoned skip)
Task 10: dispatched (implementer sonnet, BASE 7a0b88f)
Task 10: complete (commits 7a0b88f..5fbd6b0, review clean; CI run 33736530232 12/12 green; draft PR https://github.com/saad-supernal/ggufdoctor/pull/1)
Task 11: dispatched (implementer opus, BASE 5fbd6b0)
Task 11: review clean (sonnet); corpus-2 figure 14.4% (16/111), 31.2% dl-weighted, 15/91 publishers, unreliable=false; 14.8% (corpus 1) untouched. Important: docs/v0.2-kickoff.md states docs/process/v0.2/ exists — resolved by the controller copying the ledger there before merge (Finish step).
Task 11: minor (deferred to final wave): survey JSON/markdown do not carry fixture_corpus_version (cheap code fix); spike doc needs a one-line banner (module now 725,239 bytes; rich-input table superseded by shipped engine); kickoff blockquote says 672 KB.
Task 11: complete (commits 5fbd6b0..44311ab, review clean)
All 11 tasks complete. Final whole-branch review: MERGE_BASE b45223b (main) .. 44311ab.
Deferred minors to triage in the final review: T1 report count/pipefail; T2 wasmtime re-import; T4 legacy real-template tests assert (id,severity) without fixtures; T5 _diff no char budget, _signature heuristic, non-content normaliser rewrites unmirrored; T6 stale CLI test comments; T7 makedirs per repo + skip comment; T8 mudler codepoints, decorative assertion, SOURCES.md `other` licences note, scaffold↔SOURCES.md tie; T9 stale comment test_real_templates.py:115-119, null-content coercion has no explanation class, LiquidAI reasoning_content corpus gap; T11 items above.
Final review (opus, b45223b..44311ab): ready with fixes. 0 Critical, 5 Important: (1) _x002 never tries runtime-defaults/composed explanations → antirez typed_content pinned X002 ERROR though composition explains it; (2) WASM store has no fuel/epoch/memory limit — a hostile template hangs uninterruptibly; (3) LlamaCppEngine.__init__ can raise (manifest missing, wasmtime dist metadata missing) contrary to §A; (4) conformance harness downloads binary/model/toolchain without checksums, extractall without filter, cache key without digest, model at moving ref; (5) docs/process/v0.2 referenced but absent.
Ruling R13: X002's llama.cpp-renders/jinja2-fails branch applies the same explanation ladder as X001 (normaliser → runtime defaults → composed); when explained it is INFO with explained_by/defaults set; antirez typed_content re-derived. Cost if wrong: an X002 on a working template at INFO instead of ERROR; still reported and named.
Ruling R14: the wasmtime store is bounded — fuel (consume_fuel + set_fuel) and a StoreLimits memory cap; a trap maps to the existing render:wasm error. Limits are generous constants documented in the engine module. Cost if wrong: a legitimately huge template render trips the limit and is reported as a render error rather than hanging.
Ruling R15: LlamaCppEngine.__init__ never raises — manifest load and metadata.version move inside the try blocks; failures become unavailable_reason; backend falls back to "wasmtime" when the version is unknown.
Ruling R16: everything the build and conformance paths download is checksum-pinned (release asset per platform, model file, wasi-sdk tarball per host), verified before extraction/execution; tar/zip extraction uses filter="data"; the CI cache key includes the digest; the model URL pins a revision. Cost if wrong: a hash refresh is needed on every pin bump (documented in engine/README.md).
Ruling R17: docs/process/v0.2/ is created by the controller (ledger + briefs + reports) before merge; test comments cite the full docs/process/v0.2/ path.
Final fix wave: dispatched (one fixer, opus) — Important 1–5 (5 = path citations only; the copy is the controller's) + fix-before-merge minors (mudler codepoints; SOURCES.md `other` note; stale comment 115-119; survey fixture_corpus_version in JSON + markdown; spike doc banner) + cheap minors (cli --engines help wording; CHANGELOG "provably reproducible" and `extra`-on-Finding; _x002 unused fx; f-string; conformance except narrowing; _diff per-line char slice; wasm file mode 0644).
Final fix wave applied (44311ab..d4222d1): 262 passed; conformance 10/10 incl. cold-cache download→verify→extract. Ruling R14a: the range() hang trips the 512 MiB memory cap first and surfaces as render: … std::bad_alloc (bounded, reported); fuel is pinned by a separate nested-loop test that traps as render:wasm: in <1 s. Cost if wrong: none — both bounds hold.
Final fix wave re-review (sonnet): all 16 items addressed, no new breakage, no assertion weakened. Spec §B updated for R9–R13 by the controller (79c3be6).
Deferred minors (may ship, recorded for v0.3): the fuel/memory headroom regression test renders only the longest vendored template (by bytes), and its glob also matches *.upstream.jinja; CORPUS_VERSION is a constant while a --fixtures corpus carries its own version field (read it); add_generation_prompt-presence fork could be documented in the README X001 row.
Whole-branch review clean after one fix wave. Finish: copying this ledger, briefs and reports to docs/process/v0.2/ (R17); pushing feat/v0.2; CI must be green before merge.
