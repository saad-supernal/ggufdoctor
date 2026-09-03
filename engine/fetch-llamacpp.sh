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
