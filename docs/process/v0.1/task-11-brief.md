### Task 11: Source resolution and CLI

**Files:**
- Create: `src/ggufdoctor/sources.py`
- Create: `src/ggufdoctor/cli.py`
- Test: `tests/test_sources.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–10
- Produces: `resolve(target, compare_upstream=None, client=None) -> tuple[GgufModel, str | None, Coverage]`; `is_repo_id(target) -> bool`; `main(argv=None) -> int`

`resolve` never touches the network when `target` is an existing local path and `compare_upstream` is `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources.py
from ggufdoctor.sources import is_repo_id, resolve
from tests.helpers.gguf_builder import build_gguf


def test_repo_id_detection():
    assert is_repo_id("unsloth/Qwen3-8B-GGUF")
    assert not is_repo_id("./model.gguf")
    assert not is_repo_id("/abs/model.gguf")


def test_local_resolve_is_offline(tmp_path, monkeypatch):
    import urllib.request

    def explode(*a, **k):
        raise AssertionError("network access during local run")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p))
    assert model.architecture == "llama"
    assert upstream is None
    assert coverage.upstream == "not_requested"
    assert coverage.families_run == ["S"]


def test_local_with_compare_upstream_runs_r_family(tmp_path):
    class FakeClient:
        def upstream_template(self, repo):
            return "{{ 'up' }}", "ok"

    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p), compare_upstream="Qwen/Qwen3-8B",
                                        client=FakeClient())
    assert upstream == "{{ 'up' }}"
    assert coverage.families_run == ["S", "R"]
    assert coverage.upstream == "ok"
```

```python
# tests/test_cli.py
import json

from ggufdoctor.cli import main
from tests.helpers.gguf_builder import build_gguf

CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}"
            "<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")


def _model(tmp_path, **kv):
    base = {"general.architecture": ("string", "llama"),
            "tokenizer.chat_template": ("string", CHAT_TPL),
            "tokenizer.ggml.tokens": ("array_string",
                                      ["<|im_start|>", "<|im_end|>"])}
    base.update(kv)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf(base))
    return str(p)


def test_clean_model_exits_zero(tmp_path, capsys):
    assert main([_model(tmp_path)]) == 0
    assert "no findings" in capsys.readouterr().out


def test_missing_vocab_token_exits_one(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path]) == 1


def test_json_output_written(tmp_path):
    out = tmp_path / "r.json"
    main([_model(tmp_path), "--json", str(out)])
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1"


def test_fail_on_never_always_zero(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path, "--fail-on", "never"]) == 0


def test_unreadable_file_exits_two(tmp_path):
    bad = tmp_path / "x.gguf"
    bad.write_bytes(b"NOPE")
    assert main([str(bad)]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ggufdoctor.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ggufdoctor/sources.py
from __future__ import annotations

import os

from ggufdoctor.bytesource import HttpRangeByteSource
from ggufdoctor.hf import HfClient
from ggufdoctor.models import Coverage, GgufModel
from ggufdoctor.reader import read_gguf_file

RESOLVE_GGUF = "https://huggingface.co/{repo}/resolve/main/{fn}"


def is_repo_id(target: str) -> bool:
    if os.path.exists(target):
        return False
    return "/" in target and not target.startswith((".", "/", "~")) \
        and not target.endswith(".gguf")


def resolve(target: str, compare_upstream: str | None = None,
            client: object | None = None) -> tuple[GgufModel, str | None, Coverage]:
    families = ["S"]

    if is_repo_id(target):
        hf = client or HfClient()
        info = hf.model_info(target)
        gg = (info or {}).get("gguf") or {}
        model = GgufModel(source_id=target,
                          architecture=gg.get("architecture"),
                          chat_template=gg.get("chat_template"))
        base = compare_upstream or hf.base_model_of(info)
        if not base:
            return model, None, Coverage("no_base_model", families)
        upstream, why = hf.upstream_template(base)
        if why == "ok":
            families.append("R")
        return model, upstream, Coverage(why, families)

    model = read_gguf_file(target)
    if compare_upstream is None:
        return model, None, Coverage("not_requested", families)

    hf = client or HfClient()
    upstream, why = hf.upstream_template(compare_upstream)
    if why == "ok":
        families.append("R")
    return model, upstream, Coverage(why, families)
```

```python
# src/ggufdoctor/cli.py
from __future__ import annotations

import argparse
import json
import sys

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.ignorefile import apply_ignores, load_ignores
from ggufdoctor.models import CheckContext
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ggufdoctor",
        description="Lint the chat template embedded in a GGUF file.")
    p.add_argument("target", help="local .gguf path or a Hugging Face repo id")
    p.add_argument("--compare-upstream", metavar="REPO",
                   help="compare rendered output against this source model")
    p.add_argument("--fail-on", choices=["error", "warn", "info", "never"],
                   default="error")
    p.add_argument("--fixtures", metavar="PATH", help="custom fixture corpus JSON")
    p.add_argument("--json", metavar="PATH", dest="json_path")
    p.add_argument("--ignore-file", metavar="PATH", default=".ggufdoctorignore")
    p.add_argument("--require-upstream", action="store_true",
                   help="treat a missing upstream as a failure")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from ggufdoctor.sources import resolve
        model, upstream, coverage = resolve(args.target, args.compare_upstream)
        fixtures = load_fixtures(args.fixtures)
        engines = [Jinja2Engine()]
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream})
        findings = run_sanity_checks(ctx)
        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)
        rules = load_ignores(args.ignore_file)
        findings, suppressed = apply_ignores(findings, rules)
    except Exception as e:  # unreadable input, network failure, bad ignore file
        print(f"ggufdoctor: {e}", file=sys.stderr)
        return 2

    print(render_human(model, findings, suppressed, coverage, engines))

    if args.json_path:
        payload = build_json(model, findings, suppressed, coverage, engines)
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)

    if args.require_upstream and coverage.upstream not in ("ok",):
        return 1
    return exit_code(findings, args.fail_on)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py tests/test_cli.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/ggufdoctor/sources.py src/ggufdoctor/cli.py tests/test_sources.py tests/test_cli.py
git commit -m "feat: source resolution and CLI"
```

---

