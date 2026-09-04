"""Ollama's chat-template registry, reproduced as data.

Ollama has no Jinja-to-Go converter. `ollama create` runs the GGUF's Jinja
source through template.Named (template/template.go): a brute-force
Levenshtein distance against the 37 strings in template/index.json, keeping
the strictly smallest score and accepting it only when `score < 100`. On a hit
the curated `<name>.gotmpl` replaces the template; on a miss (the common case)
the GGUF's own Jinja is rendered by llama-server -- the engine v0.2 embeds.
Evidence: docs/research/2026-09-03-ollama-spike.md.

`select` is that loop, exactly, over the vendored index. The distance is
computed with a banded DP that is exact below the cutoff and saturates at it:
the decision only ever needs "is it < 100?", and the band plus a length
prefilter turn a 212 ms Go computation into ~10 ms of Python per template.
Agreement with the real `template.Named` is asserted by
tests/ollama_conformance (Go, CI); the ten vendored real templates are pinned
in tests/test_ollama_select.py.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

CUTOFF = 100
CONFIDENT_BELOW = 60


@dataclass(frozen=True)
class Pin:
    commit: str
    release: str
    fetched: str
    index_last_commit: str
    index_last_changed: str

    @property
    def short(self) -> str:
        return self.commit[:8]


@dataclass(frozen=True)
class Selection:
    name: str | None
    distance: int | None

    @property
    def recognised(self) -> bool:
        return self.name is not None

    @property
    def confident(self) -> bool:
        return self.distance is not None and self.distance < CONFIDENT_BELOW


def _data(name: str):
    return resources.files("ggufdoctor.ollama_data").joinpath(name)


@functools.lru_cache(maxsize=1)
def pin() -> Pin:
    return Pin(**json.loads(_data("OLLAMA_PIN").read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=1)
def load_index() -> list[tuple[str, str]]:
    raw = json.loads(_data("index.json").read_text(encoding="utf-8"))
    return [(e["name"], e["template"]) for e in raw]


@functools.lru_cache(maxsize=1)
def load_goldens() -> dict[str, Any]:
    return json.loads(_data("goldens.json").read_text(encoding="utf-8"))


def template_source(name: str) -> str:
    path = _data(f"{name}.gotmpl")
    if not path.is_file():
        raise FileNotFoundError(f"no vendored Ollama template named {name!r}")
    # template.go normalises line endings when it loads the embedded files.
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def references_tools(name: str) -> bool:
    return ".Tools" in template_source(name)


def bounded_levenshtein(a: str, b: str, cut: int) -> int:
    """Levenshtein distance if it is below `cut`, else exactly `cut`.

    Ukkonen band: only cells within `cut` of the diagonal can hold a value
    below `cut`, and once a whole row's minimum reaches `cut` no later row can
    drop below it, so the search stops early. Distances are over code points,
    as agnivade/levenshtein computes over runes.
    """
    la, lb = len(a), len(b)
    if abs(la - lb) >= cut:
        return cut
    if la > lb:
        a, b, la, lb = b, a, lb, la
    prev = [min(j, cut) for j in range(lb + 1)]
    for i in range(1, la + 1):
        cur = [cut] * (lb + 1)
        cur[0] = min(i, cut)
        lo, hi = max(1, i - cut), min(lb, i + cut)
        ca = a[i - 1]
        best = cur[0]
        for j in range(lo, hi + 1):
            c = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != b[j - 1]))
            if c > cut:
                c = cut
            cur[j] = c
            if c < best:
                best = c
        if best >= cut:
            return cut
        prev = cur
    return min(prev[lb], cut)


def select(template_source: str, index: list[tuple[str, str]] | None = None) -> Selection:
    """The entry template.Named would return for this Jinja source, or none.

    Iterates the index in file order and keeps a strictly smaller distance, so
    ties resolve to the earlier entry exactly as the Go loop does.
    """
    best_name: str | None = None
    best = CUTOFF
    for name, candidate in load_index() if index is None else index:
        if abs(len(template_source) - len(candidate)) >= CUTOFF:
            continue
        d = bounded_levenshtein(template_source, candidate, CUTOFF)
        if d < best:
            best, best_name = d, name
    if best_name is None:
        return Selection(None, None)
    return Selection(best_name, best)
