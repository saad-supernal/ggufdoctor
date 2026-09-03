from __future__ import annotations

import datetime
import json
import os
from collections import Counter, defaultdict
from typing import Any

from ggufdoctor.checks.reference import any_fixture_renders_both_sides, run_reference_checks
from ggufdoctor.checks.sanity import NON_CHAT_ARCHITECTURES
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import CORPUS_VERSION, load_fixtures
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

# A repo recorded as "examine_error" contributes to neither comparable nor
# divergent -- it just vanishes from both. Below this fraction of the
# sample, that is ordinary background noise (a genuine timeout, a malformed
# response). Above it, the comparable/divergent percentages were measured
# over a sample that is missing a meaningful chunk of what it was supposed
# to cover, and Hugging Face rate-limiting the extra Hub calls a survey
# makes is a real, observed way to get there quietly: a live --top 400 run
# once returned 75/400 = 18.75% examine_error, entirely rate-limiting, with
# no other symptom -- the comparable/divergent figures still came out
# looking like ordinary numbers. See final-fix-c.
UNRELIABLE_EXAMINE_ERROR_FRACTION = 0.05


def _is_non_chat_pipeline(info: dict[str, Any]) -> bool:
    pipeline_tag = str(info.get("pipeline_tag") or "").lower()
    if pipeline_tag in NON_CHAT_PIPELINE_TAGS:
        return True
    tags = {str(t).lower() for t in (info.get("tags") or [])}
    return bool(tags & NON_CHAT_PIPELINE_TAGS)


def _safe_model_info(client: Any, repo_id: str) -> dict[str, Any]:
    """client.model_info(repo_id), or {} if the lookup fails.

    This is purely an extra evidence-gathering call on top of the
    upstream-template fetch _examine already makes -- if the upstream repo
    is gated, gone, or otherwise unreachable, that is upstream_template's
    reason to report, not a new failure mode invented here. {} makes
    _is_non_chat_pipeline report False, which just falls through to the
    normal upstream_template call and its existing reason-handling.
    """
    try:
        return client.model_info(repo_id) or {}
    except Exception:
        return {}


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


