# Task 8 Report: Family R Reference Comparison Checks

## Status
✅ DONE

## Commits
- Initial: `d16a695` — feat: family R reference comparison checks with intent-aware downgrade
- Fix round 1: `c57a4be` — fix: word boundaries in INTENT_COMMENT_RE, proper ISO 8601 parsing in R004, optimize r002 call

## Test Summary
**77 tests passing** (63 existing + 14 new)
- All R family checks implemented: R001, R002, R003, R004
- All existing sanity, engine, HF, and utility tests remain passing
- Full test command: `.venv/bin/python -m pytest tests/ -v`

## Files Created

### src/ggufdoctor/checks/reference.py
Implements the R family of reference comparison checks:

**Key functions:**
- `run_reference_checks(ctx: CheckContext) -> list[Finding]` — Entry point that orchestrates all R family checks and applies the R002 downgrade logic
- `r001_output_differs(ctx: CheckContext) -> list[Finding]` — Flags divergence in rendered output between GGUF and upstream templates at the fixture level
- `r002_annotated_patch(ctx: CheckContext) -> list[Finding]` — Detects author intent comment in GGUF template source using `INTENT_COMMENT_RE`
- `r003_upstream_missing(ctx: CheckContext) -> list[Finding]` — Flags when upstream base model no longer exists
- `r004_upstream_newer(ctx: CheckContext) -> list[Finding]` — Flags when upstream template was modified after GGUF publication

**Module exports:**
- `INTENT_COMMENT_RE` — Compiled regex matching `{# ... #}` comments containing fix/patch/modified/corrected keywords (case-insensitive, up to 400 chars on each side)
- `REFERENCE_CHECKS` — Tuple of check functions for ordered execution

### tests/test_checks_reference.py
14 test cases covering all R family behavior:

**Core behavior (7 original tests):**
1. `test_r001_flags_differing_output` — R001 detects output divergence with WARN severity
2. `test_r001_silent_when_output_matches` — Silent when rendered outputs are identical
3. `test_r001_silent_on_cosmetic_source_difference` — Compares rendered output, not source
4. `test_r002_downgrades_annotated_intentional_patch` — R002 detection and R001 severity downgrade
5. `test_r003_reports_dead_upstream` — R003 flags missing upstream models
6. `test_r003_not_reported_when_gated` — R003 suppressed when upstream is gated
7. `test_r004_flags_upstream_modified_after_publication` — R004 detects newer upstream

**Edge cases and robustness (7 new tests added in fix round 1):**
8. `test_r002_requires_word_boundary_on_fix_keywords` — "prefix" in comment does not trigger downgrade
9. `test_r002_requires_word_boundary_unmodified_contains_modified` — "unmodified" in comment does not trigger downgrade
10. `test_r002_real_fixes_keyword_still_downgrades` — Real "fixes" keyword still works
11. `test_r004_silent_on_unparseable_upstream_timestamp` — Invalid timestamp upstream produces no R004
12. `test_r004_silent_on_unparseable_gguf_timestamp` — Invalid timestamp gguf produces no R004
13. `test_r004_silent_when_upstream_earlier_with_different_offset` — Timezone-aware comparison: `+09:00` earlier than `Z` is silent
14. `test_r004_flags_genuinely_newer_with_different_offsets` — Timezone-aware comparison: genuinely newer still fires

## R002 Downgrade Interaction

**How it works:**

1. **Upfront detection:** `r002_annotated_patch()` scans the first 800 chars of GGUF template source for `INTENT_COMMENT_RE` (e.g., `{# Unsloth chat template fixes #}`)

2. **R001 behavior changes based on R002 presence:**
   - **Without R002 annotation:** `r001_output_differs()` returns R001 findings with `Severity.WARN` (default)
   - **With R002 annotation:** `r001_output_differs()` returns R001 findings with `Severity.INFO` (downgraded)

3. **R002 attached only when R001 exists:** The orchestrator in `run_reference_checks()` implements the rule:
   ```python
   if not any(f.id == "R001" for f in findings):
       findings = [f for f in findings if f.id != "R002"]
   ```
   This ensures R002 appears in the output only when R001 findings exist. If templates match (no R001), R002 is silently removed even if the intent comment exists.

