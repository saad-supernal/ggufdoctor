import pytest

from ggufdoctor.ignorefile import load_ignores, apply_ignores, IgnoreRule
from ggufdoctor.models import Finding, Severity


def test_parses_rule_with_reason(tmp_path):
    p = tmp_path / ".ggufdoctorignore"
    p.write_text("R001 with_tools # upstream is wrong, ours is the fix\n")
    rules = load_ignores(str(p))
    assert rules == [IgnoreRule(id="R001", fixture="with_tools",
                                reason="upstream is wrong, ours is the fix")]


def test_rule_without_fixture_matches_any(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005 # eos handled by runtime\n")
    rules = load_ignores(str(p))
    assert rules[0].fixture is None


def test_rule_without_reason_is_rejected(tmp_path):
    p = tmp_path / "i"
    p.write_text("S005\n")
    with pytest.raises(ValueError, match="reason"):
        load_ignores(str(p))


def test_comments_and_blank_lines_skipped(tmp_path):
    p = tmp_path / "i"
    p.write_text("# header\n\nS005 # why\n")
    assert len(load_ignores(str(p))) == 1


def test_apply_splits_kept_and_suppressed():
    findings = [Finding("R001", Severity.WARN, "m", fixture="with_tools"),
                Finding("R001", Severity.WARN, "m", fixture="user_only"),
                Finding("S004", Severity.ERROR, "m")]
    rules = [IgnoreRule("R001", "with_tools", "known")]
    kept, suppressed = apply_ignores(findings, rules)
    assert len(kept) == 2
    assert len(suppressed) == 1
    assert suppressed[0].fixture == "with_tools"


def test_missing_file_yields_no_rules():
    assert load_ignores("/nonexistent/path") == []
