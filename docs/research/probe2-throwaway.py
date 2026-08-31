#!/usr/bin/env python3
"""Spike v2: does a GGUF repo's embedded chat template RENDER differently
from its upstream source model's template?

Improvements over v1:
  * publisher-diverse sampling (cap per org) - v1 was 100% unsloth
  * only models whose upstream actually has a chat template (drops ASR/embeddings)
  * compares RENDERED OUTPUT on fixture conversations, not source text,
    so cosmetic and compat-only rewrites don't count as findings

Network only. No weights downloaded, no models run.
"""
import json, sys, re, urllib.request, urllib.error, datetime
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2 import TemplateError

UA = {"User-Agent": "gguf-template-probe/0.2 (research)"}
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 150
PER_ORG = int(sys.argv[2]) if len(sys.argv) > 2 else 2
OUT = "probe2-results.json"

# ---------------------------------------------------------------- fixtures
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string"}},
                       "required": ["city"]},
    },
}]

FIXTURES = [
    ("user_only", {"messages": [{"role": "user", "content": "Hello"}],
                   "add_generation_prompt": True}),
    ("system_user", {"messages": [{"role": "system", "content": "Be brief."},
                                  {"role": "user", "content": "Hello"}],
                     "add_generation_prompt": True}),
    ("multiturn", {"messages": [{"role": "user", "content": "Hi"},
                                {"role": "assistant", "content": "Hey!"},
                                {"role": "user", "content": "Bye"}],
                   "add_generation_prompt": True}),
    ("with_tools", {"messages": [{"role": "user", "content": "Weather in Paris?"}],
                    "tools": TOOLS, "add_generation_prompt": True}),
    ("thinking_unset", {"messages": [{"role": "user", "content": "2+2?"}],
                        "add_generation_prompt": True}),
    ("thinking_true", {"messages": [{"role": "user", "content": "2+2?"}],
                       "add_generation_prompt": True, "enable_thinking": True}),
    ("thinking_false", {"messages": [{"role": "user", "content": "2+2?"}],
                        "add_generation_prompt": True, "enable_thinking": False}),
]

BASE_CTX = {
    "bos_token": "<s>", "eos_token": "</s>", "unk_token": "<unk>",
    "pad_token": "<pad>", "add_generation_prompt": True,
}


def make_env():
    env = ImmutableSandboxedEnvironment(trim_blocks=False, lstrip_blocks=False)

    def raise_exception(msg):
        raise ValueError(msg)

    def strftime_now(fmt):
        return datetime.datetime(2026, 1, 1).strftime(fmt)

    env.globals["raise_exception"] = raise_exception
    env.globals["strftime_now"] = strftime_now
    env.filters["tojson"] = lambda o, **kw: json.dumps(o)
    return env


ENV = make_env()


def render(tpl_src, ctx):
    """Return (output, error). Error is a short string if rendering failed."""
    try:
        t = ENV.from_string(tpl_src)
    except Exception as e:
        return None, f"compile:{type(e).__name__}"
    c = dict(BASE_CTX)
    c.update(ctx)
    try:
        return t.render(**c), None
    except (TemplateError, ValueError, TypeError, AttributeError,
            LookupError, ZeroDivisionError, RecursionError) as e:
        return None, f"render:{type(e).__name__}"
    except Exception as e:
        return None, f"other:{type(e).__name__}"


# ---------------------------------------------------------------- http
def gj(url, timeout=30):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout))


def gtext(url, timeout=30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout
    ).read().decode("utf-8", "replace")


def candidates(target, per_org):
    """Top GGUF repos by downloads, capped per publisher for diversity."""
    picked, by_org, page = [], defaultdict(int), 0
    while len(picked) < target and page < 15:
        batch = gj("https://huggingface.co/api/models?filter=gguf&sort=downloads"
                   f"&direction=-1&limit=100&skip={page*100}")
        if not batch:
            break
        for m in batch:
            org = m["id"].split("/")[0]
            if by_org[org] >= per_org:
                continue
            by_org[org] += 1
            picked.append({"id": m["id"], "downloads": m.get("downloads", 0)})
            if len(picked) >= target:
                break
        page += 1
    return picked


def base_model_of(info):
    cd = info.get("cardData") or {}
    bm = cd.get("base_model")
    if isinstance(bm, list):
        bm = bm[0] if bm else None
    if isinstance(bm, str) and "/" in bm:
        return bm
    for t in info.get("tags", []):
        if t.startswith("base_model:"):
            c = t.split(":")[-1]
            if "/" in c:
                return c
    return None


NON_CHAT_ARCH = {"bert", "parakeet", "asr", "audiocpp", "ced", "qwen3-tts",
                 "whisper", "clip", "t5", "nomic-bert", "jina-bert"}