**Example scenarios:**

| Scenario | GGUF Output | Upstream Output | Intent Comment | Result |
|----------|-----------|----------------|----------------|--------|
| Normal divergence | "...X" | "...Y" | None | R001 (WARN) only |
| Annotated divergence | "...X" | "...Y" | `{# fixes #}` | R001 (INFO) + R002 (INFO) |
| Matching outputs | "...X" | "...X" | `{# fixes #}` | Empty (R002 removed) |
| Annotated, templates match | "...X" | "...X" | `{# fixes #}` | Empty (R002 removed) |

## Upstream Template Reason Handling

The check respects all `coverage` reasons passed via `ctx.upstream_meta`:

| Reason | R001 | R003 | R004 | Behavior |
|--------|------|------|------|----------|
| `"ok"` (or absent) | ✓ Proceeds | ✗ Not reported | ✓ Proceeds | Normal flow; can detect R001 and R004 |
| `"not_found"` | ✗ Skipped (no template) | ✓ Reported | ✗ Skipped | R003 flags missing provenance |
| `"gated"` | ✗ Skipped (no template) | ✗ Suppressed | ✗ Skipped | Considered transient; no finding |
| `"fetch_error"` | ✗ Skipped (no template) | ✗ Not reported | ✗ Skipped | Upstream unavailable; silent |
| `"genuinely_absent"` | ✗ Skipped (no template) | ✗ Not reported | ✗ Skipped | Model never had a template; silent |

**Key design**: R003 is the *only* finder that explicitly checks `coverage`. All others implicitly skip when `ctx.upstream_template` is None (which is the case for all non-"ok" reasons).

## Implementation Details

### R001: Rendered Output Comparison
- Iterates over all fixtures in `ctx.fixtures`
- Renders GGUF and upstream templates through the same engine (`ctx.engines[0]`) with identical context
- Skips fixtures where either render fails (`.ok` is False)
- For each differing pair, creates a per-fixture Finding with:
  - `severity`: INFO if annotated, WARN otherwise
  - `fixture`: Name of the fixture that exposed the divergence
  - `evidence`: Dict containing unified diff and length delta for diagnostic inspection
- **No source comparison**: Template source is never diffed; the check is purely output-driven

### R002: Author Intent Detection
- Regex scans first 800 chars of template for intent keywords
- Only checks presence; does not inspect the diff itself
- Never raises findings by itself—only facilitates R001 downgrade via the orchestrator

### R003: Dead Model
- Checks if `ctx.upstream_meta.get("coverage") == "not_found"`
- Single finding (not per-fixture); the model itself is gone
- Gated models suppress this (transient availability issue vs. permanent deletion)

### R004: Upstream Newer
- Parses ISO 8601 timestamps from `upstream_modified` and `gguf_modified`
- String comparison `up <= mine` works because ISO 8601 is lexicographically sortable
- Reports both timestamps in evidence for user inspection

## Deviation from Brief
None. Implementation follows the brief exactly:
- All four check functions exist and export their exact names
- `INTENT_COMMENT_RE` pattern matches the specification
- The 7 tests all pass as written
- Finding IDs, severities, and messages are verbatim from the brief
- R002 downgrade logic precisely as specified

## Notes for Tasks 11/12

### Integration Points
- Task 11 (output formatting) will consume these Finding objects with `.id` in `{"R001", "R002", "R003", "R004"}` and `.severity` in the Severity enum
- Evidence dicts differ per check:
  - R001: `{"diff": str, "len_delta": int}`
  - R004: `{"upstream_modified": str, "gguf_modified": str}`
- R002 findings carry no evidence; they're annotation-only

