from ggufdoctor.engines.jinja2_engine import Jinja2Engine


def test_renders_simple_template():
    e = Jinja2Engine()
    r = e.render("{% for m in messages %}{{ m['content'] }}{% endfor %}",
                 {"messages": [{"role": "user", "content": "hi"}]})
    assert r.ok
    assert r.text == "hi"


def test_compile_error_is_captured_not_raised():
    r = Jinja2Engine().render("{% if %}", {})
    assert not r.ok
    assert r.error.startswith("compile:")


def test_render_error_is_captured_not_raised():
    r = Jinja2Engine().render("{{ raise_exception('boom') }}", {})
    assert not r.ok
    assert r.error.startswith("render:")


def test_strftime_now_is_deterministic():
    e = Jinja2Engine()
    a = e.render("{{ strftime_now('%Y') }}", {})
    b = e.render("{{ strftime_now('%Y') }}", {})
    assert a.text == b.text


def test_engine_reports_name_and_version():
    e = Jinja2Engine()
    assert e.name == "jinja2"
    assert e.version


def test_loop_controls_break_compiles_and_renders():
    e = Jinja2Engine()
    r = e.render(
        "{% for i in range(5) %}{% if i == 2 %}{% break %}{% endif %}{{ i }}{% endfor %}",
        {},
    )
    assert r.ok
    assert r.text == "01"


def test_generation_tag_compiles_and_body_appears_in_output():
    e = Jinja2Engine()
    r = e.render("a{% generation %}BODY{% endgeneration %}b", {})
    assert r.ok
    assert r.text == "aBODYb"


def test_tojson_keeps_non_ascii_literal():
    e = Jinja2Engine()
    r = e.render("{{ {'x': 'café'} | tojson }}", {})
    assert r.ok
    assert "café" in r.text
    assert "\\u" not in r.text


def test_tojson_indent_is_honoured():
    e = Jinja2Engine()
    r = e.render("{{ [1, 2] | tojson(indent=4) }}", {})
    assert r.ok
    assert r.text == "[\n    1,\n    2\n]"


def test_trim_blocks_and_lstrip_blocks_are_enabled():
    e = Jinja2Engine()
    r = e.render("{% if true %}\nX\n{% endif %}\n", {})
    assert r.ok
    # With trim_blocks/lstrip_blocks off, this renders "\nX\n" (the newline
    # right after "{% if true %}" is kept). With both on, that newline is
    # trimmed, leaving just "X\n" -- so reverting the setting flips this
    # assertion.
    assert r.text == "X\n"
