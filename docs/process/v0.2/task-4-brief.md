### Task 4: Fixture corpus v2 with tiers, and S003/S007 tier awareness

**Files:**
- Modify: `src/ggufdoctor/models.py` (`Fixture.tier`)
- Modify: `src/ggufdoctor/fixtures.py` (`CORPUS_VERSION = "2"`, tier loading)
- Modify: `src/ggufdoctor/fixture_data/corpus.json`
- Modify: `src/ggufdoctor/checks/sanity.py` (S003, S007)
- Test: `tests/test_fixtures.py`, `tests/test_checks_sanity.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Fixture(name, context, tier="core")` with `tier in {"core", "extended"}`; fixture names `tool_roundtrip`, `typed_content`, `no_generation_prompt`; `CORPUS_VERSION == "2"`.

Why tiers exist: the spike showed 10 of 100 real templates raise a `TypeError` under transformers-style Jinja2 when handed typed content, and many decline a `tool` role. Those templates are not defective; the corpus is asking them shapes they predate. An `extended` fixture therefore never produces an S003 ERROR (it produces INFO), and S007 only ever looks at `user_only`.

- [ ] **Step 1: Write the failing tests**

Replace the first and third tests in `tests/test_fixtures.py` and add two:

```python
def test_corpus_has_expected_fixtures_in_order():
    names = [f.name for f in load_fixtures()]
    assert names == ["user_only", "system_user", "multiturn", "with_tools",
                     "thinking_unset", "thinking_true", "thinking_false",
                     "tool_roundtrip", "typed_content", "no_generation_prompt"]


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
```

Add `import pytest` at the top of `tests/test_fixtures.py`.

In `tests/test_checks_sanity.py` add:

```python
def _model_with(template, **kw):
    return GgufModel(source_id="t", architecture="llama", chat_template=template,
                     tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1,
                     add_bos_token=False, **kw)


def test_s003_on_extended_fixture_is_info_not_error():
    # `'x' + None` raises TypeError under Jinja2 only on tool_roundtrip
    # (assistant content is null there). That is the fixture asking a shape
    # the template predates -- reported, but never as an error.
    # Core fixtures all have string content, so only the two extended
    # fixtures fail -- with two different TypeErrors (NoneType vs list), so
    # they collapse into two findings, not one.
    tpl = "{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content }}{% endfor %}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    findings = s003_render_error(ctx)
    found = {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}
    assert found == {("S003", Severity.INFO, ("tool_roundtrip",)),
                     ("S003", Severity.INFO, ("typed_content",))}
    for f in findings:
        assert "extended" in f.message and "broken" not in f.message


def test_s003_on_core_fixture_stays_error():
    tpl = "{{ messages[0].content + none }}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    severities = {f.severity for f in s003_render_error(ctx)
                  if "user_only" in f.evidence.get("fixtures", ())}
    assert severities == {Severity.ERROR}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fixtures.py tests/test_checks_sanity.py -v`
Expected: the new fixture tests FAIL on names/version/`tier` attribute; `test_s003_on_extended_fixture_is_info_not_error` FAILS (no `tool_roundtrip` fixture yet, and severity would be ERROR).

- [ ] **Step 3: Models and loader**

`src/ggufdoctor/models.py`:

```python
FIXTURE_TIERS = ("core", "extended")


@dataclass(frozen=True)
class Fixture:
    name: str
    context: dict[str, Any]
    # "core": a conversation every chat template is expected to handle.
    # "extended": a shape (typed content, tool-call round trip, no generation
    # prompt) that older templates legitimately predate. Checks downgrade
    # render failures on extended fixtures to INFO -- see checks/sanity.py S003.
    tier: str = "core"
```

`src/ggufdoctor/fixtures.py`:

```python
from ggufdoctor.models import FIXTURE_TIERS, Fixture

CORPUS_VERSION = "2"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    out = []
    for item in data["fixtures"]:
        tier = item.get("tier", "core")
        if tier not in FIXTURE_TIERS:
            raise ValueError(
                f"fixture {item.get('name')!r} has unknown tier {tier!r} "
                f"(expected one of {', '.join(FIXTURE_TIERS)})")
        out.append(Fixture(name=item["name"], context=item["context"], tier=tier))
    return out
```

- [ ] **Step 4: Corpus**

