### Task 9: Conformance suite against a real pinned `llama-server`

**Files:**
- Create: `tests/conformance/__init__.py`, `tests/conformance/llama_server.py`, `tests/conformance/test_llama_server.py`
- Modify: `pyproject.toml` (`markers`, `addopts`)
- Modify: `.github/workflows/ci.yml` (add `conformance` job)

**Interfaces:**
- Consumes: vendored templates (Task 8), `LlamaCppEngine`, `BASE_CONTEXT`, fixtures.
- Produces: pytest marker `conformance`; helper `LlamaServer(binary, model_path, template_path) -> context manager` with `.apply_template(body: dict) -> str`; env overrides `GGUFDOCTOR_LLAMA_SERVER` (path to a `llama-server` binary) and `GGUFDOCTOR_CONFORMANCE_MODEL` (path to any small GGUF); default download cache `~/.cache/ggufdoctor-conformance/b10775/`.

The oracle is the real thing: `llama-server` from the `b10775` GitHub release (`llama-b10775-bin-ubuntu-x64.tar.gz`, `-macos-arm64`, `-win-cpu-x64`; each 11–18 MB), started with `--jinja --chat-template-file <vendored template> -m <tiny model>`, queried through `POST /apply-template`. It needs *a* model loaded; use `ggml-org/models` → `tinyllamas/stories260K.gguf` (about 1 MB) from `https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf`.

- [ ] **Step 1: Markers**

`pyproject.toml`:

```toml
markers = [
  "network: hits the real Hugging Face API (deselected by default)",
  "conformance: downloads and runs a pinned llama-server binary (deselected by default)",
]
addopts = "-m 'not network and not conformance'"
```

- [ ] **Step 2: The helper**

```python
# tests/conformance/llama_server.py
from __future__ import annotations

import json
import os
import pathlib
import platform
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile

BUILD_TAG = "b10775"
CACHE = pathlib.Path(os.environ.get("GGUFDOCTOR_CONFORMANCE_CACHE",
                                    pathlib.Path.home() / ".cache" / "ggufdoctor-conformance")) / BUILD_TAG
MODEL_URL = "https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf"
# The tiny model's own special tokens; llama-server passes these to the template.
MODEL_BOS, MODEL_EOS = "<s>", "</s>"


def _release_asset() -> str:
    sysname, machine = platform.system(), platform.machine().lower()
    if sysname == "Linux" and machine in ("x86_64", "amd64"):
        return f"llama-{BUILD_TAG}-bin-ubuntu-x64.tar.gz"
    if sysname == "Darwin" and machine == "arm64":
        return f"llama-{BUILD_TAG}-bin-macos-arm64.tar.gz"
    if sysname == "Windows" and machine in ("x86_64", "amd64"):
        return f"llama-{BUILD_TAG}-bin-win-cpu-x64.zip"
    raise RuntimeError(f"no llama.cpp release asset for {sysname}/{machine}; set GGUFDOCTOR_LLAMA_SERVER")


def _download(url: str, dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    return dest


def server_binary() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_LLAMA_SERVER")
    if override:
        return pathlib.Path(override)
    asset = _release_asset()
    archive = _download(f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD_TAG}/{asset}",
                        CACHE / asset)
    extracted = CACHE / "bin"
    if not extracted.exists():
        extracted.mkdir(parents=True)
        if asset.endswith(".zip"):
            zipfile.ZipFile(archive).extractall(extracted)
        else:
            tarfile.open(archive).extractall(extracted)
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    found = next(extracted.rglob(name), None)
    if found is None:
        raise RuntimeError(f"{name} not found in {archive}")
    found.chmod(0o755)
    return found


def model_path() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_CONFORMANCE_MODEL")
    if override:
        return pathlib.Path(override)
    return _download(MODEL_URL, CACHE / "stories260K.gguf")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LlamaServer:
    def __init__(self, template_path: pathlib.Path):
        self.template_path = template_path
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None

    def __enter__(self):
        binary, model = server_binary(), model_path()
        env = dict(os.environ)
        # the release tarballs put shared libs next to the binary
        env["LD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
        self.proc = subprocess.Popen(
            [str(binary), "-m", str(model), "--jinja", "--chat-template-file", str(self.template_path),
             "--host", "127.0.0.1", "--port", str(self.port), "-c", "512", "--no-webui", "--log-disable"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server exited: " + self.proc.stderr.read().decode(errors="replace")[-2000:])
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1) as r:
                    if r.status == 200:
                        return self
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("llama-server did not become healthy in 60s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def apply_template(self, body: dict) -> str:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/apply-template",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["prompt"]
```

