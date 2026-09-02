# Task 9: Ignore File — Implementation Report

## Status
DONE

## Commit
SHA: `430f893` ("feat: ignore file requiring a recorded reason")

## Files Created
- `src/ggufdoctor/ignorefile.py` (47 lines) — Core implementation
- `tests/test_ignorefile.py` (60 lines) — Test suite

## Implementation Summary

### Interfaces Delivered

**`IgnoreRule` dataclass**
```python
@dataclass(frozen=True)
class IgnoreRule:
    id: str
    fixture: str | None
    reason: str
```
Frozen to ensure rules are immutable after creation. All three fields are required on construction.

**`load_ignores(path: str) -> list[IgnoreRule]`**
- Reads a file line-by-line in the format: `ID [fixture] # reason`
- Returns an empty list if the file does not exist (graceful fallback, not an error)
- Blank lines and lines starting with `#` are skipped
- Parses the line as: `head # reason` where `head` contains the ID and optional fixture, separated by whitespace

**`apply_ignores(findings, rules) -> tuple[list[Finding], list[Finding]]`**
- Returns `(kept, suppressed)` tuple
- A finding is suppressed if:
  - Its `id` matches a rule's `id`, AND
  - The rule has `fixture=None` (matches any fixture), OR the rule's `fixture` matches the finding's `fixture` exactly

### Initial Test Results (after Step 5)
6 ignorefile tests passed:
```
tests/test_ignorefile.py::test_parses_rule_with_reason PASSED
tests/test_ignorefile.py::test_rule_without_fixture_matches_any PASSED
tests/test_ignorefile.py::test_rule_without_reason_is_rejected PASSED
tests/test_ignorefile.py::test_comments_and_blank_lines_skipped PASSED
tests/test_ignorefile.py::test_apply_splits_kept_and_suppressed PASSED
tests/test_ignorefile.py::test_missing_file_yields_no_rules PASSED
```
All 83 tests passed (77 existing + 6 new = 83, no regressions)

## Handling of Malformed Lines

**Rule without a reason (no `#` marker):** Raises `ValueError` with message format `"{path}:{lineno}: ignore rules require a reason after '#': {line_text}"`. This is deliberate and necessary because:
- The design requirement is that a reason must be recorded — no reason means the user intent cannot be preserved
- Silently skipping such a line would violate the design principle: "an ignore list without reasons decays into a way of hiding problems"
- The error is raised during parsing, preventing silent data loss
- The offending line text is quoted in the error message for actionability

**Missing file:** Returns `[]` (empty list). This is not an error — an absent ignore file is equivalent to no ignores.

## Fixture-Scoped Rule Interaction with Collapsed Findings

Task 6's fix round produces **collapsed findings**: a single `Finding` with `fixture=None` and `evidence["fixtures"]` listing the fixtures that share the same failure signature. For example, S003 may produce one finding covering both `with_tools` and `user_only` fixtures.

The matching logic in `apply_ignores` now handles both normal and collapsed findings:

**Normal findings** (fixture is not `None`):
- A rule with `fixture="with_tools"` matches a finding with `fixture="with_tools"` (exact match)
- A rule with `fixture=None` matches any finding (regardless of its fixture value)

**Collapsed findings** (fixture is `None` with `evidence["fixtures"]` list):
- A rule with `fixture="with_tools"` matches **only if** `evidence["fixtures"] == ["with_tools"]` — i.e., exactly one fixture in the list
- A rule with `fixture=None` always matches (suppresses the entire collapsed finding)
- A scoped rule does NOT match a collapsed finding spanning multiple fixtures. This is intentional: a single finding cannot be half-suppressed; the user must express intent clearly. If the user writes `S003 with_tools`, they are saying "S003 in with_tools is OK" — but a collapsed S003 spanning both `with_tools` and `user_only` is not a per-fixture concern, so the un-scoped rule `S003` is the honest form.

**Findings without fixture or evidence** (neither `fixture` nor `evidence["fixtures"]`):
- Only un-scoped rules match them

## Deviations from Brief
Initial brief was correct but predated Task 6's fix round. Fix round 1 (below) addresses collapsed findings handling introduced by Task 6.

---

## Fix Round 1: Collapsed Findings Support

**Commit:** `c88a10d` ("fix(task-9): handle collapsed findings and quote parse errors")

**Changes:**
1. Updated `apply_ignores` to detect and handle collapsed findings (fixture=None with evidence["fixtures"])
2. Scoped rules now match collapsed findings only when evidence contains exactly the named fixture
3. Multi-fixture collapsed findings only suppressible by un-scoped rules
4. Error messages from `load_ignores` now quote the offending line text
5. Removed unreachable dead code branch (`if not parts` check)

**Test additions (4 new tests):**
- `test_collapsed_finding_single_fixture_matches_scoped_rule` — scoped rule suppresses single-fixture collapsed finding
- `test_collapsed_finding_multiple_fixtures_not_matched_by_scoped_rule` — scoped rule does NOT suppress multi-fixture collapsed finding
- `test_collapsed_finding_multiple_fixtures_matched_by_unscoped_rule` — un-scoped rule suppresses multi-fixture collapsed finding
- `test_rule_without_reason_error_includes_line_text` — error message quotes the line

**All 87 tests pass** (77 existing + 10 ignorefile tests, including 4 new Fix round 1 tests).

---

## Information for Task 11

**How to call `load_ignores` and `apply_ignores`:**

1. `load_ignores(path)` expects an absolute or relative file path. It performs the only file I/O in this module. Pass any path; missing files are safe (returns `[]`). A malformed file (rule without reason) will raise `ValueError` with path, line number, and the actual offending line text for user-facing error messages.

2. `apply_ignores(findings, rules)` is a pure function with no side effects. Pass it a list of `Finding` objects and a list of `IgnoreRule` objects (from `load_ignores`). The return value is a tuple; unpack it as `kept, suppressed = apply_ignores(findings, rules)`.

3. **Fixture matching rules:** A scoped rule (e.g., `S003 with_tools`) suppresses:
   - A normal finding with `fixture="with_tools"` (exact match)
   - A collapsed finding with `fixture=None` and `evidence["fixtures"]=["with_tools"]` (single fixture)
   - **NOT** a collapsed finding with `evidence["fixtures"]=["with_tools", "user_only"]` (multiple fixtures)

   An un-scoped rule (e.g., `S003`) suppresses any finding with matching ID, regardless of fixture or evidence.

4. A collapsed finding spanning multiple fixtures cannot be partially suppressed. The honest form is the un-scoped rule. A user cannot write `S003 with_tools` to suppress only that part of a multi-fixture issue — they must choose to suppress the entire collapsed finding (`S003`) or none of it. This prevents silent data hiding.

5. The `reason` field on `IgnoreRule` is informational only — it is stored but not used in matching or suppression logic. Task 11 may use it for user-facing output (e.g., "S001 with_tools (skipped: upstream is wrong, ours is the fix)").

6. Error handling: `load_ignores` raises `ValueError` on malformed input. `apply_ignores` does not raise (it is a pure filter). Callers should catch and handle `ValueError` from `load_ignores` during file parsing, not during application.
