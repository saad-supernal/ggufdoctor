### Task 12: Survey subcommand

**Files:**
- Create: `src/ggufdoctor/survey.py`
- Modify: `src/ggufdoctor/cli.py`
- Test: `tests/test_survey.py`

**Interfaces:**
- Consumes: `HfClient` from Task 7; checks from Tasks 6/8; `Coverage` from Task 1
- Produces: `sample_repos(client, top, per_org) -> list[dict]`; `survey(client, top, per_org) -> dict`; `to_markdown(result) -> str`. CLI gains `ggufdoctor survey --top N --per-org N --out PATH --markdown PATH`.

The aggregate must include `comparable`, `divergent`, `divergent_pct`, `download_weighted_pct`, `publishers_affected`, `publishers_total`, and a `coverage_gaps` breakdown keyed by reason. `per_org` defaults to `2` and appears in the output so the methodology travels with the number.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_survey.py
from ggufdoctor.survey import sample_repos, survey, to_markdown


class FakeClient:
    """Two publishers, three repos; one repo diverges from upstream."""

    def list_gguf_models(self, skip, limit):
        if skip:
            return []
        return [{"id": "orgA/one", "downloads": 100},
                {"id": "orgA/two", "downloads": 50},
                {"id": "orgA/three", "downloads": 25},
                {"id": "orgB/one", "downloads": 10}]

    def model_info(self, repo_id):
        tpl = "{% for m in messages %}{{ m['content'] }}{% endfor %}"
        if repo_id == "orgA/one":
            tpl += "DIVERGES"
        return {"gguf": {"architecture": "llama", "chat_template": tpl},
                "cardData": {"base_model": "up/stream"}}

    def base_model_of(self, info):
        return (info.get("cardData") or {}).get("base_model")

    def upstream_template(self, repo):
        return "{% for m in messages %}{{ m['content'] }}{% endfor %}", "ok"


def test_per_org_cap_limits_sample():
    repos = sample_repos(FakeClient(), top=10, per_org=2)
    assert [r["id"] for r in repos] == ["orgA/one", "orgA/two", "orgB/one"]


def test_survey_reports_divergence_and_methodology():
    r = survey(FakeClient(), top=10, per_org=2)
    assert r["aggregate"]["comparable"] == 3
    assert r["aggregate"]["divergent"] == 1
    assert r["aggregate"]["per_org"] == 2
    assert r["aggregate"]["publishers_total"] == 2
    assert r["aggregate"]["publishers_affected"] == 1


def test_download_weighting_uses_downloads():
    r = survey(FakeClient(), top=10, per_org=2)
    # divergent repo has 100 of 160 total downloads across comparable repos
    assert round(r["aggregate"]["download_weighted_pct"], 1) == 62.5


def test_markdown_includes_caveats():
    md = to_markdown(survey(FakeClient(), top=10, per_org=2))
    assert "per-org cap" in md
    assert "coverage" in md.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_survey.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.survey'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/ggufdoctor/hf.py`:

```python
    def list_gguf_models(self, skip: int, limit: int = 100) -> list[dict[str, Any]]:
        url = (f"{API}?filter=gguf&sort=downloads&direction=-1"
               f"&limit={limit}&skip={skip}")
        return json.loads(self._open(url))
```

