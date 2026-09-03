# ggufdoctor v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add llama.cpp's own chat-template engine as a second, WASM-embedded engine and report where it and transformers-style Jinja2 disagree, with a corpus that reaches the inputs where disagreement actually lives.

**Architecture:** llama.cpp's `common/jinja` C++ engine is compiled once with wasi-sdk into a ~660 KB reactor-style WASM module committed under `src/ggufdoctor/engine_data/` and driven from Python through `wasmtime` (`LlamaCppEngine`, satisfying the existing `Engine` protocol). A new pure check family `checks/cross_engine.py` renders every fixture through both engines with identical context and emits X001/X002/X004/X005. The fixture corpus gains three "extended" fixtures; an engine registry and `--engines` flag select engines; reports gain engine provenance and an explicit "engines agree" line; a conformance suite checks the bundled module against a real pinned `llama-server`.

**Tech Stack:** Python ≥ 3.11, `jinja2`, `wasmtime` (Python package, ABI-independent wheels), wasi-sdk 34 (build time only), llama.cpp `common/jinja` sources at a pinned commit, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-ggufdoctor-design.md` as amended by `docs/superpowers/specs/2026-09-03-ggufdoctor-v0.2-amendments.md`. Evidence: `docs/research/2026-09-03-engine-spike.md` (read §2 and §4 before Task 1).

## Global Constraints

- `requires-python = ">=3.11"`. Runtime dependencies are exactly `jinja2>=3.1` and `wasmtime>=48,<49`. Nothing else.
- Engine pin: llama.cpp commit `67a17c17caa95742186f8b1ecadd1b5abd6d5ebb`, build tag `b10775`. Toolchain: wasi-sdk 34. Compile flags verbatim: `--target=wasm32-wasip1 -mexec-model=reactor -std=c++17 -Oz -fwasm-exceptions -mllvm -wasm-use-legacy-eh=false -Wl,-mllvm,-wasm-use-legacy-eh=false -Wl,--strip-all`, link `-L<sysroot>/lib/wasm32-wasip1/eh ... -lunwind`. Never pass `-I<dir>/jinja` (its `string.h` shadows libc's).
- The committed module `src/ggufdoctor/engine_data/llamacpp-jinja.wasm` must be under 1,000,000 bytes and ship in the wheel with its manifest `llamacpp-jinja.json`.
- The engine does **not** strip a leading BOS. Both engines receive the identical context: `BASE_CONTEXT` defaults, then the fixture, then the model's real `bos_token`/`eos_token` via `_with_real_tokens`.
- `Engine` protocol is unchanged: `name: str`, `version: str`, `render(template, context) -> RenderResult`. Engines never raise from `render`.
- Error tag prefixes are fixed strings: `compile:`, `raise:`, `render:`, plus new `engine:unavailable:`.
- Every check that cannot evaluate appends its id(s) to `ctx.checks_not_evaluated`. A user who passes `--engines jinja2` has *declined* X, which is not a gap and is not recorded; an engine that is *unavailable* is a gap and is recorded.
- No finding message may call a template "broken". X002's message names the engine that fails, the stage, and that engine's own error text.
- False-positive discipline: S003 on an `extended`-tier fixture is INFO, never ERROR. X002 where llama.cpp rendered only after its normaliser rewrote the input is INFO.
- Tests that assert on real templates assert the **complete** finding set as `{(id, severity, fixtures...)}` — never `"S005" not in ids`. Every expected finding carries a comment saying why it is a true positive.
- No default-run test reaches the network or executes a downloaded binary. Marks: `network` (Hugging Face), `conformance` (downloads `llama-server`). `addopts = "-m 'not network and not conformance'"`.
- Fixture corpus version is `"2"`. The published 14.8% figure is tied to corpus `"1"` and must never be restated as a corpus-2 figure; both are reported with their corpus version.
- Test command: `.venv/bin/python -m pytest -q` from the repo root (the `.venv` is a `uv venv --python 3.14`; after adding a dependency run `uv pip install --python .venv/bin/python -e ".[dev]"`).
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## File structure

| Path | Responsibility |
|---|---|
| `engine/` (repo root, **not** in the wheel) | Everything that produces the module: `LLAMACPP_PIN`, `fetch-llamacpp.sh`, `llamacpp-sources.sha256`, `ggml-stub.h`, `shim.cpp`, `build.sh`, `README.md` |
| `src/ggufdoctor/engine_data/` | `__init__.py`, `llamacpp-jinja.wasm`, `llamacpp-jinja.json` — package data |
| `src/ggufdoctor/engines/llamacpp_engine.py` | `LlamaCppEngine` — wasmtime host, error mapping, availability |
| `src/ggufdoctor/engines/registry.py` | `select_engines(requested) -> EngineSelection` |
| `src/ggufdoctor/checks/common.py` | `real_token`, `with_real_tokens`, `collapse_by_signature` moved here from `sanity.py` (sanity re-exports the underscored names) |
| `src/ggufdoctor/checks/cross_engine.py` | X001/X002/X004/X005, `run_cross_engine_checks(ctx)` |
| `src/ggufdoctor/models.py` | `RenderResult.extra`, `Fixture.tier`, `Coverage.engines_unavailable`, `Coverage.engines_agreed_fixtures`, `CheckContext.stats` |
| `src/ggufdoctor/fixtures.py`, `fixture_data/corpus.json` | corpus v2 with tiers |
| `src/ggufdoctor/cli.py` | `--engines`, X wiring, `survey --save-templates` |
| `src/ggufdoctor/report/human.py`, `report/json_report.py` | engine provenance, unavailable engines, "engines agree" line |
| `src/ggufdoctor/survey.py` | `save_templates` parameter |
| `tests/data/templates/` | ten vendored real templates with sidecars and `SOURCES.md` |
| `tests/conformance/` | `llama_server.py` helper and `test_llama_server.py` |
| `.github/workflows/ci.yml` | `engine-build` and `conformance` jobs; wheel content check |

---

### Task 1: Engine build pipeline — fetch, shim, build, commit the module

**Files:**
- Create: `engine/README.md`, `engine/LLAMACPP_PIN`, `engine/fetch-llamacpp.sh`, `engine/llamacpp-sources.sha256`, `engine/ggml-stub.h`, `engine/shim.cpp`, `engine/build.sh`
- Create: `src/ggufdoctor/engine_data/__init__.py`, `src/ggufdoctor/engine_data/llamacpp-jinja.wasm`, `src/ggufdoctor/engine_data/llamacpp-jinja.json`
- Modify: `.gitignore` (add `engine/build/`)
- Test: `tests/test_engine_data.py`

**Interfaces:**
- Consumes: nothing in the Python package.
- Produces: the module's ABI — exports `memory`, `_initialize`, `gd_alloc(n) -> ptr`, `gd_free(ptr)`, `gd_render(ptr, len) -> out_ptr`, `gd_out_len() -> len`. Input JSON `{"template": str, "context": object, "normalize": bool}`; output JSON `{"ok": true, "text": str, "caps": {str: bool}, "normalized": bool}` or `{"ok": false, "stage": "lexer"|"parser"|"raise"|"render", "error": str, "caps"?: {...}, "normalized"?: bool}`. Manifest JSON keys: `engine`, `build_tag`, `commit`, `wasi_sdk`, `sha256`, `size`, `built_at`.

Read `docs/research/2026-09-03-engine-spike.md` §2 and §4 first. The spike's throwaway shim is in `docs/research/2026-09-03-engine-spike/shim.cpp`; this task's shim supersedes it (reactor exports, caps, normaliser).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine_data.py
import hashlib
import json
from importlib import resources


def _data(name):
    return resources.files("ggufdoctor.engine_data").joinpath(name)


def test_manifest_pins_the_engine_build():
    manifest = json.loads(_data("llamacpp-jinja.json").read_text(encoding="utf-8"))
    assert manifest["engine"] == "llama.cpp"
    assert manifest["build_tag"] == "b10775"
    assert manifest["commit"] == "67a17c17caa95742186f8b1ecadd1b5abd6d5ebb"
    assert manifest["wasi_sdk"] == "wasi-sdk-34"
    for key in ("sha256", "size", "built_at"):
        assert key in manifest


def test_module_matches_manifest_and_fits_budget():
    manifest = json.loads(_data("llamacpp-jinja.json").read_text(encoding="utf-8"))
    blob = _data("llamacpp-jinja.wasm").read_bytes()
    assert blob[:4] == b"\x00asm", "not a WebAssembly module"
    assert len(blob) < 1_000_000, f"module is {len(blob)} bytes; budget is 1,000,000"
    assert len(blob) == manifest["size"]
    assert hashlib.sha256(blob).hexdigest() == manifest["sha256"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_engine_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ggufdoctor.engine_data'`

- [ ] **Step 3: Pin file, fetch script, checksums**

```
# engine/LLAMACPP_PIN
commit=67a17c17caa95742186f8b1ecadd1b5abd6d5ebb
build_tag=b10775
```

```sh
#!/bin/sh
# engine/fetch-llamacpp.sh — download exactly the pinned llama.cpp sources the engine needs.
# Usage: engine/fetch-llamacpp.sh [--write-sums]
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/LLAMACPP_PIN"
OUT="$HERE/build/llamacpp"
RAW="https://raw.githubusercontent.com/ggml-org/llama.cpp/$commit"
mkdir -p "$OUT/jinja" "$OUT/common" "$OUT/include/nlohmann"
for f in caps.cpp caps.h lexer.cpp lexer.h parser.cpp parser.h runtime.cpp runtime.h string.cpp string.h utils.h value.cpp value.h; do
  curl -sfL -o "$OUT/jinja/$f" "$RAW/common/jinja/$f"
done
for f in json.cpp json.h unicode.cpp unicode.h; do
  curl -sfL -o "$OUT/common/$f" "$RAW/common/$f"
done
curl -sfL -o "$OUT/include/nlohmann/json.hpp" "$RAW/vendor/nlohmann/json.hpp"
curl -sfL -o "$OUT/include/nlohmann/json_fwd.hpp" "$RAW/vendor/nlohmann/json_fwd.hpp"
cp "$HERE/ggml-stub.h" "$OUT/include/ggml.h"
if [ "${1:-}" = "--write-sums" ]; then
  (cd "$OUT" && find . -type f | sort | xargs shasum -a 256) > "$HERE/llamacpp-sources.sha256"
  echo "wrote $HERE/llamacpp-sources.sha256"
else
  (cd "$OUT" && shasum -a 256 -c "$HERE/llamacpp-sources.sha256" --quiet)
  echo "sources verified against llamacpp-sources.sha256"
fi
```

