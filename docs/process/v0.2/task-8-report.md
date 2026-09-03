# Task 8 report: vendored real templates and complete-finding-set tests

Branch `feat/v0.2`. Commit `4b73aa5` — *test: vendor ten real chat templates
with provenance and pin their complete finding sets*.

## Step 1: the fetch

```
mkdir -p /tmp/gd-templates
.venv/bin/ggufdoctor survey --top 80 --per-org 1 --save-templates /tmp/gd-templates \
    --out /tmp/gd-templates-survey.json > /dev/null
# exit=0; ls /tmp/gd-templates | wc -l -> 148
```

148 files = 60 `.jinja` + 60 `.json` + 28 `.upstream.jinja`.

Aggregate from `/tmp/gd-templates-survey.json`:

```json
{"sampled": 80, "per_org": 1, "truncated": false, "comparable": 28,
 "divergent": 5, "divergent_pct": 17.857142857142858,
 "download_weighted_pct": 45.65036641624781,
 "publishers_total": 28, "publishers_affected": 5,
 "coverage_gaps": {"no_base_model": 9, "non_chat_architecture": 7,
                   "upstream_has_no_template": 22, "upstream_not_found": 8,
                   "upstream_gated": 4, "non_chat_pipeline_tag": 2},
 "unreliable": false}
```

**No `examine_error`** in `coverage_gaps`, so nothing was rate-limited and no
vendored template comes from a repo whose fetch failed. One run was enough.

## Step 1: selection

Rule as briefed: in download order, the first repo per distinct sidecar
`architecture`, skipping truthy `gated` or null `license`, until ten. That
consumed the first 26 records. Full table (including every skip and its reason)
is in `tests/data/templates/SOURCES.md`; the condensed version:

| # | Rank | Repo | Arch | Outcome |
|---|------|------|------|---------|
| 1 | 1 | unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF | qwen3moe | chosen |
| 2 | 2 | ornith-ai/Ornith-1.0-9B-GGUF | qwen35 | chosen |
| — | 3 | mixedbread-ai/mxbai-embed-large-v1 | — | not a candidate (non-chat arch, no template saved) |
| 3 | 4 | HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive | gemma4 | chosen |
| — | 5–7 | lmstudio-community, JonathanColetti, DavidAU (all Qwen3.x) | qwen35 | skipped — arch taken at rank 2 |
| 4 | 8 | antirez/deepseek-v4-gguf | deepseek4 | chosen |
| — | 9 | handy-computer/nemotron-3.5-asr-streaming-0.6b-gguf | — | not a candidate |
| — | 10 | huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF | qwen35 | skipped — arch taken |
| 5 | 11 | mudler/Laguna-XS-2.1-APEX-GGUF | laguna | chosen |
| — | 12, 13, 15, 16 | audio-cpp, nvidia/parakeet, Abiray/MiniMax-H3, cdiamond | — | not candidates (no template saved) |
| — | 14 | 0bserverx/Qwen3.8-27B-Heretic-… | qwen35 | skipped — arch taken |
| 6 | 17 | LuffyTheFox/Qwen3.6-35B-A3B-…-V13-GGUF | qwen35moe | chosen |
| — | 18, 19 | ggml-org/Qwen3.8-27B, datalab-to/surya-ocr-2 | qwen35 | skipped — arch taken |
| 7 | 20 | rippertnt/HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF | llama | chosen |
| 8 | 21 | LiquidAI/LFM2.5-2.6B-GGUF | lfm2 | chosen |
| — | 22, 23 | Serveurperso/Qwen3-TTS, LocalAI-io/privacy-filter-nemotron | — | not candidates |
| — | 24 | OBLITERATUS/Qwen3.8-27B-OBLITERATED | qwen35 | skipped — arch taken |
| 9 | 25 | PaddlePaddle/PaddleOCR-VL-1.6-GGUF | paddleocr | chosen |
| 10 | 26 | legraphista/glm-4-9b-chat-IMat-GGUF | chatglm | chosen |

