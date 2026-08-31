from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.checks.sanity import NON_CHAT_ARCHITECTURES
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
    arch = gg.get("architecture")
    if arch in NON_CHAT_ARCHITECTURES:
        # ASR/TTS/embedding architectures are not chat models at all --
        # counting them as "no template" or (worse) as divergent would
        # distort the denominator with repos that were never comparable in
        # the first place. They get their own coverage_gaps reason instead.
        rec["status"] = "non_chat_architecture"
        return rec
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

    model = GgufModel(source_id=repo["id"], architecture=arch, chat_template=tpl)
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
