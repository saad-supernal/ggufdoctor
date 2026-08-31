from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

A = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
B = "{% for m in messages %}{{ m['content'] }}{% endfor %}Y"


def ctx(gguf_tpl, upstream_tpl, meta=None):
    return CheckContext(
        model=GgufModel(source_id="t", architecture="llama", chat_template=gguf_tpl),
        engines=[Jinja2Engine()], fixtures=load_fixtures(),
        upstream_template=upstream_tpl, upstream_meta=meta or {})


def by_id(findings):
    return {f.id: f for f in findings}


def test_r001_flags_differing_output():
    f = by_id(run_reference_checks(ctx(A, B)))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN


def test_r001_silent_when_output_matches():
    assert run_reference_checks(ctx(A, A)) == []


def test_r001_silent_on_cosmetic_source_difference():
    # different source, identical rendered output
    same_output = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
    spaced = "{% for m in messages %}{{   m['content']   }}{% endfor %}X"
    assert run_reference_checks(ctx(spaced, same_output)) == []


def test_r002_downgrades_annotated_intentional_patch():
    annotated = "{# Unsloth chat template fixes #}" + B
    f = by_id(run_reference_checks(ctx(annotated, A)))
    assert "R002" in f
    assert f["R001"].severity == Severity.INFO


def test_r003_reports_dead_upstream():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "not_found"})))
    assert "R003" in f


def test_r003_not_reported_when_gated():
    f = by_id(run_reference_checks(ctx(A, None, {"coverage": "gated"})))
    assert "R003" not in f


def test_r004_flags_upstream_modified_after_publication():
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-06-01T00:00:00Z",
        "gguf_modified": "2026-01-01T00:00:00Z"})))
    assert "R004" in f
