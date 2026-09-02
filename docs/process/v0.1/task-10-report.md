# Task 10: Reporting and Exit Codes — Implementation Report

## Status: DONE

**Commit SHA:** `892f9d9`  
**Test Summary:** 92 tests pass (87 existing + 5 new)

## Files Created

1. **`src/ggufdoctor/report/__init__.py`** — Empty package marker
2. **`src/ggufdoctor/report/json_report.py`** — JSON report generation and exit-code logic
3. **`src/ggufdoctor/report/human.py`** — Human-readable report formatting
4. **`tests/test_report.py`** — 5 comprehensive tests covering all interfaces

## Test Execution

```bash
.venv/bin/python -m pytest tests/test_report.py -v
```

Result:
- `test_exit_code_threshold` — PASSED
- `test_json_has_stable_schema_fields` — PASSED
- `test_human_output_states_coverage_explicitly` — PASSED
- `test_human_output_shows_finding_id_and_fixture` — PASSED
- `test_human_output_reports_suppressed_count` — PASSED

Full suite: `.venv/bin/python -m pytest tests/ -v` → **92 passed in 1.85s**

## Coverage Visibility

Both outputs now make coverage (what was evaluated vs. what was not) explicit and actionable.

### Human Report

The human report makes coverage visible in **four distinct ways**:

1. **Status line:** Displays `upstream: <status>` where `<status>` is one of `"ok"`, `"gated"`, `"not_found"`, `"fetch_error"`, `"genuinely_absent"`
   ```
   families run: S, R   upstream: ok
   ```

2. **Families run:** Lists which check families actually executed
   ```
   families run: S, R
   ```

3. **Skipped families:** Explicitly notes families that were **not** run
   ```
   note: R family skipped
   ```

4. **When a user sees a "clean" model:**
   - If no findings exist AND all families ran AND upstream worked: user sees "no findings" (truly clean)
   - If no findings exist BUT upstream="gated" (e.g., proprietary model): user sees:
     ```
     no findings
     0 error, 0 warn, 0 info
     families run: S   upstream: gated
       note: R family skipped
     ```
   This prevents the dangerous "clean" vs. "not evaluated" confusion.

### JSON Report

The JSON structure exposes coverage at the top level in the `"coverage"` object:

```json
{
  "coverage": {
    "upstream": "gated",
    "families_run": ["S"]
  }
}
```

**What a consumer sees when a check could not run:**
- A field-level `coverage` object (always present) that explains *why* findings are missing
- Zero findings in the findings array (clean, not empty because of failure)
- Consumers can distinguish: "no findings because the model is clean" (all families run, upstream="ok") vs. "no findings because we couldn't check" (upstream != "ok" or families_run is incomplete)
- Downstream tools and CI pipelines can now make informed decisions: fail if upstream="fetch_error" (signal retrieval problem) vs. pass if upstream="gated" (signal known limitation)

## Complete JSON Key List (Top-Level)

1. **`schema_version`** — string `"1"` (public contract, immutable)
2. **`tool_version`** — string, ggufdoctor's version from `__version__`
3. **`fixture_corpus_version`** — string `"1"` from CORPUS_VERSION
4. **`generated_at`** — ISO 8601 datetime (UTC)
5. **`target`** — object with:
   - `id` — string, model source filename
   - `architecture` — string or null, model architecture
6. **`engines`** — array of objects, each with:
   - `name` — string (e.g., "jinja2")
   - `version` — string
7. **`coverage`** — object with:
   - `upstream` — string, one of `"ok"`, `"gated"`, `"not_found"`, `"fetch_error"`, `"genuinely_absent"`
   - `families_run` — array of strings (e.g., `["S", "R"]`)
8. **`findings`** — array of finding objects, each with:
   - `id` — string (e.g., "S001")
   - `severity` — string ("error", "warn", or "info")
   - `message` — string
   - `fixture` — string or null, fixture name (added per task brief to surface fixture context for S008 and others)
   - `evidence` — dict or null, check-specific supporting data (e.g., `{"diff": "..."}`, `{"missing": ["token"]}`)
