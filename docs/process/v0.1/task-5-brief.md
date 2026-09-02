### Task 5: Jinja2 engine and fixture corpus

**Files:**
- Create: `src/ggufdoctor/engines/__init__.py`
- Create: `src/ggufdoctor/engines/base.py`
- Create: `src/ggufdoctor/engines/jinja2_engine.py`
- Create: `src/ggufdoctor/fixtures.py`
- Create: `src/ggufdoctor/fixture_data/corpus.json`
- Test: `tests/test_engine_jinja2.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: `RenderResult`, `Fixture` from Task 1
- Produces: `Engine` protocol (`.name: str`, `.version: str`, `.render(template, context) -> RenderResult`); `Jinja2Engine()`; `load_fixtures(path=None) -> list[Fixture]`; `CORPUS_VERSION: str`

The corpus is the same seven fixtures used in the motivating survey: `user_only`, `system_user`, `multiturn`, `with_tools`, `thinking_unset`, `thinking_true`, `thinking_false`. Rendering must supply `bos_token`/`eos_token` defaults and the `raise_exception` and `strftime_now` globals that real templates call; `strftime_now` is pinned to a fixed date so renders are deterministic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_jinja2.py
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
```

```python
# tests/test_fixtures.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_jinja2.py tests/test_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.engines'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/engines/__init__.py
```

```python
# src/ggufdoctor/engines/base.py
from __future__ import annotations

from typing import Any, Protocol

from ggufdoctor.models import RenderResult


class Engine(Protocol):
    name: str
    version: str

    def render(self, template: str, context: dict[str, Any]) -> RenderResult: ...
```

```python
# src/ggufdoctor/engines/jinja2_engine.py
from __future__ import annotations

import datetime
import json
from typing import Any

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

from ggufdoctor.models import RenderResult

PINNED_NOW = datetime.datetime(2026, 1, 1)

BASE_CONTEXT: dict[str, Any] = {
    "bos_token": "<s>",
    "eos_token": "</s>",
    "unk_token": "<unk>",
    "pad_token": "<pad>",
    "add_generation_prompt": True,
}


def _raise_exception(msg: str) -> None:
    raise ValueError(msg)


def _strftime_now(fmt: str) -> str:
    return PINNED_NOW.strftime(fmt)


class Jinja2Engine:
    name = "jinja2"

    def __init__(self) -> None:
        self.version = jinja2.__version__
        self._env = ImmutableSandboxedEnvironment(
            trim_blocks=False, lstrip_blocks=False
        )
        self._env.globals["raise_exception"] = _raise_exception
        self._env.globals["strftime_now"] = _strftime_now
        self._env.filters["tojson"] = lambda o, **kw: json.dumps(o)

    def render(self, template: str, context: dict[str, Any]) -> RenderResult:
        try:
            tpl = self._env.from_string(template)
        except Exception as e:
            return RenderResult(None, f"compile:{type(e).__name__}: {e}")
        ctx = dict(BASE_CONTEXT)
        ctx.update(context)
        try:
            return RenderResult(tpl.render(**ctx), None)
        except Exception as e:
            return RenderResult(None, f"render:{type(e).__name__}: {e}")
```

```python
# src/ggufdoctor/fixtures.py
from __future__ import annotations

import json
from importlib import resources

from ggufdoctor.models import Fixture

CORPUS_VERSION = "1"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return [Fixture(name=item["name"], context=item["context"])
            for item in data["fixtures"]]
```

```json
// src/ggufdoctor/fixture_data/corpus.json
{
  "version": "1",
  "fixtures": [
    {"name": "user_only",
     "context": {"messages": [{"role": "user", "content": "Hello"}],
                 "add_generation_prompt": true}},
    {"name": "system_user",
     "context": {"messages": [{"role": "system", "content": "Be brief."},
                              {"role": "user", "content": "Hello"}],
                 "add_generation_prompt": true}},
    {"name": "multiturn",
     "context": {"messages": [{"role": "user", "content": "Hi"},
                              {"role": "assistant", "content": "Hey!"},
                              {"role": "user", "content": "Bye"}],
                 "add_generation_prompt": true}},
    {"name": "with_tools",
     "context": {"messages": [{"role": "user", "content": "Weather in Paris?"}],
                 "add_generation_prompt": true,
                 "tools": [{"type": "function",
                            "function": {"name": "get_weather",
                                         "description": "Get weather for a city",
                                         "parameters": {"type": "object",
                                                        "properties": {"city": {"type": "string"}},
                                                        "required": ["city"]}}}]}},
    {"name": "thinking_unset",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true}},
    {"name": "thinking_true",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true, "enable_thinking": true}},
    {"name": "thinking_false",
     "context": {"messages": [{"role": "user", "content": "2+2?"}],
                 "add_generation_prompt": true, "enable_thinking": false}}
  ]
}
```

Add to `pyproject.toml` under `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/ggufdoctor/fixture_data" = "ggufdoctor/fixture_data"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_jinja2.py tests/test_fixtures.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/engines src/ggufdoctor/fixtures.py src/ggufdoctor/fixture_data pyproject.toml tests/test_engine_jinja2.py tests/test_fixtures.py
git commit -m "feat: jinja2 engine and versioned fixture corpus"
```

---

