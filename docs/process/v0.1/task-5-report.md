# Task 5 report: Jinja2 engine and fixture corpus

## What was created

- `src/ggufdoctor/engines/__init__.py` — empty, marks `engines` as a package.
- `src/ggufdoctor/engines/base.py` — `Engine` Protocol (`name: str`, `version: str`, `render(template, context) -> RenderResult`).
- `src/ggufdoctor/engines/jinja2_engine.py` — `Jinja2Engine`, backed by `jinja2.sandbox.ImmutableSandboxedEnvironment`. Compile errors and render errors are both caught and returned as `RenderResult(None, "compile:...")` / `RenderResult(None, "render:...")`, never raised. Provides `bos_token`/`eos_token`/`unk_token`/`pad_token`/`add_generation_prompt` defaults via `BASE_CONTEXT` (caller context overrides), plus the `raise_exception` and `strftime_now` globals and a `tojson` filter. `strftime_now` is pinned to `PINNED_NOW = datetime.datetime(2026, 1, 1)` for determinism.
- `src/ggufdoctor/fixtures.py` — `CORPUS_VERSION = "1"` (string) and `load_fixtures(path=None) -> list[Fixture]`. With `path=None` it reads `corpus.json` out of the `ggufdoctor.fixture_data` package via `importlib.resources`; with an explicit `path` it opens that file directly. Returns `Fixture(name, context)` from Task 1's `models.py`, unmodified.
- `src/ggufdoctor/fixture_data/__init__.py` — empty (see Ruling 1 below).
- `src/ggufdoctor/fixture_data/corpus.json` — the seven-fixture corpus (`user_only`, `system_user`, `multiturn`, `with_tools`, `thinking_unset`, `thinking_true`, `thinking_false`), transcribed verbatim from the brief, `"version": "1"`.
- `tests/test_engine_jinja2.py`, `tests/test_fixtures.py` — the 8 tests exactly as given in the brief.

No other existing file was modified. `pyproject.toml` has a zero-line diff (`git diff pyproject.toml` is empty) — see Ruling 2.

## Test command and output

Failing-first check:
```
.venv/bin/python -m pytest tests/test_engine_jinja2.py tests/test_fixtures.py -v
```
→ 2 collection errors, `ModuleNotFoundError: No module named 'ggufdoctor.engines'` / `'ggufdoctor.fixtures'`, as expected before implementation existed.

After implementation:
```
.venv/bin/python -m pytest tests/ -v
```
→ **23 passed** (15 pre-existing + the 8 new: 5 in `test_engine_jinja2.py`, 3 in `test_fixtures.py`). One pre-existing test (`test_nonzero_offset_against_non_range_server_raises_error` in `test_http_range.py`, not part of this task) prints an "Exception occurred during processing of request" line to stderr from its socketserver handler but still reports PASSED — this is unrelated to Task 5 and unchanged from the pre-existing suite.

Ran the full suite a second time after the reinstall step below, still 23 passed.

## Commit

`3dc4b4f` — "feat: jinja2 engine and versioned fixture corpus", on branch `feat/v0.1`. 8 files added, 170 insertions, 0 deletions. Working tree clean after commit. `pyproject.toml` was intentionally left out of the commit (nothing to stage — see Ruling 2).

## Confirmation: packaged corpus loads from an installed, not source-tree, import

This was the highest-risk item given Ruling 2 (skip force-include), so I verified it concretely rather than assuming hatchling's default packaging behavior:

