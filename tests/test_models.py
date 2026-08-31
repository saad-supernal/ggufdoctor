from ggufdoctor.models import Severity, Finding, RenderResult, Coverage


def test_severity_is_string_valued():
    assert Severity.ERROR.value == "error"
    assert Severity.WARN.value == "warn"
    assert Severity.INFO.value == "info"


def test_finding_defaults_are_independent():
    a = Finding(id="S001", severity=Severity.ERROR, message="x")
    b = Finding(id="S002", severity=Severity.WARN, message="y")
    a.evidence["k"] = 1
    assert b.evidence == {}, "mutable default leaked between instances"


def test_render_result_ok_reflects_error():
    assert RenderResult(text="hi", error=None).ok is True
    assert RenderResult(text=None, error="render:ValueError").ok is False


def test_coverage_records_families_run():
    c = Coverage(upstream="gated", families_run=["S"])
    assert c.upstream == "gated"
    assert c.families_run == ["S"]
