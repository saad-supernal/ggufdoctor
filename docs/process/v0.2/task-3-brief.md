### Task 3: Engine semantics table — pin both engines' behaviour on the known divergences

**Files:**
- Test: `tests/test_engine_semantics.py`

**Interfaces:**
- Consumes: `Jinja2Engine`, `LlamaCppEngine` (Task 2).
- Produces: nothing; this is the tripwire that makes an engine bump visible.

- [ ] **Step 1: Write the test**

```python
# tests/test_engine_semantics.py
"""Pins how BOTH engines behave on the expressions where they are known to
differ (and a sample where they agree). Measured 2026-09-03 against Jinja2
3.1.6 and llama.cpp b10775 -- see docs/research/2026-09-03-engine-spike.md §3.

A failing row after an engine bump is not a bug in this test: it is the bump
changing user-visible semantics, and the X-family messages / spec must be
re-checked before the row is updated.
"""
import pytest

from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine

OK = "ok"
RENDER_ERR = "render"
COMPILE_ERR = "compile"

# (label, template, context, jinja2 outcome, llama.cpp outcome)
# An outcome is the rendered text, or RENDER_ERR / COMPILE_ERR.
ROWS = [
    ("print None",            "[{{ n }}]",            {"n": None},        "[None]",       "[]"),
    ("print list",            "[{{ l }}]",            {"l": [1, "a"]},    "[[1, 'a']]",   "[1a]"),
    ("print dict",            "[{{ d }}]",            {"d": {"a": 1}},    "[{'a': 1}]",   "[]"),
    ("str + None",            "[{{ 'x' + n }}]",      {"n": None},        RENDER_ERR,     "[x]"),
    ("str + list",            "[{{ 'x' + l }}]",      {"l": ["a"]},       RENDER_ERR,     "[x['a']]"),
    ("default on None",       "[{{ n | default('d') }}]", {"n": None},    "[None]",       "[d]"),
    ("floor division",        "[{{ 7 // 2 }}]",       {},                 "[3]",          COMPILE_ERR),
    ("length of None",        "[{{ n | length }}]",   {"n": None},        RENDER_ERR,     RENDER_ERR),
    # agreement rows -- these guard against regressions in either engine
    ("str ~ list",            "[{{ 'x' ~ l }}]",      {"l": ["a"]},       "[x['a']]",     "[x['a']]"),
    ("undefined var",         "[{{ u }}]",            {},                 "[]",           "[]"),
    ("tojson non-ascii",      "[{{ d | tojson }}]",   {"d": {"b": 1, "a": "é"}}, '[{"b": 1, "a": "é"}]', '[{"b": 1, "a": "é"}]'),
    ("tojson indent",         "[{{ d | tojson(indent=2) }}]", {"d": {"b": [1, 2]}},
                              '[{\n  "b": [\n    1,\n    2\n  ]\n}]', '[{\n  "b": [\n    1,\n    2\n  ]\n}]'),
    ("namespace",             "{% set ns = namespace(x=1) %}{% set ns.x = 2 %}[{{ ns.x }}]", {}, "[2]", "[2]"),
    ("generation tag",        "{% generation %}hi{% endgeneration %}", {}, "hi", "hi"),
    ("dictsort",              "{% for k, v in d | dictsort %}{{ k }}{% endfor %}", {"d": {"b": 1, "a": 2}}, "ab", "ab"),
    ("negative slice",        "[{{ s[-3:] }}]",       {"s": "abcdef"},    "[def]",        "[def]"),
    ("is mapping/iterable",   "[{{ 'ab' is iterable }}][{{ {} is mapping }}]", {}, "[True][True]", "[True][True]"),
    ("loop.index",            "{% for i in range(3) %}{{ loop.index }}{% endfor %}", {}, "123", "123"),
    ("break",                 "{% for i in range(3) %}{% if i == 1 %}{% break %}{% endif %}{{ i }}{% endfor %}", {}, "0", "0"),
]


def _outcome(result):
    if result.ok:
        return result.text
    if result.error.startswith("compile:"):
        return COMPILE_ERR
    return RENDER_ERR


@pytest.fixture(scope="module")
def engines():
    llama = LlamaCppEngine()
    assert llama.available, llama.unavailable_reason
    return Jinja2Engine(), llama


@pytest.mark.parametrize("label,template,context,expect_j2,expect_llama", ROWS,
                         ids=[r[0] for r in ROWS])
def test_semantics_row(engines, label, template, context, expect_j2, expect_llama):
    j2, llama = engines
    assert _outcome(j2.render(template, context)) == expect_j2, "jinja2 changed"
    assert _outcome(llama.render(template, context)) == expect_llama, "llama.cpp changed"


def test_table_covers_every_divergence_class_named_in_the_spike():
    labels = {r[0] for r in ROWS}
    for needed in ("print None", "print list", "str + None", "default on None", "floor division"):
        assert needed in labels
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_engine_semantics.py -v`
Expected: every row PASSES. If a row fails, do **not** edit the expectation to match: compare against `docs/research/2026-09-03-engine-spike.md` §3; a mismatch there means the engine build (Task 1) or the error mapping (Task 2) is wrong, and the fix belongs in those tasks.

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine_semantics.py
git commit -m "test: pin jinja2 vs llama.cpp semantics table from the engine spike

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