1. Reinstalled the editable install after adding the data file: `uv pip install --python .venv/bin/python -e .` — succeeded, reinstalled `ggufdoctor==0.1.0`.
2. Built an actual wheel with `uv build --wheel -o <scratch>/dist` and listed its contents with `unzip -l`. Confirmed `ggufdoctor/fixture_data/__init__.py` and `ggufdoctor/fixture_data/corpus.json` are both present in the wheel — packaged automatically because `fixture_data` sits inside `src/ggufdoctor`, which is already listed under `packages = ["src/ggufdoctor"]`. No force-include block was needed.
3. Created a **separate, fresh venv** (`uv venv <scratch>/verify-venv --python 3.11`, unrelated to the project's `.venv`) and installed the built wheel into it (not editable — a real install).
4. From `/tmp` (outside the repo entirely, so no source tree on `sys.path` by accident), ran a script against that venv's `python`:
   - `ggufdoctor.__file__` resolved to `.../verify-venv/lib/python3.11/site-packages/ggufdoctor/__init__.py` — confirming the import came from the installed package, not the repo.
   - `load_fixtures()` returned `CORPUS_VERSION == "1"` and the 7 fixture names in the exact expected order.
   - `fixtures[3].context["tools"][0]["function"]["name"] == "get_weather"`.
   - `Jinja2Engine()` reported `name="jinja2"`, a non-empty `version`, and rendered `{{ 1+1 }}` to `"2"`.
5. Cleaned up the scratch venv and wheel afterward; the project's own `.venv` was left in its normal editable-install state (re-synced via the Step-3 reinstall above), and the full suite (23 passed) was re-run in it as a final check before committing.

This confirms `resources.files("ggufdoctor.fixture_data")` resolves correctly for a genuinely installed distribution, not just an editable/source-tree import.

## The three rulings and how they were applied

1. **Empty `fixture_data/__init__.py`.** Created it (0 bytes) alongside `corpus.json`, staged and committed with the other 7 files. Without it, `resources.files("ggufdoctor.fixture_data")` would fail at import/lookup time since the directory wouldn't be a package Python (or hatchling's package-discovery) recognizes.
2. **No `[tool.hatch.build.targets.wheel.force-include]` block.** Not added. `pyproject.toml` has a zero-line diff. Verified via a real `uv build --wheel` + `unzip -l` that `fixture_data/__init__.py` and `fixture_data/corpus.json` are included in the wheel regardless, because they live under the already-declared `packages = ["src/ggufdoctor"]` path — hatchling ships non-Python files found inside a declared package directory by default, so the extra block was unnecessary and the ruling's stated risk (double-inclusion) didn't need to be taken on.
3. **Corpus JSON starts with `{`.** The brief's ```` ```json ```` block opened with `// src/ggufdoctor/fixture_data/corpus.json`, which is a file-path marker/comment, not valid JSON (JSON has no `//` comment syntax). I omitted that line; `corpus.json` on disk starts at `{` and was validated with `json.load()` before running any tests. All seven fixture objects and their contexts were transcribed byte-for-byte from the brief's JSON body (lines 189–222), preserving key order, nesting, and the `true`/`false` literal casing — nothing paraphrased, reordered, or reformatted beyond the mechanical removal of that one leading comment line.

No other deviations from the brief. All test code, `base.py`, `jinja2_engine.py`, and `fixtures.py` were transcribed exactly as given.

## What Tasks 6, 8, 10, 12 should know

- **Engine interface:** `Engine` is a `typing.Protocol` (`src/ggufdoctor/engines/base.py`) with `name: str`, `version: str`, and `render(template: str, context: dict[str, Any]) -> RenderResult`. Anything duck-typed to that shape satisfies it — no need to subclass. `Jinja2Engine()` takes no constructor args; instantiate once and reuse (it builds its own sandboxed environment).
- **RenderResult contract:** `render()` **never raises**. A `RenderResult` always comes back; check `.ok` (True iff `.error is None`) before trusting `.text`. `.error` is a string prefixed `"compile:<ExceptionType>: <message>"` for template-syntax/compile-time failures, or `"render:<ExceptionType>: <message>"` for failures during actual rendering (undefined vars, `raise_exception()` calls, bad filters, etc.). Downstream checks that want to distinguish "template doesn't even compile" from "template compiles but blows up on this fixture" can split on that prefix.
- **Context merging:** `Jinja2Engine.render` merges a `BASE_CONTEXT` (bos/eos/unk/pad tokens, `add_generation_prompt=True`) underneath whatever `context` dict is passed in — the caller's keys win on conflict. So a fixture's own `context` (e.g. `with_tools`'s `tools` list, or `thinking_true`/`thinking_false`'s explicit `enable_thinking`) is exactly what reaches the template; fixtures that don't set `enable_thinking` (`thinking_unset`) simply won't have that key at all — templates that check `enable_thinking is defined` or similar will see it as genuinely undefined, not `False`.
- **Determinism:** `strftime_now` is pinned to `2026-01-01T00:00:00`. Any check comparing rendered output across runs, models, or engines can rely on date-derived output being stable — but note the pinned date is a fixed constant in `jinja2_engine.py`, not configurable per-call.
- **Fixture interface:** `load_fixtures(path=None) -> list[Fixture]` returns the 7 fixtures **in the fixed order** given in the brief (tests assert exact list equality on `[f.name for f in load_fixtures()]`), each a frozen `Fixture(name: str, context: dict)` from Task 1's `models.py`. `CORPUS_VERSION` (module-level string `"1"`) is exported from `ggufdoctor.fixtures` for anything that wants to record/report which corpus version produced a given result (e.g. for the `Coverage` dataclass or report metadata in later tasks). The optional `path` argument lets callers/tests point at an alternate corpus file on disk (bypassing the packaged resource) but nothing in this task's tests exercises that path — future tasks needing a custom/test corpus can pass `path=...` directly.
- **Packaging shape:** the corpus lives at `src/ggufdoctor/fixture_data/corpus.json`, shipped as package data automatically (confirmed above) — no manifest/force-include entries needed elsewhere in `pyproject.toml` for this or future data files placed under any existing package directory.
- **Fixture content specifics future checks may care about:** `with_tools` is the only fixture carrying a `tools` list (OpenAI-style tool-call schema, one tool `get_weather`); `system_user` is the only one with a `system` role message; `multiturn` is the only one with an `assistant` message already in history; the three `thinking_*` fixtures are otherwise identical (`"2+2?"` single-turn) and differ only in whether/how `enable_thinking` is set — they exist specifically to let a check assert a template's behavior changes appropriately (or doesn't crash) across that flag's three states.