`engine/llamacpp-sources.sha256` is produced once by running `engine/fetch-llamacpp.sh --write-sums` and committed; every later fetch verifies against it. (On Linux, `shasum` is in the `perl` package and present on GitHub runners; `sha256sum` output format is compatible if `shasum` is missing — the CI job in Task 10 uses `shasum`.)

```c
/* engine/ggml-stub.h — common/json.cpp includes ggml.h only for GGML_ASSERT. */
#pragma once
#include <stdio.h>
#include <stdlib.h>
#define GGML_ASSERT(x) do { if (!(x)) { fprintf(stderr, "GGML_ASSERT(%s) failed at %s:%d\n", #x, __FILE__, __LINE__); abort(); } } while (0)
```

- [ ] **Step 4: The shim**

```cpp
// engine/shim.cpp — reactor-style WASM entry points around llama.cpp's common/jinja engine.
// Mirrors common_chat_template_direct_apply_impl (common/chat.cpp) minus the BOS strip:
//   lex -> parse -> caps_get -> normalise messages -> render at a pinned clock.
// JSON in, JSON out, through linear memory. Never lets a C++ exception escape.
#include "jinja/caps.h"
#include "jinja/lexer.h"
#include "jinja/parser.h"
#include "jinja/runtime.h"
#include "jinja/value.h"
#include "json.h"
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <cstring>
#include <string>

using njson = nlohmann::ordered_json;

// 2026-01-01T00:00:00Z; must equal ggufdoctor.engines.jinja2_engine.PINNED_NOW.
static const std::time_t PINNED_NOW = 1767225600;
static const char * RAISE_MARKER = "Jinja Exception: ";

static std::string g_out;

// ---- port of messages_inp_normalizer from common/chat.cpp (keep in sync on every engine bump) ----

static std::string concat_content_parts(const njson & parts) {
    std::string text;
    bool last_was_media_marker = false;
    for (const auto & part : parts) {
        std::string type = part.value("type", "");
        bool add_new_line = true;
        if (type == "text") {
            add_new_line = !last_was_media_marker && !text.empty();
            last_was_media_marker = false;
        } else if (type == "media_marker") {
            add_new_line = false;
            last_was_media_marker = true;
        } else {
            continue; // chat.cpp logs a warning and drops unknown part types
        }
        if (add_new_line) {
            text += '\n';
        }
        text += part.value("text", "");
    }
    return text;
}

static njson normalize_messages(const njson & messages, const jinja::caps & caps, bool & changed) {
    changed = false;
    const bool only_string = caps.supports_string_content && !caps.supports_typed_content;
    const bool only_typed  = !caps.supports_string_content && caps.supports_typed_content;
    if ((!only_string && !only_typed) || !messages.is_array()) {
        return messages;
    }
    njson out = njson::array();
    for (const auto & msg : messages) {
        njson copy = msg;
        if (copy.contains("content")) {
            njson & it = copy.at("content");
            if (only_typed && it.is_string()) {
                it = njson::array({ njson{{"type", "text"}, {"text", it.get<std::string>()}} });
                changed = true;
            } else if (only_string && it.is_array()) {
                it = concat_content_parts(it);
                changed = true;
            }
        }
        out.push_back(std::move(copy));
    }
    return out;
}

// ---- rendering ----

static njson caps_to_json(const jinja::caps & caps) {
    njson out = njson::object();
    for (const auto & kv : caps.to_map()) {
        out[kv.first] = kv.second;
    }
    return out;
}

static njson render_job(const std::string & job_text) {
    njson out;
    njson caps_json = njson::object();
    bool normalized = false;
    try {
        njson job = njson::parse(job_text);
        const std::string tmpl = job.at("template").get<std::string>();
        const bool normalize = job.value("normalize", true);
        njson context = job.contains("context") ? job.at("context") : njson::object();

        jinja::lexer lexer;
        jinja::lexer_result lexed;
        jinja::program prog;
        try {
            lexed = lexer.tokenize(tmpl);
        } catch (const std::exception & e) {
            return njson{{"ok", false}, {"stage", "lexer"}, {"error", e.what()}};
        }
        try {
            prog = jinja::parse_from_tokens(lexed);
        } catch (const std::exception & e) {
            return njson{{"ok", false}, {"stage", "parser"}, {"error", e.what()}};
        }

        jinja::caps caps = jinja::caps_get(prog);
        caps_json = caps_to_json(caps);
        if (normalize && context.contains("messages")) {
            context["messages"] = normalize_messages(context.at("messages"), caps, normalized);
        }

        jinja::context ctx(lexed.source);
        ctx.current_time = PINNED_NOW;
        common_json inp = common_json::parse(context.dump());
        jinja::global_from_json(ctx, inp, false);

        jinja::runtime rt(ctx);
        const jinja::value results = rt.execute(prog);
        auto parts = jinja::runtime::gather_string_parts(results);
        out = njson{{"ok", true}, {"text", parts->as_string().str()}};
    } catch (const std::exception & e) {
        // raise_exception() throws "Jinja Exception: <author message>", which the
        // runtime re-wraps with source location. Recover the author's message.
        const std::string what = e.what();
        const size_t at = what.find(RAISE_MARKER);
        if (at != std::string::npos) {
            out = njson{{"ok", false}, {"stage", "raise"}, {"error", what.substr(at + std::strlen(RAISE_MARKER))}};
        } else {
            out = njson{{"ok", false}, {"stage", "render"}, {"error", what}};
        }
    } catch (...) {
        out = njson{{"ok", false}, {"stage", "render"}, {"error", "unknown non-standard exception"}};
    }
    out["caps"] = caps_json;
    out["normalized"] = normalized;
    return out;
}

extern "C" {

__attribute__((export_name("gd_alloc")))
char * gd_alloc(size_t n) { return static_cast<char *>(malloc(n)); }

__attribute__((export_name("gd_free")))
void gd_free(char * p) { free(p); }

__attribute__((export_name("gd_out_len")))
size_t gd_out_len() { return g_out.size(); }

__attribute__((export_name("gd_render")))
const char * gd_render(const char * in, size_t len) {
    try {
        g_out = render_job(std::string(in, len)).dump();
    } catch (...) {
        g_out = "{\"ok\":false,\"stage\":\"render\",\"error\":\"shim failure while serialising result\"}";
    }
    return g_out.c_str();
}

} // extern "C"
```

Note that a `raise_exception` reached via `{{ ... }}` is stage `raise`; a `{% raise_exception(...) %}` *statement* is a parser error in llama.cpp (the engine has no such statement) and stays stage `parser` — that is the truth about llama.cpp, and Task 5 reports it as "will not load".

- [ ] **Step 5: The build script**

```sh
#!/bin/sh
# engine/build.sh — build src/ggufdoctor/engine_data/llamacpp-jinja.wasm from the pinned sources.
# Usage: engine/build.sh [--out DIR]     (default DIR: src/ggufdoctor/engine_data)
# Env:   WASI_SDK=/path/to/wasi-sdk-34.0-<host>   (downloaded into engine/build/ when unset)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
. "$HERE/LLAMACPP_PIN"
OUT_DIR="$ROOT/src/ggufdoctor/engine_data"
if [ "${1:-}" = "--out" ]; then OUT_DIR="$2"; fi
mkdir -p "$OUT_DIR"

SRC="$HERE/build/llamacpp"
[ -f "$SRC/jinja/runtime.cpp" ] || "$HERE/fetch-llamacpp.sh"

WASI_SDK_TAG=wasi-sdk-34
if [ -z "${WASI_SDK:-}" ]; then
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)  HOST=arm64-macos ;;
    Darwin-x86_64) HOST=x86_64-macos ;;
    Linux-x86_64)  HOST=x86_64-linux ;;
    Linux-aarch64) HOST=arm64-linux ;;
    *) echo "unsupported host $(uname -s)-$(uname -m); set WASI_SDK" >&2; exit 2 ;;
  esac
  WASI_SDK="$HERE/build/${WASI_SDK_TAG}.0-$HOST"
  if [ ! -x "$WASI_SDK/bin/clang++" ]; then
    mkdir -p "$HERE/build"
    curl -sfL "https://github.com/WebAssembly/wasi-sdk/releases/download/${WASI_SDK_TAG}/${WASI_SDK_TAG}.0-${HOST}.tar.gz" \
      | tar xz -C "$HERE/build"
  fi
fi
SYSROOT="$WASI_SDK/share/wasi-sysroot"

# See https://github.com/WebAssembly/wasi-sdk/blob/main/CppExceptions.md for the EH flags.
# -I must not include $SRC/jinja: jinja/string.h would shadow the C <string.h>.
"$WASI_SDK/bin/clang++" --target=wasm32-wasip1 -mexec-model=reactor -std=c++17 -Oz \
  -fwasm-exceptions -mllvm -wasm-use-legacy-eh=false -Wl,-mllvm,-wasm-use-legacy-eh=false \
  -Wl,--strip-all \
  -I"$SRC" -I"$SRC/include" -I"$SRC/common" \
  -L"$SYSROOT/lib/wasm32-wasip1/eh" \
  "$HERE/shim.cpp" \
  "$SRC/jinja/lexer.cpp" "$SRC/jinja/parser.cpp" "$SRC/jinja/runtime.cpp" \
  "$SRC/jinja/value.cpp" "$SRC/jinja/string.cpp" "$SRC/jinja/caps.cpp" \
  "$SRC/common/json.cpp" "$SRC/common/unicode.cpp" \
  -lunwind -o "$OUT_DIR/llamacpp-jinja.wasm"

python3 - "$OUT_DIR/llamacpp-jinja.wasm" "$commit" "$build_tag" "$WASI_SDK_TAG" <<'PY'
import datetime, hashlib, json, os, sys
path, commit, tag, sdk = sys.argv[1:5]
blob = open(path, "rb").read()
manifest = {
    "engine": "llama.cpp", "build_tag": tag, "commit": commit, "wasi_sdk": sdk,
    "sha256": hashlib.sha256(blob).hexdigest(), "size": len(blob),
    "built_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
with open(os.path.splitext(path)[0] + ".json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=1)
    f.write("\n")
print(f"{path}: {len(blob)} bytes, sha256 {manifest['sha256'][:12]}...")
PY
```

`engine/README.md` states, in prose: what the module is, how to rebuild it (`engine/build.sh`), how to bump the pin (edit `LLAMACPP_PIN`, run `fetch-llamacpp.sh --write-sums`, rebuild, run the semantics test and conformance suite, update `SOURCES` in the bump PR), and that the normaliser in `shim.cpp` is a port of `messages_inp_normalizer` from `common/chat.cpp` that must be re-checked on every bump. Create `src/ggufdoctor/engine_data/__init__.py` empty. Append `engine/build/` to `.gitignore`.

- [ ] **Step 6: Build and run the tests**

```bash
chmod +x engine/fetch-llamacpp.sh engine/build.sh
engine/fetch-llamacpp.sh --write-sums
engine/build.sh
.venv/bin/python -m pytest tests/test_engine_data.py -v
```

