# Final fix wave — report (2026-09-03)

Branch `feat/v0.2`, base for this wave `44311ab`. Five commits, nothing pushed.

| commit | subject |
|---|---|
| `5cb0974` | checks: apply the full explanation ladder to X002, bound diff lines |
| `d3d2c78` | engine: bound the WASM store, never raise from `__init__` |
| `1d24de2` | conformance: pin every download by digest, extract safely |
| `470e87a` | docs, tests: corpus version in the survey, citations, and stale figures |
| *(HEAD)* | docs: state the shared ladder, correct the store-limit measurements — this commit, which also carries this report |

Verification, run last, in this order:

```
$ .venv/bin/python -m pytest -q
262 passed, 10 deselected in 12.78s

$ .venv/bin/python -m pytest -m conformance tests/conformance -q
10 passed in 3.28s
```

The default suite is network-free; conformance is the only thing that downloads,
and it was additionally run once from a completely cold cache (`rm -rf
~/.cache/ggufdoctor-conformance`) to exercise the new download → verify →
extract path: 10 passed in 7.05s.

---

## Important 1 — `_x002` explanation ladder (R13)

**What was wrong.** `_x002`'s llama.cpp-renders / jinja2-fails branch consulted
only `_explained_by_normaliser`. A one-sided divergence whose cause was the
runtime defaults, or the normaliser *and* the defaults composed, was reported at
ERROR — while the structurally identical both-engines-rendered case was INFO. The
grade depended on whether jinja2 limped through the un-normalised input or raised
on it, not on the cause.

**What changed** (`src/ggufdoctor/checks/cross_engine.py`):

* New `_explain(j2, tpl, context, ok_result) -> (explained_by, defaults)` holds
  the ladder — normaliser → runtime defaults → composed, with the `normalized`
  flag gating only the two rungs that involve the normaliser and the composition
  tried last. **Both** paths call it (the both-rendered classifier and `_x002`),
  so the two cannot drift apart; the previous parallel implementation in
  `run_cross_engine_checks` was replaced by dispatch on `_explain`'s result, with
  no behaviour change on that path (all 20 pre-existing cross-engine tests passed
  unmodified).
