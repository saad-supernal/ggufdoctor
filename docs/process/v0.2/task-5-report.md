# Task 5 report: Family X — cross-engine checks

Branch: `feat/v0.2`. Commit: `0398840` "feat(checks): family X — cross-engine comparison of jinja2 and llama.cpp".

## What was implemented

Followed the brief's TDD steps 1-6, with one deviation from the brief's literal check code (Step 4) that was required to make the brief's own tests pass — see "Check-logic fix" below.

Files:
- Created `src/ggufdoctor/checks/common.py` — `real_token`, `with_real_tokens`, `collapse_by_signature`, moved verbatim (docstrings included) from `sanity.py`, renamed without the leading underscore.
- Modified `src/ggufdoctor/checks/sanity.py` — replaced the three inline definitions with an import from `common.py` plus the three underscored aliases (`_real_token = real_token`, etc.) exactly as the brief specifies. Also dropped the now-unused `GgufModel` import and `Callable` import (both only existed to type the moved functions).
- Modified `src/ggufdoctor/models.py` — added `CheckContext.stats: dict[str, Any] = field(default_factory=dict)` with the brief's exact comment.
- Created `src/ggufdoctor/checks/cross_engine.py` — `X_IDS`, `is_tool_fixture`, `run_cross_engine_checks`, per the brief, plus two additions (see below): `_signature` and `_flatten_typed_content`/`_explained_by_normaliser`.
- Created `tests/test_checks_cross_engine.py` — the brief's test file, copied verbatim (13 tests).

## TDD evidence

**RED** (Step 2):
```
$ .venv/bin/python -m pytest tests/test_checks_cross_engine.py -v
...
ModuleNotFoundError: No module named 'ggufdoctor.checks.cross_engine'
1 error in 0.05s
```

**Intermediate RED after pasting the brief's `cross_engine.py` verbatim** (before my fix):
```
$ .venv/bin/python -m pytest tests/test_checks_cross_engine.py -v
...
FAILED tests/test_checks_cross_engine.py::test_x001_output_differs_collapses_across_fixtures_with_a_diff
FAILED tests/test_checks_cross_engine.py::test_x005_owns_tool_fixtures_and_x001_the_rest
2 failed, 11 passed in 0.43s
```

**GREEN** (Step 5, after the fix described below):
```
$ .venv/bin/python -m pytest tests/test_checks_cross_engine.py tests/test_checks_sanity.py tests/test_checks_reference.py -v
...
70 passed in 0.78s
```

**Full suite** (Step 6):
```
$ .venv/bin/python -m pytest -q
218 passed in 3.30s
```

## Check-logic fix (not a test/template adjustment — a real bug in the brief's `cross_engine.py`)

The brief's Step 4 code, pasted verbatim, failed two tests. I dug into *why* against the real engines (not FakeEngine) before touching anything, per systematic-debugging practice. Root cause, confirmed empirically:

1. **Signature-as-full-diff-text doesn't collapse fixtures whose message-role lists differ.** The brief's `differs`/`differs_tools`/`explained`/`whitespace` lists use `evidence["diff"]` (the full unified-diff text) as the dedup key passed to `collapse_by_signature`. For a template like `{{ none }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}`, `user_only` renders `'None<|im_start|>user'` vs `'<|im_start|>user'`, but `multiturn` renders `'None<|im_start|>userassistantuser'` vs `'<|im_start|>userassistantuser'`. Both are "the same divergence" (jinja2 prints `None`, llama.cpp doesn't) but the full-line diff text differs per fixture (since `difflib.unified_diff` compares whole strings as opaque "lines" when there's no `\n`), so they never collapsed — `test_x001_output_differs_collapses_across_fixtures_with_a_diff` got 4 separate X001 findings instead of 1, and `test_x005_owns_tool_fixtures_and_x001_the_rest` got 2 separate X005 findings instead of 1.

   Fix: added `_signature(a, b)` — a character-level `difflib.SequenceMatcher` opcode diff with the `"equal"` spans dropped, so the dedup key captures only the replaced/deleted/inserted substrings (`(('delete', 'None', ''),)` in the example above), independent of whatever both engines already agree on around it. Verified empirically this signature is identical across all ten fixtures for the `{{ none }}` template. `evidence["diff"]` itself (the human-readable unified diff, used by the substring assertions in the tests) is untouched — only the internal dedup key changed.