Expected: the module builds with no `error:` lines; the file is roughly 650–700 KB; both tests PASS. If the wasi-sdk download fails for the host, set `WASI_SDK` to a pre-downloaded SDK. Smoke-test the module by hand once with the spike venv recipe if you want to see it render (`docs/research/2026-09-03-engine-spike/driver.py` shows the wasmtime calls) — Task 2 does this properly.

- [ ] **Step 7: Commit**

```bash
git add engine/ src/ggufdoctor/engine_data/ tests/test_engine_data.py .gitignore
git commit -m "feat(engine): build llama.cpp common/jinja to WASM with caps and message normaliser

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `LlamaCppEngine` — the wasmtime host

**Files:**
- Modify: `src/ggufdoctor/models.py` (`RenderResult.extra`)
- Create: `src/ggufdoctor/engines/llamacpp_engine.py`
- Modify: `pyproject.toml` (`dependencies`)
- Test: `tests/test_engine_llamacpp.py`

**Interfaces:**
- Consumes: module ABI and manifest from Task 1; `BASE_CONTEXT` from `ggufdoctor.engines.jinja2_engine`.
- Produces: `class LlamaCppEngine` with `name = "llama.cpp"`, `version: str` (build tag), `commit: str`, `backend: str | None` (e.g. `"wasmtime 48.0.0"`), `available: bool`, `unavailable_reason: str | None`, `render(template, context) -> RenderResult`; `RenderResult.extra: dict[str, Any]` (keys `caps`, `normalized` when the llama.cpp engine produced the result); module constant `ENV_MODULE_PATH = "GGUFDOCTOR_ENGINE_WASM"`.

- [ ] **Step 1: Add the dependency and install**

In `pyproject.toml` set `dependencies = ["jinja2>=3.1", "wasmtime>=48,<49"]`, then:

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -c "import wasmtime; print('wasmtime ok')"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_engine_llamacpp.py
import sys

import pytest

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT, Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import ENV_MODULE_PATH, LlamaCppEngine

MESSAGES = {"messages": [{"role": "user", "content": "hi"}]}


def test_engine_identifies_the_pinned_llama_cpp_build():
    e = LlamaCppEngine()
    assert e.available, e.unavailable_reason
    assert e.name == "llama.cpp"
    assert e.version == "b10775"
    assert e.commit == "67a17c17caa95742186f8b1ecadd1b5abd6d5ebb"
    assert e.backend.startswith("wasmtime ")


def test_renders_simple_template():
    r = LlamaCppEngine().render(
        "{% for m in messages %}{{ m['content'] }}{% endfor %}", MESSAGES)
    assert r.ok
    assert r.text == "hi"
    assert r.extra["normalized"] is False
    assert "supports_tools" in r.extra["caps"]


def test_base_context_defaults_match_jinja2_engine():
    # Both engines must see the identical context. BASE_CONTEXT is what
    # Jinja2Engine fills in; the llama.cpp engine must fill in the same.
    tpl = "{{ bos_token }}|{{ eos_token }}|{{ add_generation_prompt }}"
    a = Jinja2Engine().render(tpl, {})
    b = LlamaCppEngine().render(tpl, {})
    assert a.ok and b.ok
    assert a.text == b.text == f"{BASE_CONTEXT['bos_token']}|{BASE_CONTEXT['eos_token']}|True"


def test_parser_failure_is_a_compile_error():
    # `//` (floor division) is valid Jinja but llama.cpp's parser rejects it.
    r = LlamaCppEngine().render("{{ 7 // 2 }}", {})
    assert not r.ok
    assert r.error.startswith("compile:parser:")


def test_author_decline_is_tagged_raise_with_verbatim_message():
    r = LlamaCppEngine().render(
        "{{ raise_exception('Only user and assistant roles are supported!') }}", {})
    assert not r.ok
    assert r.error == "raise:Only user and assistant roles are supported!"


def test_engine_failure_is_tagged_render():
    r = LlamaCppEngine().render("{{ none | length }}", {})
    assert not r.ok
    assert r.error.startswith("render:")
    assert "\n" not in r.error, "render errors are one line for the report"


def test_strftime_now_is_pinned_like_jinja2():
    tpl = "{{ strftime_now('%d %b %Y') }}"
    assert LlamaCppEngine().render(tpl, {}).text == Jinja2Engine().render(tpl, {}).text == "01 Jan 2026"


def test_normaliser_rewrites_typed_content_for_string_only_templates():
    # This template concatenates content as a string, so caps say
    # supports_typed_content=false; llama.cpp joins the parts with "\n".
    tpl = "{% for m in messages %}<{{ m['content'] }}>{% endfor %}"
    ctx = {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "Hello"}, {"type": "text", "text": "there"}]}]}
    r = LlamaCppEngine().render(tpl, ctx)
    assert r.ok
    assert r.text == "<Hello\nthere>"
    assert r.extra["normalized"] is True
    assert r.extra["caps"]["supports_typed_content"] is False


def test_missing_module_file_makes_engine_unavailable_not_raising(tmp_path):
    e = LlamaCppEngine(module_path=str(tmp_path / "missing.wasm"))
    assert e.available is False
    assert "missing.wasm" in e.unavailable_reason
    r = e.render("x", {})
    assert not r.ok
    assert r.error.startswith("engine:unavailable:")


def test_env_var_overrides_module_path(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.wasm"
    bad.write_bytes(b"\x00asm\x01\x00\x00\x00garbage")
    monkeypatch.setenv(ENV_MODULE_PATH, str(bad))
    e = LlamaCppEngine()
    assert e.available  # the file exists; compile happens lazily
    r = e.render("x", {})
    assert not r.ok
    assert r.error.startswith("render:wasm:")


def test_wasmtime_import_failure_makes_engine_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "wasmtime", None)  # forces ImportError
    e = LlamaCppEngine()
    assert e.available is False
    assert "wasmtime" in e.unavailable_reason
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_engine_llamacpp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ggufdoctor.engines.llamacpp_engine'`

- [ ] **Step 4: `RenderResult.extra`**

In `src/ggufdoctor/models.py`:

```python
@dataclass
class RenderResult:
    text: str | None
    error: str | None
    # Engine-specific facts about how this result was produced, for reports
    # and checks that need to explain a divergence (llama.cpp: "caps" and
    # "normalized"). Empty for engines with nothing to add.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None
```

- [ ] **Step 5: The engine**

```python
# src/ggufdoctor/engines/llamacpp_engine.py
"""llama.cpp's own chat-template engine (common/jinja), run from a WASM module.

The module is built by engine/build.sh from a pinned llama.cpp commit; see
engine/README.md. It mirrors common_chat_template_direct_apply_impl in
common/chat.cpp (caps probe, message normaliser, pinned clock) but does not
strip a leading BOS -- see the v0.2 spec amendments, section A.
"""
from __future__ import annotations

import json
import os
from importlib import metadata, resources
from typing import Any

from ggufdoctor.engines.jinja2_engine import BASE_CONTEXT
from ggufdoctor.models import RenderResult

MODULE_NAME = "llamacpp-jinja.wasm"
MANIFEST_NAME = "llamacpp-jinja.json"
ENV_MODULE_PATH = "GGUFDOCTOR_ENGINE_WASM"


def load_manifest() -> dict[str, Any]:
    raw = (resources.files("ggufdoctor.engine_data")
           .joinpath(MANIFEST_NAME).read_text(encoding="utf-8"))
    return json.loads(raw)


def _first_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[0] if lines else text.strip()


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else text.strip()


class LlamaCppEngine:
    name = "llama.cpp"

    def __init__(self, module_path: str | None = None) -> None:
        manifest = load_manifest()
        self.version: str = manifest["build_tag"]
        self.commit: str = manifest["commit"]
        self.backend: str | None = None
        self.available = False
        self.unavailable_reason: str | None = None
        self._module_path = module_path or os.environ.get(ENV_MODULE_PATH)
        self._wasm_bytes: bytes | None = None
        self._engine = None
        self._module = None
        self._linker = None

        try:
            import wasmtime  # noqa: F401  (import check only)
        except Exception as e:  # ImportError, or a broken native library
            self.unavailable_reason = f"wasmtime not importable: {e}"
            return
        self.backend = f"wasmtime {metadata.version('wasmtime')}"

        try:
            self._wasm_bytes = self._read_module()
        except Exception as e:
            self.unavailable_reason = f"engine module unavailable: {e}"
            return
        self.available = True

    def _read_module(self) -> bytes:
        if self._module_path:
            with open(self._module_path, "rb") as f:
                return f.read()
        return resources.files("ggufdoctor.engine_data").joinpath(MODULE_NAME).read_bytes()

    def _ensure_compiled(self) -> None:
        if self._module is not None:
            return
        import wasmtime
        cfg = wasmtime.Config()
        cfg.wasm_exceptions = True
        try:
            # ~120 ms JIT compile per process without this, ~6 ms with it.
            # A read-only or missing cache directory must never stop a render.
            cfg.cache = True
        except Exception:
            pass
        self._engine = wasmtime.Engine(cfg)
        self._module = wasmtime.Module(self._engine, self._wasm_bytes)
        self._linker = wasmtime.Linker(self._engine)
        self._linker.define_wasi()

    def render(self, template: str, context: dict[str, Any]) -> RenderResult:
        if not self.available:
            return RenderResult(None, f"engine:unavailable: {self.unavailable_reason}")
        ctx = dict(BASE_CONTEXT)
        ctx.update(context)
        payload = json.dumps({"template": template, "context": ctx, "normalize": True}).encode("utf-8")
        try:
            self._ensure_compiled()
            import wasmtime
            store = wasmtime.Store(self._engine)
            store.set_wasi(wasmtime.WasiConfig())
            exports = self._linker.instantiate(store, self._module).exports(store)
            exports["_initialize"](store)
            memory = exports["memory"]
            in_ptr = exports["gd_alloc"](store, len(payload))
            memory.write(store, payload, in_ptr)
            out_ptr = exports["gd_render"](store, in_ptr, len(payload))
            out_len = exports["gd_out_len"](store)
            raw = bytes(memory.read(store, out_ptr, out_ptr + out_len))
            exports["gd_free"](store, in_ptr)
            result = json.loads(raw)
        except Exception as e:  # wasmtime trap, compile failure, corrupt module
            return RenderResult(None, f"render:wasm: {type(e).__name__}: {_first_line(str(e))}")

        extra = {"caps": result.get("caps", {}), "normalized": bool(result.get("normalized", False))}
        if result.get("ok"):
            return RenderResult(result["text"], None, extra=extra)
        stage = result.get("stage", "render")
        err = result.get("error", "")
        if stage in ("lexer", "parser"):
            return RenderResult(None, f"compile:{stage}: {_first_line(err)}", extra=extra)
        if stage == "raise":
            return RenderResult(None, f"raise:{err}", extra=extra)
        return RenderResult(None, f"render:{_last_line(err)}", extra=extra)
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_engine_llamacpp.py tests/test_engine_jinja2.py -v`
Expected: all PASS. If `test_wasmtime_import_failure_makes_engine_unavailable` fails because `wasmtime` was already imported by an earlier test, that is fine: `monkeypatch.setitem(sys.modules, "wasmtime", None)` makes `import wasmtime` raise `ImportError` regardless of prior imports.

