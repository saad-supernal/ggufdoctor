import pytest

from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures, CORPUS_VERSION


def test_corpus_has_expected_fixtures_in_order():
    names = [f.name for f in load_fixtures()]
    assert names == ["user_only", "system_user", "multiturn", "with_tools",
                     "thinking_unset", "thinking_true", "thinking_false",
                     "tool_roundtrip", "typed_content", "no_generation_prompt"]


def test_tools_fixture_carries_a_tool_definition():
    f = next(f for f in load_fixtures() if f.name == "with_tools")
    assert f.context["tools"][0]["function"]["name"] == "get_weather"


def test_corpus_version_is_declared():
    assert CORPUS_VERSION == "2"


def test_tiers_split_core_from_extended():
    tiers = {f.name: f.tier for f in load_fixtures()}
    assert {n for n, t in tiers.items() if t == "extended"} == {
        "tool_roundtrip", "typed_content", "no_generation_prompt"}
    assert all(t == "core" for n, t in tiers.items()
               if n not in ("tool_roundtrip", "typed_content", "no_generation_prompt"))


def test_extended_fixtures_carry_the_shapes_the_spike_found_divergence_on():
    fx = {f.name: f.context for f in load_fixtures()}
    assistant = fx["tool_roundtrip"]["messages"][2]
    assert assistant["role"] == "assistant" and assistant["content"] is None
    assert isinstance(assistant["tool_calls"][0]["function"]["arguments"], dict)
    assert fx["tool_roundtrip"]["messages"][3]["role"] == "tool"
    assert fx["tool_roundtrip"]["tools"][0]["function"]["name"] == "get_weather"
    assert isinstance(fx["typed_content"]["messages"][0]["content"], list)
    assert fx["no_generation_prompt"]["add_generation_prompt"] is False


def test_unknown_tier_is_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"version": "x", "fixtures": [{"name": "a", "tier": "bogus", "context": {}}]}')
    with pytest.raises(ValueError, match="tier"):
        load_fixtures(str(p))


def test_system_user_fixture_renders_exact_text_through_the_engine():
    # Guards the literal contents of the system_user fixture (e.g. a typo in
    # "Be brief.") that the fixture-name and tool-definition checks above
    # would not catch.
    f = next(f for f in load_fixtures() if f.name == "system_user")
    r = Jinja2Engine().render(
        "{% for m in messages %}[{{ m.role }}] {{ m.content }}\n{% endfor %}",
        f.context,
    )
    assert r.ok
    assert r.text == "[system] Be brief.\n[user] Hello\n"


def test_thinking_fixtures_pin_the_enable_thinking_triple():
    fixtures = {f.name: f for f in load_fixtures()}
    assert "enable_thinking" not in fixtures["thinking_unset"].context
    assert fixtures["thinking_true"].context["enable_thinking"] is True
    assert fixtures["thinking_false"].context["enable_thinking"] is False
