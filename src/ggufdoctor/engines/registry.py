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
