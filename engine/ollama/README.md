# engine/ollama/

This directory vendors data, not an engine. `src/ggufdoctor/ollama_data/` carries Ollama's
own template registry — `template/index.json` and its 20 `*.gotmpl` files — copied verbatim
from an Ollama checkout at a pinned commit. Nothing here ships in the wheel as code: Ollama's
template selection is a Levenshtein lookup against `index.json`, not a Jinja-to-Go conversion,
so reproducing it in Python needs only the registry's own data, matched the same way. The Go
module under `gotools/` exists purely as an oracle — it regenerates `goldens.json` and backs the
`ollama_conformance` suite, and no normal test run or install touches it. See
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
`LICENSE-ollama`, and all 20 `*.gotmpl` files, one `sha256  filename` line each. The
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

## Regenerating the goldens

`src/ggufdoctor/ollama_data/goldens.json` is what Ollama's own Go template package renders for
every vendored `*.gotmpl` against every fixture in `src/ggufdoctor/fixture_data/corpus.json`.
It is committed so nothing in the normal test run, or on a user's machine, needs Go or a
network — Go is needed here and in the `ollama-conformance` CI job only.

```json
{
 "ollama_commit": "b79067b0db7417f20108363bc22adb97f35c966a",
 "corpus_version": "2",
 "renders": {"chatml": {"user_only": "<|im_start|>user\nHello<|im_end|>\n<|im_start|>assistant\n"}}
}
```

Each `renders[template][fixture]` is the rendered string, or `{"unrepresentable": msg}` when the
fixture does not unmarshal into `api.Message` (all ten `typed_content` entries: `Content` is a Go
`string`, so list-of-parts content cannot reach a Go template at all), or `{"error": msg}` when
`template.Execute` failed. There is deliberately no `generated_at` or other timestamp: the file is
byte-reproducible, so CI can regenerate it and diff.

`engine/ollama/regen-goldens.sh [out.json]` writes it. It reads the commit from `OLLAMA_PIN`,
fetches Ollama into `engine/build/ollama` if that isn't already at the pin, and runs
`gotools/cmd/goldengen` there.

`engine/ollama/gotools/` is a small Go module — the only Go in the repo — whose `replace`
directive points `github.com/ollama/ollama` at `engine/build/ollama`. That fixed path is the
whole configuration: there is no `OLLAMA_SRC` override in the script, because a `-modfile`
override buys nothing a symlink doesn't. To reuse a checkout you already have:

```sh
mkdir -p engine/build && ln -s /path/to/ollama engine/build/ollama
```

(The conformance suite does honour `OLLAMA_SRC`, and makes exactly that symlink for you.)

It holds two commands:

- `goldengen DIR CORPUS.json OLLAMA_COMMIT` — parses and executes each `.gotmpl` through
  `template.Parse`/`Execute`, so `collate`, `convertMessagesForTemplate` and `templateArgs` are
  the genuine upstream code rather than a re-implementation. `Values.Think`/`IsThinkSet` come
  from a fixture's `enable_thinking` when it has one, mirroring how `/api/chat` fills them from
  the request's `think` (no vendored template references `.Think`, so this changes no render
  today; it keeps the mapping honest if one starts to).
- `namedcheck INDEX.json` — reads a JSON array of template strings on stdin and prints
  `[{"name": string|null, "distance": int}]`: what the real `template.Named` returned (null when
  it errored) and the exact minimum Levenshtein distance over the index, computed with the same
  `agnivade/levenshtein` package Ollama uses.

## What the conformance job proves

`tests/ollama_conformance` is deselected by default (marker `ollama_conformance`) and runs in the
`ollama-conformance` CI job, which first `cmp`s every vendored file against a fresh checkout at
the pin. Two claims:

1. **The Python selector is `template.Named`.** `test_python_selector_agrees_with_real_template_named`
   feeds both tools the ten real vendored Jinja templates plus synthetic probes built around every
   index entry — truncations landing at exactly 59/60/99/100/101 edits and seeded random
   substitutions — and asserts the name and the distance match, including that a miss is a miss on
   both sides. That is where `ollama.py`'s banded Levenshtein and its strict `< 100` cutoff would
   drift; a one-off cutoff fails this test.
2. **The committed goldens are current.** `test_committed_goldens_are_what_ollama_renders_at_the_pin`
   re-runs `goldengen` and compares `renders` with `goldens.json` byte-for-byte. It fails with
   "run engine/ollama/regen-goldens.sh" if the pin moved, the corpus changed, or a render drifted.

## Bumping the pin

1. Edit `OLLAMA_PIN` to the new `commit`, `release`, `fetched`, and (if `template/index.json`
   moved) `index_last_commit` / `index_last_changed`.
2. Run `engine/ollama/fetch-ollama.sh` to fetch the new commit into `engine/build/ollama`.
3. Run `engine/ollama/vendor.sh` to copy the registry in and regenerate `sources.sha256`.
4. Regenerate goldens and re-check conformance: run `regen-goldens.sh`, then the
   `ollama_conformance` suite, to confirm nothing the matcher or renderer depends on shifted
   underneath the pin.
5. Update the version string wherever it's surfaced to users (e.g. `--version` output,
   changelog) to note the new Ollama pin.

## Drift watch

`.github/workflows/ollama-registry-drift.yml` runs weekly against `ollama/ollama@main`: it
downloads the current `index.json` and every vendored `*.gotmpl` by name, diffs them
byte-for-byte against what's vendored, and diffs the index entries. A vendored `*.gotmpl` that
404s at HEAD (renamed or deleted upstream) counts as drift too rather than aborting the job —
only `index.json` itself failing to download is treated as a hard error, since without it
there's nothing to diff against. If anything changed, 404'd, or was added or removed, the job
opens (or leaves open) a maintenance issue summarizing the drift and fails the run — a nudge to
bump the pin, not an automatic bump.
