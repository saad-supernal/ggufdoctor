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

# clang marks its output executable; this is a data file loaded by wasmtime,
# never exec'd, and it is committed to the repo -- so ship it 0644.
chmod 644 "$OUT_DIR/llamacpp-jinja.wasm"

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
