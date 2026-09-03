from __future__ import annotations

import json
import time
import urllib.error
import os
import urllib.request

from ggufdoctor import __version__
from typing import Any, Callable

API = "https://huggingface.co/api/models"
RESOLVE = "https://huggingface.co/{repo}/resolve/main/{fn}"

# A modest, bounded backoff for HTTP 429 (rate limited) -- stdlib time.sleep
# only, no retry/backoff dependency. A 429 means "the Hub is throttling us
# right now", not "this URL is invalid or gone": the same request very
# likely succeeds a moment later, so it deserves a few short retries before
# survey.py's caller has to file it as a genuine examine_error. A survey run
# that does hundreds of these calls back to back is exactly the case that
# trips this, and filing a throttled call as a permanent failure would
# quietly shrink the comparable sample without saying so (see final-fix-c).
_RATE_LIMIT_RETRY_DELAYS = (0.5, 1.0, 2.0)


def _default_opener(token: str | None) -> Callable[[str], str]:
    def _open(url: str) -> str:
        headers = {"User-Agent": f"ggufdoctor/{__version__}"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")
    return _open


HF_TOKEN_ENV = "HF_TOKEN"


class HfClient:
    def __init__(self, token: str | None = None,
                 opener: Callable[[str], str] | None = None) -> None:
        # An explicit token wins; otherwise honour the standard HF_TOKEN
        # environment variable (the same one huggingface_hub reads). With a
        # token, gated upstreams become comparable and the API rate limit is
        # higher. The value is only ever sent as an Authorization header to
        # huggingface.co; it is never logged or written to any report.
        if token is None:
            token = os.environ.get(HF_TOKEN_ENV) or None
        self.token = token
        self._open = opener or _default_opener(token)

    def _fetch(self, url: str) -> str:
        """self._open(url), retrying a bounded number of times on HTTP 429.

        Anything other than a 429 propagates immediately -- a 404, a 500, a
        network error are genuine failures the caller needs to see right
        away, not conditions worth waiting out. A URL still returning 429
        after every retry also propagates, so a repo that is truly
        unreachable still ends up recorded as a failure rather than retried
        forever; it just isn't blamed for merely having been asked at a bad
        moment.
        """
        last_exc: urllib.error.HTTPError | None = None
        for delay in (0.0, *_RATE_LIMIT_RETRY_DELAYS):
            if delay:
                time.sleep(delay)
            try:
                return self._open(url)
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                last_exc = e
        assert last_exc is not None
        raise last_exc

    def model_info(self, repo_id: str) -> dict[str, Any]:
        # Every field a caller reads has to be named in expand[]: the Hub's
        # model endpoint returns only the requested ones, silently omitting
        # the rest rather than erroring. `sha` is the repo's current commit,
        # which survey.py records as a saved template's `revision` -- without
        # it every provenance sidecar pinned `"revision": null` (ruling R8).
        url = (f"{API}/{repo_id}?expand[]=gguf&expand[]=cardData"
               "&expand[]=tags&expand[]=pipeline_tag&expand[]=sha")
        return json.loads(self._fetch(url))

    def gguf_chat_template(self, repo_id: str) -> str | None:
        try:
            info = self.model_info(repo_id)
            if not isinstance(info, dict):
                return None
            gg = info.get("gguf") or {}
            return gg.get("chat_template")
        except Exception:
            return None

    def base_model_of(self, info: dict[str, Any]) -> str | None:
        bm = (info.get("cardData") or {}).get("base_model")
        if isinstance(bm, list):
            bm = bm[0] if bm else None
        if isinstance(bm, str) and "/" in bm:
            return bm
        for tag in info.get("tags", []) or []:
            if isinstance(tag, str) and tag.startswith("base_model:"):
                cand = tag.split(":")[-1]
                if "/" in cand:
                    return cand
        return None

    # Where a Hub repo can keep its chat template, in the order transformers
    # itself prefers: the standalone `chat_template.jinja` (the save format
    # since transformers 4.55 -- repos published after mid-2025 often have
    # ONLY this file), then the older `chat_template.json`, then the
    # `chat_template` key inside `tokenizer_config.json`.
    TEMPLATE_FILES = ("chat_template.jinja", "chat_template.json", "tokenizer_config.json")

    def upstream_template(self, repo_id: str) -> tuple[str | None, str]:
        reasons: list[str] = []
        for fn in self.TEMPLATE_FILES:
            try:
                raw = self._fetch(RESOLVE.format(repo=repo_id, fn=fn))
                if fn.endswith(".jinja"):
                    # Raw template text, not JSON.
                    if raw.strip():
                        return raw, "ok"
                    reasons.append("genuinely_absent")
                    continue
                data = json.loads(raw)
                if not isinstance(data, dict):
                    reasons.append("fetch_error")
                    continue
                ct = data.get("chat_template")
                if isinstance(ct, list):
                    pick = None
                    for entry in ct:
                        if isinstance(entry, dict) and entry.get("name") == "default":
                            pick = entry.get("template")
                    if pick is None and ct and isinstance(ct[0], dict):
                        pick = ct[0].get("template")
                    ct = pick
                if isinstance(ct, str) and ct.strip():
                    return ct, "ok"
                reasons.append("genuinely_absent")
            except urllib.error.HTTPError as e:
                reasons.append("gated" if e.code in (401, 403)
                               else "not_found" if e.code == 404
                               else "fetch_error")
                continue
            except Exception:
                reasons.append("fetch_error")
                continue
        for preferred in ("gated", "genuinely_absent", "fetch_error", "not_found"):
            if preferred in reasons:
                return None, preferred
        return None, "not_found"

    def list_gguf_models(self, skip: int, limit: int = 100) -> list[dict[str, Any]]:
        url = (f"{API}?filter=gguf&sort=downloads&direction=-1"
               f"&limit={limit}&skip={skip}")
        return json.loads(self._fetch(url))
