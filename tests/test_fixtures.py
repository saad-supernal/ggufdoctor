from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures, CORPUS_VERSION


def test_corpus_has_expected_fixtures():
    names = [f.name for f in load_fixtures()]
    assert names == ["user_only", "system_user", "multiturn", "with_tools",
                     "thinking_unset", "thinking_true", "thinking_false"]


def test_tools_fixture_carries_a_tool_definition():
    f = next(f for f in load_fixtures() if f.name == "with_tools")
    assert f.context["tools"][0]["function"]["name"] == "get_weather"


def test_corpus_version_is_declared():
    assert CORPUS_VERSION == "1"


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