Both filters in the rule turned out to exclude nothing inside the 26-record
window: every sidecar there reports `gated: null`, and none has a null
`license`. Eight later records do have `license: null` and are named in
SOURCES.md for transparency; only one of them (rank 52, `instella-moe`) carried
an unrepresented architecture, so the licence filter would have started to
matter only past the tenth pick. Four repos elsewhere in the sample were
excluded *by the survey* as `upstream_gated`, which is a different thing —
rank 20's own `gated` is null, which is what the rule reads, so it is eligible.

The rule was applied mechanically, with one case worth flagging rather than
quietly re-rolling: rank 26's published `chat_template` is the eight-byte
literal `ChatGLM4` (llama.cpp's legacy *named* built-in template, published
where a Jinja template belongs), not a template at all. Kept — the rule selects
on architecture, and a repo publishing the wrong kind of string is exactly the
real-world defect this corpus should carry. It is the sharpest entry in the set:
S005 WARN and S007 WARN.

Three `.upstream.jinja` files came along (unsloth, mudler, legraphista); the
mudler one is byte-identical to its GGUF-side template (that repo's survey
status was `identical`) and is kept as fetched.

`revision` is `null` in all sixty sidecars this run produced — the Hub
`model_info` responses carried no `sha`. Recorded honestly as `—` in
SOURCES.md; see Concerns.

## TDD evidence

Scaffold with `EXPECTED = {}`, before any expectation was written:

```
tests/test_real_templates.py::test_complete_finding_set[NOTSET] SKIPPED  [100%]
____ test_every_vendored_template_has_a_sidecar_and_an_expectation ____
>       assert set(slugs) == set(EXPECTED), "add an EXPECTED entry for every vendored template"
E       AssertionError: add an EXPECTED entry for every vendored template
E       assert {'HauhauCS__G...at-GGUF', ...} == set()
1 failed, 1 skipped in 0.04s
```

Note `assert len(slugs) == 10` passed at that point, so the ten-file count was
established before the expectations existed.

I also mutation-checked that the completeness assertion actually bites: deleting
one line — the honest `("X002", Severity.ERROR, ("tool_roundtrip",))` on
rippertnt — gives `1 failed, 10 passed`, failing on exactly that slug. Restored,
back to `11 passed`. So the set equality catches both a missing and (by
symmetry) a spurious finding; it cannot be satisfied by narrowing.

## Step 3: the pinned sets

All ten have `checks_not_evaluated == ["S006"]`, because `run()` passes
`add_bos_token=None` (HF's `gguf` metadata block carries bos/eos *strings* but
no `add_bos_token` flag), so `s006_double_bos` cannot tell whether it applies.

| Slug | Finding set | agreed |
|------|-------------|--------|
| HauhauCS__Gemma-4-E4B-… | S004 ERROR; S005 WARN; X004 WARN (typed_content) | 9 |
| LiquidAI__LFM2.5-2.6B-GGUF | S004 ERROR; X004 WARN (typed_content) | 9 |
| LuffyTheFox__Qwen3.6-35B-A3B-… | S004 ERROR; X004 WARN (typed_content) | 9 |
| PaddlePaddle__PaddleOCR-VL-1.6-GGUF | S003 INFO (tool_roundtrip); S004 ERROR; X004 WARN (typed_content) | 8 |
| antirez__deepseek-v4-gguf | S003 INFO (typed_content); X002 INFO (typed_content) | 9 |
| legraphista__glm-4-9b-chat-IMat-GGUF | S005 WARN; S007 WARN (user_only) | 10 |
| mudler__Laguna-XS-2.1-APEX-GGUF | X001 INFO (typed_content) | 9 |
| ornith-ai__Ornith-1.0-9B-GGUF | S004 ERROR; X004 WARN (typed_content) | 9 |
| rippertnt__HyperCLOVAX-… | S003 INFO ×2 (tool_roundtrip, typed_content); S004 ERROR; S005 WARN; **X002 ERROR (tool_roundtrip)**; X002 INFO (typed_content) | 8 |
| unsloth__Qwen3-Coder-30B-A3B-Instruct-GGUF | S003 INFO (typed_content); S004 ERROR; X002 INFO (typed_content) | 9 |