In `src/ggufdoctor/fixture_data/corpus.json` set `"version": "2"` and append these three entries after `thinking_false` (copy the `get_weather` tool object from `with_tools` verbatim into `tool_roundtrip`):

```json
    {"name": "tool_roundtrip", "tier": "extended",
     "context": {"messages": [
                   {"role": "system", "content": "Be brief."},
                   {"role": "user", "content": "Weather in Paris?"},
                   {"role": "assistant", "content": null,
                    "tool_calls": [{"id": "call_1", "type": "function",
                                    "function": {"name": "get_weather",
                                                 "arguments": {"city": "Paris"}}}]},
                   {"role": "tool", "tool_call_id": "call_1", "name": "get_weather",
                    "content": "{\"temp_c\": 18}"}],
                 "add_generation_prompt": true,
                 "tools": [ ...the same get_weather tool object as with_tools... ]}},
    {"name": "typed_content", "tier": "extended",
     "context": {"messages": [{"role": "user",
                               "content": [{"type": "text", "text": "Hello"},
                                           {"type": "text", "text": "there"}]}],
                 "add_generation_prompt": true}},
    {"name": "no_generation_prompt", "tier": "extended",
     "context": {"messages": [{"role": "user", "content": "Hi"},
                              {"role": "assistant", "content": "Hello!"}],
                 "add_generation_prompt": false}}
```

Validate the file parses: `.venv/bin/python -c "from ggufdoctor.fixtures import load_fixtures; print([f.name for f in load_fixtures()])"`.

- [ ] **Step 5: S003 and S007 tier awareness**

In `src/ggufdoctor/checks/sanity.py`, `s003_render_error` gets a third bucket:

```python
    failures: list[tuple[str, Any, dict[str, Any]]] = []
    extended_failures: list[tuple[str, Any, dict[str, Any]]] = []
    declines: list[tuple[str, Any, dict[str, Any]]] = []
    for fx in ctx.fixtures:
        r = _render_fixture(ctx, fx)
        if not r.error:
            continue
        if r.error.startswith("render:"):
            bucket = extended_failures if fx.tier == "extended" else failures
            bucket.append((fx.name, r.error, {"error": r.error}))
        elif r.error.startswith("raise:"):
            ...unchanged...
    findings = _collapse_by_signature(
        "S003", Severity.ERROR,
        "template raises while rendering a standard conversation", failures)
    findings.extend(_collapse_by_signature(
        "S003", Severity.INFO,
        lambda evidence: (
            "template does not handle an extended conversation shape "
            f"({', '.join(evidence['fixtures'])}); older templates predate these "
            f"inputs — {evidence['error']}"),
        extended_failures))
    findings.extend(_collapse_by_signature("S003", Severity.INFO, ...declines unchanged...))
    return findings
```

S007 already renders only `user_only`, which is core; add one line of comment saying so, no code change. S008 (empty render) is left as is: an extended fixture rendering to *empty* is still a real fact about the template.

- [ ] **Step 6: Run the whole suite and reconcile real-template expectations**

Run: `.venv/bin/python -m pytest -q`

The four complete-finding-set tests in `tests/test_checks_sanity.py` (Mistral-v0.2, Llama-2, Gemma-2, Llama-3.3-tools) will now see three more fixtures and may gain findings. For each changed expectation, **read the template** and write the reason into the test's comment block in the same style as the existing ones (e.g. "S003 INFO on `tool_roundtrip`: Mistral's alternation guard rejects the `tool` role via `raise_exception` — author decline, same signature as `system_user` so it collapses into that finding"; "S003 INFO on `typed_content`: `message['content']` is concatenated as a string, list content raises `TypeError` under transformers; extended tier, hence INFO"). Do not add expectations you cannot justify from the template text; if a finding looks wrong, stop and report it (`DONE_WITH_CONCERNS`).

Expected: all tests PASS with justified updates only.

- [ ] **Step 7: Commit**

```bash
git add src/ggufdoctor/models.py src/ggufdoctor/fixtures.py src/ggufdoctor/fixture_data/corpus.json src/ggufdoctor/checks/sanity.py tests/test_fixtures.py tests/test_checks_sanity.py
git commit -m "feat(fixtures): corpus v2 adds extended-tier fixtures; S003 reports them at INFO

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

