### Task 6: Engine registry, `--engines`, X wiring, report provenance

**Files:**
- Create: `src/ggufdoctor/engines/registry.py`
- Modify: `src/ggufdoctor/models.py` (`Coverage.engines_unavailable`, `Coverage.engines_agreed_fixtures`)
- Modify: `src/ggufdoctor/cli.py`
- Modify: `src/ggufdoctor/report/human.py`, `src/ggufdoctor/report/json_report.py`
- Test: `tests/test_registry.py`, `tests/test_cli.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `LlamaCppEngine` (Task 2), `run_cross_engine_checks`, `X_IDS` (Task 5).
- Produces: `registry.ENGINE_NAMES = ("jinja2", "llama.cpp")`; `registry.EngineSelection(engines: list, unavailable: dict[str, str])`; `registry.select_engines(requested: list[str] | None) -> EngineSelection` (raises `ValueError` for an unknown name or an explicitly requested engine that is unavailable); CLI flag `--engines NAMES`; `Coverage.engines_unavailable: dict[str, str]`, `Coverage.engines_agreed_fixtures: int | None`; JSON `engines[]` entries gain `commit` and `backend` when the engine has them, `coverage.engines_unavailable`, `coverage.engines_agreed_fixtures`; human report engine line `llama.cpp b10775 (67a17c17, wasmtime 48.0.0)`, an `engines agree` line, and `llama.cpp unavailable — <reason>` when applicable.

- [ ] **Step 0: Make the shared test template engine-neutral**

`CHAT_TPL` in `tests/test_cli.py` and `tests/test_checks_sanity.py` prints `{{ m['content'] }}` unconditionally. With corpus v2 that diverges between the engines on `tool_roundtrip` (content is null: jinja2 prints `None`, llama.cpp prints nothing → X005 ERROR → exit 1) and on `typed_content`. Every CLI test that assumes exit 0 would break for a reason that has nothing to do with the CLI. Replace both copies with a template that handles null and typed content the same way under both engines, and confirm with a one-off render through `Jinja2Engine` and `LlamaCppEngine` on all ten fixtures that the outputs are byte-identical before touching anything else:

```python
CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n"
            "{% if m['content'] is string %}{{ m['content'] }}"
            "{% elif m['content'] is not none %}{% for p in m['content'] %}{{ p['text'] }}{% endfor %}"
            "{% endif %}<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")
```

If llama.cpp rejects the `is string` test, fall back to `{% if m['content'] is none %}{% elif m['content'] is mapping or (m['content'] is iterable and m['content'] is not string) %}...parts...{% else %}{{ m['content'] }}{% endif %}` and record which form worked in the report. Expected finding sets in `test_checks_sanity.py` that use `CHAT_TPL` must be re-derived and re-justified, not re-pasted.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registry.py
import pytest

from ggufdoctor.engines import registry


def test_default_selection_is_jinja2_then_llama_cpp():
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2", "llama.cpp"]
    assert sel.unavailable == {}


def test_subset_keeps_jinja2_first_and_declines_are_not_gaps():
    sel = registry.select_engines(["jinja2"])
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {}


def test_unknown_engine_is_an_error():
    with pytest.raises(ValueError, match="unknown engine 'minja'"):
        registry.select_engines(["minja"])


def test_jinja2_cannot_be_dropped():
    with pytest.raises(ValueError, match="jinja2"):
        registry.select_engines(["llama.cpp"])


def test_unavailable_engine_is_recorded_by_default_but_fatal_when_requested(monkeypatch):
    class Broken:
        name = "llama.cpp"
        version = "b0"
        available = False
        unavailable_reason = "wasmtime not importable: boom"
    monkeypatch.setattr(registry, "_construct", lambda name: Broken() if name == "llama.cpp" else registry._construct_default(name))
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {"llama.cpp": "wasmtime not importable: boom"}
    with pytest.raises(ValueError, match="boom"):
        registry.select_engines(["jinja2", "llama.cpp"])
```