9. **`suppressed`** — array of suppressed finding objects, each with:
   - `id` — string
   - `fixture` — string or null
10. **`summary`** — object with count keys:
    - `error` — integer count
    - `warn` — integer count
    - `info` — integer count

## JSON Serialization

Verified: `json.dumps()` round-trip succeeds on all generated JSON structures, including dictionaries with arbitrary evidence content. Tests confirm this.

## Exit-Code Policy

Three functions implement the exit-code contract:

1. **`exit_code(findings: list[Finding], fail_on: str) -> int`**
   - Returns `1` when any finding's severity is **at or above** the `fail_on` threshold
   - Returns `0` otherwise
   - `fail_on="never"` always returns `0` (no failures ever)
   - Thresholds: `"error"` > `"warn"` > `"info"` (SEVERITY_ORDER from Task 1)

2. **`summarize(findings: list[Finding]) -> dict[str, int]`**
   - Helper used by both human and JSON outputs
   - Returns `{"error": count, "warn": count, "info": count}`

3. **`build_json(...)` and `render_human(...)`**
   - Both consume findings and construct outputs deterministically
   - No I/O, no network, no side effects

## Deviations from Brief

**None.** Implementation follows the brief exactly, including:
- Verbatim JSON schema keys and `schema_version="1"`
- Exact functions and signatures
- All test assertions as written
- All features described (coverage visibility, evidence display, suppressed counts)

## S008 Evidence Handling

**Correction (Fix round 1, see below): this claim was false as originally written.** `_collapse_by_signature` (used by S003 and S008) always constructs
`Finding(..., evidence=evidence)` with `fixture` left at its default of `None`
and the affected fixture names placed in `evidence["fixtures"]` instead. The
`fixture` field does **not** surface which fixture was involved for any
collapsed finding — it is only populated for findings built directly with
`fixture=fx.name` (e.g. S007). `human.py` rendered neither `f.fixture` (always
`None` here) nor `evidence["fixtures"]`, so two unrelated S008 defects on
different fixture pairs rendered as byte-identical lines. Fixed below.

S008 (constant signature check) can collapse multiple unrelated template branches into a single finding if they both render empty. The `fixture` field in the JSON/human outputs now surfaces which fixture was involved:

Example human output:
```
S008  ERROR  template renders to empty string   [common_template]
```

Example JSON:
```json
{"id": "S008", "severity": "error", "message": "...", "fixture": "common_template", "evidence": {...}}
```

This allows downstream tools and users to correlate the finding back to the specific template in the corpus, addressing the "thin evidence" concern.

## What Tasks 11 and 12 Should Know

### Task 11 (CLI Integration)

- **Interfaces are now stable:** `render_human()`, `build_json()`, and `exit_code()` are the complete reporting surface
- **CLI must handle these outputs:**
  1. Call `render_human(model, findings, suppressed, coverage, engines)` → print to stdout
  2. Call `build_json(model, findings, suppressed, coverage, engines)` → serialize and write (or return as needed)
  3. Call `exit_code(findings, fail_on)` → sys.exit() with result
- **The `fail_on` parameter** is passed from CLI args or config; thresholds are `"never"`, `"info"`, `"warn"`, `"error"`
- **Suppressed findings:** Passed as the second list argument to both reporting functions; they appear in JSON but not in counts (only in the "suppressed" array and a note in human output)
- **Engines list:** Pass the actual engine objects (they have `.name` and `.version` attributes); reporting extracts these, no serialization needed

### Task 12 (Survey)

