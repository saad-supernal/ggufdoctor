### Task 8: Vendored real templates and complete-finding-set tests

**Files:**
- Create: `tests/data/templates/SOURCES.md`, ten `tests/data/templates/<org>__<repo>.jinja` + `.json` pairs (+ `.upstream.jinja` where saved)
- Create: `tests/data/__init__.py` (empty; keeps pytest collection simple)
- Test: `tests/test_real_templates.py`

**Interfaces:**
- Consumes: `survey --save-templates` (Task 7), both engines, `run_sanity_checks`, `run_cross_engine_checks`.
- Produces: `tests/data/templates/` as the offline real-template corpus that later tasks (conformance) iterate.

This task needs the network once, to fetch. The tests it leaves behind do not.

- [ ] **Step 1: Fetch candidates**

```bash
mkdir -p /tmp/gd-templates
.venv/bin/ggufdoctor survey --top 80 --per-org 1 --save-templates /tmp/gd-templates --out /tmp/gd-templates-survey.json > /dev/null
ls /tmp/gd-templates | wc -l
```

Pick exactly ten by this rule, in download order from the survey output: the first repo for each **distinct `architecture`** in its sidecar, skipping any sidecar whose `gated` is truthy or whose `license` is null, until ten are chosen. Copy each `.jinja`, `.json` and (if present) `.upstream.jinja` into `tests/data/templates/`. Write `SOURCES.md` as a table: repo, architecture, revision, licence, fetched-at, upstream repo (or "—"). State at the top that the files are unmodified copies of published model-repo content included as test data under each repo's own licence.

- [ ] **Step 2: Write the test scaffold (failing)**

```python
# tests/test_real_templates.py
"""Complete S + X finding sets on ten real, vendored templates.

Every expected finding below is a true positive with a stated reason. If a
change to the checks alters any set, this test fails loudly -- that is the
point. Never narrow an assertion to a single id to make it pass.
"""
import json
import pathlib

import pytest

from ggufdoctor.checks.cross_engine import run_cross_engine_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

DATA = pathlib.Path(__file__).parent / "data" / "templates"


def load(slug):
    tpl = (DATA / f"{slug}.jinja").read_text(encoding="utf-8")
    side = json.loads((DATA / f"{slug}.json").read_text(encoding="utf-8"))
    return tpl, side


def run(slug):
    tpl, side = load(slug)
    tokens = [side["bos_token"] or "<s>", side["eos_token"] or "</s>"]
    model = GgufModel(source_id=side["repo"], architecture=side["architecture"],
                      chat_template=tpl, tokens=tokens, bos_token_id=0, eos_token_id=1,
                      add_bos_token=None)  # HF metadata does not carry add_bos_token
    ctx = CheckContext(model=model, engines=[Jinja2Engine(), LlamaCppEngine()],
                       fixtures=load_fixtures())
    findings = run_sanity_checks(ctx) + run_cross_engine_checks(ctx)
    def fixtures_of(f):
        return tuple(f.evidence.get("fixtures") or ((f.fixture,) if f.fixture else ()))
    return ({(f.id, f.severity, fixtures_of(f)) for f in findings},
            sorted(ctx.checks_not_evaluated), ctx.stats)


def test_every_vendored_template_has_a_sidecar_and_an_expectation():
    slugs = sorted(p.stem for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))
    assert len(slugs) == 10
    assert set(slugs) == set(EXPECTED), "add an EXPECTED entry for every vendored template"
    for s in slugs:
        assert (DATA / f"{s}.json").exists()


# slug -> (expected finding set, expected checks_not_evaluated)
# Fill in from a first run, then JUSTIFY EACH LINE by reading the template.
EXPECTED = {
    # "Qwen__Qwen2.5-3B-Instruct-GGUF": (
    #     {
    #         # S006 skipped: add_bos_token unknown from HF metadata.
    #     },
    #     ["S006"],
    # ),
}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_complete_finding_set(slug):
    found, not_evaluated, stats = run(slug)
    expected_findings, expected_not_evaluated = EXPECTED[slug]
    assert found == expected_findings
    assert not_evaluated == expected_not_evaluated
    assert stats["engines_agreed_fixtures"] >= 1, "both engines must agree on at least one fixture"
```

- [ ] **Step 3: Run once to see the real sets**

Run: `.venv/bin/python -m pytest tests/test_real_templates.py -v`
Expected: `test_every_vendored_template_has_a_sidecar_and_an_expectation` FAILS (EXPECTED empty).

Then for each slug run `.venv/bin/python -c "from tests.test_real_templates import run; print(run('<slug>'))"` and fill `EXPECTED`. For every finding, add a comment with the reason, in the same style as `tests/test_checks_sanity.py`'s Mistral test: quote the template construct that produces it. Expected shapes, from the spike: S006 in `not_evaluated` everywhere (no `add_bos_token`); S003 INFO author declines on `system_user`/`tool_roundtrip` for templates that `raise_exception` on those roles; S003 INFO extended-tier render errors on `typed_content` for string-concatenating templates; possibly S007 INFO; **no X001/X005 on any of the ten** — if one appears, read the diff: it is either a real engine divergence worth a line in the spike doc, or a bug in Task 5. X002 INFO on `typed_content` for string-only templates is expected and is not a bug.

- [ ] **Step 4: Run and commit**

```bash
.venv/bin/python -m pytest tests/test_real_templates.py -q
git add tests/data tests/test_real_templates.py
git commit -m "test: vendor ten real chat templates with provenance and pin their complete finding sets

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

