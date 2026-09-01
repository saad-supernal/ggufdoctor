from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

A = "{% for m in messages %}{{ m['content'] }}{% endfor %}X"
B = "{% for m in messages %}{{ m['content'] }}{% endfor %}Y"


def ctx(gguf_tpl, upstream_tpl, meta=None, **model_kw):
    return CheckContext(
        model=GgufModel(source_id="t", architecture="llama", chat_template=gguf_tpl,
                        **model_kw),
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


# --- Fix round 3 (final whole-branch review): R001 must reason about the
# model's real bos/eos tokens on both sides, and must separate a
# whitespace-only divergence from one that changes the prompt's content. ---

def test_r001_uses_real_eos_token_not_fabricated_placeholder():
    # A GGUF that inlines the model's real EOS where upstream still writes
    # {{ eos_token }} is the commonest engine-compatibility rewrite there
    # is. Rendering both sides with the engine's fabricated BASE_CONTEXT
    # placeholder ("</s>") made this diverge on every fixture despite being
    # behaviourally identical -- a live false-positive generator.
    gguf_tpl = "hello<|eot_id|>"
    upstream_tpl = "hello{{ eos_token }}"
    c = ctx(gguf_tpl, upstream_tpl, tokens=["<unk>", "<|eot_id|>"], eos_token_id=1)
    assert run_reference_checks(c) == []


def test_r001_still_flags_a_genuine_eos_divergence():
    # Guard against the fix above going too far: if the GGUF's literal
    # token genuinely differs from the model's real EOS, that's still a
    # real divergence and must still be flagged.
    gguf_tpl = "hello</s>"
    upstream_tpl = "hello{{ eos_token }}"
    c = ctx(gguf_tpl, upstream_tpl, tokens=["<unk>", "<|eot_id|>"], eos_token_id=1)
    f = by_id(run_reference_checks(c))
    assert "R001" in f
    assert f["R001"].severity == Severity.WARN


def test_r001_separates_whitespace_only_divergence_from_content_divergence():
    # TheBloke/Mistral-7B-Instruct-v0.2-GGUF-style divergence: the GGUF's
    # template has a single space where upstream doesn't
    # ("<s> [INST]" vs "<s>[INST]") -- a different claim from a divergence
    # that changes the prompt's content, per design spec section 5's
    # "whitespace-only differences are always separated from semantic
    # differences". Reported at INFO, not silenced and not called
    # equivalent -- the diff evidence still shows exactly what changed.
    gguf_tpl = "<s> [INST] {{ messages[0]['content'] }} [/INST]"
    upstream_tpl = "<s>[INST] {{ messages[0]['content'] }} [/INST]"
    f = run_reference_checks(ctx(gguf_tpl, upstream_tpl))
    r001 = [x for x in f if x.id == "R001"]
    assert len(r001) == len(load_fixtures())
    assert all(x.severity == Severity.INFO for x in r001)
    assert all(x.evidence["whitespace_only"] is True for x in r001)
    assert all(x.evidence["diff"] for x in r001)


def test_r001_content_divergence_is_not_marked_whitespace_only():
    f = by_id(run_reference_checks(ctx(A, B)))
    assert f["R001"].evidence["whitespace_only"] is False