One-line reason per finding (the full justifications, with the template
constructs quoted verbatim, are the comments in `tests/test_real_templates.py`):

**HauhauCS/Gemma-4-E4B** — S004: emits `<|"|>` (tool-schema quoting,
`description:<|"|>{{ value['description'] }}<|"|>`) and `<|think|>`
(`{{- '<|think|>' -}}` under `enable_thinking`), neither being the declared
`<bos>`/`<eos>`. S005: closes turns with the literal `{{- '<turn|>\n' -}}` and
contains zero occurrences of `eos_token`, so `<eos>` is never emitted — a real
metadata/template disagreement. X004: its own `{%- for item in message['content'] -%}`
… `{{- item['text'] | trim -}}` concatenates the two text parts with no
separator ("Hellothere") against llama.cpp's normaliser-joined "Hello\nthere".

**LiquidAI/LFM2.5** — S004: `<|im_start|>`, `<|tool_call_start|>`,
`<|tool_call_end|>` (the latter two from `render_tool_calls`, reached on
tool_roundtrip); the declared eos `<|im_end|>` is correctly *not* reported.
X004: `parse_content`'s `{%- set _ns.result = _ns.result + ((item.get("text") or "") | string) -%}`
joins with no separator.

**LuffyTheFox/Qwen3.6-35B-A3B** — S004: `<|im_start|>` only. X004: the
`render_content` macro's `{%- elif 'text' in item %}{{- item.text }}` inside
`{%- for item in content %}`, no separator.

**PaddlePaddle/PaddleOCR-VL** — S003 INFO: on tool_roundtrip's assistant
`content: null`, `{%- if message["content"] is string -%}` is false and the else
branch iterates None → `TypeError: 'NoneType' object is not iterable`; extended
tier, so INFO. S004: `<|begin_of_sentence|>`, which the template supplies as its
own default (`{%- set cls_token = "<|begin_of_sentence|>" -%}`) while the sidecar
declares bos `<s>`. Worth noting the check did *not* report
`<|IMAGE_START|>`/`<|IMAGE_PLACEHOLDER|>`/`<|IMAGE_END|>`, also present in the
source — no fixture supplies an image part, so S004 never observed them and
refused to guess. X004: the user branch's separator-free
`{%- for content in message["content"] -%}` … `{{ content["text"] }}`.

**antirez/deepseek-v4** — S003 INFO: `{{- '<｜User｜>' + (message['content'] or '') -}}`
— a non-empty list is truthy, so `or ''` passes it through and `+` raises
`can only concatenate str (not "list") to str`; extended tier → INFO. X002 INFO:
llama.cpp's normaliser flattened the list first so its `+` saw a string;
re-rendering under jinja2 with the content pre-flattened reproduces llama.cpp's
output byte for byte, which is what earns the INFO. No S004 because every
special token here uses fullwidth `｜` (U+FF5C), which `SPECIAL_TOKEN_RE`'s
ASCII `<\|…\|>` does not match. No S005 because the template emits the literal
`<｜end▁of▁sentence｜>`, exactly the declared eos.

**legraphista/glm-4-9b-chat** — the "template" is the constant `ChatGLM4`.
S005: the multiturn render is `ChatGLM4`, which does not contain the declared
`<|endoftext|>` — this prompt would never terminate a turn. S007 **WARN**, not
INFO: a constant cannot respond to `add_generation_prompt`, and `ChatGLM4` ends
with none of `_ASSISTANT_OPEN_MARKERS`, so nothing suggests the assistant turn
opens by other means. S002/S008 correctly stay silent (it compiles, and
`ChatGLM4` is non-empty). Both engines render the same constant on all ten
fixtures → the only entry with `agreed == 10`.

**mudler/Laguna-XS-2.1** — see the X001 section below. No S004 (fullwidth
`〈|EOS|〉` plus plain `<system>`/`<user>` tags — no ASCII `<|…|>` match); no
S005 (its first act is `{{- "〈|EOS|〉" -}}`, and this repo declares that same
string as *both* bos and eos).