```python
# src/ggufdoctor/survey.py
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel

COMPARABLE = {"identical", "cosmetic_only", "output_differs"}


def sample_repos(client: Any, top: int, per_org: int) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen: dict[str, int] = defaultdict(int)
    skip = 0
    while len(picked) < top and skip < top * 20:
        batch = client.list_gguf_models(skip=skip, limit=100)
        if not batch:
            break
        for m in batch:
            org = m["id"].split("/")[0]
            if seen[org] >= per_org:
                continue
            seen[org] += 1
            picked.append({"id": m["id"], "downloads": m.get("downloads", 0)})
            if len(picked) >= top:
                break
        skip += 100
    return picked


def _examine(client: Any, repo: dict[str, Any], engine: Any,
             fixtures: list[Any]) -> dict[str, Any]:
    rec = {"id": repo["id"], "org": repo["id"].split("/")[0],
           "downloads": repo["downloads"], "status": None}
    info = client.model_info(repo["id"])
    gg = (info or {}).get("gguf") or {}
    tpl = gg.get("chat_template")
    base = client.base_model_of(info)
    if not base:
        rec["status"] = "no_base_model"
        return rec
    upstream, why = client.upstream_template(base)
    if why != "ok":
        rec["status"] = {"gated": "upstream_gated",
                         "genuinely_absent": "non_chat_model"}.get(
                             why, "upstream_fetch_failed")
        return rec
    if not tpl:
        rec["status"] = "missing_template"
        return rec

    model = GgufModel(source_id=repo["id"], architecture=gg.get("architecture"),
                      chat_template=tpl)
    ctx = CheckContext(model=model, engines=[engine], fixtures=fixtures,
                       upstream_template=upstream, upstream_meta={"coverage": "ok"})
    findings = [f for f in run_reference_checks(ctx) if f.id == "R001"]
    if findings:
        rec["status"] = "output_differs"
        rec["fixtures"] = sorted({f.fixture for f in findings if f.fixture})
    elif tpl == upstream:
        rec["status"] = "identical"
    else:
        rec["status"] = "cosmetic_only"
    return rec


def survey(client: Any, top: int, per_org: int) -> dict[str, Any]:
    engine = Jinja2Engine()
    fixtures = load_fixtures()
    repos = sample_repos(client, top, per_org)
    records = [_examine(client, r, engine, fixtures) for r in repos]

    comparable = [r for r in records if r["status"] in COMPARABLE]
    divergent = [r for r in comparable if r["status"] == "output_differs"]
    dl_total = sum(r["downloads"] for r in comparable) or 1
    dl_div = sum(r["downloads"] for r in divergent)

    return {
        "records": records,
        "aggregate": {
            "sampled": len(records),
            "per_org": per_org,
            "comparable": len(comparable),
            "divergent": len(divergent),
            "divergent_pct": 100 * len(divergent) / len(comparable) if comparable else 0.0,
            "download_weighted_pct": 100 * dl_div / dl_total,
            "publishers_total": len({r["org"] for r in comparable}),
            "publishers_affected": len({r["org"] for r in divergent}),
            "coverage_gaps": dict(Counter(
                r["status"] for r in records if r["status"] not in COMPARABLE)),
        },
    }


def to_markdown(result: dict[str, Any]) -> str:
    a = result["aggregate"]
    lines = [
        "# GGUF chat-template survey",
        "",
        f"- Sampled: **{a['sampled']}** repos (per-org cap: {a['per_org']})",
        f"- Comparable chat models: **{a['comparable']}**",
        f"- Render-different from upstream: **{a['divergent']}** "
        f"({a['divergent_pct']:.1f}%)",
        f"- Download-weighted: **{a['download_weighted_pct']:.1f}%**",
        f"- Publishers affected: **{a['publishers_affected']}** of "
        f"{a['publishers_total']}",
        "",
        "## Coverage gaps",
        "",
        "Repos excluded from the denominator, by reason:",
        "",
    ]
    for reason, n in sorted(a["coverage_gaps"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{reason}`: {n}")
    lines += [
        "",
        "The per-org cap matters: without it the download ranking is dominated by "
        "a small number of publishers and the figure is not representative.",
    ]
    return "\n".join(lines)
```

Modify `src/ggufdoctor/cli.py` — replace the body of `main` with a subcommand dispatch, keeping the single-target path unchanged:

```python
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "survey":
        return _survey_main(argv[1:])
    return _lint_main(argv)


def _survey_main(argv: list[str]) -> int:
    import json as _json

    from ggufdoctor.hf import HfClient
    from ggufdoctor.survey import survey, to_markdown

    p = argparse.ArgumentParser(prog="ggufdoctor survey")
    p.add_argument("--top", type=int, default=200)
    p.add_argument("--per-org", type=int, default=2)
    p.add_argument("--out", metavar="PATH")
    p.add_argument("--markdown", metavar="PATH")
    args = p.parse_args(argv)

    try:
        result = survey(HfClient(), top=args.top, per_org=args.per_org)
    except Exception as e:
        print(f"ggufdoctor survey: {e}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump(result, f, indent=1)
    md = to_markdown(result)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0
```

Rename the existing `main` body to `_lint_main(argv)`, taking `argv` and calling `build_parser().parse_args(argv)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_survey.py tests/test_cli.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/survey.py src/ggufdoctor/hf.py src/ggufdoctor/cli.py tests/test_survey.py
git commit -m "feat: survey subcommand reproducing the ecosystem measurement"
```

---

## Deliberately deferred from this plan

These spec items belong to later plans and are **not** gaps to fix here:

- `--engines` and `--runtime` flags — meaningless with one engine; land with v0.2/v0.3.
- Engine conformance suite (bundled WASM vs real llama.cpp/Ollama) — requires the
  engines it validates; lands with v0.2.
- **Vendored real templates as test data** — the spec calls for these so reference-mode
  tests run offline. v0.1's reference tests use synthetic templates, which is
  sufficient to test the *logic*. Vendoring real ones is a v0.2 task, and should
  reuse templates already captured in `docs/research/2026-08-31-survey-raw.json`.

## Definition of done for v0.1

- [ ] `pytest` green with no network access.
- [ ] `ggufdoctor path/to/model.gguf` runs fully offline and issues zero HTTP requests (asserted by `test_local_resolve_is_offline`).
- [ ] `ggufdoctor org/repo` reports findings plus an explicit coverage line.
- [ ] `ggufdoctor survey --top 400 --per-org 2` reproduces a figure comparable to the 15.1% recorded in `docs/research/`.
- [ ] Every finding id in the spec (`S001`–`S008`, `R001`–`R004`) has at least one test.
