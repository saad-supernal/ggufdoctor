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

# sha256 of each wasi-sdk host tarball. The toolchain that compiles the
# committed module is pinned by content, not just by URL: this script downloads
# an archive over the network, unpacks it and then *executes* the compiler
# inside it. All four were computed on 2026-09-03 by downloading the official
# release assets (`shasum -a 256`); a host with no entry prints UNVERIFIED and
# the script refuses to auto-download for it. Refresh per engine/README.md when
# WASI_SDK_TAG changes.
wasi_sdk_sha256() {
  case "$1" in
    arm64-macos)  echo 9c59398106b417f8f14913380fdf0097a8cc0ff4af9eb3ce0065a859e88d49e9 ;;
    x86_64-macos) echo 87d27fa8adc68dee59bfbf2e22a6d34ef717c34d6bf1d8af2a56fc929d9ce0eb ;;
    x86_64-linux) echo b761e3a0721dbae9c09a0059e5fdb2bf917d1b4a8a7b430fb3b5aafb0984b2c4 ;;
    arm64-linux)  echo f7e243dff54d60bcc576e94d6166b69f410f2500ae4a9ceef34315be10e77971 ;;
    *) echo UNVERIFIED ;;
  esac
}

# `shasum -a 256 -c` where it exists (macOS, and any host with perl), falling
# back to coreutils sha256sum. No hashing tool at all is a hard failure, never
# a skipped check.
sha256_check() {  # $1 = expected hex, $2 = file
  if command -v shasum >/dev/null 2>&1; then
    echo "$1  $2" | shasum -a 256 -c - >/dev/null
  elif command -v sha256sum >/dev/null 2>&1; then
    echo "$1  $2" | sha256sum -c - >/dev/null
  else
    echo "neither shasum nor sha256sum is available to verify $2" >&2
    return 1
  fi
}

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
    SUM=$(wasi_sdk_sha256 "$HOST")
    if [ "$SUM" = UNVERIFIED ]; then
      echo "no pinned sha256 for wasi-sdk ${WASI_SDK_TAG}.0-$HOST; install it yourself and set WASI_SDK" >&2
      exit 2
    fi
    mkdir -p "$HERE/build"
    TARBALL="$HERE/build/${WASI_SDK_TAG}.0-${HOST}.tar.gz"
    # Downloaded to a file, verified, only then extracted -- the previous
    # `curl | tar xz` could neither check the bytes nor notice a truncated
    # transfer (a pipeline whose head fails still leaves tar's status 0).
    curl -sfL -o "$TARBALL.part" \
      "https://github.com/WebAssembly/wasi-sdk/releases/download/${WASI_SDK_TAG}/${WASI_SDK_TAG}.0-${HOST}.tar.gz"
    mv "$TARBALL.part" "$TARBALL"
    if ! sha256_check "$SUM" "$TARBALL"; then
      rm -f "$TARBALL"
      echo "wasi-sdk ${WASI_SDK_TAG}.0-$HOST failed its sha256 check; refusing to extract or run it" >&2
      exit 2
    fi
    tar xzf "$TARBALL" -C "$HERE/build"
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
