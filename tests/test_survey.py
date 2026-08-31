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
