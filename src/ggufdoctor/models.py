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
    # Engine-specific facts about how this result was produced, for reports
    # and checks that need to explain a divergence (llama.cpp: "caps" and
    # "normalized"). Empty for engines with nothing to add.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Coverage:
    upstream: str
    families_run: list[str] = field(default_factory=list)
    checks_not_evaluated: list[str] = field(default_factory=list)
    # Engines the default selection could not construct (name -> reason).
    # Distinct from a user-requested --engines subset, which is a decline.
    engines_unavailable: dict[str, str] = field(default_factory=dict)
    # Fixtures both engines rendered byte-identically when family X ran.
    engines_agreed_fixtures: int | None = None


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


@dataclass
class CheckContext:
    model: GgufModel
    engines: list[Any]
    fixtures: list[Fixture]
    upstream_template: str | None = None
    upstream_meta: dict[str, Any] = field(default_factory=dict)
    # Populated by individual checks (see checks/sanity.py S005/S006) when
    # they cannot evaluate at all due to missing or out-of-range token
    # metadata. Distinct from "found nothing wrong": this says the check
    # never got to look. Feeds Coverage.checks_not_evaluated downstream.
    checks_not_evaluated: list[str] = field(default_factory=list)
    # Facts a check family wants the report to carry that are not findings
    # (e.g. cross_engine: "engines_agreed_fixtures"). Never used to decide
    # exit codes.
    stats: dict[str, Any] = field(default_factory=dict)