Append to `tests/test_cli.py` (use the file's existing `_model(tmp_path)` helper that writes a GGUF with `CHAT_TPL`, and `capsys`):

```python
def test_default_run_uses_both_engines_and_reports_agreement(tmp_path, capsys):
    assert main([_model(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "engines: jinja2 " in out and "llama.cpp b10775 (67a17c17, wasmtime " in out
    assert "engines agree:" in out


def test_engines_flag_subsets_without_recording_a_gap(tmp_path, capsys):
    assert main([_model(tmp_path), "--engines", "jinja2"]) == 0
    out = capsys.readouterr().out
    assert "llama.cpp" not in out
    assert "partial" not in out and "X001" not in out


def test_unknown_engine_exits_two_with_one_line(tmp_path, capsys):
    assert main([_model(tmp_path), "--engines", "jinja2,minja"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ggufdoctor: unknown engine 'minja'")


def test_json_carries_engine_provenance_and_agreement(tmp_path):
    target = tmp_path / "r.json"
    assert main([_model(tmp_path), "--json", str(target)]) == 0
    payload = json.loads(target.read_text())
    llama = next(e for e in payload["engines"] if e["name"] == "llama.cpp")
    assert llama["version"] == "b10775" and llama["commit"].startswith("67a17c17")
    assert llama["backend"].startswith("wasmtime ")
    assert payload["coverage"]["families_run"] == ["S", "X"]
    assert payload["coverage"]["engines_unavailable"] == {}
    assert isinstance(payload["coverage"]["engines_agreed_fixtures"], int)
    assert payload["fixture_corpus_version"] == "2"


def test_unavailable_engine_makes_the_run_partial(tmp_path, capsys, monkeypatch):
    from ggufdoctor.engines import registry
    class Broken:
        name = "llama.cpp"; version = "b0"; available = False
        unavailable_reason = "wasmtime not importable: boom"
    monkeypatch.setattr(registry, "_construct",
                        lambda n: Broken() if n == "llama.cpp" else registry._construct_default(n))
    assert main([_model(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "llama.cpp unavailable — wasmtime not importable: boom" in out
    assert "partial" in out and "X001, X002, X004, X005 not evaluated" in out
```

Append to `tests/test_report.py` (adapt to the file's existing helpers for building a model/coverage):

```python
def test_human_report_prints_agreement_line_only_when_x_ran():
    model = GgufModel(source_id="m", architecture="llama", chat_template="x")
    cov = Coverage(upstream="not_requested", families_run=["S", "X"], engines_agreed_fixtures=10)
    text = render_human(model, [], [], cov, [Jinja2Engine()])
    assert "engines agree: jinja2 and llama.cpp rendered 10 fixtures identically" in text
    cov_no_x = Coverage(upstream="not_requested", families_run=["S"])
    assert "engines agree" not in render_human(model, [], [], cov_no_x, [Jinja2Engine()])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_registry.py tests/test_cli.py tests/test_report.py -v`
Expected: FAIL — no `registry` module; `--engines` unrecognised; report strings absent.

- [ ] **Step 3: Registry and coverage fields**

```python
# src/ggufdoctor/engines/registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine

# Order matters: checks/sanity.py uses engines[0] as the transformers-reference
# engine, so jinja2 is always first and can never be deselected.
ENGINE_NAMES = ("jinja2", "llama.cpp")


@dataclass
class EngineSelection:
    engines: list[Any]
    # name -> reason, for engines the user did NOT exclude but that could not
    # be constructed. A user-requested subset never appears here: declining an
    # engine is not a coverage gap.
    unavailable: dict[str, str] = field(default_factory=dict)


def _construct_default(name: str) -> Any:
    if name == "jinja2":
        return Jinja2Engine()
    if name == "llama.cpp":
        return LlamaCppEngine()
    raise ValueError(f"unknown engine {name!r} (choose from {', '.join(ENGINE_NAMES)})")


# Indirection so tests can substitute a broken engine.
_construct = _construct_default


def select_engines(requested: list[str] | None) -> EngineSelection:
    explicit = requested is not None
    names = list(requested) if explicit else list(ENGINE_NAMES)
    for n in names:
        if n not in ENGINE_NAMES:
            raise ValueError(f"unknown engine {n!r} (choose from {', '.join(ENGINE_NAMES)})")
    if "jinja2" not in names:
        raise ValueError("jinja2 is the reference engine and cannot be deselected")
    ordered = [n for n in ENGINE_NAMES if n in names]
    selection = EngineSelection(engines=[])
    for n in ordered:
        engine = _construct(n)
        if getattr(engine, "available", True):
            selection.engines.append(engine)
        elif explicit:
            raise ValueError(f"engine {n!r} is unavailable: {engine.unavailable_reason}")
        else:
            selection.unavailable[n] = engine.unavailable_reason or "unavailable"
    return selection
```

`models.py`, on `Coverage`:

```python
    # Engines the default selection could not construct (name -> reason).
    # Distinct from a user-requested --engines subset, which is a decline.
    engines_unavailable: dict[str, str] = field(default_factory=dict)
    # Fixtures both engines rendered byte-identically when family X ran.
    engines_agreed_fixtures: int | None = None
```

- [ ] **Step 4: CLI**

In `build_parser` add:

```python
    p.add_argument("--engines", metavar="NAMES",
                   help="comma-separated engines to run (default: all available; "
                        "choose from jinja2, llama.cpp). jinja2 is always included.")
```

In `_lint_main`, replace `engines = [Jinja2Engine()]` and the check calls with:

```python
        from ggufdoctor.checks.cross_engine import X_IDS, run_cross_engine_checks
        from ggufdoctor.engines.registry import select_engines

        requested = ([n.strip() for n in args.engines.split(",") if n.strip()]
                     if args.engines else None)
        selection = select_engines(requested)   # ValueError -> "ggufdoctor: ..." exit 2 below
        engines = selection.engines
        coverage.engines_unavailable = dict(selection.unavailable)
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream})
        findings = run_sanity_checks(ctx)
        if len(engines) >= 2:
            findings += run_cross_engine_checks(ctx)
            coverage.families_run.append("X")
            coverage.engines_agreed_fixtures = ctx.stats.get("engines_agreed_fixtures")
        elif selection.unavailable:
            # X was not declined -- it could not run. That is a coverage gap.
            ctx.checks_not_evaluated.extend(X_IDS)
        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)
```

`families_run` is built by `sources.resolve` as `["S"]` or `["S", "R"]`; keep "X" in the middle by inserting it after "S" instead of appending: `coverage.families_run.insert(coverage.families_run.index("S") + 1, "X")`. Remove the now-unused `Jinja2Engine` import from `cli.py`. The `except Exception` block already turns the registry's `ValueError` into `ggufdoctor: <message>` and exit 2.

- [ ] **Step 5: Reports**

`report/human.py`: `ALL_FAMILIES = ["S", "X", "R"]`. Engine line:

```python
def _engine_label(e: Any) -> str:
    label = f"{e.name} {e.version}"
    details = []
    commit = getattr(e, "commit", None)
    if commit:
        details.append(commit[:8])
    backend = getattr(e, "backend", None)
    if backend:
        details.append(backend)
    return f"{label} ({', '.join(details)})" if details else label
```

Use it for `engine_names`. After the header line, for each `name, reason in coverage.engines_unavailable.items()` append `f"  {name} unavailable — {_visible(reason)}"`. After the findings loop and before the tail, when `"X" in coverage.families_run and coverage.engines_agreed_fixtures is not None`, append `f"  engines agree: jinja2 and llama.cpp rendered {coverage.engines_agreed_fixtures} fixtures identically"` followed by a blank line. The existing "partial" headline needs no change: an unavailable engine reaches it through `checks_not_evaluated`.

`report/json_report.py`: build each engine entry as `{"name": e.name, "version": e.version}` plus `"commit"` and `"backend"` when `getattr(e, ..., None)` is truthy; add `"engines_unavailable": coverage.engines_unavailable` and `"engines_agreed_fixtures": coverage.engines_agreed_fixtures` under `coverage`.

- [ ] **Step 6: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASS. Existing CLI tests that assert exact report text may need the new engine label; update only the label text, and only where the assertion was about the header.

- [ ] **Step 7: Commit**

```bash
git add src/ggufdoctor/engines/registry.py src/ggufdoctor/models.py src/ggufdoctor/cli.py src/ggufdoctor/report/ tests/test_registry.py tests/test_cli.py tests/test_report.py
git commit -m "feat(cli): --engines, family X wiring, engine provenance and agreement in reports

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