2. **`RenderResult.extra["normalized"]` is a per-render fact, not proof of causation.** llama.cpp's message normaliser runs whenever its caps probe decides a template is string-content-only *and* a message's `content` happens to be a list — regardless of whether the template ever reads `m.content`. I confirmed this directly: rendering `{{ none }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}` (which never touches `.content`) against the `typed_content` fixture returns `normalized: True`, even though the observed divergence (`None` vs empty) is caused by `{{ none }}`, not by the normaliser. The brief's code treated the bare flag as sufficient to route a divergence into the INFO "explained by normaliser" bucket, which misclassified `typed_content` in `test_x001_output_differs_collapses_across_fixtures_with_a_diff` (it should be a plain ERROR grouped with the rest) and prevented the collapse in point 1 above from being clean.

   Fix: added `_flatten_typed_content(context)` (mirrors llama.cpp's observed join of text parts with `"\n"`) and `_explained_by_normaliser(j2, tpl, context, llama_text)`, which re-renders under jinja2 with content pre-flattened and only reports "explained" if that retried render actually reproduces llama.cpp's output. This is used in both the "both engines ok, text differs" branch and inside `_x002` (the one-side-fails branch), replacing the bare `ok_result.extra.get("normalized")` check with a causally-confirmed one. `_x002`'s signature grew three keyword-only params (`j2`, `tpl`, `context`) to support the retry; both call sites in `run_cross_engine_checks` now pass them.

   I verified this against the real engines for the four templates the tests exercise (`{{ none }}...`, `{{ m.content }}...`, the guarded and unguarded `'x' + m.content` templates), for both `typed_content` and `tool_roundtrip`, before writing the fix — see the empirical `render(...)` output captured during debugging (available in the session transcript; not reproduced here since it is not the load-bearing artifact, the fix is).

Per the orchestrator's guidance ("first check whether the check logic is wrong ... never weaken the check code to make a test pass"): this was the check logic being wrong (a real bug, not an engine-semantics assumption mismatch of the kind flagged for `caps_get`/string-only classification), so I fixed the check code rather than the test. No test file or test template was altered — `tests/test_checks_cross_engine.py` is the brief's file byte-for-byte. I'm flagging this as a concern (see below) since it's a deviation from "use verbatim," even though it was necessary and additive (nothing in the brief's public interface or behavior contract changed — `X_IDS`, `run_cross_engine_checks`, `is_tool_fixture` all match the brief's signatures and the resulting classification behavior matches every one of the brief's test expectations).

No `test_identical_engines_produce_no_findings_and_record_agreement` count adjustment was needed — it passed on the first real-engine run with `len(CORE) == 7`, matching the corpus's `tier == "core"` fixtures exactly.

No engine-semantics assumption in the "Facts the brief cannot know" section needed adjusting either:
- `caps_get` did classify `{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}{% endfor %}` as string-only (confirmed `supports_typed_content: False` in `caps`), so the normaliser joins `typed_content`'s parts to `"Hello\nthere"` as the brief assumed.
- `m.content is not none` parsed and ran fine under llama.cpp (no rewrite needed for `test_x002_renders_in_llama_cpp_only_via_normaliser_is_info`).

## Self-review

- **Completeness**: X001, X002, X004, X005 are all produced by `run_cross_engine_checks` (verified via the test suite exercising every branch). The "explained by normaliser" bucket is X001/INFO as specified. `ctx.stats["engines_agreed_fixtures"]` is set whenever the engine pair is present (and only then — absent when only one engine, per `test_single_engine_records_x_family_as_not_evaluated`). `ctx.checks_not_evaluated` gets `X_IDS` appended when the jinja2/llama.cpp pair isn't both present.
- **Quality**: grepped every message string in `cross_engine.py` — none call a template "broken" (`test_x001_...` explicitly asserts `"broken" not in f.message`, and it passes). Both engines always render `with_real_tokens(ctx, fx.context)` — the same dict — for `a = j2.render(...)` and `b = llama.render(...)`, confirmed by `test_real_tokens_reach_both_engines` passing.
- **Discipline**: touched exactly the five files the brief lists (`git status --short` before commit showed only `common.py`, `cross_engine.py`, `test_checks_cross_engine.py` as new, `sanity.py` and `models.py` as modified — nothing else).
- **Testing**: real `Jinja2Engine()`/`LlamaCppEngine()` are used via `load_fixtures()` defaults in every test except the four that explicitly construct `FakeEngine` (`test_author_decline_on_one_side_only_is_x002`, `test_x004_whitespace_only_is_warn`, `test_real_tokens_reach_both_engines`, and one branch of `test_single_engine_records_x_family_as_not_evaluated` which uses only `Jinja2Engine()`), matching the brief's test file exactly. Output is clean — no stray print/debug statements left in `cross_engine.py`.

## Concerns

1. **Deviation from "verbatim" check code.** `cross_engine.py`'s `run_cross_engine_checks`, `_x002`, and the new `_signature`/`_flatten_typed_content`/`_explained_by_normaliser` helpers are not byte-for-byte the brief's Step 4 listing — the dedup-signature and normalizer-causation logic were both genuinely necessary fixes (demonstrated above with real-engine output), not stylistic changes. The public interface (`X_IDS`, `run_cross_engine_checks(ctx)`, `is_tool_fixture(fixture)`) and every one of the brief's 13 tests match exactly, unmodified. Flagging per the task instructions ("mark DONE_WITH_CONCERNS so the controller can rule") since this is a larger deviation than the single-line normalizer-detail escape hatch the orchestrator anticipated, even though it falls under the same "check logic is wrong, fix the logic, don't touch the tests" principle it laid out.
2. `_x002`'s added keyword params (`j2`, `tpl`, `context`, all defaulting to `None`) are unused when `ok_engine != LLAMACPP` or when `ok_result.extra` has no `"normalized"` key (e.g. every `FakeEngine`-based test) — safe, but worth a reviewer's eye that no call site should ever hit `_explained_by_normaliser` with `j2=None` (verified: the only caller, `run_cross_engine_checks`, always passes real values from the resolved engine pair).

## Status

DONE_WITH_CONCERNS — implementation complete, TDD followed, all 218 tests pass, commit made — flagging the check-logic deviation above for the controller's review.

---

## Fix round 1 (review findings)

The coordinator's Task 5 review approved both deviations documented above (the `_signature` collapse fix and the `_explained_by_normaliser` causation fix) as correct fixes to defects in the brief's original code. It then raised one Important and three Minor findings, all in `src/ggufdoctor/checks/cross_engine.py`. All four addressed:

1. **Important — unavailable llama.cpp engine misreported as X002.** `LlamaCppEngine.render` returns `RenderResult(None, "engine:unavailable: <reason>")` when the WASM module or `wasmtime` isn't available. Previously that flowed straight down the one-side-failure path (`a.ok` true, `b.ok` false) and became a collapsed `X002 ERROR "renders under jinja2 but fails under llama.cpp (...)"` on every fixture — reporting an engine outage as a template defect. Fixed per ledger R3: added `_engine_unavailable(r)` (checks `r.error.startswith("engine:unavailable:")`) and a check at the top of the fixture loop, before the `a.ok and b.ok` branch — if either render result is an unavailable-engine result, `ctx.checks_not_evaluated.extend(X_IDS)` and return `[]` immediately (no findings, `ctx.stats["engines_agreed_fixtures"]` never set since the loop exits before reaching that line, and it happens exactly once since we return on first occurrence rather than looping further). The existing single-engine-missing path (`_engine_pair` returning `None`) is untouched. Added `test_unavailable_engine_records_x_family_as_not_evaluated` using `FakeEngine` for the llama.cpp side returning that exact `RenderResult` on every call; asserts `run_cross_engine_checks(ctx) == []`, `ctx.checks_not_evaluated == X_IDS`, and `"engines_agreed_fixtures" not in ctx.stats`.

2. **Minor — `_x002`'s `j2`/`tpl`/`context` params were optional with dishonest types.** Changed the signature from `*, j2: Any = None, tpl: str | None = None, context: dict[str, Any] | None = None` to `*, j2: Any, tpl: str, context: dict[str, Any]` — required keyword-only, honest types (they are always used unconditionally inside `_x002` whenever the `normalized`-confirmation branch is taken, so `None` defaults were never actually safe, just silently permitted by the type). Both call sites in `run_cross_engine_checks` already pass all three explicitly, so no call-site changes were needed.

3. **Minor — two X002 messages omitted the failure stage.** `renders under jinja2 but fails under llama.cpp ({msg})` → `... ({stage}: {msg})`, and `renders under llama.cpp but fails under jinja2 (transformers path) ({msg})` → `... (transformers path) ({stage}: {msg})`. The brief's own test assertions (`test_x002_template_that_will_not_load_in_llama_cpp`'s `startswith("template will not load in llama.cpp (parser:")`, and the various `"in message"` substring checks) target a different branch (the lexer/parser branch, already stage-qualified) or don't inspect these two exact strings, so no test assertions needed updating — reconfirmed by the full covering-test and full-suite runs below, both green.

4. **Minor — `_flatten_typed_content` docstring didn't name its blind spot.** Added: "This does NOT mirror every rewrite llama.cpp's normaliser can make -- notably request-level rewrites of tool_calls[].function.arguments (string <-> object) and reasoning_content are not reproduced here, so a divergence caused by those is reported at ERROR rather than INFO (the conservative direction: a real divergence surfaced, never a real one hidden)."

### Verification

```
$ .venv/bin/python -m pytest tests/test_checks_cross_engine.py tests/test_checks_sanity.py tests/test_checks_reference.py -q
71 passed in 1.34s
```

```
$ .venv/bin/python -m pytest -q
219 passed in 3.95s
```

(70 → 71 covering tests: the one new `test_unavailable_engine_records_x_family_as_not_evaluated`. 218 → 219 full suite, same delta.)

### Status

DONE — all four review findings fixed, covering tests and full suite green, ready to commit.