## Fix round 1

The coordinator's reviewer compared `jinja2_engine.py` against an actually-installed `transformers` (`transformers/utils/chat_template_utils.py`, found locally at `/Users/saad/.cache/uv/archive-v0/DB2eN0L8gg2iim5a/transformers/utils/chat_template_utils.py` and used as the ground truth for this fix) and found the environment did not match the spec's "this is the transformers reference" claim in four places. All four are fixed in `src/ggufdoctor/engines/jinja2_engine.py`; no other file changed.

**1. Block trimming.** `trim_blocks` and `lstrip_blocks` are now both `True` on the `ImmutableSandboxedEnvironment`, matching transformers exactly. Verified with `test_trim_blocks_and_lstrip_blocks_are_enabled`: the same template renders `"\nX\n"` with both settings `False` and `"X\n"` with both `True` — confirmed by direct experiment before writing the test, so the assertion actually distinguishes the two settings rather than passing either way.

**2. `jinja2.ext.loopcontrols` is now loaded** via the environment's `extensions=[...]` argument (alongside the new `GenerationExtension`, see below). `{% break %}` / `{% continue %}` inside a loop now compile and render instead of raising `TemplateSyntaxError` at compile time. Verified with `test_loop_controls_break_compiles_and_renders`. Also spot-checked that `{% break %}` used outside any loop still correctly fails to compile (`SyntaxError: 'break' outside loop`) and comes back as a `RenderResult` with a `compile:` error, not a raised exception — the never-crash contract holds for this new path too.

**3. `{% generation %}...{% endgeneration %}` is now supported** via a new `GenerationExtension(jinja2.ext.Extension)` class in the same file. It parses the tag pair (`parser.parse_statements(["name:endgeneration"], drop_needle=True)`) and renders the enclosed body unchanged via a `CallBlock` — the same parse-time mechanism transformers' `AssistantTracker` uses, minus the tracking. **Deliberately not implemented:** transformers' version also records `(start_index, end_index)` character offsets of each generation span for `return_assistant_tokens_mask`, via an `activate_tracker` context manager and a `@pass_eval_context`-decorated call method. v0.1 has no consumer for those offsets (no task in the plan reads `return_assistant_tokens_mask` or an index list), so `GenerationExtension._generation_support` just returns `caller()` with no side channel. This is the documented, deliberate gap: templates using `{% generation %}` will compile and render correct text under ggufdoctor, but nothing in this codebase can (yet) tell you which character ranges came from inside those tags. Verified with `test_generation_tag_compiles_and_body_appears_in_output`; also spot-checked that an unclosed `{% generation %}` tag fails to compile with a clean `compile:TemplateSyntaxError`, not a raised exception.

