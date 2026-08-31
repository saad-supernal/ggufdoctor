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
