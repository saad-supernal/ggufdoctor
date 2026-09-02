### Task 1: Project scaffolding and shared value types

**Files:**
- Create: `pyproject.toml`
- Create: `src/ggufdoctor/__init__.py`
- Create: `src/ggufdoctor/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Severity` (`ERROR`/`WARN`/`INFO`, str-valued), `Finding(id, severity, message, fixture=None, evidence=dict)`, `GgufModel(source_id, architecture, chat_template, tokens, bos_token_id, eos_token_id, add_bos_token, metadata)`, `RenderResult(text, error)` with `.ok`, `Coverage(upstream, families_run)`, `Fixture(name, context)`, `CheckContext(model, engines, fixtures, upstream_template, upstream_meta)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from ggufdoctor.models import Severity, Finding, RenderResult, Coverage


def test_severity_is_string_valued():
    assert Severity.ERROR.value == "error"
    assert Severity.WARN.value == "warn"
    assert Severity.INFO.value == "info"


def test_finding_defaults_are_independent():
    a = Finding(id="S001", severity=Severity.ERROR, message="x")
    b = Finding(id="S002", severity=Severity.WARN, message="y")
    a.evidence["k"] = 1
    assert b.evidence == {}, "mutable default leaked between instances"


def test_render_result_ok_reflects_error():
    assert RenderResult(text="hi", error=None).ok is True
    assert RenderResult(text=None, error="render:ValueError").ok is False


def test_coverage_records_families_run():
    c = Coverage(upstream="gated", families_run=["S"])
    assert c.upstream == "gated"
    assert c.families_run == ["S"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ggufdoctor"
version = "0.1.0"
description = "Lint chat templates embedded in GGUF files"
requires-python = ">=3.11"
dependencies = ["jinja2>=3.1"]

[project.scripts]
ggufdoctor = "ggufdoctor.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/ggufdoctor"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["network: hits the real Hugging Face API (deselected by default)"]
addopts = "-m 'not network'"
```

```python
# src/ggufdoctor/__init__.py
__version__ = "0.1.0"
```

```python
# src/ggufdoctor/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARN: 1, Severity.ERROR: 2}


@dataclass
class Finding:
    id: str
    severity: Severity
    message: str
    fixture: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GgufModel:
    source_id: str
    architecture: str | None = None
    chat_template: str | None = None
    tokens: list[str] = field(default_factory=list)
    bos_token_id: int | None = None
    eos_token_id: int | None = None
    add_bos_token: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    text: str | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Coverage:
    upstream: str
    families_run: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Fixture:
    name: str
    context: dict[str, Any]


@dataclass
class CheckContext:
    model: GgufModel
    engines: list[Any]
    fixtures: list[Fixture]
    upstream_template: str | None = None
    upstream_meta: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e . && pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ggufdoctor/__init__.py src/ggufdoctor/models.py tests/test_models.py
git commit -m "feat: project scaffolding and shared value types"
```

---