**4. `tojson` now matches transformers' signature and defaults exactly:** `_tojson(x, ensure_ascii=False, indent=None, separators=None, sort_keys=False)`, calling `json.dumps` with all four kwargs forwarded (previously: `lambda o, **kw: json.dumps(o)`, which silently dropped every kwarg and defaulted to `ensure_ascii=True`). Verified with `test_tojson_keeps_non_ascii_literal` (`café` stays literal, no `\u` escapes) and `test_tojson_indent_is_honoured` (`[1, 2] | tojson(indent=4)` now actually produces indented, multi-line JSON instead of silently rendering compact).

**Globals check (as instructed, no new globals added beyond what transformers provides):** `raise_exception` was already present (transformers raises `jinja2.exceptions.TemplateError(message)`; ours raises `ValueError(msg)` — left as-is since the coordinator confirmed this global was "present and working" and did not flag the exception type as a defect; both are caught by the engine's blanket `except Exception` and surface as a `render:` error either way, so the observable contract is identical). `strftime_now` was already present (ours pins to a fixed date instead of `datetime.now()`, which is intentional for determinism per the original task brief, not a defect). No globals were added or removed relative to transformers' `raise_exception` / `strftime_now` pair.

**Sandbox regression check:** re-confirmed after all changes that `ImmutableSandboxedEnvironment` still blocks a real escape attempt — `{{ ''.__class__.__mro__[1].__subclasses__() }}` and `{{ ().__class__.__base__.__subclasses__() }}` both come back as `RenderResult(text=None, error="render:SecurityError: access to attribute '__class__' of '...' object is unsafe.")`, not a raised exception and not executed. This was true before and after the fix; nothing in the four changes touches sandboxing.

**Tests added** (all in existing files, no new test files):
- `tests/test_engine_jinja2.py`: `test_loop_controls_break_compiles_and_renders`, `test_generation_tag_compiles_and_body_appears_in_output`, `test_tojson_keeps_non_ascii_literal`, `test_tojson_indent_is_honoured`, `test_trim_blocks_and_lstrip_blocks_are_enabled`.
- `tests/test_fixtures.py`: `test_system_user_fixture_renders_exact_text_through_the_engine` (renders the `system_user` fixture through `Jinja2Engine` with a small hand-written template and asserts the exact output string `"[system] Be brief.\n[user] Hello\n"`, so a typo in the corpus's `"Be brief."` or a dropped message would now fail a test) and `test_thinking_fixtures_pin_the_enable_thinking_triple` (asserts `enable_thinking` is absent from `thinking_unset`'s context, `True` in `thinking_true`'s, `False` in `thinking_false`'s). `corpus.json` itself was **not** touched, per instruction.

**Full suite result:** `.venv/bin/python -m pytest tests/ -v` → **30 passed** (the 23 from the first round plus these 7 new tests). No existing test needed modification; no regressions.

### What Tasks 6, 8, 10, 12 should know (revision — supersedes the equivalent claims in the first report where they conflict)

The engine now matches transformers' `_cached_compile_jinja_template` on: `trim_blocks=True`, `lstrip_blocks=True`, the `jinja2.ext.loopcontrols` extension, the `tojson` filter's signature and defaults (`ensure_ascii=False`, and honouring `indent`/`separators`/`sort_keys`), and the presence of `raise_exception` and `strftime_now` as globals (with `strftime_now` intentionally pinned rather than wall-clock, for determinism — this is a deliberate, documented divergence, not a bug). It also matches on sandboxing (`ImmutableSandboxedEnvironment`, unchanged and reverified).

It still diverges from transformers in exactly one place, and it is load-bearing for how Task 8 (and anything else that inspects `{% generation %}` templates) should interpret results: **`{% generation %}` spans are not tracked.** The tag compiles and its body renders as ordinary text — identical to what transformers would render — but there is no equivalent of transformers' `generation_indices` output anywhere in ggufdoctor. Concretely: if a check needs to know *which part* of a rendered string came from inside a `{% generation %}` block (e.g. to validate assistant-masking behavior, not just that the template renders), that capability does not exist yet and would need a new extension (or promoting `GenerationExtension` to the full `AssistantTracker` pattern) rather than being inferable from today's `RenderResult`. Any render difference Task 8 observes between ggufdoctor and a real transformers run should now be attributable to the model/template itself, or to the "no span-tracking" gap above — not to trim/lstrip, loop-control support, or `tojson` fidelity, all of which are now exact matches.
