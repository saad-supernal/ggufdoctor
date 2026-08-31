from __future__ import annotations

import json
from importlib import resources

from ggufdoctor.models import Fixture

CORPUS_VERSION = "1"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return [Fixture(name=item["name"], context=item["context"])
            for item in data["fixtures"]]
