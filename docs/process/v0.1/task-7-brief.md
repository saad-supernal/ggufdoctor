### Task 7: Hugging Face client and upstream resolution

**Files:**
- Create: `src/ggufdoctor/hf.py`
- Test: `tests/test_hf.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `HfClient(token=None, opener=None)` with `model_info(repo_id) -> dict`, `gguf_chat_template(repo_id) -> str | None`, `base_model_of(info) -> str | None`, `upstream_template(repo_id) -> tuple[str | None, str]`. The second element of the tuple is one of `"ok"`, `"gated"`, `"not_found"`, `"fetch_error"`, `"genuinely_absent"`.

`opener` is an injectable callable `(url: str) -> str` returning body text, raising `urllib.error.HTTPError` on failure. Tests inject a fake; production uses `urllib`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hf.py
import json
import urllib.error

import pytest

from ggufdoctor.hf import HfClient


def fake_opener(responses):
    def _open(url):
        for frag, val in responses.items():
            if frag in url:
                if isinstance(val, int):
                    raise urllib.error.HTTPError(url, val, "err", {}, None)
                return val
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    return _open


def test_base_model_from_card_data():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"cardData": {"base_model": "Qwen/Qwen3-8B"}}) == "Qwen/Qwen3-8B"


def test_base_model_from_list_takes_first():
    c = HfClient(opener=fake_opener({}))
    info = {"cardData": {"base_model": ["Qwen/Qwen3-8B", "other/x"]}}
    assert c.base_model_of(info) == "Qwen/Qwen3-8B"


def test_base_model_from_tag_fallback():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["base_model:Qwen/Qwen3-8B"]}) == "Qwen/Qwen3-8B"


def test_base_model_absent():
    c = HfClient(opener=fake_opener({}))
    assert c.base_model_of({"tags": ["gguf"]}) is None


def test_upstream_template_ok():
    body = json.dumps({"chat_template": "{{ 'hi' }}"})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    tpl, why = c.upstream_template("org/model")
    assert why == "ok"
    assert tpl == "{{ 'hi' }}"


def test_upstream_gated_is_distinguished_from_missing():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 401}))
    tpl, why = c.upstream_template("google/gemma-4")
    assert tpl is None
    assert why == "gated"


def test_upstream_404_is_not_found():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": 404,
                                     "chat_template.json": 404}))
    assert c.upstream_template("dead/repo")[1] == "not_found"


def test_upstream_present_but_no_template_field():
    c = HfClient(opener=fake_opener({"tokenizer_config.json": json.dumps({})}))
    assert c.upstream_template("org/embed")[1] == "genuinely_absent"


def test_multi_template_list_picks_default():
    body = json.dumps({"chat_template": [
        {"name": "tool_use", "template": "T"},
        {"name": "default", "template": "D"}]})
    c = HfClient(opener=fake_opener({"tokenizer_config.json": body}))
    assert c.upstream_template("org/m")[0] == "D"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.hf'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/hf.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hf.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/hf.py tests/test_hf.py
git commit -m "feat: Hugging Face client with coverage-classified upstream resolution"
```

---