- [ ] **Step 7: Full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add pyproject.toml src/ggufdoctor/models.py src/ggufdoctor/engines/llamacpp_engine.py tests/test_engine_llamacpp.py
git commit -m "feat(engine): LlamaCppEngine hosts the WASM module through wasmtime

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Engine semantics table — pin both engines' behaviour on the known divergences

**Files:**
- Test: `tests/test_engine_semantics.py`

**Interfaces:**
- Consumes: `Jinja2Engine`, `LlamaCppEngine` (Task 2).
- Produces: nothing; this is the tripwire that makes an engine bump visible.

- [ ] **Step 1: Write the test**

```python
# tests/test_engine_semantics.py
"""Pins how BOTH engines behave on the expressions where they are known to
differ (and a sample where they agree). Measured 2026-09-03 against Jinja2
3.1.6 and llama.cpp b10775 -- see docs/research/2026-09-03-engine-spike.md §3.

A failing row after an engine bump is not a bug in this test: it is the bump
changing user-visible semantics, and the X-family messages / spec must be
re-checked before the row is updated.
"""
import pytest

from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine

OK = "ok"
RENDER_ERR = "render"
COMPILE_ERR = "compile"

# (label, template, context, jinja2 outcome, llama.cpp outcome)
# An outcome is the rendered text, or RENDER_ERR / COMPILE_ERR.
ROWS = [
    ("print None",            "[{{ n }}]",            {"n": None},        "[None]",       "[]"),
    ("print list",            "[{{ l }}]",            {"l": [1, "a"]},    "[[1, 'a']]",   "[1a]"),
    ("print dict",            "[{{ d }}]",            {"d": {"a": 1}},    "[{'a': 1}]",   "[]"),
    ("str + None",            "[{{ 'x' + n }}]",      {"n": None},        RENDER_ERR,     "[x]"),
    ("str + list",            "[{{ 'x' + l }}]",      {"l": ["a"]},       RENDER_ERR,     "[x['a']]"),
    ("default on None",       "[{{ n | default('d') }}]", {"n": None},    "[None]",       "[d]"),
    ("floor division",        "[{{ 7 // 2 }}]",       {},                 "[3]",          COMPILE_ERR),
    ("length of None",        "[{{ n | length }}]",   {"n": None},        RENDER_ERR,     RENDER_ERR),
    # agreement rows -- these guard against regressions in either engine
    ("str ~ list",            "[{{ 'x' ~ l }}]",      {"l": ["a"]},       "[x['a']]",     "[x['a']]"),
    ("undefined var",         "[{{ u }}]",            {},                 "[]",           "[]"),
    ("tojson non-ascii",      "[{{ d | tojson }}]",   {"d": {"b": 1, "a": "é"}}, '[{"b": 1, "a": "é"}]', '[{"b": 1, "a": "é"}]'),
    ("tojson indent",         "[{{ d | tojson(indent=2) }}]", {"d": {"b": [1, 2]}},
                              '[{\n  "b": [\n    1,\n    2\n  ]\n}]', '[{\n  "b": [\n    1,\n    2\n  ]\n}]'),
    ("namespace",             "{% set ns = namespace(x=1) %}{% set ns.x = 2 %}[{{ ns.x }}]", {}, "[2]", "[2]"),
    ("generation tag",        "{% generation %}hi{% endgeneration %}", {}, "hi", "hi"),
    ("dictsort",              "{% for k, v in d | dictsort %}{{ k }}{% endfor %}", {"d": {"b": 1, "a": 2}}, "ab", "ab"),
    ("negative slice",        "[{{ s[-3:] }}]",       {"s": "abcdef"},    "[def]",        "[def]"),
    ("is mapping/iterable",   "[{{ 'ab' is iterable }}][{{ {} is mapping }}]", {}, "[True][True]", "[True][True]"),
    ("loop.index",            "{% for i in range(3) %}{{ loop.index }}{% endfor %}", {}, "123", "123"),
    ("break",                 "{% for i in range(3) %}{% if i == 1 %}{% break %}{% endif %}{{ i }}{% endfor %}", {}, "0", "0"),
]


def _outcome(result):
    if result.ok:
        return result.text
    if result.error.startswith("compile:"):
        return COMPILE_ERR
    return RENDER_ERR


@pytest.fixture(scope="module")
def engines():
    llama = LlamaCppEngine()
    assert llama.available, llama.unavailable_reason
    return Jinja2Engine(), llama


@pytest.mark.parametrize("label,template,context,expect_j2,expect_llama", ROWS,
                         ids=[r[0] for r in ROWS])
def test_semantics_row(engines, label, template, context, expect_j2, expect_llama):
    j2, llama = engines
    assert _outcome(j2.render(template, context)) == expect_j2, "jinja2 changed"
    assert _outcome(llama.render(template, context)) == expect_llama, "llama.cpp changed"


def test_table_covers_every_divergence_class_named_in_the_spike():
    labels = {r[0] for r in ROWS}
    for needed in ("print None", "print list", "str + None", "default on None", "floor division"):
        assert needed in labels
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_engine_semantics.py -v`
Expected: every row PASSES. If a row fails, do **not** edit the expectation to match: compare against `docs/research/2026-09-03-engine-spike.md` §3; a mismatch there means the engine build (Task 1) or the error mapping (Task 2) is wrong, and the fix belongs in those tasks.

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine_semantics.py
git commit -m "test: pin jinja2 vs llama.cpp semantics table from the engine spike

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
### Task 4: Fixture corpus v2 with tiers, and S003/S007 tier awareness

**Files:**
- Modify: `src/ggufdoctor/models.py` (`Fixture.tier`)
- Modify: `src/ggufdoctor/fixtures.py` (`CORPUS_VERSION = "2"`, tier loading)
- Modify: `src/ggufdoctor/fixture_data/corpus.json`
- Modify: `src/ggufdoctor/checks/sanity.py` (S003, S007)
- Test: `tests/test_fixtures.py`, `tests/test_checks_sanity.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Fixture(name, context, tier="core")` with `tier in {"core", "extended"}`; fixture names `tool_roundtrip`, `typed_content`, `no_generation_prompt`; `CORPUS_VERSION == "2"`.

Why tiers exist: the spike showed 10 of 100 real templates raise a `TypeError` under transformers-style Jinja2 when handed typed content, and many decline a `tool` role. Those templates are not defective; the corpus is asking them shapes they predate. An `extended` fixture therefore never produces an S003 ERROR (it produces INFO), and S007 only ever looks at `user_only`.

- [ ] **Step 1: Write the failing tests**

Replace the first and third tests in `tests/test_fixtures.py` and add two:

```python
def test_corpus_has_expected_fixtures_in_order():
    names = [f.name for f in load_fixtures()]
    assert names == ["user_only", "system_user", "multiturn", "with_tools",
                     "thinking_unset", "thinking_true", "thinking_false",
                     "tool_roundtrip", "typed_content", "no_generation_prompt"]


def test_corpus_version_is_declared():
    assert CORPUS_VERSION == "2"


def test_tiers_split_core_from_extended():
    tiers = {f.name: f.tier for f in load_fixtures()}
    assert {n for n, t in tiers.items() if t == "extended"} == {
        "tool_roundtrip", "typed_content", "no_generation_prompt"}
    assert all(t == "core" for n, t in tiers.items()
               if n not in ("tool_roundtrip", "typed_content", "no_generation_prompt"))


def test_extended_fixtures_carry_the_shapes_the_spike_found_divergence_on():
    fx = {f.name: f.context for f in load_fixtures()}
    assistant = fx["tool_roundtrip"]["messages"][2]
    assert assistant["role"] == "assistant" and assistant["content"] is None
    assert isinstance(assistant["tool_calls"][0]["function"]["arguments"], dict)
    assert fx["tool_roundtrip"]["messages"][3]["role"] == "tool"
    assert fx["tool_roundtrip"]["tools"][0]["function"]["name"] == "get_weather"
    assert isinstance(fx["typed_content"]["messages"][0]["content"], list)
    assert fx["no_generation_prompt"]["add_generation_prompt"] is False


def test_unknown_tier_is_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"version": "x", "fixtures": [{"name": "a", "tier": "bogus", "context": {}}]}')
    with pytest.raises(ValueError, match="tier"):
        load_fixtures(str(p))
```

Add `import pytest` at the top of `tests/test_fixtures.py`.

In `tests/test_checks_sanity.py` add:

```python
def _model_with(template, **kw):
    return GgufModel(source_id="t", architecture="llama", chat_template=template,
                     tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1,
                     add_bos_token=False, **kw)


def test_s003_on_extended_fixture_is_info_not_error():
    # `'x' + None` raises TypeError under Jinja2 only on tool_roundtrip
    # (assistant content is null there). That is the fixture asking a shape
    # the template predates -- reported, but never as an error.
    # Core fixtures all have string content, so only the two extended
    # fixtures fail -- with two different TypeErrors (NoneType vs list), so
    # they collapse into two findings, not one.
    tpl = "{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content }}{% endfor %}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    findings = s003_render_error(ctx)
    found = {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}
    assert found == {("S003", Severity.INFO, ("tool_roundtrip",)),
                     ("S003", Severity.INFO, ("typed_content",))}
    for f in findings:
        assert "extended" in f.message and "broken" not in f.message


def test_s003_on_core_fixture_stays_error():
    tpl = "{{ messages[0].content + none }}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    severities = {f.severity for f in s003_render_error(ctx)
                  if "user_only" in f.evidence.get("fixtures", ())}
    assert severities == {Severity.ERROR}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fixtures.py tests/test_checks_sanity.py -v`
Expected: the new fixture tests FAIL on names/version/`tier` attribute; `test_s003_on_extended_fixture_is_info_not_error` FAILS (no `tool_roundtrip` fixture yet, and severity would be ERROR).

- [ ] **Step 3: Models and loader**

`src/ggufdoctor/models.py`:

```python
FIXTURE_TIERS = ("core", "extended")


@dataclass(frozen=True)
class Fixture:
    name: str
    context: dict[str, Any]
    # "core": a conversation every chat template is expected to handle.
    # "extended": a shape (typed content, tool-call round trip, no generation
    # prompt) that older templates legitimately predate. Checks downgrade
    # render failures on extended fixtures to INFO -- see checks/sanity.py S003.
    tier: str = "core"
```

