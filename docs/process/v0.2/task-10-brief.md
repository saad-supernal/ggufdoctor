### Task 10: CI engine-build job, wheel contents, version bump

**Files:**
- Modify: `pyproject.toml` (`version = "0.2.0"`), `src/ggufdoctor/__init__.py` (`__version__ = "0.2.0"`)
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `engine/fetch-llamacpp.sh`, `engine/build.sh --out DIR` (Task 1), `ENV_MODULE_PATH` (Task 2).
- Produces: CI jobs `engine-build` and an extended `build` check.

- [ ] **Step 1: Version bump and a test that pins it**

Append to `tests/test_cli.py`:

```python
def test_version_is_0_2_0():
    import ggufdoctor
    assert ggufdoctor.__version__ == "0.2.0"
```

Set `version = "0.2.0"` in `pyproject.toml` and `__version__ = "0.2.0"` in `src/ggufdoctor/__init__.py`. Run `.venv/bin/python -m pytest tests/test_cli.py -q`.

- [ ] **Step 2: Wheel check**

In the `build` job's Python snippet, extend `need`:

```python
          need = ["ggufdoctor/fixture_data/corpus.json",
                  "ggufdoctor/engine_data/llamacpp-jinja.wasm",
                  "ggufdoctor/engine_data/llamacpp-jinja.json"]
```

and add a step after `installed console script runs`:

```yaml
      - name: installed engine renders through the wheel's module
        run: |
          cd /tmp && python - <<'PY'
          from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
          e = LlamaCppEngine(); assert e.available, e.unavailable_reason
          r = e.render("{{ messages[0].content }}", {"messages": [{"role": "user", "content": "ok"}]})
          assert r.ok and r.text == "ok", r
          print("engine ok:", e.version, e.backend)
          PY
```

- [ ] **Step 3: `engine-build` job**

```yaml
  engine-build:
    # Proves the committed module can be regenerated from the pinned sources
    # with the pinned toolchain, and that the fresh build passes the suite.
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e ".[dev]"
      - name: fetch pinned llama.cpp sources (verified against llamacpp-sources.sha256)
        run: engine/fetch-llamacpp.sh
      - name: build the module with wasi-sdk 34
        run: engine/build.sh --out /tmp/fresh
      - name: fresh module passes the whole suite
        run: GGUFDOCTOR_ENGINE_WASM=/tmp/fresh/llamacpp-jinja.wasm python -m pytest -q
      - name: report whether the fresh build is byte-identical to the committed one
        run: |
          python - <<'PY'
          import hashlib, json
          fresh = hashlib.sha256(open("/tmp/fresh/llamacpp-jinja.wasm","rb").read()).hexdigest()
          committed = json.load(open("src/ggufdoctor/engine_data/llamacpp-jinja.json"))["sha256"]
          print("fresh    ", fresh); print("committed", committed)
          print("byte-identical" if fresh == committed else "differs (informational: toolchain nondeterminism)")
          PY
```

Note `engine/build.sh` downloads wasi-sdk for `Linux-x86_64` on its own when `WASI_SDK` is unset; the job needs `curl` and `shasum`, both present on `ubuntu-latest`.

- [ ] **Step 4: Trigger and check CI**

```bash
git add pyproject.toml src/ggufdoctor/__init__.py tests/test_cli.py .github/workflows/ci.yml
git commit -m "ci: engine-build job regenerates the module; wheel must carry it; version 0.2.0

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feat/v0.2
gh run list --branch feat/v0.2 --limit 3
```

CI runs on pull requests and on `main`; to exercise the branch open a draft PR (`gh pr create --draft --fill --base main`) or trigger `workflow_dispatch` on the branch. Expected: `test` (9 jobs), `build`, `engine-build`, `conformance` all green. Fix what is red before committing further work.

---