**ornith-ai/Ornith-1.0-9B** — S004: `<|im_start|>` only. X004: `render_content`
macro, separator-free text-part loop. No S003 because that macro handles every
shape the corpus offers, including
`{%- elif content is none or content is undefined %}{{- '' }}` for
tool_roundtrip's null.

**rippertnt/HyperCLOVAX** — the whole template is one unguarded concatenation,
`{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}`,
which explains four of five findings. S003 INFO ×2: that `+` raises on
`content: null` (tool_roundtrip, `not "NoneType"`) and on list content
(typed_content, `not "list"`) — reported separately, not collapsed, because the
two error signatures differ. S004: `<|im_start|>` *and* `<|im_end|>` — and
`<|im_end|>` is not a synthetic-vocab artefact: this repo declares eos
`<|endofturn|>`, so the token the template actually uses to close turns is
genuinely not the declared one. S005: the same disagreement from the other side.
X002 ERROR: see below.

**unsloth/Qwen3-Coder-30B-A3B** — S003 INFO: line 115,
`{{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>' + '\n' }}`,
raises on list content; tool_roundtrip does *not* fail because the tool_calls
branch guards with
`{%- if message.content is defined and message.content is string and message.content | trim | length > 0 %}`.
S004: `<|im_start|>` only. X002 INFO: normaliser-explained, confirmed by the
pre-flattened re-render.

## X001 / X005 observed

**No X001 ERROR and no X005 at all.** Two things did appear and are recorded
rather than avoided:

### X001 INFO on mudler/Laguna-XS-2.1-APEX-GGUF (typed_content)

This is the normaliser-explained INFO variant, not the ERROR bucket. The main
loop opens with

```jinja
{%- set content = message.content if message.content is string else "" -%}
```

so under jinja2 a list content fails `is string` and becomes the empty string —
jinja2 silently drops the user's message. llama.cpp's normaliser had already
joined the parts into a string, so `is string` holds there. Diff:

```
--- jinja2
+++ llama.cpp
@@ -1,3 +1,4 @@
 〈|EOS|〉<system>You are a helpful, conversationally-fluent assistant made by Poolside. …</system>
-<user></user>
+<user>Hello
+there</user>
 <assistant></think>
```

Not whitespace-only (jinja2 emits no content whatsoever), so it does not collapse
into X004; re-rendering under jinja2 with the content pre-flattened reproduces
llama.cpp's text exactly, which is what `_explained_by_normaliser` requires for
the INFO downgrade. Consistent with the spike's `typed_content` finding, and not
a bug in Task 5.

### X002 ERROR on rippertnt/HyperCLOVAX (tool_roundtrip) — a real divergence

jinja2 (the transformers path) raises
`TypeError: can only concatenate str (not "NoneType") to str` on the assistant
message's `content: null`. llama.cpp's minja coerces the null to an empty string
and renders happily:

```
<|im_start|>system\nBe brief.<|im_end|>
<|im_start|>user\nWeather in Paris?<|im_end|>
<|im_start|>assistant\n<|im_end|>            <-- empty turn; the tool call is gone
<|im_start|>tool\n{"temp_c": 18}<|im_end|>
<|im_start|>assistant\n
```

llama.cpp silently drops the assistant's tool call and feeds the model an empty
assistant turn followed by a tool result for a call that was never shown, while
transformers refuses the conversation outright. ERROR is the right severity: the
runtimes disagree about a conversation one of them will serve, and llama.cpp's
answer is wrong. Evidence carries `"normalized": false` — pre-flattening typed
content does not make jinja2 reproduce llama.cpp's text here, so the normaliser
is demonstrably not the explanation.

This is the `tool_roundtrip` divergence class the engine spike already
documented (assistant `content: null` → jinja2 prints `None`, llama.cpp prints
nothing), in its *concatenating* form: because this template concatenates rather
than prints, jinja2 raises instead of printing `None`, which turns a two-sided
X001 into a one-sided X002 at ERROR. It is a fact about the template plus a
known engine difference, not a new engine bug and not a Task 5 defect — so I did
not add a line to the spike doc, but a coordinator may want one recording that
the null-content divergence surfaces as X002 ERROR (not only X001/X005) when the
template concatenates.

