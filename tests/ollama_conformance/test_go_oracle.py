"""Python selector and committed goldens vs Ollama's real template package.

Run with:
    .venv/bin/python -m pytest -m ollama_conformance tests/ollama_conformance -v
"""
import pathlib
import random

import pytest

from ggufdoctor.ollama import CUTOFF, load_goldens, load_index, pin, select
from tests.ollama_conformance import gotools

pytestmark = pytest.mark.ollama_conformance
DATA = pathlib.Path(__file__).parent.parent / "data" / "templates"
VENDORED = sorted(p for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))


@pytest.fixture(scope="module")
def src():
    s = gotools.ollama_src()
    gotools.ensure_replace(s)
    return s


def _synthetic_variants():
    """Near-threshold probes around every index entry: truncations that land
    exactly at 59/60/99/100/101 edits, plus seeded random substitutions.
    These exercise the band and the strict cutoff where a port would drift."""
    rng = random.Random(20260904)
    out = []
    for _, tpl in load_index():
        for k in (0, 1, 59, 60, 99, 100, 101, 150):
            if k <= len(tpl):
                out.append(tpl[:-k] if k else tpl)
        chars = list(tpl)
        for k in (30, 70, 99, 100):
            mutated = chars[:]
            for pos in rng.sample(range(len(chars)), min(k, len(chars))):
                mutated[pos] = "~"
            out.append("".join(mutated))
    return out


def test_python_selector_agrees_with_real_template_named(src):
    inputs = [p.read_text(encoding="utf-8") for p in VENDORED] + _synthetic_variants()
    go = gotools.run_named(inputs, src)
    assert len(go) == len(inputs)
    for s, g in zip(inputs, go):
        mine = select(s)
        assert mine.name == g["name"], (mine, g, s[:80])
        if g["name"] is not None:
            assert g["distance"] < CUTOFF and mine.distance == g["distance"], (mine, g)
        else:
            assert g["distance"] >= CUTOFF and mine.distance is None, (mine, g)


def test_committed_goldens_are_what_ollama_renders_at_the_pin(src):
    fresh = gotools.run_goldengen(src, pin().commit)
    committed = load_goldens()
    assert fresh["ollama_commit"] == committed["ollama_commit"]
    assert fresh["corpus_version"] == committed["corpus_version"]
    assert fresh["renders"] == committed["renders"], "goldens.json is stale: run engine/ollama/regen-goldens.sh"