- **JSON schema is immutable:** `schema_version="1"` and all keys listed above are locked; any future version bump requires explicit schema_version increment
- **Coverage field is foundational:** All outputs expose it. **Correction (Fix round 1): the original text claimed this "addresses the credibility risk flagged in the brief." It did not** — `families_run`/`upstream` covered family-level gaps, but per-check gaps (S005/S006 silently returning `[]` when token metadata is missing or out of range) were invisible in both outputs until `Coverage.checks_not_evaluated` was added in Fix round 1 below. That per-check gap was the sharper half of the credibility risk, since it let a check silently no-op while still counting as "run."
- **Fixture field is now part of the contract:** Findings can now be correlated back to their source in the corpus **for findings that set `fixture` directly (e.g. S007). Collapsed findings (S003, S008) instead carry `evidence["fixtures"]`; see the S008 Evidence Handling correction above and the Fix round 1 section below.**
- **All JSON is serializable:** Verified with `json.dumps()` tests
- **Exit code semantics:** `fail_on="never"` always returns 0 (defensive against misconfiguration)
- **Round-trip contract:** The JSON output can be parsed, the findings reconstructed for downstream use (though `Severity` is a str subclass, so JSON parsers will treat severity as a plain string, which is correct)

## Summary

Task 10 is complete. The reporting layer now:
1. Makes coverage visible in both outputs, preventing the dangerous "clean" vs. "not evaluated" ambiguity
2. Surfaces fixture names in both human and JSON outputs for better traceability
3. Provides stable, serializable JSON with locked schema_version="1"
4. Implements exit-code policy correctly per threshold
5. Passes all tests alongside 87 existing tests (92 total)

---

## Fix round 1

Review of `892f9d9` found four problems, three of them in the original design
rather than the transcription. `exit_code` and the overall test count claim
were correct and untouched. Fixed on top of `892f9d9`, no rebase.

### 1. Control-character / ANSI injection in the human report (security)

`render_human` printed `model.source_id`, finding messages, fixture names,
and evidence strings (`diff`, `missing`) verbatim. All of these originate
inside the GGUF file being linted — untrusted input — so a crafted file
could embed `\x1b[2J` (clear screen), `\x1b[31m`, `\x07` (bell), or raw
newlines and have them interpreted by the reader's terminal, up to forging a
fake "no findings" line.

Fix: added `_visible()` in `src/ggufdoctor/report/human.py`, a single regex
(`[\x00-\x1f\x7f]`) that rewrites every C0 control byte and DEL as a visible
`\xHH` escape. Escaping the ESC byte alone is sufficient to defang any ANSI
sequence, since the printable bytes that would otherwise follow it (e.g.
`[2J`) become inert literal text once ESC itself is gone; escaping CR/LF
stops a file from forging extra report lines. Applied to `model.source_id`,
`model.architecture`, `finding.message`, `finding.fixture`,
`evidence["fixtures"]`, `evidence["diff"]` (per line, after `splitlines()`),
and `evidence["missing"]` — i.e. every file-derived string actually rendered
into the human report. **Deliberately not applied in `build_json`**: `json.dumps`
already escapes control characters correctly (as `\u00XX`), and running
`_visible` first would double-escape the backslash, corrupting the
machine-readable value and breaking round-tripping via `json.loads`.

### 2. Headline didn't carry its own caveat

Previously, zero findings under partial coverage (e.g.
`Coverage(upstream="gated", families_run=["S"])`) printed a bare
`no findings`, with the caveats (`upstream: gated`, `note: R family
skipped`) three lines below at equal visual weight — trivially misread by a
skimming human or a naive CI grep for "no findings".