## Verification

- `.venv/bin/python -m pytest tests/test_real_templates.py -q` → `11 passed in 3.21s`
- `.venv/bin/python -m pytest -q` (full suite) → **`245 passed in 6.96s`**, no
  warnings, no skips, output pristine.
- No test in this task reaches the network: `tests/test_real_templates.py` reads
  only `tests/data/templates/*`, and constructs `Jinja2Engine` (pure Python) and
  `LlamaCppEngine` (the vendored local WASM module). No `network` marker needed.

## Files changed

Commit `4b73aa5`, 26 files, +1956:

- `tests/test_real_templates.py` (new, 377 lines)
- `tests/data/__init__.py` (new, empty)
- `tests/data/templates/SOURCES.md` (new)
- `tests/data/templates/*.jinja` ×10 + `*.json` ×10 + `*.upstream.jinja` ×3
  (verbatim fetched copies)

## Concerns

1. **S004 ERROR on six of the ten is an artefact of the harness's two-token
   vocab, not (mostly) a defect in those repos.** The briefed `run()` builds
   `tokens = [bos_token, eos_token]` because HF metadata carries no vocab, so
   S004 — "emits `<|…|>` tokens absent from *this file's* vocab" — fires
   wherever a template emits any other special token, e.g. `<|im_start|>` on
   every ChatML-family template. The finding is correct about the
   (template, vocab) pair it was handed, and each expectation comment says
   which listed tokens are artefacts versus real disagreements (rippertnt's
   `<|im_end|>` and PaddleOCR's `<|begin_of_sentence|>` are real; the
   `<|im_start|>`s are not). I pinned it as observed rather than narrowing the
   assertion — but if a later task wants this corpus to say something about the
   *repos* rather than about a synthetic vocab, `run()` needs a real vocab (or
   S004 needs to record a coverage gap when the vocab is implausibly small,
   which would be a check change, not a test change). Flagging because six
   ERROR-severity findings on six working, popular models is precisely the
   false-positive shape that kills linters.
2. **`_whitespace_only` is tested before the normaliser-explained branch** in
   `run_cross_engine_checks`, so a divergence that is *both* normaliser-caused
   and whitespace-only lands at X004 WARN rather than X001 INFO. That is five of
   the ten entries here (all the separator-free text-part loops). I think WARN is
   defensible — the model really does see "Hellothere" vs "Hello\nthere" — but
   the ordering means the INFO downgrade is unreachable for that overlap, which
   is a Task 5 design point a coordinator may want to confirm was intended.
3. **Every sidecar's `revision` is null.** `survey --save-templates` reads it
   from `model_info`'s `sha`, which this run's responses did not carry, so the
   corpus is pinned by content and `fetched_at` rather than by commit. Not
   fixable in this directory; it is a `--save-templates` gap.
4. **CI runs Python 3.11–3.13; these sets were pinned on 3.14.** The pinned
   tuples carry no error strings, so only a change that merges or splits S003's
   collapse signatures could shift a set — that needs CPython to reword
   `can only concatenate str (not "X") to str` such that "NoneType" and "list"
   stop being distinguishable, which is very unlikely. Untested on 3.11–3.13
   locally; CI will say.

---

# Fix report — rulings R6, R7, R8

All three applied. Commits, oldest first:

| SHA | Subject |
|-----|---------|
| `0069561` | fix(checks): a normaliser-explained divergence outranks whitespace-only (R7) |
| `1a6ffbe` | fix(hf): request expand[]=sha so saved templates record a revision (R8) |
| `f502387` | test: stop fabricating a vocab for the vendored templates; pin revisions (R6, R8) |

Covering tests: `.venv/bin/python -m pytest tests/test_real_templates.py
tests/test_checks_cross_engine.py tests/test_hf.py tests/test_survey.py -q` →
**`64 passed`**. Full suite before committing → **`247 passed in 6.60s`** (up
from 245: one new test each for R7 and R8), no warnings, no skips.

## R7 — normaliser-explained outranks whitespace-only

