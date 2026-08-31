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
