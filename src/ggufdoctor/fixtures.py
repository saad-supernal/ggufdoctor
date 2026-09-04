from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from ggufdoctor.models import CORPUS_VERSION_DEFAULT, FIXTURE_TIERS, Fixture

# Alias, not a redeclaration: models.py cannot import this module (fixtures.py
# already imports models.py, and models.CheckContext.corpus_version needs a
# default before fixtures.py has run), so the bundled corpus's version is
# defined once in models.py and mirrored here under its historical name.
CORPUS_VERSION = CORPUS_VERSION_DEFAULT


@dataclass(frozen=True)
class Corpus:
    version: str
    fixtures: list[Fixture]
    path: str | None   # None for the bundled corpus

    @property
    def custom(self) -> bool:
        return self.path is not None


def _parse_fixtures(data: dict) -> list[Fixture]:
    out = []
    for item in data["fixtures"]:
        tier = item.get("tier", "core")
        if tier not in FIXTURE_TIERS:
            raise ValueError(
                f"fixture {item.get('name')!r} has unknown tier {tier!r} "
                f"(expected one of {', '.join(FIXTURE_TIERS)})")
        out.append(Fixture(name=item["name"], context=item["context"], tier=tier))
    return out


def load_corpus(path: str | None = None) -> Corpus:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return Corpus(version=data.get("version", "unversioned"),
                  fixtures=_parse_fixtures(data), path=path)


def load_fixtures(path: str | None = None) -> list[Fixture]:
    return load_corpus(path).fixtures