* An explained X002 is INFO with `evidence["explained_by"]`
  (`normaliser` / `runtime_defaults` / `normaliser+runtime_defaults`),
  `evidence["defaults"]` (the keys the confirming re-render had to add) and
  `evidence["normalized"]` true iff the normaliser is part of the explanation.
  Each new message names the cause **and** still states the one-sided fact — it
  ends `jinja2 (transformers path) fails on the original (<error>)` — plus the fix
  ("pass them explicitly", "pre-join typed content and pass those defaults
  explicitly").
* `_x002` lost its unused `fx` parameter; both call sites updated.
* Ordering deliberately unchanged: `stage == "raise"` and the llama.cpp-failing
  branches still return before the ladder, exactly the position the old
  `if normalized:` branch occupied. Widening the ladder to cover a jinja2
  `raise_exception` would be a behaviour change beyond R13 and was not made.

**Tests.**
`tests/test_checks_cross_engine.py::test_x002_renders_in_llama_cpp_only_via_normaliser_and_defaults_is_info`
— real engines, template
`{% if not enable_thinking %}<think>{% endif %}{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content if m.content is not none else '' }}{% endfor %}`
(the composed-X001 test's shape with `'x' + m.content` so typed content *raises*
under jinja2 instead of printing a repr). Asserts the complete finding set, plus
`explained_by == "normaliser+runtime_defaults"`, `normalized is True`,
`defaults == list(RUNTIME_DEFAULTS)`, both causes named in the message,
`"fails on the original" in message`, and `engines_agreed_fixtures == 2`.

**Real-template re-derivation.** Exactly one entry shifted, as predicted:
`antirez__deepseek-v4-gguf` / `typed_content`, X002 **ERROR → INFO**
`normaliser+runtime_defaults` with all six `RUNTIME_DEFAULTS` keys. Its
justification was rewritten from scratch: the two causes (the normaliser's
`"Hello\nthere"` join and the `enable_thinking` `<think>`), why neither alone
reproduces llama.cpp, and why this entry is the one R13 exists for — the same two
causes on Gemma-4 and mudler were already INFO because jinja2 happened not to
raise there.

Every other X002 entry was re-checked and none shifts:

| entry | rung reached | outcome |
|---|---|---|
| PaddlePaddle / `tool_roundtrip` | none — no typed content to flatten; defaults leave the `for content in message["content"]` loop iterating `None` | ERROR, unchanged |
| rippertnt / `tool_roundtrip` | none — defaults leave `+ message['content']` looking at the same null | ERROR, unchanged |
| rippertnt / `typed_content` | normaliser (first rung) | INFO, unchanged |
| unsloth / `typed_content` | normaliser (first rung) | INFO, unchanged |

The two ERROR entries' comments now say the whole ladder was walked and *why*
each rung fails, rather than only mentioning the pre-flatten. The `EXPECTED`
header's two recurring-shape bullets were generalised to the shared ladder.

## Important 2 — bounded WASM store (R14)

**API check first**, as instructed:

```
$ .venv/bin/python -c "import wasmtime; print([n for n in dir(wasmtime.Store) if 'fuel' in n or 'limit' in n])"
['get_fuel', 'set_fuel', 'set_limits']
```

wasmtime-py 48.0.0 has **no `wasmtime.StoreLimits`** object (`hasattr` is False);
limits are set directly with `store.set_limits(memory_size=…, …)`, negative
meaning "leave alone". So the code passes `memory_size` only. This is the one
place the brief's wording could not be followed literally, and the comment in the
source says why.

**What changed** (`src/ggufdoctor/engines/llamacpp_engine.py`):

* `cfg.consume_fuel = True` on the `Config` (must precede module compilation — it
  changes the generated code), `store.set_fuel(FUEL_BUDGET)` and
  `store.set_limits(memory_size=MEMORY_LIMIT_BYTES)` per render.
* `FUEL_BUDGET = 5_000_000_000`, `MEMORY_LIMIT_BYTES = 512 * 1024 * 1024`, module
  constants with a comment giving the reason (stranger's template text; a native
  call cannot be interrupted by Ctrl-C, which is only checked between Python
  bytecodes) and the measured headroom.
* A trap surfaces through the existing `except Exception` →
  `render:wasm: <type>: <first line>` path, untouched.

**Measured, to justify the constants** (instrumented probe, all ten vendored
templates × all ten fixtures):

* worst real render: **60,492,787 fuel units** (LuffyTheFox / `tool_roundtrip`) —
  ~80x headroom;
* peak linear memory over the same sweep: **393,216 bytes (0.4 MiB)** — ~1300x
  headroom;
* a trivial render costs ~7M fuel (mostly instantiation), and a bare loop costs
  ~900K fuel per iteration, so 5e9 stops a runaway inside ~0.7 s.

**Tests** (`tests/test_engine_llamacpp.py`):

* `test_a_runaway_template_traps_on_fuel_instead_of_hanging` —
  `{% for i in range(10000) %}{% for j in range(10000) %}{% endfor %}{% endfor %}`
  → `not r.ok`, `r.error.startswith("render:wasm:")`, one line, in 0.72 s
  (asserted `< 30`). Verified this template runs **81.7 s to completion** with
  fuel disabled, i.e. the test really exercises the new bound.
* `test_a_memory_hungry_template_is_bounded_too` —
  `{% for i in range(200000000) %}{% endfor %}` → `not r.ok`,
  `r.error.startswith("render:")`, 4.5 s.
* `test_the_whole_fixture_corpus_renders_on_the_longest_vendored_template` — the
  longest vendored template (`HauhauCS__Gemma-4…`, 11,926 bytes) × all ten
  fixtures, every one `r.ok`.

**Deviation, stated plainly.** The brief asked for
`{% for i in range(200000000) %}{% endfor %}` to return
`r.error.startswith("render:wasm:")`. It does not, and the reason is the memory
cap the same ruling asked for: that template asks `range` for the whole list at
once, so it hits `MEMORY_LIMIT_BYTES` while *growing* linear memory having burned
only 3.3M fuel. `memory.grow` then returns -1, the module's own allocator throws,
and `shim.cpp`'s C++ catch turns it into a clean in-module `render: Error:
std::bad_alloc` — a reported render error, not a trap. (With the memory cap
removed it grows to 1.4 GB and *then* exhausts fuel → `render:wasm:`.) Rather
than loosen the assertion to `render:` and lose the trap coverage, or drop the
memory cap to force a trap, both bounds are pinned separately with the exact
prefix each one actually produces, and each test's comment explains its
mechanism. Nothing is unbounded either way.

## Important 3 — `__init__` never raises (R15)

`load_manifest()` ran *before* any `try`, and `metadata.version("wasmtime")` ran
outside one, so a wheel with no manifest or a wasmtime with no dist-info took the
CLI down with a traceback — contrary to spec amendments §A.

**What changed**: `version`/`commit` are initialised to `"unknown"` before
anything fallible; `load_manifest()` is inside a `try` whose failure sets
`unavailable_reason = "engine manifest unavailable: …"` and returns;
`metadata.version` is inside its own `try` whose failure sets
`backend = "wasmtime"` and leaves the engine **available** (the import worked, so
the runtime is there — only its dist-info is missing).

**Tests** (`tests/test_engine_llamacpp.py`):

* `test_missing_manifest_makes_engine_unavailable_not_raising` — monkeypatches
  `llamacpp_engine.load_manifest` to raise `FileNotFoundError`; asserts
  `available is False`, the reason names the manifest, and `render()` returns
  `engine:unavailable:`.
* `test_unknown_wasmtime_dist_version_still_leaves_the_engine_available` —
  monkeypatches `metadata.version` to raise `PackageNotFoundError`; asserts
  `available is True`, `backend == "wasmtime"`, and that it still renders.
* `test_select_engines_degrades_instead_of_raising_when_the_manifest_is_gone` —
  the required `select_engines(None)` assertion: `[e.name for e in
  selection.engines] == ["jinja2"]` and the gap recorded in
  `selection.unavailable["llama.cpp"]`.

## Important 4 — checksums and safe extraction (R16)

### Digests computed for this task

Network was used once per asset, from the canonical URL, on 2026-09-03; digest via
`shasum -a 256`.

llama.cpp release assets, `https://github.com/ggml-org/llama.cpp/releases/download/b10775/<asset>`:

| asset | sha256 |
|---|---|
| `llama-b10775-bin-ubuntu-x64.tar.gz` | `faac52e16e5749713d33531ab7e4161fd0f09e7f2dccb4ed7527162d4c3bd103` |
| `llama-b10775-bin-macos-arm64.tar.gz` | `cd91a87f6e00dddeab16469cf5fc3bf09ee535705a0d09e8cd2e8ef7da4d2cac` |
| `llama-b10775-bin-win-cpu-x64.zip` | `1da037557b6bb588fc48a8d371b948ed6c4334831f23af8a0b084319e7e81a9b` |

Model, `https://huggingface.co/ggml-org/models/resolve/499bc8821c6b12b4e53c5bffcb21ec206f212d81/tinyllamas/stories260K.gguf`:

| file | sha256 |
|---|---|
| `stories260K.gguf` | `270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d` |

wasi-sdk, `https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-34/wasi-sdk-34.0-<host>.tar.gz`
— **all four hosts downloaded and hashed, so there are no `UNVERIFIED` entries**:

| host | sha256 |
|---|---|
| `arm64-macos` | `9c59398106b417f8f14913380fdf0097a8cc0ff4af9eb3ce0065a859e88d49e9` |
| `x86_64-macos` | `87d27fa8adc68dee59bfbf2e22a6d34ef717c34d6bf1d8af2a56fc929d9ce0eb` |
| `x86_64-linux` | `b761e3a0721dbae9c09a0059e5fdb2bf917d1b4a8a7b430fb3b5aafb0984b2c4` |
| `arm64-linux` | `f7e243dff54d60bcc576e94d6166b69f410f2500ae4a9ceef34315be10e77971` |

The macos-arm64 asset and the model digests also match the copies already in this
machine's conformance cache from Task 9's runs, which is an independent
confirmation that the pinned bytes are the bytes the suite has been passing
against.

### `MODEL_REVISION`

`ggml-org/models` now **redirects to `ggml-org/models-moved`**; its current commit
sha, via `curl -sSL "https://huggingface.co/api/models/ggml-org/models?expand[]=sha"`
(the `-L` matters — without it the API returns a redirect body, not JSON), is
`499bc8821c6b12b4e53c5bffcb21ec206f212d81`. All three of
`ggml-org/models/resolve/main/…`, `ggml-org/models/resolve/<sha>/…` and
`ggml-org/models-moved/resolve/<sha>/…` return 200. `MODEL_URL` keeps the name
the project already used and pins the sha — and since the digest is verified
anyway, a further rename cannot substitute content.

### `tests/conformance/llama_server.py`

* `SHA256` table for the three selectable release assets and the model; an asset
  with no entry raises `KeyError` rather than being fetched unverified.
* `_download` verifies **on every call**, not only after a fresh download — CI
  restores this directory from a cache key, so a cached file earns the same trust
  a new one does. A mismatch `unlink()`s the file (never leave a copy that just
  failed for the next run to reuse) and raises before anything is unpacked.
* `tarfile.open(...).extractall(path, filter="data")`.
* `_extract_zip` resolves every member against the target and rejects any that
  would land outside it, checked for all members before one byte is written
  (zipfile has no `filter=`).
* Extraction stages into `bin.part` and renames, so an interrupted run cannot
  leave a half-populated `bin` the next run treats as complete.
* `GGUFDOCTOR_LLAMA_SERVER` / `GGUFDOCTOR_CONFORMANCE_MODEL` still short-circuit
  before any download, with no digest check — a user-supplied path is their own
  trust decision. Comments say so at both sites.

Proved by hand, in addition to the suite runs:

```
tampered the cached model, then called _download:
rejected: stories260K.gguf: sha256 cd2a32f7d5e713a996e02b8103ff816e247d705e300438634ad1e8b6824f0587 does not match the p…
deleted: True
re-download ok: True
```

### `engine/build.sh`

* `wasi_sdk_sha256()` per host (all four filled in); a host with no entry prints
  `UNVERIFIED`, and the script then refuses to auto-download and tells the user to
  install the SDK and set `WASI_SDK`.
* `sha256_check()` uses `shasum -a 256 -c` where available, falls back to
  `sha256sum -c`, and treats "no hashing tool" as a hard failure — never a skipped
  check.
* The old `curl … | tar xz` is gone: the tarball is downloaded to `…part`, moved
  into place, verified, and only then extracted. That pipeline could neither check
  the bytes nor notice a truncated transfer (T1's deferred `pipefail` minor is
  therefore also resolved).
* `chmod 644` on the built module, so clang's executable bit does not come back.
* Verified with `sh -n`, and the two helpers exercised directly against the real
  tarball: correct hash accepted, wrong hash rejected (exit 1), unknown host
  refused.

### `.github/workflows/ci.yml`

A `pins` step reads the digest **from the same `SHA256` table the download
verifies against** and the model revision, and the cache key becomes
`conformance-b10775-${{ runner.os }}-${{ steps.pins.outputs.assets }}` →
`conformance-b10775-Linux-faac52e16e57-499bc8821c6b` today. Bump a pin and the key
changes, so a stale entry is never restored and then rejected on every run. The
key cannot drift from the table because it is derived from it.

### `src/ggufdoctor/engine_data/llamacpp-jinja.wasm`

`git update-index --chmod=-x` applied; `git ls-files -s` now shows `100644`.

### `engine/README.md`

"Bumping the pin" gained a step 4 documenting the refresh for both digest tables,
with the exact commands, and noting that a stale digest fails closed. Steps
renumbered (the old list had two step 5s). The "Rebuilding" section states the
0644 mode and the verification.

## Important 5 — path citations (R17)

`tests/test_cli.py` (1) and `tests/test_checks_sanity.py` (2) now cite
`docs/process/v0.2/task-6-report.md`. A repo-wide grep for `task-N-report`
outside `docs/process/` returns nothing else. The directory was **not** created —
that is the controller's copy step.

## Fix-before-merge minors

6. `tests/test_real_templates.py` header: `_explained_by_thinking_default` →
   `_explained_by_runtime_defaults`, `"enable_thinking_default"` →
   `"runtime_defaults"`.
7. mudler entry: the brackets are **U+3008 / U+3009** (verified by scanning the
   vendored template for codepoints > U+2000: it contains `〈` U+3008 and `〉`
   U+3009, and no U+2329/U+232A), and the comment now names them and says they are
   not the mathematical pair they resemble.
8. `tests/data/templates/SOURCES.md` gained an "On the Licence column" paragraph:
   `other` (three repos) and `gemma` (one) name no licence — they point at a file
   nobody here has read — and anyone redistributing beyond ggufdoctor's test data
   must read each repo's actual licence text first.
9. `survey.py`: `"fixture_corpus_version": CORPUS_VERSION` first in the aggregate,
   and `- Fixture corpus version: **N**` as the first figure in `to_markdown`.
   New `tests/test_survey.py::test_figures_are_published_with_their_fixture_corpus_version`
   checks both against `fixtures.CORPUS_VERSION` (not a literal, so it cannot go
   stale). The committed `.json` was edited **in place** (one inserted line) and
   then diffed key-by-key against the original in memory to prove `records` and
   every other aggregate value are byte-identical; the `.md` was regenerated from
   that JSON by `to_markdown` and the diff against the committed file is exactly
   the one new line (trailing-newline state preserved). The survey was **not**
   re-run. `docs/research/README.md` no longer claims the output cannot record the
   corpus version, while keeping the corpus-1 tie documentary for the two v0.1
   artefacts.
10. `docs/research/2026-09-03-engine-spike.md` banner under the title: the shipped
    module is **725,239 bytes** (confirmed against the committed manifest), the
    caps probe / normaliser / runtime defaults landed after the 672 KB
    measurement, and §3's expression table describes the raw `common/jinja`
    runtime rather than the shipped engine that wraps it (pointing at
    `tests/test_engine_semantics.py` for what the shipped engine does).
    `docs/v0.2-kickoff.md`'s 672 KB blockquote is qualified the same way.

## Cheap minors

11. `--engines` help: "jinja2 is the reference engine and cannot be deselected" —
    matches the README and the error `select_engines` actually raises.
12. `CHANGELOG.md`: the engine-build job now reads "the committed module is one
    anyone can regenerate", with the hash comparison called informational and the
    reason (`-Oz` is not bit-reproducible across toolchain builds); `extra` moved
    from findings to `RenderResult`, with findings' `evidence` named. Same `extra`
    slip fixed in the spec amendments §F. Two knock-on accuracy fixes made because
    finding 1 changed behaviour: the README's `X002` row and the CHANGELOG's INFO
    rule now say `X001` and `X002` share one ladder.
13. f-string with no placeholders in `llamacpp_engine.render`.
14. `tests/conformance/test_llama_server.py`: `except Exception` → `except
    urllib.error.HTTPError` with a `400 <= code < 500` guard; anything else
    re-raises and fails the pair. A 5xx, a dropped connection or a timeout is a
    broken harness, not "the server declined", and must not be scored as agreement
    because we happened to fail too.
15. `_diff` slices each emitted line to `DIFF_LINE_CHARS = 400` with a `…` marker.
    New `test_diff_evidence_is_bounded_per_line_not_just_per_line_count` renders
    100,000 identical characters on each side and asserts every diff line is
    within budget — the 40-line cap bounds nothing for a minified template.
16. wasm mode 0644 (see Important 4) and `chmod 644` in `build.sh`.

## Not done / for the controller

* **`docs/process/v0.2/`** is not created here (R17 assigns the copy to the
  controller). The citations point at it already.
* **Spec amendments §B still says X002 is "error (INFO when explained by the
  normaliser)"**, and its X001 row likewise predates R9/R10/R12. I did not amend
  §B: that table is already behind on three earlier rulings that the controller
  chose to record in the ledger rather than in the spec (only R7 got a spec
  amendment), so fixing R13 alone there would make the doc inconsistent in a new
  way. The user-facing README **was** updated. Flagging it as a controller call.
* **`docs/v0.2-kickoff.md`'s claim that `docs/process/v0.2/` exists** is still
  resolved by the controller's copy, as recorded in the ledger.
* The brief's exact `render:wasm:` assertion for
  `{% for i in range(200000000) %}{% endfor %}` could not be met as written; see
  the deviation note under Important 2. Both bounds are tested, each against the
  prefix it actually produces.