def _slug(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def _save_template(save_dir: str, repo_id: str, info: dict[str, Any], tpl: str,
                   base: str | None) -> None:
    os.makedirs(save_dir, exist_ok=True)
    slug = _slug(repo_id)
    gg = (info or {}).get("gguf") or {}
    with open(os.path.join(save_dir, f"{slug}.jinja"), "w", encoding="utf-8") as f:
        f.write(tpl)
    sidecar = {
        "repo": repo_id,
        "revision": (info or {}).get("sha"),
        "fetched_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "license": ((info or {}).get("cardData") or {}).get("license"),
        "gated": (info or {}).get("gated"),
        "architecture": gg.get("architecture"),
        "bos_token": gg.get("bos_token"),
        "eos_token": gg.get("eos_token"),
        "base_model": base,
        "upstream_saved": False,
    }
    with open(os.path.join(save_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=1)
        f.write("\n")


def _save_upstream(save_dir: str, repo_id: str, upstream: str) -> None:
    slug = _slug(repo_id)
    with open(os.path.join(save_dir, f"{slug}.upstream.jinja"), "w", encoding="utf-8") as f:
        f.write(upstream)
    path = os.path.join(save_dir, f"{slug}.json")
    with open(path, encoding="utf-8") as f:
        sidecar = json.load(f)
    sidecar["upstream_saved"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=1)
        f.write("\n")


def _examine(client: Any, repo: dict[str, Any], engine: Any,
             fixtures: list[Any], save_dir: str | None = None) -> dict[str, Any]:
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
        if save_dir and tpl:
            _save_template(save_dir, repo["id"], info, tpl, base)
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
        if save_dir and tpl:
            _save_upstream(save_dir, repo["id"], upstream)
        if not tpl:
            rec["status"] = "missing_template"
            return rec

        # The GGUF-side check above tests the GGUF repo's own pipeline_tag/
        # tags -- but a GGUF repo built by a quantizer (e.g. unslothai/
        # Qwen3-ASR-*-GGUF) routinely carries neither: pipeline_tag is often
        # None and its tags are generic ("conversational"). The ASR/TTS fact
        # lives on the *upstream* model card (Qwen/Qwen3-ASR-0.6B publishes
        # pipeline_tag: automatic-speech-recognition), so it has to be
        # checked there too. Deliberately lazy: this is the one check in
        # this function that costs an extra Hub call beyond what fetching
        # and comparing the templates already needs, so it only runs once a
        # repo has survived every other filter and is one step from being
        # counted as comparable -- not for every repo that merely carries a
        # base model, most of which would be excluded for some other reason
        # (missing/gated/absent upstream, no gguf-side template) anyway. A
        # live --top 400 run once found this check running unconditionally
        # here roughly doubled Hub calls and tripped rate limiting badly
        # enough to turn a fifth of the sample into examine_error -- see
        # final-fix-c.
        if _is_non_chat_pipeline(_safe_model_info(client, base)):
            rec["status"] = "upstream_non_chat_pipeline_tag"
            return rec

        # This GgufModel deliberately carries no tokens/bos_token_id/
        # eos_token_id: the survey has no per-repo vocab to fetch for either
        # side. checks/sanity._with_real_tokens is therefore a no-op here,
        # so both the GGUF's own template and the upstream template render
        # against the same engine-fabricated placeholder bos_token/
        # eos_token strings (Jinja2Engine's BASE_CONTEXT) rather than either
        # side's real tokens. That's symmetric -- both sides get the same
        # placeholders, so it can't manufacture a divergence between them by
        # itself -- but it does mean the survey never exercises the
        # real-token protection the lint path has (see sanity.py's S004/
        # S005/S006, which gate on _real_token specifically to avoid a
        # fabricated placeholder standing in for a real token). Fetching a
        # vocab per repo to close that gap is out of scope for v0.1.
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


def survey(client: Any, top: int, per_org: int,
           save_templates: str | None = None) -> dict[str, Any]:
    engine = Jinja2Engine()
    fixtures = load_fixtures()
    repos, truncated = _sample_repos(client, top, per_org)
    records = [_examine(client, r, engine, fixtures, save_templates) for r in repos]

    comparable = [r for r in records if r["status"] in COMPARABLE]
    divergent = [r for r in comparable if r["status"] == "output_differs"]
    dl_total = sum(r["downloads"] for r in comparable) or 1
    dl_div = sum(r["downloads"] for r in divergent)
    coverage_gaps = dict(Counter(
        r["status"] for r in records if r["status"] not in COMPARABLE))

    examine_error_n = coverage_gaps.get("examine_error", 0)
    # Guard len(records) == 0 the same way dl_total's `or 1` does above --
    # an empty sample is "nothing to say", not "100% unreliable".
    unreliable = bool(records) and (
        examine_error_n / len(records) > UNRELIABLE_EXAMINE_ERROR_FRACTION)

    return {
        "records": records,
        "aggregate": {
            # Which fixture corpus produced these figures. The divergent
            # percentage is a measurement *of* a fixture set, so a figure
            # published without its corpus version cannot be compared with the
            # next one (spec amendments §C, §G).
            "fixture_corpus_version": CORPUS_VERSION,
            "sampled": len(records),
            "per_org": per_org,
            "truncated": truncated,
            "comparable": len(comparable),
            "divergent": len(divergent),
            "divergent_pct": 100 * len(divergent) / len(comparable) if comparable else 0.0,
            "download_weighted_pct": 100 * dl_div / dl_total,
            "publishers_total": len({r["org"] for r in comparable}),
            "publishers_affected": len({r["org"] for r in divergent}),
            "coverage_gaps": coverage_gaps,
            "unreliable": unreliable,
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
    if a.get("unreliable"):
        lines.append(
            "> **Unreliable sample:** "
            f"{a['coverage_gaps'].get('examine_error', 0)} of {a['sampled']} "
            "repos failed to fetch (`examine_error`) -- likely Hugging Face "
            "rate limiting rather than genuinely gone or broken repos. The "
            "comparable/divergent figures below were computed over a sample "
            "missing a meaningful share of what it was supposed to cover; "
            "do not quote them as representative.")
        lines.append("")
    lines += [
        f"- Fixture corpus version: **{a['fixture_corpus_version']}**",
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
