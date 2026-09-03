### Task 7: `survey --save-templates DIR`

**Files:**
- Modify: `src/ggufdoctor/survey.py` (`survey`, `_examine`)
- Modify: `src/ggufdoctor/cli.py` (`_build_survey_parser`, `_survey_main`)
- Test: `tests/test_survey.py`

**Interfaces:**
- Consumes: `HfClient.model_info` (dict with `sha`, `gguf.bos_token`, `gguf.eos_token`, `cardData.license`, `gated`).
- Produces: `survey(client, top, per_org, save_templates: str | None = None)`; `_examine(client, repo, engine, fixtures, save_dir: str | None = None)`; files `<org>__<name>.jinja`, `<org>__<name>.json`, `<org>__<name>.upstream.jinja`; sidecar keys `repo, revision, fetched_at, license, gated, architecture, bos_token, eos_token, base_model, upstream_saved`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_survey.py`, using the file's existing `FakeClient` (extend its `model_info` return to include `"sha": "abc123"`, `"cardData": {"license": "apache-2.0"}`, and `gguf.bos_token`/`eos_token` where it builds the dict, if not already present):

```python
def test_save_templates_writes_template_sidecar_and_upstream(tmp_path):
    client = FakeClient()
    result = survey(client, top=10, per_org=2, save_templates=str(tmp_path))
    saved = sorted(p.name for p in tmp_path.iterdir())
    # every repo with a GGUF-side template is saved, whatever its final status
    with_tpl = [r for r in result["records"] if r["status"] not in ("missing_template", "non_chat_architecture", "non_chat_pipeline_tag", "examine_error")]
    assert with_tpl, "fake client must include at least one repo with a template"
    first = with_tpl[0]["id"].replace("/", "__")
    assert f"{first}.jinja" in saved and f"{first}.json" in saved
    side = json.loads((tmp_path / f"{first}.json").read_text())
    assert side["repo"] == with_tpl[0]["id"]
    for key in ("revision", "fetched_at", "license", "gated", "architecture",
                "bos_token", "eos_token", "base_model", "upstream_saved"):
        assert key in side
    if side["upstream_saved"]:
        assert f"{first}.upstream.jinja" in saved


def test_survey_without_save_dir_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    survey(FakeClient(), top=10, per_org=2)
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_survey.py -v`
Expected: FAIL — `survey() got an unexpected keyword argument 'save_templates'`

- [ ] **Step 3: Implement**

In `survey.py`:

```python
import datetime
import os


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
```

In `_examine(client, repo, engine, fixtures, save_dir=None)`: right after `tpl`/`arch` are read from `info`, and before the architecture filter, add `base = client.base_model_of(info)` early enough to pass it, then `if save_dir and tpl: _save_template(save_dir, repo["id"], info, tpl, base)`. (Reorder: compute `base` before the non-chat filters — it is a pure dict read with no network cost — and keep the existing `if not base or base.lower() == ...` branch where it is.) After `upstream, why = client.upstream_template(base)` succeeds with `why == "ok"`, add `if save_dir and tpl: _save_upstream(save_dir, repo["id"], upstream)`. In `survey(...)` add the `save_templates: str | None = None` parameter and pass it through: `records = [_examine(client, r, engine, fixtures, save_templates) for r in repos]`.

In `cli.py`, `_build_survey_parser` gets:

```python
    p.add_argument("--save-templates", metavar="DIR",
                   help="also write every fetched chat template (and its upstream, "
                        "when resolved) to DIR as <org>__<repo>.jinja with a .json "
                        "sidecar recording repo, revision, licence and tokens")
```

and `_survey_main` passes `save_templates=args.save_templates`.

- [ ] **Step 4: Run tests, commit**

```bash
.venv/bin/python -m pytest tests/test_survey.py tests/test_cli.py -q
git add src/ggufdoctor/survey.py src/ggufdoctor/cli.py tests/test_survey.py
git commit -m "feat(survey): --save-templates writes fetched templates with provenance sidecars

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
