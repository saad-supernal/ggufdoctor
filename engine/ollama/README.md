# engine/ollama/

This directory vendors data, not an engine. `src/ggufdoctor/ollama_data/` carries Ollama's
own template registry — `template/index.json` and its 20 `*.gotmpl` files — copied verbatim
from an Ollama checkout at a pinned commit. There is nothing here to build or run: Ollama's
template selection is a Levenshtein lookup against `index.json`, not a Jinja-to-Go conversion,
so reproducing it in Python needs only the registry's own data, matched the same way. See
`docs/research/2026-09-03-ollama-spike.md` for how that was established and what it changes
about the v0.3 plan.

`vicuna.gotmpl` is vendored even though no `index.json` entry points at it — it is embedded
upstream but unreachable from the matcher. It is kept anyway so the vendored directory mirrors
upstream exactly rather than second-guessing which files matter.

## The pin

`src/ggufdoctor/ollama_data/OLLAMA_PIN` is JSON:

```json
{
 "commit": "b79067b0db7417f20108363bc22adb97f35c966a",
 "release": "v0.33.2",
 "fetched": "2026-09-03",
 "index_last_commit": "f8c3dbe5",
 "index_last_changed": "2025-03-20"
}
```

`commit` is the Ollama commit everything below is copied from; `release` is the nearest
tagged release, for humans. `fetched` is when the vendoring happened. `index_last_commit` /
`index_last_changed` record the most recent commit that actually touched `template/index.json`
upstream (as opposed to the pin commit itself) — a cheap signal for how stale the registry
plausibly is, independent of how old the pin is.

`src/ggufdoctor/ollama_data/sources.sha256` pins every vendored file by content: `index.json`,
`LICENSE-ollama`, and all 20 `*.gotmpl` files, one `sha256  filename` line each. Task 3's
`ollama_conformance` suite and golden regeneration read this layout to know exactly what was
vendored and detect any accidental edit.

## Fetching and vendoring

`fetch-ollama.sh [dest]` clones the pinned commit only (`git fetch --depth 1`) into
`engine/build/ollama` by default, or `dest` if given. It reads the commit straight out of
`OLLAMA_PIN`, so it always fetches whatever the pin currently says, and it is a no-op if
`dest` is already checked out to that commit.

`vendor.sh [src]` copies `template/index.json`, `template/*.gotmpl` and `LICENSE` from an
Ollama checkout (`engine/build/ollama` by default, or `src` if given) into
`src/ggufdoctor/ollama_data/`, refuses to run if `src` isn't at the pinned commit, and
(re)writes `sources.sha256` from what it just copied.

`engine/build/` is git-ignored; it is scratch space for the fetched checkout, not something to
commit.

## Bumping the pin

1. Edit `OLLAMA_PIN` to the new `commit`, `release`, `fetched`, and (if `template/index.json`
   moved) `index_last_commit` / `index_last_changed`.
2. Run `engine/ollama/fetch-ollama.sh` to fetch the new commit into `engine/build/ollama`.
3. Run `engine/ollama/vendor.sh` to copy the registry in and regenerate `sources.sha256`.
4. Regenerate goldens and re-check conformance (Task 3): run `regen-goldens.sh`, then the
   `ollama_conformance` suite, to confirm nothing the matcher or renderer depends on shifted
   underneath the pin.
5. Update the version string wherever it's surfaced to users (e.g. `--version` output,
   changelog) to note the new Ollama pin.

## Drift watch

`.github/workflows/ollama-registry-drift.yml` runs weekly against `ollama/ollama@main`: it
downloads the current `index.json` and every vendored `*.gotmpl` by name, diffs them
byte-for-byte against what's vendored, and diffs the index entries. If anything changed or was
added or removed, it opens (or leaves open) a maintenance issue summarizing the drift and fails
the run — a nudge to bump the pin, not an automatic bump.
