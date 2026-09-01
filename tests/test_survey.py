from ggufdoctor.checks.sanity import NON_CHAT_ARCHITECTURES
from ggufdoctor.survey import sample_repos, survey, to_markdown


class FakeClient:
    """Two publishers, three repos; one repo diverges from upstream."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 100},
                {"id": "orgA/two", "downloads": 50},
                {"id": "orgA/three", "downloads": 25},
                {"id": "orgB/one", "downloads": 10}]

    def model_info(self, repo_id):
        tpl = "{% for m in messages %}{{ m['content'] }}{% endfor %}"
        if repo_id == "orgA/one":
            tpl += "DIVERGES"
        return {"gguf": {"architecture": "llama", "chat_template": tpl},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "{% for m in messages %}{{ m['content'] }}{% endfor %}", "ok"


def test_per_org_cap_limits_sample():
    repos = sample_repos(FakeClient(), top=10, per_org=2)
    assert [r["id"] for r in repos] == ["orgA/one", "orgA/two", "orgB/one"]


def test_survey_reports_divergence_and_methodology():
    r = survey(FakeClient(), top=10, per_org=2)
    assert r["aggregate"]["comparable"] == 3
    assert r["aggregate"]["divergent"] == 1
    assert r["aggregate"]["per_org"] == 2
    assert r["aggregate"]["publishers_total"] == 2
    assert r["aggregate"]["publishers_affected"] == 1


def test_download_weighting_uses_downloads():
    r = survey(FakeClient(), top=10, per_org=2)
    # divergent repo has 100 of 160 total downloads across comparable repos
    assert round(r["aggregate"]["download_weighted_pct"], 1) == 62.5


def test_markdown_includes_caveats():
    md = to_markdown(survey(FakeClient(), top=10, per_org=2))
    assert "per-org cap" in md
    assert "coverage" in md.lower()


# --- Fix round 1 ---

class PaginationFailsPartwayClient:
    """First page succeeds; the next page raises (simulated transient 503)."""

    def list_gguf_models(self, skip, limit):
        if skip == 0:
            return [{"id": "orgA/repo1", "downloads": 10}]
        raise RuntimeError("simulated 503")

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "T", "ok"


def test_pagination_failure_keeps_partial_sample_and_flags_truncated():
    r = survey(PaginationFailsPartwayClient(), top=50, per_org=2)
    assert r["aggregate"]["truncated"] is True
    assert r["aggregate"]["sampled"] == 1
    assert r["aggregate"]["comparable"] == 1

    md = to_markdown(r)
    assert "truncated" in md.lower()


class ExamineFailsForOneRepoClient:
    """orgA/bad blows up while being examined; orgA/good succeeds."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/bad", "downloads": 5},
                {"id": "orgA/good", "downloads": 7}]

    def model_info(self, repo_id):
        if repo_id == "orgA/bad":
            raise RuntimeError("boom")
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "T", "ok"


def test_examine_failure_is_recorded_as_gap_and_survey_continues():
    r = survey(ExamineFailsForOneRepoClient(), top=10, per_org=2)
    assert r["aggregate"]["truncated"] is False
    assert r["aggregate"]["sampled"] == 2
    assert r["aggregate"]["comparable"] == 1
    assert r["aggregate"]["coverage_gaps"].get("examine_error") == 1


class MixedUpstreamReasonsClient:
    """One repo's upstream is 404, the other errors reaching it."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 1},
                {"id": "orgB/one", "downloads": 1}]

    def model_info(self, repo_id):
        base = "up/gone" if repo_id == "orgA/one" else "up/unreachable"
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": base}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        if repo == "up/gone":
            return None, "not_found"
        return None, "fetch_error"


def test_not_found_and_fetch_error_are_distinct_gap_keys():
    r = survey(MixedUpstreamReasonsClient(), top=10, per_org=2)
    gaps = r["aggregate"]["coverage_gaps"]
    assert gaps.get("upstream_not_found") == 1
    assert gaps.get("upstream_fetch_error") == 1

    md = to_markdown(r)
    assert "upstream_not_found" in md
    assert "upstream_fetch_error" in md


# --- Final fix B: encode the survey's audit criteria in code ---

class GenuinelyAbsentUpstreamClient:
    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return None, "genuinely_absent"


def test_upstream_missing_template_is_labeled_by_observation_not_inference():
    # "genuinely_absent" means the upstream repo's tokenizer_config.json (and
    # chat_template.json) have no chat_template field -- that's equally
    # consistent with a pretrain base model as with a "non chat model", so
    # the coverage_gaps key must say the former, not assert the latter.
    r = survey(GenuinelyAbsentUpstreamClient(), top=10, per_org=2)
    gaps = r["aggregate"]["coverage_gaps"]
    assert gaps.get("upstream_has_no_template") == 1
    assert "non_chat_model" not in gaps


class UppercaseNonChatArchClient:
    """Architecture string cased like the raw GGUF metadata often is."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/embed-GGUF", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "BERT", "chat_template": None},
                "cardData": {}}

    def base_model_of(self, info):
        raise AssertionError("architecture exclusion must short-circuit "
                             "before base_model resolution")

    def upstream_template(self, repo):
        raise AssertionError("must not resolve upstream for a non-chat architecture")