`src/ggufdoctor/fixtures.py`:

```python
from ggufdoctor.models import FIXTURE_TIERS, Fixture

CORPUS_VERSION = "2"


def load_fixtures(path: str | None = None) -> list[Fixture]:
    if path is None:
        raw = (resources.files("ggufdoctor.fixture_data")
               .joinpath("corpus.json").read_text(encoding="utf-8"))
        data = json.loads(raw)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    out = []
    for item in data["fixtures"]:
        tier = item.get("tier", "core")
        if tier not in FIXTURE_TIERS:
            raise ValueError(
                f"fixture {item.get('name')!r} has unknown tier {tier!r} "
                f"(expected one of {', '.join(FIXTURE_TIERS)})")
        out.append(Fixture(name=item["name"], context=item["context"], tier=tier))
    return out
```

- [ ] **Step 4: Corpus**

In `src/ggufdoctor/fixture_data/corpus.json` set `"version": "2"` and append these three entries after `thinking_false` (copy the `get_weather` tool object from `with_tools` verbatim into `tool_roundtrip`):

```json
    {"name": "tool_roundtrip", "tier": "extended",
     "context": {"messages": [
                   {"role": "system", "content": "Be brief."},
                   {"role": "user", "content": "Weather in Paris?"},
                   {"role": "assistant", "content": null,
                    "tool_calls": [{"id": "call_1", "type": "function",
                                    "function": {"name": "get_weather",
                                                 "arguments": {"city": "Paris"}}}]},
                   {"role": "tool", "tool_call_id": "call_1", "name": "get_weather",
                    "content": "{\"temp_c\": 18}"}],
                 "add_generation_prompt": true,
                 "tools": [ ...the same get_weather tool object as with_tools... ]}},
    {"name": "typed_content", "tier": "extended",
     "context": {"messages": [{"role": "user",
                               "content": [{"type": "text", "text": "Hello"},
                                           {"type": "text", "text": "there"}]}],
                 "add_generation_prompt": true}},
    {"name": "no_generation_prompt", "tier": "extended",
     "context": {"messages": [{"role": "user", "content": "Hi"},
                              {"role": "assistant", "content": "Hello!"}],
                 "add_generation_prompt": false}}
```

Validate the file parses: `.venv/bin/python -c "from ggufdoctor.fixtures import load_fixtures; print([f.name for f in load_fixtures()])"`.

- [ ] **Step 5: S003 and S007 tier awareness**

In `src/ggufdoctor/checks/sanity.py`, `s003_render_error` gets a third bucket:

```python
    failures: list[tuple[str, Any, dict[str, Any]]] = []
    extended_failures: list[tuple[str, Any, dict[str, Any]]] = []
    declines: list[tuple[str, Any, dict[str, Any]]] = []
    for fx in ctx.fixtures:
        r = _render_fixture(ctx, fx)
        if not r.error:
            continue
        if r.error.startswith("render:"):
            bucket = extended_failures if fx.tier == "extended" else failures
            bucket.append((fx.name, r.error, {"error": r.error}))
        elif r.error.startswith("raise:"):
            ...unchanged...
    findings = _collapse_by_signature(
        "S003", Severity.ERROR,
        "template raises while rendering a standard conversation", failures)
    findings.extend(_collapse_by_signature(
        "S003", Severity.INFO,
        lambda evidence: (
            "template does not handle an extended conversation shape "
            f"({', '.join(evidence['fixtures'])}); older templates predate these "
            f"inputs — {evidence['error']}"),
        extended_failures))
    findings.extend(_collapse_by_signature("S003", Severity.INFO, ...declines unchanged...))
    return findings
```

S007 already renders only `user_only`, which is core; add one line of comment saying so, no code change. S008 (empty render) is left as is: an extended fixture rendering to *empty* is still a real fact about the template.

- [ ] **Step 6: Run the whole suite and reconcile real-template expectations**

Run: `.venv/bin/python -m pytest -q`

The four complete-finding-set tests in `tests/test_checks_sanity.py` (Mistral-v0.2, Llama-2, Gemma-2, Llama-3.3-tools) will now see three more fixtures and may gain findings. For each changed expectation, **read the template** and write the reason into the test's comment block in the same style as the existing ones (e.g. "S003 INFO on `tool_roundtrip`: Mistral's alternation guard rejects the `tool` role via `raise_exception` — author decline, same signature as `system_user` so it collapses into that finding"; "S003 INFO on `typed_content`: `message['content']` is concatenated as a string, list content raises `TypeError` under transformers; extended tier, hence INFO"). Do not add expectations you cannot justify from the template text; if a finding looks wrong, stop and report it (`DONE_WITH_CONCERNS`).

Expected: all tests PASS with justified updates only.

- [ ] **Step 7: Commit**

```bash
git add src/ggufdoctor/models.py src/ggufdoctor/fixtures.py src/ggufdoctor/fixture_data/corpus.json src/ggufdoctor/checks/sanity.py tests/test_fixtures.py tests/test_checks_sanity.py
git commit -m "feat(fixtures): corpus v2 adds extended-tier fixtures; S003 reports them at INFO

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Family X — cross-engine checks

**Files:**
- Create: `src/ggufdoctor/checks/common.py`
- Modify: `src/ggufdoctor/checks/sanity.py` (import the shared helpers; keep `_real_token`, `_with_real_tokens`, `_collapse_by_signature` names as aliases so existing imports keep working)
- Modify: `src/ggufdoctor/models.py` (`CheckContext.stats`)
- Create: `src/ggufdoctor/checks/cross_engine.py`
- Test: `tests/test_checks_cross_engine.py`

**Interfaces:**
- Consumes: `Jinja2Engine`, `LlamaCppEngine` (by `.name`), `Fixture.tier`, `RenderResult.extra`.
- Produces: `X_IDS = ["X001", "X002", "X004", "X005"]`; `run_cross_engine_checks(ctx: CheckContext) -> list[Finding]`; `ctx.stats["engines_agreed_fixtures"]: int` (fixtures both engines rendered byte-identically); `is_tool_fixture(fixture) -> bool`; `checks/common.py` exposing `real_token`, `with_real_tokens`, `collapse_by_signature`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_checks_cross_engine.py
from ggufdoctor.checks.cross_engine import X_IDS, run_cross_engine_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, RenderResult, Severity


def _ctx(template, engines=None, fixtures=None):
    model = GgufModel(source_id="t", architecture="llama", chat_template=template,
                      tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1,
                      add_bos_token=True)
    return CheckContext(model=model, engines=engines or [Jinja2Engine(), LlamaCppEngine()],
                        fixtures=fixtures or load_fixtures())


def _set(findings):
    return {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}


class FakeEngine:
    def __init__(self, name, outputs):
        self.name, self.version, self._outputs = name, "fake", outputs

    def render(self, template, context):
        out = self._outputs(context)
        return out if isinstance(out, RenderResult) else RenderResult(out, None)


ALL = ("user_only", "system_user", "multiturn", "with_tools", "thinking_unset",
       "thinking_true", "thinking_false", "tool_roundtrip", "typed_content", "no_generation_prompt")


CORE = ALL[:7]
NON_TOOL = ("user_only", "system_user", "multiturn", "thinking_unset", "thinking_true",
            "thinking_false", "typed_content", "no_generation_prompt")
TOOL = ("with_tools", "tool_roundtrip")


def test_identical_engines_produce_no_findings_and_record_agreement():
    core = [f for f in load_fixtures() if f.tier == "core"]
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}<|im_end|>", fixtures=core)
    assert run_cross_engine_checks(ctx) == []
    assert ctx.stats["engines_agreed_fixtures"] == len(CORE)
    assert ctx.checks_not_evaluated == []


def test_x001_output_differs_collapses_across_fixtures_with_a_diff():
    # `{{ none }}` prints "None" under jinja2 and nothing under llama.cpp, on
    # every fixture -- one collapsed X001, not ten.
    ctx = _ctx("{{ none }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    # tool fixtures belong to X005 (same divergence, its own id), the rest to X001
    assert _set(found) == {("X001", Severity.ERROR, NON_TOOL), ("X005", Severity.ERROR, TOOL)}
    f = next(f for f in found if f.id == "X001")
    assert f.evidence["engines"] == ["jinja2", "llama.cpp"]
    assert "-None<|im_start|>" in f.evidence["diff"] and "+<|im_start|>" in f.evidence["diff"]
    assert "broken" not in f.message


def test_x001_explained_by_the_normaliser_is_info():
    # `{{ m.content }}` on typed content: jinja2 prints the Python repr of the
    # list; llama.cpp's caps probe finds the template string-only, joins the
    # parts to text first, and prints "Hello\nthere". A real divergence, but
    # one llama.cpp's compatibility rewrite explains -- INFO, and the message
    # says so. tool_roundtrip (assistant content null) is the plain
    # None-vs-empty divergence with no rewrite involved -> X005 ERROR.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}<|im_end|>")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X001", Severity.INFO, ("typed_content",)),
                           ("X005", Severity.ERROR, ("tool_roundtrip",))}
    info = next(f for f in found if f.id == "X001")
    assert info.evidence["normalized"] is True and "normalis" in info.message


def test_x005_owns_tool_fixtures_and_x001_the_rest():
    ctx = _ctx("{% if tools %}{{ none }}{% endif %}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    assert _set(run_cross_engine_checks(ctx)) == {("X005", Severity.ERROR, TOOL)}


def test_x002_template_that_will_not_load_in_llama_cpp():
    ctx = _ctx("{{ 7 // 2 }}<|im_start|>{% for m in messages %}{{ m.role }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.ERROR, ALL)}
    assert found[0].message.startswith("template will not load in llama.cpp (parser:")
    assert found[0].evidence["failing_engine"] == "llama.cpp"


def test_x002_renders_in_llama_cpp_only_via_normaliser_is_info():
    # String concatenation: jinja2 raises TypeError on typed_content; llama.cpp
    # joins the parts first because caps say the template is string-only.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content if m.content is not none else '' }}{% endfor %}")
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.INFO, ("typed_content",))}
    assert found[0].evidence["failing_engine"] == "jinja2"
    assert found[0].evidence["normalized"] is True
    assert "normalis" in found[0].message  # "normaliser" spelled as in the report


def test_x002_renders_in_llama_cpp_only_without_normaliser_is_error():
    # `'x' + none` is a plain engine difference (jinja2 TypeError, llama.cpp "x")
    # on tool_roundtrip (assistant content is null). No normalisation involved.
    ctx = _ctx("{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content }}{% endfor %}")
    found = {(f.id, f.severity, tuple(f.evidence["fixtures"]), f.evidence["failing_engine"],
              f.evidence.get("normalized")) for f in run_cross_engine_checks(ctx)}
    assert ("X002", Severity.ERROR, ("tool_roundtrip",), "jinja2", False) in found
    assert ("X002", Severity.INFO, ("typed_content",), "jinja2", True) in found
    assert len(found) == 2


def test_both_engines_failing_is_not_an_x_finding():
    ctx = _ctx("{{ none | length }}")
    assert run_cross_engine_checks(ctx) == []


def test_author_decline_on_one_side_only_is_x002():
    j2 = FakeEngine("jinja2", lambda c: RenderResult(None, "raise:no system role"))
    llama = FakeEngine("llama.cpp", lambda c: "ok")
    ctx = _ctx("irrelevant", engines=[j2, llama])
    found = run_cross_engine_checks(ctx)
    assert _set(found) == {("X002", Severity.ERROR, ALL)}
    assert "raise_exception" in found[0].message and "no system role" in found[0].message


def test_x004_whitespace_only_is_warn():
    j2 = FakeEngine("jinja2", lambda c: "a b\n")
    llama = FakeEngine("llama.cpp", lambda c: "a  b")
    ctx = _ctx("irrelevant", engines=[j2, llama])
    assert _set(run_cross_engine_checks(ctx)) == {("X004", Severity.WARN, ALL)}


def test_single_engine_records_x_family_as_not_evaluated():
    ctx = _ctx("{{ messages[0].content }}", engines=[Jinja2Engine()])
    assert run_cross_engine_checks(ctx) == []
    assert ctx.checks_not_evaluated == X_IDS
    assert "engines_agreed_fixtures" not in ctx.stats


def test_no_template_is_not_an_x_finding():
    ctx = _ctx(None)
    assert run_cross_engine_checks(ctx) == []
    assert ctx.checks_not_evaluated == []


def test_real_tokens_reach_both_engines():
    seen = {}
    j2 = FakeEngine("jinja2", lambda c: seen.setdefault("j2", c["bos_token"]) and "x")
    llama = FakeEngine("llama.cpp", lambda c: seen.setdefault("llama", c["bos_token"]) and "x")
    run_cross_engine_checks(_ctx("irrelevant", engines=[j2, llama]))
    assert seen == {"j2": "<s>", "llama": "<s>"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_checks_cross_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ggufdoctor.checks.cross_engine'`

