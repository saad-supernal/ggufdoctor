#!/bin/sh
# Fetch Ollama at the pinned commit into engine/build/ollama (or $1).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
DEST=${1:-$ROOT/engine/build/ollama}
COMMIT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['commit'])" \
         "$ROOT/src/ggufdoctor/ollama_data/OLLAMA_PIN")
if [ -d "$DEST/.git" ] && [ "$(git -C "$DEST" rev-parse HEAD)" = "$COMMIT" ]; then
  echo "ollama already at $COMMIT in $DEST"; exit 0
fi
rm -rf "$DEST"; mkdir -p "$DEST"
git -C "$DEST" init -q
git -C "$DEST" remote add origin https://github.com/ollama/ollama.git
git -C "$DEST" fetch -q --depth 1 origin "$COMMIT"
git -C "$DEST" checkout -q FETCH_HEAD
[ "$(git -C "$DEST" rev-parse HEAD)" = "$COMMIT" ] || { echo "checkout is not $COMMIT" >&2; exit 1; }
echo "ollama $COMMIT in $DEST"
