import pathlib
import random
import time

import pytest

from ggufdoctor import ollama
from ggufdoctor.ollama import CUTOFF, Selection, bounded_levenshtein, load_index, pin, select

DATA = pathlib.Path(__file__).parent / "data" / "templates"
VENDORED = sorted(p for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))


def naive_levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def test_bounded_levenshtein_is_exact_below_the_cut_and_saturates_above():
    rng = random.Random(7)
    alphabet = "ab{}%|<>\n "
    for _ in range(300):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        b = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        cut = rng.randint(1, 45)
        exact = naive_levenshtein(a, b)
        got = bounded_levenshtein(a, b, cut)
        assert got == (exact if exact < cut else cut), (a, b, cut)


def test_bounded_levenshtein_handles_empty_and_identical():
    assert bounded_levenshtein("", "", 100) == 0
    assert bounded_levenshtein("abc", "abc", 100) == 0
    assert bounded_levenshtein("", "abcd", 100) == 4
    assert bounded_levenshtein("", "x" * 100, 100) == 100


def test_pin_matches_the_data_file():
    p = pin()
    assert p.commit == "b79067b0db7417f20108363bc22adb97f35c966a"
    assert p.short == "b79067b0" and p.release == "v0.33.2"


def test_index_is_in_file_order_with_37_entries():
    index = load_index()
    assert len(index) == 37
    assert index[0][0] == "chatml" and index[0][1].startswith("{% if messages[0]['role'] == 'system' %}")


def test_exact_index_entry_is_recognised_at_distance_zero():
    for name, tpl in load_index():
        s = select(tpl)
        assert s == Selection(name, 0), name
        assert s.recognised and s.confident


def test_ties_go_to_the_first_index_entry():
    # Two entries with the same template text: template.Named keeps the first
    # strictly-smaller score, so the earlier entry wins.
    index = [("alpha", "same text"), ("beta", "same text")]
    assert select("same text", index).name == "alpha"


def test_cutoff_is_strict_and_confidence_band_is_sixty():
    base = "x" * 300
    index = [("t", base)]
    assert select(base[:-59], index) == Selection("t", 59)
    assert select(base[:-59], index).confident
    assert select(base[:-60], index) == Selection("t", 60)
    assert not select(base[:-60], index).confident
    assert select(base[:-99], index) == Selection("t", 99)
    assert select(base[:-100], index) == Selection(None, None)
    assert select(base + "y" * 100, index) == Selection(None, None)


def test_length_prefilter_never_changes_the_answer():
    # A candidate whose length differs by >= CUTOFF cannot be within the cutoff;
    # the prefilter is an optimisation and must agree with the full comparison.
    index = [("short", "ab"), ("long", "z" * 150)]
    assert select("ab" + "c" * 120, index) == Selection(None, None)
    assert select("z" * 149, index) == Selection("long", 1)


def test_the_ten_vendored_templates_match_real_ollama():
    # Ground truth from docs/research/2026-09-03-ollama-spike.md §5, produced by
    # running Ollama's real template.Named at the pinned commit: exactly one of
    # the ten is recognised (HyperCLOVAX, a verbatim ChatML copy, distance 0).
    # The other nine are thousands of edits away (nearest miss: 194); the
    # selector proves only ">= 100" for them, which is Selection(None, None).
    picks = {p.stem: select(p.read_text(encoding="utf-8")) for p in VENDORED}
    assert len(picks) == 10
    hyper = next(k for k in picks if k.startswith("rippertnt__HyperCLOVAX"))
    assert picks.pop(hyper) == Selection("chatml", 0)
    assert all(s == Selection(None, None) for s in picks.values()), picks


def test_selection_over_all_vendored_templates_is_fast():
    t0 = time.perf_counter()
    for p in VENDORED:
        select(p.read_text(encoding="utf-8"))
    assert time.perf_counter() - t0 < 2.0


def test_template_source_and_references_tools():
    assert ollama.template_source("chatml").startswith("{{- range .Messages }}")
    assert "\r" not in ollama.template_source("chatml")
    assert ollama.references_tools("command-r") is True
    assert ollama.references_tools("chatml") is False
    with pytest.raises(FileNotFoundError):
        ollama.template_source("no-such-template")