- [ ] **Step 3: Shared helpers and `CheckContext.stats`**

Create `src/ggufdoctor/checks/common.py` by **moving** `_real_token`, `_with_real_tokens` and `_collapse_by_signature` out of `sanity.py` verbatim (docstrings included), renamed without the underscore: `real_token`, `with_real_tokens`, `collapse_by_signature`. In `sanity.py` replace the three definitions with:

```python
from ggufdoctor.checks.common import collapse_by_signature, real_token, with_real_tokens

# Kept under their old names: tests and the reference checks import these.
_real_token = real_token
_with_real_tokens = with_real_tokens
_collapse_by_signature = collapse_by_signature
```

In `models.py` add to `CheckContext`:

```python
    # Facts a check family wants the report to carry that are not findings
    # (e.g. cross_engine: "engines_agreed_fixtures"). Never used to decide
    # exit codes.
    stats: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: The checks**

```python
# src/ggufdoctor/checks/cross_engine.py
"""Family X: does llama.cpp render this template the way transformers does?

Both engines get the identical context -- BASE_CONTEXT defaults, the fixture,
the model's real bos/eos tokens -- and the raw rendered text is compared.
Neither side strips BOS (spec amendments §A). A fixture both engines fail on
belongs to S003, not here.
"""
from __future__ import annotations

import difflib
from typing import Any

from ggufdoctor.checks.common import collapse_by_signature, with_real_tokens
from ggufdoctor.models import CheckContext, Finding, Fixture, RenderResult, Severity

X_IDS = ["X001", "X002", "X004", "X005"]
JINJA2 = "jinja2"
LLAMACPP = "llama.cpp"
DIFF_LINES = 40


def is_tool_fixture(fixture: Fixture) -> bool:
    return "tools" in fixture.context


def _engine_pair(ctx: CheckContext) -> tuple[Any, Any] | None:
    by_name = {getattr(e, "name", None): e for e in ctx.engines}
    if JINJA2 in by_name and LLAMACPP in by_name:
        return by_name[JINJA2], by_name[LLAMACPP]
    return None


def _whitespace_only(a: str, b: str) -> bool:
    return a != b and "".join(a.split()) == "".join(b.split())


def _diff(a: str, b: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(),
                                 fromfile=JINJA2, tofile=LLAMACPP, lineterm="", n=1)
    out = list(lines)
    if len(out) > DIFF_LINES:
        out = out[:DIFF_LINES] + [f"... ({len(out) - DIFF_LINES} more diff lines)"]
    return "\n".join(out)


def _failure_text(r: RenderResult) -> tuple[str, str]:
    """(stage, one-line text) for a failed RenderResult."""
    tag, _, rest = r.error.partition(":")
    rest = rest.strip()
    if tag == "compile":
        stage, _, msg = rest.partition(":")
        return stage.strip() or "compile", msg.strip()
    if tag == "raise":
        return "raise", rest
    return "render", rest


def _x002(fx: Fixture, ok_engine: str, failing: RenderResult, ok_result: RenderResult,
          failing_engine: str) -> tuple[Severity, str, dict[str, Any]]:
    stage, msg = _failure_text(failing)
    normalized = bool(ok_result.extra.get("normalized")) if ok_engine == LLAMACPP else False
    evidence: dict[str, Any] = {
        "engines": [JINJA2, LLAMACPP], "failing_engine": failing_engine,
        "stage": stage, "error": msg, "normalized": normalized,
    }
    if ok_engine == LLAMACPP and ok_result.extra.get("caps"):
        evidence["llamacpp_caps"] = ok_result.extra["caps"]
    if stage == "raise":
        text = (f"{failing_engine} takes the template's raise_exception branch "
                f"({msg!r}) while {ok_engine} renders")
        return Severity.ERROR, text, evidence
    if failing_engine == LLAMACPP and stage in ("lexer", "parser"):
        return Severity.ERROR, f"template will not load in llama.cpp ({stage}: {msg})", evidence
    if failing_engine == LLAMACPP:
        return Severity.ERROR, f"renders under jinja2 but fails under llama.cpp ({msg})", evidence
    if normalized:
        return (Severity.INFO,
                "renders under llama.cpp only after its message normaliser rewrote the "
                f"input; jinja2 (transformers path) fails on the original ({msg})", evidence)
    return Severity.ERROR, f"renders under llama.cpp but fails under jinja2 (transformers path) ({msg})", evidence


def run_cross_engine_checks(ctx: CheckContext) -> list[Finding]:
    tpl = ctx.model.chat_template
    if not tpl:
        return []
    pair = _engine_pair(ctx)
    if pair is None:
        ctx.checks_not_evaluated.extend(X_IDS)
        return []
    j2, llama = pair

    differs: list[tuple[str, Any, dict[str, Any]]] = []
    differs_tools: list[tuple[str, Any, dict[str, Any]]] = []
    explained: list[tuple[str, Any, dict[str, Any]]] = []   # llama.cpp rewrote the input first
    whitespace: list[tuple[str, Any, dict[str, Any]]] = []
    one_side: dict[tuple[Severity, str], list[tuple[str, Any, dict[str, Any]]]] = {}
    agreed = 0

    for fx in ctx.fixtures:
        context = with_real_tokens(ctx, fx.context)
        a = j2.render(tpl, context)
        b = llama.render(tpl, context)
        if a.ok and b.ok:
            if a.text == b.text:
                agreed += 1
                continue
            evidence: dict[str, Any] = {"engines": [JINJA2, LLAMACPP], "diff": _diff(a.text, b.text)}
            if b.extra.get("normalized"):
                evidence["normalized"] = True
                evidence["llamacpp_caps"] = b.extra.get("caps", {})
            if _whitespace_only(a.text, b.text):
                whitespace.append((fx.name, evidence["diff"], evidence))
            elif evidence.get("normalized"):
                explained.append((fx.name, evidence["diff"], evidence))
            elif is_tool_fixture(fx):
                differs_tools.append((fx.name, evidence["diff"], evidence))
            else:
                differs.append((fx.name, evidence["diff"], evidence))
            continue
        if not a.ok and not b.ok:
            continue  # S003 owns "fails everywhere"
        if a.ok:
            severity, message, evidence = _x002(fx, JINJA2, b, a, LLAMACPP)
        else:
            severity, message, evidence = _x002(fx, LLAMACPP, a, b, JINJA2)
        one_side.setdefault((severity, message), []).append(
            (fx.name, (evidence["failing_engine"], evidence["stage"], evidence["error"]), evidence))

    ctx.stats["engines_agreed_fixtures"] = agreed

    findings: list[Finding] = []
    findings += collapse_by_signature(
        "X001", Severity.ERROR, "rendered output differs between jinja2 and llama.cpp", differs)
    findings += collapse_by_signature(
        "X005", Severity.ERROR, "tool-calling output differs between jinja2 and llama.cpp", differs_tools)
    findings += collapse_by_signature(
        "X001", Severity.INFO,
        "rendered output differs only because llama.cpp's message normaliser rewrote the "
        "input before rendering (typed content joined to text); jinja2 (transformers path) "
        "rendered the original", explained)
    findings += collapse_by_signature(
        "X004", Severity.WARN, "rendered output differs between jinja2 and llama.cpp by whitespace only",
        whitespace)
    for (severity, message), results in one_side.items():
        findings += collapse_by_signature("X002", severity, message, results)
    return findings
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_checks_cross_engine.py tests/test_checks_sanity.py tests/test_checks_reference.py -v`
Expected: all PASS. If `test_identical_engines_produce_no_findings_and_record_agreement` disagrees on the count, check whether `typed_content` rendered on both engines (`default('', true)` on a list is falsy-safe under both) and adjust the *template in the test* — not the check — so that exactly the intended fixtures agree; then fix the expected number with a comment.

- [ ] **Step 6: Full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add src/ggufdoctor/checks/common.py src/ggufdoctor/checks/sanity.py src/ggufdoctor/checks/cross_engine.py src/ggufdoctor/models.py tests/test_checks_cross_engine.py
git commit -m "feat(checks): family X — cross-engine comparison of jinja2 and llama.cpp

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Engine registry, `--engines`, X wiring, report provenance

**Files:**
- Create: `src/ggufdoctor/engines/registry.py`
- Modify: `src/ggufdoctor/models.py` (`Coverage.engines_unavailable`, `Coverage.engines_agreed_fixtures`)
- Modify: `src/ggufdoctor/cli.py`
- Modify: `src/ggufdoctor/report/human.py`, `src/ggufdoctor/report/json_report.py`
- Test: `tests/test_registry.py`, `tests/test_cli.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `LlamaCppEngine` (Task 2), `run_cross_engine_checks`, `X_IDS` (Task 5).
- Produces: `registry.ENGINE_NAMES = ("jinja2", "llama.cpp")`; `registry.EngineSelection(engines: list, unavailable: dict[str, str])`; `registry.select_engines(requested: list[str] | None) -> EngineSelection` (raises `ValueError` for an unknown name or an explicitly requested engine that is unavailable); CLI flag `--engines NAMES`; `Coverage.engines_unavailable: dict[str, str]`, `Coverage.engines_agreed_fixtures: int | None`; JSON `engines[]` entries gain `commit` and `backend` when the engine has them, `coverage.engines_unavailable`, `coverage.engines_agreed_fixtures`; human report engine line `llama.cpp b10775 (67a17c17, wasmtime 48.0.0)`, an `engines agree` line, and `llama.cpp unavailable — <reason>` when applicable.

