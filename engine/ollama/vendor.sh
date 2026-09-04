#!/bin/sh
# Copy template/index.json, template/*.gotmpl and LICENSE from an Ollama checkout
# (default engine/build/ollama) into src/ggufdoctor/ollama_data and write sources.sha256.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SRC=${1:-$ROOT/engine/build/ollama}
OUT="$ROOT/src/ggufdoctor/ollama_data"
COMMIT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['commit'])" "$OUT/OLLAMA_PIN")
[ "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" ] || { echo "$SRC is not at pinned commit $COMMIT" >&2; exit 1; }
rm -f "$OUT"/*.gotmpl
cp "$SRC/template/index.json" "$OUT/index.json"
cp "$SRC"/template/*.gotmpl "$OUT/"
cp "$SRC/LICENSE" "$OUT/LICENSE-ollama"
( cd "$OUT" && ls index.json LICENSE-ollama *.gotmpl | sort | while read -r f; do
    python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()+'  '+sys.argv[1])" "$f"
  done > sources.sha256 )
echo "vendored $(ls "$OUT"/*.gotmpl | wc -l | tr -d ' ') templates from $COMMIT"
