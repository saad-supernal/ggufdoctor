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
