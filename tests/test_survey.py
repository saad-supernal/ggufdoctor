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