Fix: added `_coverage_caveats()` in `human.py`, which collects skipped
families, non-`"ok"` upstream status, and (new, see #3)
`checks_not_evaluated` into short phrases. When the finding list is empty
and any caveat applies, the headline becomes
`no findings (partial: R family skipped, upstream gated)` (parts joined with
`, `, order: families, upstream, checks). When coverage is fully complete
(`upstream="ok"`, all families run, nothing left unevaluated), the headline
stays the original bare `no findings`. The existing tail lines
(`families run: ...`, `note: ... skipped`) are unchanged and still appear
regardless of finding count.

### 3. Per-check coverage gaps were never recorded (crosses file boundaries)

`s005_eos_mismatch` and `s006_double_bos` return `[]` when they lack the
token metadata needed to evaluate — S005 when `eos_token_id` is `None` or
the vocab is empty; S006 when `add_bos_token` is true but the real BOS
string can't be resolved (missing or out-of-range `bos_token_id`, or no
vocab). The S family still reported as "run" and nothing recorded that
these specific checks silently no-op'd. This reaches across three files:

- `src/ggufdoctor/models.py`: added `Coverage.checks_not_evaluated: list[str]
  = field(default_factory=list)` (existing `Coverage(...)` constructions
  unaffected) and `CheckContext.checks_not_evaluated: list[str] =
  field(default_factory=list)` — a mutable list individual checks append to
  when they bail. `CheckContext` was the necessary bridge: `run_sanity_checks`
  builds `Coverage` in no file today (Task 11/the CLI, which wires checks to
  `Coverage`, doesn't exist yet), so the skip has to be recorded somewhere
  check functions can reach without changing `run_sanity_checks`'s
  `-> list[Finding]` signature, which ~20 existing tests depend on directly.
- `src/ggufdoctor/checks/sanity.py`: `s005_eos_mismatch` appends `"S005"` to
  `ctx.checks_not_evaluated` both when `eos_token_id is None or not
  m.tokens` (silent bail, unchanged) and when `eos_token_id >=
  len(m.tokens)` (still emits its existing "out of range" WARN finding —
  that metadata problem is real and worth flagging on its own — but the
  deeper "does the template emit EOS" comparison genuinely never ran, so
  both the finding and the coverage gap are recorded). `s006_double_bos`
  appends `"S006"` only when `add_bos_token` is true and the resolved BOS
  string is `None`; when `add_bos_token` is false the check correctly
  doesn't apply and nothing is recorded (verified by
  `test_s006_not_recorded_when_add_bos_token_is_false`).
- `src/ggufdoctor/report/human.py` / `report/json_report.py`: surfaced as
  `coverage["checks_not_evaluated"]` in the JSON `coverage` object, as
  `  note: S005 not evaluated` lines in the human tail, and folded into the
  qualified headline from #2.

**New `Coverage` field:** `checks_not_evaluated` (also the JSON key, nested
under `"coverage"`).

### 4. Collapsed findings didn't show their fixture names

`_collapse_by_signature` (used by S003 and S008) builds
`Finding(check_id, severity, message, evidence=evidence)` with `fixture`
left at its dataclass default of `None`, putting the affected fixture names
in `evidence["fixtures"]` instead. `human.py` handled `evidence["diff"]` and
`evidence["missing"]` but never `evidence["fixtures"]`, so two unrelated
S008 defects on different fixture pairs rendered as byte-identical lines —
for a check that collapses on a constant signature, the fixture list is the
only thing that distinguishes them.

Fix: in `human.py`'s finding-line rendering, when `f.fixture` is falsy (the
collapsed case), fall back to `evidence.get("fixtures")` and render the
joined, sanitized names in the same `[...]` bracket position `f.fixture`
would have used.

### Tests

All additions; no existing test body was modified.