def test_non_chat_architecture_exclusion_is_case_insensitive():
    r = survey(UppercaseNonChatArchClient(), top=10, per_org=2)
    assert r["aggregate"]["coverage_gaps"].get("non_chat_architecture") == 1


class SpeechPipelineClient:
    """Reports a real chat-capable architecture name, but is an ASR model.

    Mirrors unslothai/Qwen3-ASR-*-GGUF: architecture 'qwen3vl' is a
    legitimate architecture for real chat models, so name-based exclusion
    (NON_CHAT_ARCHITECTURES) must not catch it -- only the Hub's own
    pipeline_tag/tags evidence should.
    """

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "unslothai/Qwen3-ASR-0.6B-GGUF", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "qwen3vl", "chat_template": "T"},
                "cardData": {"base_model": "Qwen/Qwen3-ASR-0.6B"},
                "pipeline_tag": "automatic-speech-recognition",
                "tags": ["gguf", "automatic-speech-recognition"]}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        raise AssertionError("pipeline-tag exclusion must short-circuit "
                             "before upstream resolution")


def test_speech_pipeline_tag_excludes_despite_chat_capable_architecture_name():
    r = survey(SpeechPipelineClient(), top=10, per_org=2)
    assert r["aggregate"]["comparable"] == 0
    assert r["aggregate"]["coverage_gaps"].get("non_chat_pipeline_tag") == 1
    assert "qwen3vl" not in NON_CHAT_ARCHITECTURES


class TtsPipelineViaTagsClient:
    """pipeline_tag absent, but 'text-to-speech' shows up in tags instead."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/tts-model-GGUF", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": "up/stream"},
                "tags": ["gguf", "text-to-speech"]}

    def base_model_of(self, info):
        raise AssertionError("pipeline-tag exclusion must short-circuit "
                             "before base_model resolution")

    def upstream_template(self, repo):
        raise AssertionError("pipeline-tag exclusion must short-circuit "
                             "before upstream resolution")


def test_tts_tag_excludes_even_without_a_pipeline_tag_field():
    r = survey(TtsPipelineViaTagsClient(), top=10, per_org=2)
    assert r["aggregate"]["coverage_gaps"].get("non_chat_pipeline_tag") == 1


class SelfReferentialBaseModelClient:
    """Lists itself (different case) as its own base_model."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/Model-GGUF", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "llama", "chat_template": "T"},
                "cardData": {"base_model": "orga/model-gguf"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        raise AssertionError("must not compare a repo's template against itself")


def test_self_referential_base_model_is_excluded_not_compared_to_itself():
    r = survey(SelfReferentialBaseModelClient(), top=10, per_org=2)
    assert r["aggregate"]["comparable"] == 0
    assert r["aggregate"]["coverage_gaps"].get("no_base_model") == 1


class BothSidesFailToRenderClient:
    """Neither the GGUF's template nor the upstream's ever renders."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 5}]

    def model_info(self, repo_id):
        return {"gguf": {"architecture": "llama",
                         "chat_template": "{{ raise_exception('gguf side') }}"},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "{{ raise_exception('upstream side') }}", "ok"


def test_both_sides_failing_to_render_is_unrenderable_not_cosmetic_only():
    # Before this fix: no R001 findings (r001 skips fixtures where either
    # side errors), the two template strings differ, so the record fell
    # through to "cosmetic_only" -- publishing "the rewrite changes nothing
    # the model sees" about a repo the tool never actually rendered.
    r = survey(BothSidesFailToRenderClient(), top=10, per_org=2)
    statuses = {rec["id"]: rec["status"] for rec in r["records"]}
    assert statuses["orgA/one"] == "unrenderable"
    assert r["aggregate"]["comparable"] == 0
    assert r["aggregate"]["coverage_gaps"].get("unrenderable") == 1
    assert "cosmetic_only" not in r["aggregate"]["coverage_gaps"]