- [ ] **Step 0: Make the shared test template engine-neutral**

`CHAT_TPL` in `tests/test_cli.py` and `tests/test_checks_sanity.py` prints `{{ m['content'] }}` unconditionally. With corpus v2 that diverges between the engines on `tool_roundtrip` (content is null: jinja2 prints `None`, llama.cpp prints nothing → X005 ERROR → exit 1) and on `typed_content`. Every CLI test that assumes exit 0 would break for a reason that has nothing to do with the CLI. Replace both copies with a template that handles null and typed content the same way under both engines, and confirm with a one-off render through `Jinja2Engine` and `LlamaCppEngine` on all ten fixtures that the outputs are byte-identical before touching anything else:

```python
CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n"
            "{% if m['content'] is string %}{{ m['content'] }}"
            "{% elif m['content'] is not none %}{% for p in m['content'] %}{{ p['text'] }}{% endfor %}"
            "{% endif %}<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")
```

If llama.cpp rejects the `is string` test, fall back to `{% if m['content'] is none %}{% elif m['content'] is mapping or (m['content'] is iterable and m['content'] is not string) %}...parts...{% else %}{{ m['content'] }}{% endif %}` and record which form worked in the report. Expected finding sets in `test_checks_sanity.py` that use `CHAT_TPL` must be re-derived and re-justified, not re-pasted.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registry.py
import pytest

from ggufdoctor.engines import registry


def test_default_selection_is_jinja2_then_llama_cpp():
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2", "llama.cpp"]
    assert sel.unavailable == {}


def test_subset_keeps_jinja2_first_and_declines_are_not_gaps():
    sel = registry.select_engines(["jinja2"])
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {}


def test_unknown_engine_is_an_error():
    with pytest.raises(ValueError, match="unknown engine 'minja'"):
        registry.select_engines(["minja"])


def test_jinja2_cannot_be_dropped():
    with pytest.raises(ValueError, match="jinja2"):
        registry.select_engines(["llama.cpp"])


def test_unavailable_engine_is_recorded_by_default_but_fatal_when_requested(monkeypatch):
    class Broken:
        name = "llama.cpp"
        version = "b0"
        available = False
        unavailable_reason = "wasmtime not importable: boom"
    monkeypatch.setattr(registry, "_construct", lambda name: Broken() if name == "llama.cpp" else registry._construct_default(name))
    sel = registry.select_engines(None)
    assert [e.name for e in sel.engines] == ["jinja2"]
    assert sel.unavailable == {"llama.cpp": "wasmtime not importable: boom"}
    with pytest.raises(ValueError, match="boom"):
        registry.select_engines(["jinja2", "llama.cpp"])