`src/ggufdoctor/checks/cross_engine.py`: the `explained_flag` branch now
precedes the `_whitespace_only` branch, with a comment giving the reason (cause
outranks magnitude) and citing the ruling.

Test added to `tests/test_checks_cross_engine.py`:
`test_normaliser_explained_divergence_outranks_whitespace_only`, built with
`FakeEngine` as preferred — **no real-engine fallback was needed**. The
construction: the jinja2 fake returns `"Hello there"` when any message content
is still a list and `"Hello  there"` when it is not, so it (a) diverges from the
llama.cpp fake by whitespace only, and (b) reproduces the llama.cpp output
exactly on the pre-flattened context, which is what `_explained_by_normaliser`
requires. The llama.cpp fake returns `RenderResult(..., extra={"normalized":
True, ...})`. Every other fixture agrees byte for byte, so the expected set is a
single `("X001", INFO, ("typed_content",))` and `engines_agreed_fixtures == 9`.
The test also asserts the two strings really are whitespace-only variants, so it
cannot pass by drifting onto a different branch.

Verified it bites: with the old ordering restored, it fails with
`Extra items in the right set: ('X001', <Severity.INFO>, ('typed_content',))` —
i.e. the finding came back as X004 — and passes with the fix. (Note for anyone
repeating this: a stale `__pycache__` made one intermediate run misreport; clear
it when flipping source back and forth.)

Effect on the corpus: five entries moved X004 WARN → X001 INFO (HauhauCS
Gemma-4, LiquidAI, LuffyTheFox, PaddleOCR, ornith-ai). mudler/Laguna was already
X001 INFO (its jinja2 side drops the message entirely, so it was never
whitespace-only).

## R6 — no fabricated vocabulary

`run()` now builds `GgufModel(tokens=[], bos_token_id=None, eos_token_id=None,
add_bos_token=None)`. Verified by running: **every template's
`checks_not_evaluated` is now `["S004", "S005", "S006"]`**, exactly as the
ruling predicted, and no S004 ERROR is pinned anywhere.

The module docstring now explains why real tokens are not used — HF's `gguf`
metadata carries bos/eos strings but no vocab, and the fabricated two-token
vocab produced false S004 ERRORs on six of ten working models — and notes that
both engines therefore render with the symmetric `BASE_CONTEXT` placeholders
(`<s>`/`</s>`), which is why the X family is unaffected in kind and why a `<s>`
appears in some quoted diffs. The shared gap list is a named constant
`NO_VOCAB_GAPS` rather than repeated ten times.

`stats["engines_agreed_fixtures"] >= 1` was **kept**: the minimum across the ten
is 8 of 10 (PaddleOCR and HyperCLOVAX), so no template agrees on zero fixtures
and the assertion stays meaningful. A comment says so.

Every set was re-derived and re-justified from the template text. Net changes
from the first revision:

| Slug | Before | After |
|------|--------|-------|
| HauhauCS Gemma-4 | S004 ERROR; S005 WARN; X004 WARN | X001 INFO |
| LiquidAI LFM2.5 | S004 ERROR; X004 WARN | X001 INFO |
| LuffyTheFox Qwen3.6 | S004 ERROR; X004 WARN | X001 INFO |
| PaddleOCR-VL | S003 INFO; S004 ERROR; X004 WARN | S003 INFO; X001 INFO |
| antirez deepseek-v4 | S003 INFO; X002 INFO | unchanged |
| legraphista glm-4 | S005 WARN; S007 WARN | S007 WARN |
| mudler Laguna | X001 INFO | unchanged |
| ornith-ai Ornith | S004 ERROR; X004 WARN | X001 INFO |
| rippertnt HyperCLOVAX | S003 INFO ×2; S004 ERROR; S005 WARN; X002 ERROR; X002 INFO | S003 INFO ×2; X002 ERROR; X002 INFO |
| unsloth Qwen3-Coder | S003 INFO; S004 ERROR; X002 INFO | S003 INFO; X002 INFO |