- `tests/test_report.py`:
  - `test_human_output_escapes_control_characters_and_ansi` — ESC/BEL/CR/LF
    injected into `source_id`, a message, and a fixture name; asserts the
    raw bytes are absent and their `\xHH` escapes are present.
  - `test_json_output_leaves_control_characters_for_json_dumps` — same
    payload through `build_json`; asserts the raw value survives untouched
    in the dict, and `json.dumps`/`json.loads` round-trips it correctly.
  - `test_headline_is_qualified_when_coverage_is_partial` /
    `test_headline_is_unqualified_when_coverage_is_complete` — zero findings
    under `COV` (gated, S only) vs. a fully-covered `Coverage`.
  - `test_out_of_range_eos_token_id_records_s005_as_not_evaluated` — runs
    `run_sanity_checks` on a model with `eos_token_id=99` against a 3-token
    vocab, confirms `"S005"` lands in `ctx.checks_not_evaluated`, and that a
    `Coverage` built from it produces both the qualified headline and the
    JSON `checks_not_evaluated` key.
  - `test_collapsed_finding_shows_fixture_names_from_evidence` — builds a
    `Finding` the way `_collapse_by_signature` actually does
    (`fixture=None`, `evidence={"fixtures": [...]}`) and asserts both names
    appear in the human output.
- `tests/test_checks_sanity.py`:
  - `test_s005_records_not_evaluated_when_eos_id_missing`
  - `test_s005_records_not_evaluated_when_eos_id_out_of_range` — also
    confirms the WARN finding is still emitted alongside the coverage
    record.
  - `test_s006_records_not_evaluated_when_bos_id_missing`
  - `test_s006_not_recorded_when_add_bos_token_is_false` — guards against
    over-recording on the legitimate no-op path.

Full suite: `.venv/bin/python -m pytest tests/ -v` → **102 passed** (92
existing + 10 new).

### Concerns / follow-ups for later tasks

- `run_sanity_checks` still returns only `list[Finding]`; the new
  `ctx.checks_not_evaluated` has to be read off the `CheckContext` after the
  call. Whoever writes Task 11 (CLI integration, not yet built) needs to
  construct `Coverage(..., checks_not_evaluated=ctx.checks_not_evaluated)`
  explicitly — it is not automatic. This was the least invasive option
  given `run_sanity_checks`'s signature is depended on by ~20 existing
  tests, but it does mean the wiring is easy to forget.
- `_real_token`'s and `s005`'s range checks don't treat a negative
  `bos_token_id`/`eos_token_id` as out-of-range on the low end for S005
  specifically (`s006` is fine via `_real_token`'s `0 <= token_id <
  len(m.tokens)` bound, but `s005`'s own inline check is
  `eos_token_id >= len(m.tokens)` only, so a negative id would fall through
  to `m.tokens[m.eos_token_id]` and silently wrap via Python's negative
  indexing). Out of scope for this fix round (not raised by review), but
  worth a look if S005 gets touched again.

---

## Fix round 2

Took the negative-id gap flagged above rather than leaving it. Confirmed:
with `eos_token_id=-1` and a 3-token vocab, `s005_eos_mismatch` returned
`[]` with no WARN — the guard `eos_token_id >= len(m.tokens)` lets a
negative id through, and `_real_token`'s `0 <= id < len` bound (used
elsewhere, not by S005's own inline check) played no role here since S005
doesn't call it before this point. The check was "safe" only by accident,
and worse, `checks_not_evaluated` reported S005 as merely "not evaluated,"
implying a missing id rather than a corrupt one.

Fix: changed the guard in `src/ggufdoctor/checks/sanity.py` from
`if m.eos_token_id >= len(m.tokens):` to
`if not (0 <= m.eos_token_id < len(m.tokens)):`. A negative id now takes
the same out-of-range WARN path a too-large id already did — same finding
id, severity, and message — and still appends `"S005"` to
`ctx.checks_not_evaluated`, per the round 1 decision that the bad-metadata
finding and the never-ran coverage fact are both true and independently
worth recording.

Added `test_s005_negative_eos_id_takes_the_out_of_range_warn_path` in
`tests/test_checks_sanity.py` (`eos_token_id=-1`), asserting the WARN
finding's id/severity/message and the coverage record. Required importing
`Severity` into that test module. No other test changed.

Full suite: `.venv/bin/python -m pytest tests/ -v` → **103 passed** (102 +
1 new).