```

Append to `tests/test_cli.py` (use the file's existing `_model(tmp_path)` helper that writes a GGUF with `CHAT_TPL`, and `capsys`):

```python
def test_default_run_uses_both_engines_and_reports_agreement(tmp_path, capsys):
    assert main([_model(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "engines: jinja2 " in out and "llama.cpp b10775 (67a17c17, wasmtime " in out
    assert "engines agree:" in out


def test_engines_flag_subsets_without_recording_a_gap(tmp_path, capsys):
    assert main([_model(tmp_path), "--engines", "jinja2"]) == 0
    out = capsys.readouterr().out
    assert "llama.cpp" not in out
    assert "partial" not in out and "X001" not in out


def test_unknown_engine_exits_two_with_one_line(tmp_path, capsys):
    assert main([_model(tmp_path), "--engines", "jinja2,minja"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ggufdoctor: unknown engine 'minja'")


def test_json_carries_engine_provenance_and_agreement(tmp_path):
    target = tmp_path / "r.json"
    assert main([_model(tmp_path), "--json", str(target)]) == 0
    payload = json.loads(target.read_text())
    llama = next(e for e in payload["engines"] if e["name"] == "llama.cpp")
    assert llama["version"] == "b10775" and llama["commit"].startswith("67a17c17")
    assert llama["backend"].startswith("wasmtime ")
    assert payload["coverage"]["families_run"] == ["S", "X"]
    assert payload["coverage"]["engines_unavailable"] == {}
    assert isinstance(payload["coverage"]["engines_agreed_fixtures"], int)
    assert payload["fixture_corpus_version"] == "2"


def test_unavailable_engine_makes_the_run_partial(tmp_path, capsys, monkeypatch):
    from ggufdoctor.engines import registry
    class Broken:
        name = "llama.cpp"; version = "b0"; available = False
        unavailable_reason = "wasmtime not importable: boom"
    monkeypatch.setattr(registry, "_construct",
                        lambda n: Broken() if n == "llama.cpp" else registry._construct_default(n))
    assert main([_model(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "llama.cpp unavailable — wasmtime not importable: boom" in out
    assert "partial" in out and "X001, X002, X004, X005 not evaluated" in out
```

Append to `tests/test_report.py` (adapt to the file's existing helpers for building a model/coverage):

```python
def test_human_report_prints_agreement_line_only_when_x_ran():
    model = GgufModel(source_id="m", architecture="llama", chat_template="x")
    cov = Coverage(upstream="not_requested", families_run=["S", "X"], engines_agreed_fixtures=10)
    text = render_human(model, [], [], cov, [Jinja2Engine()])
    assert "engines agree: jinja2 and llama.cpp rendered 10 fixtures identically" in text
    cov_no_x = Coverage(upstream="not_requested", families_run=["S"])
    assert "engines agree" not in render_human(model, [], [], cov_no_x, [Jinja2Engine()])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_registry.py tests/test_cli.py tests/test_report.py -v`
Expected: FAIL — no `registry` module; `--engines` unrecognised; report strings absent.

- [ ] **Step 3: Registry and coverage fields**

```python
# src/ggufdoctor/engines/registry.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine

# Order matters: checks/sanity.py uses engines[0] as the transformers-reference
# engine, so jinja2 is always first and can never be deselected.
ENGINE_NAMES = ("jinja2", "llama.cpp")


@dataclass
class EngineSelection:
    engines: list[Any]
    # name -> reason, for engines the user did NOT exclude but that could not
    # be constructed. A user-requested subset never appears here: declining an
    # engine is not a coverage gap.
    unavailable: dict[str, str] = field(default_factory=dict)


def _construct_default(name: str) -> Any:
    if name == "jinja2":
        return Jinja2Engine()
    if name == "llama.cpp":
        return LlamaCppEngine()
    raise ValueError(f"unknown engine {name!r} (choose from {', '.join(ENGINE_NAMES)})")


# Indirection so tests can substitute a broken engine.
_construct = _construct_default


def select_engines(requested: list[str] | None) -> EngineSelection:
    explicit = requested is not None
    names = list(requested) if explicit else list(ENGINE_NAMES)
    for n in names:
        if n not in ENGINE_NAMES:
            raise ValueError(f"unknown engine {n!r} (choose from {', '.join(ENGINE_NAMES)})")
    if "jinja2" not in names:
        raise ValueError("jinja2 is the reference engine and cannot be deselected")
    ordered = [n for n in ENGINE_NAMES if n in names]
    selection = EngineSelection(engines=[])
    for n in ordered:
        engine = _construct(n)
        if getattr(engine, "available", True):
            selection.engines.append(engine)
        elif explicit:
            raise ValueError(f"engine {n!r} is unavailable: {engine.unavailable_reason}")
        else:
            selection.unavailable[n] = engine.unavailable_reason or "unavailable"
    return selection
```

`models.py`, on `Coverage`:

```python
    # Engines the default selection could not construct (name -> reason).
    # Distinct from a user-requested --engines subset, which is a decline.
    engines_unavailable: dict[str, str] = field(default_factory=dict)
    # Fixtures both engines rendered byte-identically when family X ran.
    engines_agreed_fixtures: int | None = None
```

- [ ] **Step 4: CLI**

In `build_parser` add:

```python
    p.add_argument("--engines", metavar="NAMES",
                   help="comma-separated engines to run (default: all available; "
                        "choose from jinja2, llama.cpp). jinja2 is always included.")
```

In `_lint_main`, replace `engines = [Jinja2Engine()]` and the check calls with:

```python
        from ggufdoctor.checks.cross_engine import X_IDS, run_cross_engine_checks
        from ggufdoctor.engines.registry import select_engines

        requested = ([n.strip() for n in args.engines.split(",") if n.strip()]
                     if args.engines else None)
        selection = select_engines(requested)   # ValueError -> "ggufdoctor: ..." exit 2 below
        engines = selection.engines
        coverage.engines_unavailable = dict(selection.unavailable)
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream})
        findings = run_sanity_checks(ctx)
        if len(engines) >= 2:
            findings += run_cross_engine_checks(ctx)
            coverage.families_run.append("X")
            coverage.engines_agreed_fixtures = ctx.stats.get("engines_agreed_fixtures")
        elif selection.unavailable:
            # X was not declined -- it could not run. That is a coverage gap.
            ctx.checks_not_evaluated.extend(X_IDS)
        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)
```

`families_run` is built by `sources.resolve` as `["S"]` or `["S", "R"]`; keep "X" in the middle by inserting it after "S" instead of appending: `coverage.families_run.insert(coverage.families_run.index("S") + 1, "X")`. Remove the now-unused `Jinja2Engine` import from `cli.py`. The `except Exception` block already turns the registry's `ValueError` into `ggufdoctor: <message>` and exit 2.

- [ ] **Step 5: Reports**

`report/human.py`: `ALL_FAMILIES = ["S", "X", "R"]`. Engine line:

```python
def _engine_label(e: Any) -> str:
    label = f"{e.name} {e.version}"
    details = []
    commit = getattr(e, "commit", None)
    if commit:
        details.append(commit[:8])
    backend = getattr(e, "backend", None)
    if backend:
        details.append(backend)
    return f"{label} ({', '.join(details)})" if details else label
```

Use it for `engine_names`. After the header line, for each `name, reason in coverage.engines_unavailable.items()` append `f"  {name} unavailable — {_visible(reason)}"`. After the findings loop and before the tail, when `"X" in coverage.families_run and coverage.engines_agreed_fixtures is not None`, append `f"  engines agree: jinja2 and llama.cpp rendered {coverage.engines_agreed_fixtures} fixtures identically"` followed by a blank line. The existing "partial" headline needs no change: an unavailable engine reaches it through `checks_not_evaluated`.

`report/json_report.py`: build each engine entry as `{"name": e.name, "version": e.version}` plus `"commit"` and `"backend"` when `getattr(e, ..., None)` is truthy; add `"engines_unavailable": coverage.engines_unavailable` and `"engines_agreed_fixtures": coverage.engines_agreed_fixtures` under `coverage`.

- [ ] **Step 6: Run the suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASS. Existing CLI tests that assert exact report text may need the new engine label; update only the label text, and only where the assertion was about the header.

- [ ] **Step 7: Commit**

```bash
git add src/ggufdoctor/engines/registry.py src/ggufdoctor/models.py src/ggufdoctor/cli.py src/ggufdoctor/report/ tests/test_registry.py tests/test_cli.py tests/test_report.py
git commit -m "feat(cli): --engines, family X wiring, engine provenance and agreement in reports

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

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
### Task 8: Vendored real templates and complete-finding-set tests

**Files:**
- Create: `tests/data/templates/SOURCES.md`, ten `tests/data/templates/<org>__<repo>.jinja` + `.json` pairs (+ `.upstream.jinja` where saved)
- Create: `tests/data/__init__.py` (empty; keeps pytest collection simple)
- Test: `tests/test_real_templates.py`

**Interfaces:**
- Consumes: `survey --save-templates` (Task 7), both engines, `run_sanity_checks`, `run_cross_engine_checks`.
- Produces: `tests/data/templates/` as the offline real-template corpus that later tasks (conformance) iterate.

This task needs the network once, to fetch. The tests it leaves behind do not.

- [ ] **Step 1: Fetch candidates**

```bash
mkdir -p /tmp/gd-templates
.venv/bin/ggufdoctor survey --top 80 --per-org 1 --save-templates /tmp/gd-templates --out /tmp/gd-templates-survey.json > /dev/null
ls /tmp/gd-templates | wc -l
```

Pick exactly ten by this rule, in download order from the survey output: the first repo for each **distinct `architecture`** in its sidecar, skipping any sidecar whose `gated` is truthy or whose `license` is null, until ten are chosen. Copy each `.jinja`, `.json` and (if present) `.upstream.jinja` into `tests/data/templates/`. Write `SOURCES.md` as a table: repo, architecture, revision, licence, fetched-at, upstream repo (or "—"). State at the top that the files are unmodified copies of published model-repo content included as test data under each repo's own licence.

- [ ] **Step 2: Write the test scaffold (failing)**

```python
# tests/test_real_templates.py
"""Complete S + X finding sets on ten real, vendored templates.

Every expected finding below is a true positive with a stated reason. If a
change to the checks alters any set, this test fails loudly -- that is the
point. Never narrow an assertion to a single id to make it pass.
"""
import json
import pathlib

import pytest

from ggufdoctor.checks.cross_engine import run_cross_engine_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

DATA = pathlib.Path(__file__).parent / "data" / "templates"


def load(slug):
    tpl = (DATA / f"{slug}.jinja").read_text(encoding="utf-8")
    side = json.loads((DATA / f"{slug}.json").read_text(encoding="utf-8"))
    return tpl, side


def run(slug):
    tpl, side = load(slug)
    tokens = [side["bos_token"] or "<s>", side["eos_token"] or "</s>"]
    model = GgufModel(source_id=side["repo"], architecture=side["architecture"],
                      chat_template=tpl, tokens=tokens, bos_token_id=0, eos_token_id=1,
                      add_bos_token=None)  # HF metadata does not carry add_bos_token
    ctx = CheckContext(model=model, engines=[Jinja2Engine(), LlamaCppEngine()],
                       fixtures=load_fixtures())
    findings = run_sanity_checks(ctx) + run_cross_engine_checks(ctx)
    def fixtures_of(f):
        return tuple(f.evidence.get("fixtures") or ((f.fixture,) if f.fixture else ()))
    return ({(f.id, f.severity, fixtures_of(f)) for f in findings},
            sorted(ctx.checks_not_evaluated), ctx.stats)


def test_every_vendored_template_has_a_sidecar_and_an_expectation():
    slugs = sorted(p.stem for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))
    assert len(slugs) == 10
    assert set(slugs) == set(EXPECTED), "add an EXPECTED entry for every vendored template"
    for s in slugs:
        assert (DATA / f"{s}.json").exists()


# slug -> (expected finding set, expected checks_not_evaluated)
# Fill in from a first run, then JUSTIFY EACH LINE by reading the template.
EXPECTED = {
    # "Qwen__Qwen2.5-3B-Instruct-GGUF": (
    #     {
    #         # S006 skipped: add_bos_token unknown from HF metadata.
    #     },
    #     ["S006"],
    # ),
}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_complete_finding_set(slug):
    found, not_evaluated, stats = run(slug)
    expected_findings, expected_not_evaluated = EXPECTED[slug]
    assert found == expected_findings
    assert not_evaluated == expected_not_evaluated
    assert stats["engines_agreed_fixtures"] >= 1, "both engines must agree on at least one fixture"
```

- [ ] **Step 3: Run once to see the real sets**

Run: `.venv/bin/python -m pytest tests/test_real_templates.py -v`
Expected: `test_every_vendored_template_has_a_sidecar_and_an_expectation` FAILS (EXPECTED empty).

Then for each slug run `.venv/bin/python -c "from tests.test_real_templates import run; print(run('<slug>'))"` and fill `EXPECTED`. For every finding, add a comment with the reason, in the same style as `tests/test_checks_sanity.py`'s Mistral test: quote the template construct that produces it. Expected shapes, from the spike: S006 in `not_evaluated` everywhere (no `add_bos_token`); S003 INFO author declines on `system_user`/`tool_roundtrip` for templates that `raise_exception` on those roles; S003 INFO extended-tier render errors on `typed_content` for string-concatenating templates; possibly S007 INFO; **no X001/X005 on any of the ten** — if one appears, read the diff: it is either a real engine divergence worth a line in the spike doc, or a bug in Task 5. X002 INFO on `typed_content` for string-only templates is expected and is not a bug.

- [ ] **Step 4: Run and commit**

```bash
.venv/bin/python -m pytest tests/test_real_templates.py -q
git add tests/data tests/test_real_templates.py
git commit -m "test: vendor ten real chat templates with provenance and pin their complete finding sets

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

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

### Task 11: Documentation and the corpus-2 survey

**Files:**
- Modify: `README.md`, `NEXT-SESSION.md`, `docs/research/README.md`, `docs/v0.2-kickoff.md`
- Create: `CHANGELOG.md`, `docs/research/2026-09-<dd>-survey-corpus2.json`, `docs/research/2026-09-<dd>-survey-corpus2.md`

**Interfaces:**
- Consumes: everything above.
- Produces: user-facing documentation for v0.2.

- [ ] **Step 1: Run the survey on corpus 2**

```bash
.venv/bin/ggufdoctor survey --top 400 --per-org 2 --out docs/research/$(date +%F)-survey-corpus2.json --markdown docs/research/$(date +%F)-survey-corpus2.md
```

Expected: about ten minutes; `unreliable: false` in the aggregate (if `examine_error` exceeds 5% the tool says so — wait for the rate limit to clear and re-run, do not publish an unreliable run). Note the figure with its corpus version.

- [ ] **Step 2: README**

- Install: `pip install ggufdoctor` pulls `wasmtime`; one sentence on what for.
- New section **"Two engines"** after "What it checks": what `llama.cpp` (`b10775`) is, that it is the real llama.cpp engine compiled to WASM, the X table (X001/X002/X004/X005 with severities and the INFO rule for normaliser-explained X002), `--engines`, and the spike result stated plainly: *on the seven standard fixtures, llama.cpp's engine agreed with transformers-style Jinja2 on 100 of 100 top GGUF templates; the divergence that exists is on typed content, `None` content and templates using `//`.* Link the spike doc.
- "The finding": keep the 14.8% table and add one line beneath: "Corpus 2 (v0.2, adds tool round-trip, typed content, no generation prompt): **N%** (a of b) — the two figures use different fixture corpora and are not comparable to one decimal."
- Limitations: replace "One engine" with "Ollama's Go conversion is not yet compared (v0.3)"; add "`llama-server` also rewrites requests before templating (tool-call arguments become strings); the bundled engine mirrors the message normaliser and whatever Task 9 ported — list it."

- [ ] **Step 3: CHANGELOG, NEXT-SESSION, research index, kickoff**

`CHANGELOG.md` with `0.2.0` (engine, X family, corpus v2 with tiers, `--engines`, `--save-templates`, conformance suite, wasmtime dependency) and `0.1.0`. `NEXT-SESSION.md`: v0.2 state, PyPI still pending (Saad's call), v0.3 pointer (Ollama engine, X003, `--runtime`), where the ledger was copied. `docs/research/README.md`: add the corpus-2 survey entry and the spike. `docs/v0.2-kickoff.md`: one line at the top saying v0.2 shipped and pointing at the plan and ledger.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md NEXT-SESSION.md docs/research docs/v0.2-kickoff.md
git commit -m "docs: v0.2 — two engines, X family, corpus-2 survey figure

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Deliberately deferred

- Ollama engine, X003, `--runtime` (v0.3).
- Counting X divergence inside `survey` (would need real tokens per repo and a second engine per record; the spike's 100/100 stands as the published statement until then).
- Per-repo vocab fetching in the survey (unchanged v0.1 limitation).
- Automatic engine bumps.

## Definition of done for v0.2

- [ ] `.venv/bin/python -m pytest -q` green with no network and no downloaded binaries.
- [ ] `ggufdoctor model.gguf` prints two engines with versions and either X findings or an "engines agree" line; `--engines jinja2` runs S only with no "partial".
- [ ] With `wasmtime` uninstalled, `ggufdoctor model.gguf` still exits 0/1 and says `llama.cpp unavailable — ...` plus "partial".
- [ ] CI: `test` × 9, `build`, `engine-build`, `conformance` green on `feat/v0.2`.
- [ ] Every id `S001–S008`, `X001/X002/X004/X005`, `R001–R004` has at least one test; ten real templates have complete finding sets.
- [ ] The corpus-2 survey figure is recorded with its corpus version and the 14.8% (corpus 1) is unchanged in the README.
