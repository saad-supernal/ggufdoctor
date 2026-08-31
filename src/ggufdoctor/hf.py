from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

API = "https://huggingface.co/api/models"
RESOLVE = "https://huggingface.co/{repo}/resolve/main/{fn}"


def _default_opener(token: str | None) -> Callable[[str], str]:
    def _open(url: str) -> str:
        headers = {"User-Agent": "ggufdoctor/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")
    return _open


class HfClient:
    def __init__(self, token: str | None = None,
                 opener: Callable[[str], str] | None = None) -> None:
        self.token = token
        self._open = opener or _default_opener(token)

    def model_info(self, repo_id: str) -> dict[str, Any]:
        url = f"{API}/{repo_id}?expand[]=gguf&expand[]=cardData&expand[]=tags"
        return json.loads(self._open(url))

    def gguf_chat_template(self, repo_id: str) -> str | None:
        gg = (self.model_info(repo_id) or {}).get("gguf") or {}
        return gg.get("chat_template")

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

    def upstream_template(self, repo_id: str) -> tuple[str | None, str]:
        reasons: list[str] = []
        for fn in ("tokenizer_config.json", "chat_template.json"):
            try:
                data = json.loads(self._open(RESOLVE.format(repo=repo_id, fn=fn)))
            except urllib.error.HTTPError as e:
                reasons.append("gated" if e.code in (401, 403)
                               else "not_found" if e.code == 404
                               else "fetch_error")
                continue
            except Exception:
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
        for preferred in ("gated", "genuinely_absent", "fetch_error", "not_found"):
            if preferred in reasons:
                return None, preferred
        return None, "not_found"
