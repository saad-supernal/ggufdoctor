from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.models import Coverage, Finding, GgufModel, Severity
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code

MODEL = GgufModel(source_id="m.gguf", architecture="llama")
COV = Coverage(upstream="gated", families_run=["S"])


def test_exit_code_threshold():
    warn = [Finding("R001", Severity.WARN, "m")]
    err = [Finding("S004", Severity.ERROR, "m")]
    assert exit_code(warn, "error") == 0
    assert exit_code(warn, "warn") == 1
    assert exit_code(err, "error") == 1
    assert exit_code(err, "never") == 0
    assert exit_code([], "info") == 0


def test_json_has_stable_schema_fields():
    d = build_json(MODEL, [Finding("S004", Severity.ERROR, "m")], [], COV,
                   [Jinja2Engine()])
    assert d["schema_version"] == "1"
    assert d["target"]["id"] == "m.gguf"
    assert d["coverage"]["upstream"] == "gated"
    assert d["summary"] == {"error": 1, "warn": 0, "info": 0}
    assert d["engines"][0]["name"] == "jinja2"
    assert d["fixture_corpus_version"] == "1"


def test_human_output_states_coverage_explicitly():
    out = render_human(MODEL, [], [], COV, [Jinja2Engine()])
    assert "gated" in out
    assert "R family skipped" in out or "families run: S" in out


def test_human_output_shows_finding_id_and_fixture():
    f = Finding("R001", Severity.WARN, "differs", fixture="with_tools",
                evidence={"diff": "-a\n+b"})
    out = render_human(MODEL, [f], [], COV, [Jinja2Engine()])
    assert "R001" in out
    assert "with_tools" in out
    assert "+b" in out


def test_human_output_reports_suppressed_count():
    sup = [Finding("R001", Severity.WARN, "m", fixture="user_only")]
    out = render_human(MODEL, [], sup, COV, [Jinja2Engine()])
    assert "1 suppressed" in out
