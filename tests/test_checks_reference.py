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


def test_r002_requires_word_boundary_on_fix_keywords():
    # "prefix" contains "fix" but is not the keyword; should not downgrade
    not_annotated = "{# minor prefix cleanup #}" + B
    f = by_id(run_reference_checks(ctx(not_annotated, A)))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN
    assert "R002" not in f


def test_r002_requires_word_boundary_unmodified_contains_modified():
    # "unmodified" contains "modified" but is not the keyword; should not downgrade
    not_annotated = "{# unmodified copy from base #}" + B
    f = by_id(run_reference_checks(ctx(not_annotated, A)))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN
    assert "R002" not in f


def test_r002_real_fixes_keyword_still_downgrades():
    # Real fix keyword should still downgrade
    annotated = "{# fixes the tool-call role #}" + B
    f = by_id(run_reference_checks(ctx(annotated, A)))
    assert "R001" in f
    assert "R002" in f
    assert f["R001"].severity == Severity.INFO


def test_r004_silent_on_unparseable_upstream_timestamp():
    # not-a-date in upstream timestamp produces no R004
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "not-a-date",
        "gguf_modified": "2026-01-01T00:00:00Z"})))
    assert "R004" not in f


def test_r004_silent_on_unparseable_gguf_timestamp():
    # not-a-date in gguf timestamp produces no R004
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-06-01T00:00:00Z",
        "gguf_modified": "not-a-date"})))
    assert "R004" not in f


def test_r004_silent_when_upstream_earlier_with_different_offset():
    # upstream +09:00 at 15:00 UTC on Jan 1 is earlier than GGUF Z at 20:00 UTC on Jan 1
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-01-01T15:00:00+09:00",
        "gguf_modified": "2026-01-01T20:00:00Z"})))
    assert "R004" not in f


def test_r004_flags_genuinely_newer_with_different_offsets():
    # upstream +09:00 at 20:00 UTC on Jan 2 is genuinely newer
    f = by_id(run_reference_checks(ctx(A, A, {
        "upstream_modified": "2026-01-02T20:00:00+09:00",
        "gguf_modified": "2026-01-01T20:00:00Z"})))
    assert "R004" in f
