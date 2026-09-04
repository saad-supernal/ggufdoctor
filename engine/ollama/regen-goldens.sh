#!/bin/sh
# Regenerate src/ggufdoctor/ollama_data/goldens.json with Ollama's own template
# package at the pinned commit. Needs Go; fetches Ollama if engine/build/ollama
# is absent or at the wrong commit.
#
# The gotools module's `replace` directive points at engine/build/ollama, so
# that is where the checkout has to be. To reuse a checkout you already have,
# symlink it: ln -s /path/to/ollama engine/build/ollama.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SRC=$ROOT/engine/build/ollama
OUT=${1:-$ROOT/src/ggufdoctor/ollama_data/goldens.json}
COMMIT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['commit'])" "$ROOT/src/ggufdoctor/ollama_data/OLLAMA_PIN")
if [ ! -d "$SRC/.git" ] || [ "$(git -C "$SRC" rev-parse HEAD)" != "$COMMIT" ]; then
  "$HERE/fetch-ollama.sh" "$SRC"
fi
cd "$HERE/gotools"
# Render to a temporary file first: a failed run must not leave $OUT truncated.
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
go run ./cmd/goldengen "$ROOT/src/ggufdoctor/ollama_data" "$ROOT/src/ggufdoctor/fixture_data/corpus.json" "$COMMIT" > "$TMP"
cat "$TMP" > "$OUT"
echo "wrote $OUT"
