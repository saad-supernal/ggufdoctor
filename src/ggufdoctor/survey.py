from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ggufdoctor.checks.reference import any_fixture_renders_both_sides, run_reference_checks
from ggufdoctor.checks.sanity import NON_CHAT_ARCHITECTURES
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel

COMPARABLE = {"identical", "cosmetic_only", "output_differs"}

# Each of hf.upstream_template's four non-"ok" reasons gets its own
# coverage_gaps key. Collapsing "not_found" (the upstream repo no longer
# exists) and "fetch_error" (we couldn't reach it, for some other reason)
# into one bucket would erase a real, citable result -- "the upstream is
# gone" is a materially different finding from "we hit a transient error"
# even though neither one shrinks the comparable denominator.
#
# "genuinely_absent" maps to "upstream_has_no_template", not "non_chat_
# model": all we observed is that the upstream repo's tokenizer_config.json
# (and chat_template.json) have no chat_template field. That is equally
# consistent with a pretrain base model that was never meant to be a chat
# model -- calling it "non_chat_model" asserts an inference the data doesn't
# support.
UPSTREAM_REASON_TO_GAP = {
    "gated": "upstream_gated",
    "genuinely_absent": "upstream_has_no_template",
    "not_found": "upstream_not_found",
    "fetch_error": "upstream_fetch_error",
}

# Hugging Face's own pipeline_tag/tags, not architecture-name guessing, is
# the evidence used to exclude ASR/TTS repos that happen to report a
# generic or shared architecture string (e.g. unslothai/Qwen3-ASR-* reports
# `qwen3vl`, a real architecture for actual chat models -- adding it to
# NON_CHAT_ARCHITECTURES would incorrectly exclude those). A speech
# recognition or text-to-speech pipeline is definitionally not a chat
# model, and pipeline_tag/tags are published, citable facts about the repo
# rather than a guess from its architecture name.
NON_CHAT_PIPELINE_TAGS = {"automatic-speech-recognition", "text-to-speech"}


def _is_non_chat_pipeline(info: dict[str, Any]) -> bool:
    pipeline_tag = str(info.get("pipeline_tag") or "").lower()
    if pipeline_tag in NON_CHAT_PIPELINE_TAGS:
        return True
    tags = {str(t).lower() for t in (info.get("tags") or [])}
    return bool(tags & NON_CHAT_PIPELINE_TAGS)


def _sample_repos(client: Any, top: int,
                   per_org: int) -> tuple[list[dict[str, Any]], bool]:
    """Collect up to `top` repos, capped at `per_org` per organisation.

    Returns `(picked, truncated)`. A failure inside `list_gguf_models` stops
    pagination immediately -- no retries -- but keeps whatever was already
    collected rather than discarding the whole run; `truncated` is True in
    that case so callers can say the sample is partial rather than complete.
    """
    picked: list[dict[str, Any]] = []
    seen: dict[str, int] = defaultdict(int)
    skip = 0
    truncated = False
    while len(picked) < top and skip < top * 20:
        try:
            batch = client.list_gguf_models(skip=skip, limit=100)
        except Exception:
            truncated = True
            break
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
    return picked, truncated


def sample_repos(client: Any, top: int, per_org: int) -> list[dict[str, Any]]:
    picked, _truncated = _sample_repos(client, top, per_org)
    return picked


def _examine(client: Any, repo: dict[str, Any], engine: Any,
             fixtures: list[Any]) -> dict[str, Any]:
    rec = {"id": repo["id"], "org": repo["id"].split("/")[0],
           "downloads": repo["downloads"], "status": None}
    try:
        info = client.model_info(repo["id"])
        gg = (info or {}).get("gguf") or {}
        tpl = gg.get("chat_template")
        arch = gg.get("architecture")
        if (arch or "").lower() in NON_CHAT_ARCHITECTURES:
            # ASR/TTS/embedding architectures are not chat models at all --
            # counting them as "no template" or (worse) as divergent would
            # distort the denominator with repos that were never comparable
            # in the first place. They get their own coverage_gaps reason.
            rec["status"] = "non_chat_architecture"
            return rec
        if _is_non_chat_pipeline(info or {}):
            # Same reasoning as above, evidenced by pipeline_tag/tags
            # instead of architecture -- see NON_CHAT_PIPELINE_TAGS.
            rec["status"] = "non_chat_pipeline_tag"
            return rec
        base = client.base_model_of(info)
        if not base or base.lower() == repo["id"].lower():
            # A repo can't be its own upstream: comparing a template against
            # itself always scores "identical" and would silently inflate
            # both the sample size and the (fake) agreement rate.
            rec["status"] = "no_base_model"
            return rec
        upstream, why = client.upstream_template(base)
        if why != "ok":
            rec["status"] = UPSTREAM_REASON_TO_GAP.get(why, "upstream_fetch_error")
            return rec
        if not tpl:
            rec["status"] = "missing_template"
            return rec

        model = GgufModel(source_id=repo["id"], architecture=arch, chat_template=tpl)
        ctx = CheckContext(model=model, engines=[engine], fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": "ok"})
        findings = [f for f in run_reference_checks(ctx) if f.id == "R001"]
        if findings:
            rec["status"] = "output_differs"
            rec["fixtures"] = sorted({f.fixture for f in findings if f.fixture})
        elif tpl == upstream:
            rec["status"] = "identical"
        elif not any_fixture_renders_both_sides(ctx):
            # Neither side ever rendered successfully on the same fixture,
            # so "the templates render the same thing" was never actually
            # observed -- only that the two source strings differ. Reporting
            # that as "cosmetic_only" would publish "the rewrite changes
            # nothing the model sees" about a repo this tool never
            # successfully rendered at all.
            rec["status"] = "unrenderable"
        else:
            rec["status"] = "cosmetic_only"
        return rec
    except Exception:
        # One repo's API call blowing up (timeout, malformed response, a
        # 500 from the Hub) must not take down a --top 400 survey that has
        # already done hundreds of other calls' worth of work. Record it as
        # its own coverage-gap reason -- it never counts as comparable, let
        # alone divergent -- and let the rest of the sample proceed.
        rec["status"] = "examine_error"
        return rec


def survey(client: Any, top: int, per_org: int) -> dict[str, Any]:
    engine = Jinja2Engine()
    fixtures = load_fixtures()
    repos, truncated = _sample_repos(client, top, per_org)
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
            "truncated": truncated,
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
    ]
    if a.get("truncated"):
        lines.append(
            "> **Truncated sample:** pagination stopped early after an API "
            "failure. The figures below cover only the repos collected "
            "before that point -- do not quote this run as a complete "
            "survey of the requested sample size.")
        lines.append("")
    lines += [
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
