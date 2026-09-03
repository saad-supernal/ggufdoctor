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