- [ ] **Step 3: The test**

```python
# tests/conformance/test_llama_server.py
"""Bundled WASM engine vs the real llama-server at the same build tag.

Deselected by default (marker `conformance`): it downloads a 10-20 MB binary
and a 1 MB model on first run. Run with:
    .venv/bin/python -m pytest -m conformance tests/conformance -v
"""
import pathlib

import pytest

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from tests.conformance.llama_server import MODEL_BOS, MODEL_EOS, LlamaServer

pytestmark = pytest.mark.conformance
DATA = pathlib.Path(__file__).parent.parent / "data" / "templates"
TEMPLATES = sorted(p for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))


def _body(fixture):
    body = {"messages": fixture.context["messages"],
            "add_generation_prompt": fixture.context.get("add_generation_prompt", True)}
    if "tools" in fixture.context:
        body["tools"] = fixture.context["tools"]
    if "enable_thinking" in fixture.context:
        body["chat_template_kwargs"] = {"enable_thinking": fixture.context["enable_thinking"]}
    return body


def _ours(engine, template, fixture):
    ctx = dict(BASE_CONTEXT)
    ctx.update(fixture.context)
    ctx["bos_token"], ctx["eos_token"] = MODEL_BOS, MODEL_EOS
    return engine.render(template, ctx)


@pytest.fixture(scope="module")
def engine():
    e = LlamaCppEngine()
    assert e.available, e.unavailable_reason
    return e


@pytest.mark.parametrize("template_path", TEMPLATES, ids=[p.stem for p in TEMPLATES])
def test_bundled_engine_matches_real_llama_server(engine, template_path):
    template = template_path.read_text(encoding="utf-8")
    mismatches = []
    with LlamaServer(template_path) as server:
        for fx in load_fixtures():
            ours = _ours(engine, template, fx)
            try:
                theirs = server.apply_template(_body(fx))
            except Exception as e:  # the server refuses shapes the template declines
                if not ours.ok:
                    continue  # both sides fail: agreement
                mismatches.append((fx.name, "server error while we rendered", str(e)[:200]))
                continue
            if not ours.ok:
                mismatches.append((fx.name, "we failed while server rendered", ours.error))
                continue
            expect = ours.text
            # llama-server strips the leading BOS when the vocab has add_bos (the tiny
            # model does); our engine deliberately does not (spec amendments §A).
            if expect.startswith(MODEL_BOS) and not theirs.startswith(MODEL_BOS):
                expect = expect[len(MODEL_BOS):]
            if expect != theirs:
                mismatches.append((fx.name, "text differs", f"ours={expect[:300]!r}\ntheirs={theirs[:300]!r}"))
    assert not mismatches, "\n".join(f"{n}: {why}\n{detail}" for n, why, detail in mismatches)
```

- [ ] **Step 4: Run it once, locally**

Run: `.venv/bin/python -m pytest -m conformance tests/conformance -v`

Expected on the first run: it may **not** be green, and that is information, not failure of this task. Known things llama-server does beyond our shim that would show up here:

- it converts assistant `tool_calls[].function.arguments` from a dict to a JSON **string** while parsing the request (`common_chat_tool_call.arguments` is a `std::string`), and may convert it back for templates whose caps say `supports_object_arguments` — the `tool_roundtrip` fixture is where this surfaces;
- it may reject `content: null` or a `tool` role for templates lacking those caps with an HTTP 400 (counted above as agreement only if our engine also fails).

For each mismatch class, decide: (a) it is server-side request parsing that a faithful engine must reproduce → port that step into `engine/shim.cpp` (beside the normaliser, with a comment naming the `chat.cpp`/`server-common.cpp` function it mirrors), rebuild via `engine/build.sh`, re-run Tasks 1–3 tests; or (b) it is request-level validation with no rendering analogue → exclude that fixture for that template *with a reason string* in a small `SKIP = {(slug, fixture): reason}` table in the test. Record every such decision in the ledger as a ruling. Do not weaken the byte-equality assertion.

- [ ] **Step 5: CI job**

Append to `.github/workflows/ci.yml`:

```yaml
  conformance:
    # Real llama-server at the pinned build vs the bundled WASM engine.
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[dev]"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/ggufdoctor-conformance
          key: conformance-b10775-${{ runner.os }}
      - run: python -m pytest -m conformance tests/conformance -v
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/conformance .github/workflows/ci.yml engine/shim.cpp src/ggufdoctor/engine_data
git commit -m "test: conformance suite runs the bundled engine against real llama-server b10775

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Include `engine/shim.cpp` and `engine_data/` only if Step 4 changed them; say so in the commit body.)

---