def upstream_template(base):
    """Return (template, reason). reason distinguishes gated/missing/absent."""
    reasons = []
    for fn in ("tokenizer_config.json", "chat_template.json"):
        try:
            data = json.loads(gtext(f"https://huggingface.co/{base}/resolve/main/{fn}"))
        except urllib.error.HTTPError as e:
            reasons.append("gated" if e.code in (401, 403)
                           else "not_found" if e.code == 404 else f"http{e.code}")
            continue
        except Exception:
            reasons.append("fetch_error")
            continue
        ct = data.get("chat_template")
        if isinstance(ct, list):
            pick = None
            for e in ct:
                if isinstance(e, dict) and e.get("name") == "default":
                    pick = e.get("template")
            if pick is None and ct and isinstance(ct[0], dict):
                pick = ct[0].get("template")
            ct = pick
        if isinstance(ct, str) and ct.strip():
            return ct, "ok"
        reasons.append("no_template_field")
    if "gated" in reasons:
        return None, "gated"
    if "no_template_field" in reasons:
        return None, "genuinely_absent"
    return None, reasons[0] if reasons else "unknown"


def examine(repo):
    rec = {"id": repo["id"], "downloads": repo["downloads"],
           "org": repo["id"].split("/")[0], "status": None}
    try:
        info = gj(f"https://huggingface.co/api/models/{repo['id']}"
                  "?expand[]=gguf&expand[]=cardData&expand[]=tags")
    except Exception as e:
        rec["status"] = "api_error"; rec["error"] = str(e)[:100]; return rec

    gg = info.get("gguf") or {}
    rec["arch"] = gg.get("architecture")
    g_ct = gg.get("chat_template")
    base = base_model_of(info)
    rec["base_model"] = base

    if (rec.get("arch") or "").lower() in NON_CHAT_ARCH:
        rec["status"] = "non_chat_arch"; return rec
    if not base or base.lower() == repo["id"].lower():
        rec["status"] = "no_base_model"; return rec
    up_ct, why = upstream_template(base)
    if up_ct is None:
        rec["status"] = {"gated": "upstream_gated",
                         "genuinely_absent": "non_chat_model"}.get(why, "upstream_fetch_failed")
        rec["why"] = why; return rec
    if not g_ct:
        # upstream IS a chat model but the GGUF ships no template
        rec["status"] = "missing_template"; return rec

    rec["identical_source"] = (g_ct == up_ct)

    diffs, errs = [], []
    for name, ctx in FIXTURES:
        go, ge = render(g_ct, ctx)
        uo, ue = render(up_ct, ctx)
        if ge or ue:
            errs.append({"fixture": name, "gguf_err": ge, "upstream_err": ue})
            continue
        if go != uo:
            diffs.append({"fixture": name,
                          "gguf_tail": go[-90:], "upstream_tail": uo[-90:],
                          "len_delta": len(go) - len(uo)})
    rec["render_errors"] = errs
    rec["diff_fixtures"] = [d["fixture"] for d in diffs]
    rec["diff_detail"] = diffs[:3]

    if rec["identical_source"]:
        rec["status"] = "identical"
    elif diffs:
        rec["status"] = "output_differs"
    elif errs and len(errs) == len(FIXTURES):
        rec["status"] = "unrenderable"
    else:
        rec["status"] = "cosmetic_only"
    return rec


def main():
    print(f"sampling up to {TARGET} repos, max {PER_ORG}/org ...", flush=True)
    repos = candidates(TARGET, PER_ORG)
    print(f"got {len(repos)} across {len(set(r['id'].split('/')[0] for r in repos))} orgs",
          flush=True)
    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, r in enumerate(ex.map(examine, repos), 1):
            res.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(repos)}", flush=True)
    json.dump(res, open(OUT, "w"), indent=1)

    c = Counter(r["status"] for r in res)
    print("\n=== STATUS ===")
    for k, v in c.most_common():
        print(f"{v:5d}  {k}")

    comparable = [r for r in res if r["status"] in
                  ("identical", "cosmetic_only", "output_differs", "unrenderable")]
    differ = [r for r in comparable if r["status"] == "output_differs"]
    print(f"\ncomparable chat models: {len(comparable)}")
    if comparable:
        pct = 100 * len(differ) / len(comparable)
        print(f"RENDER-DIFFERENT: {len(differ)}  = {pct:.1f}% of comparable")
        print(f"orgs affected: {len(set(r['org'] for r in differ))} "
              f"of {len(set(r['org'] for r in comparable))}")
    fc = Counter(f for r in differ for f in r["diff_fixtures"])
    print("\n=== FIXTURES THAT DIVERGE ===")
    for k, v in fc.most_common():
        print(f"{v:5d}  {k}")
    print("\n=== TOP AFFECTED ORGS ===")
    for org, n in Counter(r["org"] for r in differ).most_common(12):
        print(f"{n:5d}  {org}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
