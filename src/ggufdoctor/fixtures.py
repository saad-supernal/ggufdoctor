from __future__ import annotations

import json
from importlib import resources

from ggufdoctor.models import FIXTURE_TIERS, Fixture

CORPUS_VERSION = "2"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    out = []
    for item in data["fixtures"]:
        tier = item.get("tier", "core")
        if tier not in FIXTURE_TIERS:
            raise ValueError(
                f"fixture {item.get('name')!r} has unknown tier {tier!r} "
                f"(expected one of {', '.join(FIXTURE_TIERS)})")
        out.append(Fixture(name=item["name"], context=item["context"], tier=tier))
    return out
