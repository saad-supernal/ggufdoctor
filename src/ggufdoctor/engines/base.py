from __future__ import annotations

from typing import Any, Protocol

from ggufdoctor.models import RenderResult


class Engine(Protocol):
    name: str
    version: str

    def render(self, template: str, context: dict[str, Any]) -> RenderResult: ...
