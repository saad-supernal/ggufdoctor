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
