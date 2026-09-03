import json
import urllib.error

import pytest

from ggufdoctor.hf import HfClient


def fake_opener(responses):
    def _open(url):
        for frag, val in responses.items():
            if frag in url:
                if isinstance(val, int):
                    raise urllib.error.HTTPError(url, val, "err", {}, None)
                return val
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    return _open


def test_base_model_from_card_data():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"cardData": {"base_model": "Qwen/Qwen3-8B"}}) == "Qwen/Qwen3-8B"


def test_base_model_from_list_takes_first():
    c = HfClient(opener=fake_opener({}))
    info = {"cardData": {"base_model": ["Qwen/Qwen3-8B", "other/x"]}}
    assert c.base_model_of(info) == "Qwen/Qwen3-8B"


def test_base_model_from_tag_fallback():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["base_model:Qwen/Qwen3-8B"]}) == "Qwen/Qwen3-8B"


def test_base_model_absent():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["gguf"]}) is None


def test_upstream_template_ok():
    body = json.dumps({"chat_template": "{{ 'hi' }}"})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    tpl, why = c.upstream_template("org/model")
    assert why == "ok"
    assert tpl == "{{ 'hi' }}"


def test_upstream_gated_is_distinguished_from_missing():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 401}))
    tpl, why = c.upstream_template("google/gemma-4")
    assert tpl is None
    assert why == "gated"


def test_upstream_404_is_not_found():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 404,
                                     "chat_template.json": 404}))
    assert c.upstream_template("dead/repo")[1] == "not_found"


def test_upstream_present_but_no_template_field():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": json.dumps({})}))
    assert c.upstream_template("org/embed")[1] == "genuinely_absent"


def test_multi_template_list_picks_default():
    body = json.dumps({"chat_template": [
        {"name": "tool_use", "template": "T"},
        {"name": "default", "template": "D"}]})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    assert c.upstream_template("org/m")[0] == "D"


def test_upstream_json_array_is_fetch_error():
    # Valid JSON but not a dict: [1, 2, 3]
    c = HfClient(opener=fake_opener({"tokenizer_config.json": "[1,2,3]",
                                     "chat_template.json": 404}))
    tpl, why = c.upstream_template("broken/model")
    assert tpl is None
    assert why == "fetch_error"


def test_upstream_json_bare_string_is_fetch_error():
    # Valid JSON but not a dict: bare string
    c = HfClient(opener=fake_opener({"tokenizer_config.json": '"just a string"',
                                     "chat_template.json": 404}))
    tpl, why = c.upstream_template("broken/model")
    assert tpl is None
    assert why == "fetch_error"


def test_gguf_chat_template_handles_non_dict_model_info():
    # model_info returns a JSON array instead of dict
    c = HfClient(opener=fake_opener({"models": "[1,2,3]"}))
    result = c.gguf_chat_template("bad/repo")
    assert result is None


def test_gguf_chat_template_handles_bare_string_model_info():
    # model_info returns a JSON string instead of dict
    c = HfClient(opener=fake_opener({"models": '"just a string"'}))
    result = c.gguf_chat_template("bad/repo")
    assert result is None


def test_model_info_requests_every_field_its_callers_read():
    # The Hub returns ONLY the fields named in expand[], silently omitting the
    # rest, so an unnamed field reads as None forever. Ruling R8: `sha` was
    # missing, which is why every `survey --save-templates` provenance sidecar
    # recorded `"revision": null`. This pins the whole set, since the failure
    # mode of forgetting one is silent.
    seen = {}

    def opener(url):
        seen["url"] = url
        return json.dumps({"sha": "abc123", "gguf": {}})

    info = HfClient(opener=opener).model_info("org/model")
    assert info["sha"] == "abc123"
    for field in ("gguf", "cardData", "tags", "pipeline_tag", "sha"):
        assert f"expand[]={field}" in seen["url"], field


# --- Final fix C: bounded retry/backoff on HTTP 429, so a rate-limited
# request becomes a successful (if slightly delayed) call rather than a
# permanent failure that survey.py has to file as examine_error. ---

def test_model_info_retries_past_a_transient_rate_limit(monkeypatch):
    monkeypatch.setattr("ggufdoctor.hf.time.sleep", lambda s: None)
    calls = {"n": 0}
    body = json.dumps({"gguf": {"chat_template": "T"}})

    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)
        return body

    c = HfClient(opener=flaky)
    info = c.model_info("org/model")
    assert info["gguf"]["chat_template"] == "T"
    assert calls["n"] == 2


def test_upstream_template_retries_past_a_transient_rate_limit(monkeypatch):
    monkeypatch.setattr("ggufdoctor.hf.time.sleep", lambda s: None)
    calls = {"n": 0}
    body = json.dumps({"chat_template": "{{ 'hi' }}"})

    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)
        return body

    c = HfClient(opener=flaky)
    tpl, why = c.upstream_template("org/model")
    assert why == "ok"
    assert tpl == "{{ 'hi' }}"


def test_non_429_http_error_is_not_retried(monkeypatch):
    monkeypatch.setattr("ggufdoctor.hf.time.sleep", lambda s: None)
    calls = {"n": 0}

    def always_404(url):
        calls["n"] += 1
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    c = HfClient(opener=always_404)
    with pytest.raises(urllib.error.HTTPError):
        c.model_info("org/model")
    assert calls["n"] == 1


def test_persistent_rate_limit_eventually_raises_after_bounded_retries(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("ggufdoctor.hf.time.sleep", sleeps.append)
    calls = {"n": 0}

    def always_429(url):
        calls["n"] += 1
        raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)

    c = HfClient(opener=always_429)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        c.model_info("org/model")
    assert exc_info.value.code == 429
    # Bounded: a handful of attempts, not an infinite or unbounded retry loop.
    assert 2 <= calls["n"] <= 6
    assert len(sleeps) == calls["n"] - 1