Three S005 WARNs disappeared (HauhauCS, legraphista, rippertnt). Those were
*real facts about those repos* — Gemma-4 closes turns with `<turn|>` and
references `eos_token` zero times; glm-4's constant can never emit EOS;
HyperCLOVAX declares `<|endofturn|>` but emits `<|im_end|>` — but they were only
observable because the harness fabricated an EOS string from the sidecar. With
no vocab, S005 correctly records a coverage gap instead. I kept each fact in a
comment on the relevant entry, explicitly marked as true-of-the-repo but
not-establishable-from-metadata, so the knowledge is not lost and nobody later
mistakes the silence for a clean bill of health. The glm-4 entry says plainly
that the most defective template in the corpus is the one the missing vocab
costs us most on.

Concern 2 kept as ruled: the HyperCLOVAX `X002 ERROR` on `tool_roundtrip`
survives with llama.cpp's full render quoted in the comment.

## R8 — revisions populated

`src/ggufdoctor/hf.py::HfClient.model_info` now requests
`&expand[]=sha`. There was **no existing URL assertion** in `tests/test_hf.py`,
so I added `test_model_info_requests_every_field_its_callers_read`, which pins
the whole `expand[]` set (`gguf`, `cardData`, `tags`, `pipeline_tag`, `sha`) —
appropriate because omitting a field fails silently, reading as `None` forever,
rather than erroring.

Re-fetch: `.venv/bin/ggufdoctor survey --top 80 --per-org 1 --save-templates
/tmp/gd-templates-2 --out /tmp/gd-survey-2.json` — exit 0, 148 files, and again
**no `examine_error`** in `coverage_gaps`, so nothing was rate-limited.

**All ten vendored `.jinja` files re-fetched byte-identical** (verified with
`filecmp.cmp(..., shallow=False)`), so every sidecar received its `revision`:

| Repo | Revision (short) |
|------|------------------|
| unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF | `b17cb02dd882` |
| ornith-ai/Ornith-1.0-9B-GGUF | `3296bc7a4048` |
| HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive | `45b6a334b4bc` |
| antirez/deepseek-v4-gguf | `f71f23d552d6` |
| mudler/Laguna-XS-2.1-APEX-GGUF | `e9e9293c1979` |
| LuffyTheFox/Qwen3.6-35B-A3B-…-V13-GGUF | `0095a3d1c1e1` |
| rippertnt/HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF | `3d2edd543d75` |
| LiquidAI/LFM2.5-2.6B-GGUF | `84022ce711b2` |
| PaddlePaddle/PaddleOCR-VL-1.6-GGUF | `511b09642bb3` |
| legraphista/glm-4-9b-chat-IMat-GGUF | `0c1dbb84faf5` |

No template text was touched: the update script asserted byte-identity first,
then asserted that `revision` was the *only* key whose value changed and that
key order was preserved. `git diff --stat` confirms one changed line per
sidecar. Nothing needed the "left null because the bytes moved" treatment, and
`SOURCES.md` says so explicitly rather than leaving the reader to infer it.

`SOURCES.md` also had its stale glm-4 callout corrected: it previously said S005
fires there, which R6 makes untrue, so it now states the S007 WARN and explains
that the EOS fact is unevaluated for want of a vocab.

## Remaining concern (one, and it needs a coordinator decision)

`docs/v0.2-kickoff.md:115` reads **"Whitespace-only goes to X004, never
X001."** R7 deliberately overrides that for the normaliser-explained subset. I
did **not** edit that design doc — it is not this task's file, and silently
rewriting a spec line is worse than flagging it — but as written it now
contradicts the shipped behaviour, and a later task reading it could "fix" R7
back out. The code comment cites ruling R7 by name as a guard. Suggest the
coordinator amend that bullet to something like "Whitespace-only goes to X004,
never X001 — unless llama.cpp's normaliser is the proven cause, which is X001
INFO (R7)."

Concerns 1, 3 and 4 from the original report are resolved by R6, R7 and R8
respectively. Concern 2 was ruled a true positive and is kept. The
Python-version note from the original report still stands unchanged: these sets
were pinned on 3.14 and CI covers 3.11–3.13; the pinned tuples carry no error
strings, so only a CPython rewording that made "NoneType" and "list"
indistinguishable in `can only concatenate str (not "X") to str` could shift a
set.