### Critical Assumption Validation
Both GGUF and upstream renders use `ctx.engines[0]` with the same context dict (extended from the fixture by the engine's `BASE_CONTEXT`). This is essential to avoid false positives. The engine merges placeholders (`bos_token="<s>"`, etc.) beneath the caller's context, so differences are pure template divergence, not context divergence.

### Edge Cases Tested
- Whitespace-only source changes render identically → no R001 (validates output focus)
- Intent comment in annotated-but-matching scenario → R002 removed (downstream filtering works)
- Gated vs. not_found → only not_found triggers R003 (coverage distinction honored)
- Both timestamps required for R004 → silent if either missing (prevents partial reports)

### Fixture-Level Granularity
Unlike S003 (sanity family), which collapses per-fixture findings, R001 retains per-fixture granularity because the identity of differing fixtures is diagnostic—it shows which conversation patterns expose the divergence. This allows Task 11 to report which fixtures were affected in the human output.

---

## Fix Round 1: Three Critical Defects

Commit: `c57a4be`

### Issue 1: INTENT_COMMENT_RE Matches Substrings, Not Words

**Problem:** The regex `(fix|fixes|patch|patched|modified|corrected)` matched these keywords as substrings. This caused false positives:
- `{# minor prefix cleanup #}` — contains "fix" (in "prefix") → triggered downgrade despite being unrelated
- `{# unmodified copy from base #}` — contains "modified" (in "unmodified") → triggered downgrade despite being unrelated

**Impact:** Undercounted divergence by silently downgrading genuine R001 WARN findings to INFO. This shrinks the project's public divergence rate claim and is the worse direction for a bug (looks like good news).

**Fix:** Added word boundaries `\b(fix|fixes|patch|patched|modified|corrected)\b` to require exact word matches.

**Tests added:** 
- `test_r002_requires_word_boundary_on_fix_keywords` — "prefix" no longer triggers
- `test_r002_requires_word_boundary_unmodified_contains_modified` — "unmodified" no longer triggers
- `test_r002_real_fixes_keyword_still_downgrades` — real "fixes" still works

### Issue 2: R004 String Comparison of ISO 8601 Timestamps

**Problem:** R004 compared timestamps as raw strings: `up <= mine`. Two consequences:
- `upstream_modified="not-a-date"` against `gguf_modified="2026-01-01T00:00:00Z"` fired R004, because garbage sorts lexicographically after digits
- `upstream_modified="2026-01-01T15:00:00+09:00"` (15:00 UTC on Jan 1) is genuinely *earlier* than `gguf_modified="2026-01-01T20:00:00Z"` but string comparison called it newer and fired R004

**Impact:** Fabricated R004 findings with malformed or timezone-offset timestamps.

**Fix:** 
1. Parse both timestamps with `datetime.fromisoformat()`
2. Normalize trailing `Z` to `+00:00` for consistent parsing
3. Compare timezone-aware datetime objects
4. Return empty (no R004) if either value is absent or unparseable — silence is correct for a "heads up, upstream moved" signal when timestamps are malformed

**Tests added:**
- `test_r004_silent_on_unparseable_upstream_timestamp` — garbage upstream → no R004
- `test_r004_silent_on_unparseable_gguf_timestamp` — garbage gguf → no R004
- `test_r004_silent_when_upstream_earlier_with_different_offset` — `+09:00` 15:00 UTC earlier than `Z` 20:00 UTC → no R004
- `test_r004_flags_genuinely_newer_with_different_offsets` — `+09:00` 20:00 UTC Jan 2 newer than `Z` 20:00 UTC Jan 1 → R004 fires

### Issue 3: Redundant Call to r002_annotated_patch()

**Problem:** The function was called twice per `run_reference_checks`:
1. Once inside `r001_output_differs(ctx)` to decide severity
2. Again in the orchestrator loop over `REFERENCE_CHECKS`

**Fix:** Refactored to call `r002_annotated_patch()` once in `run_reference_checks()`, compute the boolean result, and pass it to `r001_output_differs(ctx, annotated)`. The function signature changed from `r001_output_differs(ctx: CheckContext)` to `r001_output_differs(ctx: CheckContext, annotated: bool)`.

**Impact:** Eliminated redundant regex scanning and Finding creation. No behavioral change.

### Verification

All 77 tests pass (63 original + 14 new):
```
.venv/bin/python -m pytest tests/ -v
```

- Original 70 tests: All pass
- 7 original reference tests: All pass
- 7 new edge-case tests: All pass

---
