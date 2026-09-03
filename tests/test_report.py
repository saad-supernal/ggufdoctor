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
    # Task 4 (corpus v2): fixture_corpus_version mirrors
    # ggufdoctor.fixtures.CORPUS_VERSION, bumped to "2" for the new
    # extended-tier fixtures (tool_roundtrip, typed_content,
    # no_generation_prompt).
    assert d["fixture_corpus_version"] == "2"


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


# --- Fix round 1 ---

CONTROL_PAYLOAD = "\x1b[2Jcleared\x07\x1b[31mred\nnewline"


def test_human_output_escapes_control_characters_and_ansi():
    model = GgufModel(source_id=f"m{CONTROL_PAYLOAD}.gguf", architecture="llama")
    f = Finding("S004", Severity.ERROR, f"bad {CONTROL_PAYLOAD} message",
               fixture=f"fixture{CONTROL_PAYLOAD}")
    out = render_human(model, [f], [], COV, [Jinja2Engine()])
    # None of the raw control bytes survive into the rendered text.
    assert "\x1b" not in out
    assert "\x07" not in out
    # But their presence is still visible, not silently dropped.
    assert "\\x1b" in out
    assert "\\x07" in out
    assert "\\x0a" in out  # the embedded newline is escaped too
    assert "cleared" in out and "red" in out and "newline" in out


def test_json_output_leaves_control_characters_for_json_dumps():
    import json

    model = GgufModel(source_id=f"m{CONTROL_PAYLOAD}.gguf", architecture="llama")
    f = Finding("S004", Severity.ERROR, f"bad {CONTROL_PAYLOAD} message")
    d = build_json(model, [f], [], COV, [Jinja2Engine()])
    # build_json must not pre-escape -- it hands raw strings to the caller,
    # who is expected to serialise with json.dumps().
    assert d["target"]["id"] == f"m{CONTROL_PAYLOAD}.gguf"
    assert d["findings"][0]["message"] == f"bad {CONTROL_PAYLOAD} message"
    # json.dumps() escapes them correctly on its own.
    dumped = json.dumps(d)
    assert "\x1b" not in dumped
    assert "\\u001b" in dumped
    # And the round trip recovers the original raw value.
    assert json.loads(dumped)["target"]["id"] == f"m{CONTROL_PAYLOAD}.gguf"


def test_headline_is_qualified_when_coverage_is_partial():
    out = render_human(MODEL, [], [], COV, [Jinja2Engine()])
    assert "no findings (partial:" in out
    assert "R family skipped" in out
    assert "upstream gated" in out


def test_headline_is_unqualified_when_coverage_is_complete():
    full = Coverage(upstream="ok", families_run=["S", "R"])
    out = render_human(MODEL, [], [], full, [Jinja2Engine()])
    lines = out.splitlines()
    assert "  no findings" in lines
    assert not any("no findings (partial" in line for line in lines)


def test_out_of_range_eos_token_id_records_s005_as_not_evaluated():
    from ggufdoctor.checks.sanity import run_sanity_checks
    from ggufdoctor.engines.jinja2_engine import Jinja2Engine as Engine
    from ggufdoctor.fixtures import load_fixtures
    from ggufdoctor.models import CheckContext

    model = GgufModel(source_id="m.gguf", architecture="llama",
                      chat_template="{% for m in messages %}{{ m['content'] }}{% endfor %}",
                      tokens=["<unk>", "<s>", "</s>"], eos_token_id=99,
                      # Isolates this test to S005's own coverage gap --
                      # add_bos_token=False keeps S006 from also recording
                      # itself as not-evaluated (it correctly no-ops instead,
                      # since metadata confidently says no BOS is added).
                      add_bos_token=False)
    ctx = CheckContext(model=model, engines=[Engine()], fixtures=load_fixtures())
    run_sanity_checks(ctx)
    assert "S005" in ctx.checks_not_evaluated

    coverage = Coverage(upstream="ok", families_run=["S", "R"],
                        checks_not_evaluated=ctx.checks_not_evaluated)
    human = render_human(model, [], [], coverage, [Jinja2Engine()])
    assert "S005 not evaluated" in human
    assert "no findings (partial: S005 not evaluated)" in human

    d = build_json(model, [], [], coverage, [Jinja2Engine()])
    assert d["coverage"]["checks_not_evaluated"] == ["S005"]


def test_collapsed_finding_shows_fixture_names_from_evidence():
    f = Finding("S008", Severity.ERROR, "template renders to empty output",
               fixture=None, evidence={"fixtures": ["fixture_a", "fixture_b"]})
    out = render_human(MODEL, [f], [], COV, [Jinja2Engine()])
    assert "fixture_a" in out
    assert "fixture_b" in out
