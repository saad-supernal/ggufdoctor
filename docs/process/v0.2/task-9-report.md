# Task 9 report — conformance suite against a real pinned `llama-server`

Status: **DONE_WITH_CONCERNS** (the suite is green; it found four real engine-fidelity gaps,
and fixing them changed the product's findings on four of ten corpus templates. That change
is honest and pinned, but the severity policy behind it needs a ruling — see §7.)

## 1. The command and its full per-template result

```
$ .venv/bin/python -m pytest -m conformance tests/conformance -v
```

Final state (macOS arm64, `llama-b10775-bin-macos-arm64.tar.gz`, `stories260K.gguf`):

| template | result |
| --- | --- |
| `HauhauCS__Gemma-4-E4B-Uncensored-HauhauCS-Aggressive` | PASSED (9/10 fixtures byte-equal, 1 skipped with reason) |
| `LiquidAI__LFM2.5-2.6B-GGUF` | PASSED (10/10) |
| `LuffyTheFox__Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-V13-GGUF` | PASSED (10/10) |
| `PaddlePaddle__PaddleOCR-VL-1.6-GGUF` | PASSED (10/10) |
| `antirez__deepseek-v4-gguf` | PASSED (10/10) |
| `legraphista__glm-4-9b-chat-IMat-GGUF` | PASSED (10/10) |
| `mudler__Laguna-XS-2.1-APEX-GGUF` | PASSED (10/10) |
| `ornith-ai__Ornith-1.0-9B-GGUF` | PASSED (10/10) |
| `rippertnt__HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF` | PASSED (10/10) |
| `unsloth__Qwen3-Coder-30B-A3B-Instruct-GGUF` | PASSED (10/10) |

`10 passed in 3.06s`. 99 of 100 (template × fixture) pairs are byte-equal against the real
`llama-server`; one is skipped with a stated reason (§4). The byte-equality assertion was
not weakened.

The first run was **10 failed** — 26 diverging pairs across 5 templates. Everything below is
the work of turning that into the table above.

Environment overrides both verified working:
`GGUFDOCTOR_LLAMA_SERVER` + `GGUFDOCTOR_CONFORMANCE_MODEL` + a deliberately bogus
`GGUFDOCTOR_CONFORMANCE_CACHE` → `10 passed`, nothing downloaded.

Liveness of the oracle was verified rather than assumed: injecting
`ctx["enable_thinking"] = False` on our side alone turns the run into `5 failed, 5 passed`,
and a direct probe shows the server answering (`healthy in 0.22s`, `/apply-template` →
`'<｜User｜>PING-CANARY<｜Assistant｜><think>'`). The 3-second runtime is real: a 1 MB model
loads in ~0.2 s and the suite starts one server per template.

## 2. Mismatch classes found, and how each was classified

Five classes. The brief predicted two of them (the `content: null` and the dict-`arguments`
handling); the three biggest were unpredicted.

### Class 1 — assistant prefill (`no_generation_prompt`, all 10 templates) → **oracle config**

`oaicompat_chat_params_parse` (`tools/server/server-common.cpp`) sets
`continue_final_message = COMMON_CHAT_CONTINUATION_AUTO` and forces
`add_generation_prompt = false` whenever `prefill_assistant` is on (the default) **and the
last message has role `assistant`** — it does not even consult the request's
`add_generation_prompt`. `common_chat_templates_apply_jinja` (`common/chat.cpp`) then pops
that message, renders `messages[:-1]` **with** a generation prompt, and appends the popped
message's content verbatim.

Evidence it is not template application at all: for `legraphista__glm-4-9b-chat-IMat-GGUF`,
whose "template" is the constant `ChatGLM4`, the server returned `ChatGLM4Hello!` — the
template never saw the message.

Neither (a) nor (b): it is a serving policy for resuming a half-finished turn, with a
documented off switch. Resolved by configuring the oracle to answer the question we ask it —
`--no-prefill-assistant` in `tests/conformance/llama_server.py`, with the reasoning in a
comment at the flag. This *keeps* full byte-equality coverage of `no_generation_prompt`,
which a skip would have thrown away.

### Class 2 — `enable_thinking` is always defined and defaults to true (4 templates, 20 pairs) → **(a), ported**

`common_chat_template_direct_apply_impl` (`common/chat.cpp:946`) writes
`{"enable_thinking", inputs.enable_thinking}` into the render context **unconditionally**,
from `autoparser::generation_params::enable_thinking` whose in-struct default is `true`
(`common/chat.h:261`). There is no path through llama.cpp that leaves the variable
undefined: `--reasoning-budget 0` makes it *false*, not absent.

The bundled engine left it undefined, i.e. it was rendering something real llama.cpp can
never render. Ported. Divergences it explained:

- `HauhauCS` Gemma-4: line 157 opens a whole system turn for
  `(enable_thinking is defined and enable_thinking) or tools or ...` and line 161 emits
  `<|think|>` inside it → the server's prompt had a turn ours lacked, on 8 fixtures.
- `antirez__deepseek-v4`: lines 4–9 default `thinking` to *false* when `enable_thinking` is
  undefined; line 91 then emits `</think>` where the server emits `<think>` — one token,
  opposite meaning, on 7 fixtures.
- `mudler__Laguna-XS`: line 4 is `enable_thinking | default(false)`, same inversion, plus an
  empty `<think></think>` on every historical assistant turn (line 54), on 8 fixtures.

### Class 3 — `add_generation_prompt` is absent, never false (1 template) → **(a), ported**

Same function: `if (inputs.add_generation_prompt) inp["add_generation_prompt"] = true;`. The
key exists only when the flag is on. `PaddlePaddle__PaddleOCR-VL-1.6`'s first two lines are
`{%- if not add_generation_prompt is defined -%}{%- set add_generation_prompt = true -%}`,
so llama.cpp defaults it back on and appends `Assistant:\n` while we, passing an explicit
`false`, did not. Ported: a falsy `add_generation_prompt` is erased from the context, a
truthy one canonicalised to `true`.

### Class 4 — `caps_apply_preserve_reasoning` (1 template) → **(a) for the reaction, oracle-symmetry for the default**

`direct_apply_impl` (`common/chat.cpp:966-973`) expands a `preserve_reasoning` boolean in the
context through `jinja::caps_apply_preserve_reasoning`, which sets `preserve_thinking`,
`clear_thinking`, `truncate_history_thinking` and `drop_thinking`; likewise
`reasoning_effort` through `jinja::caps_apply_reasoning_effort`. The shim omitted both.
`LuffyTheFox__Qwen3.6`'s line 100 tests `preserve_thinking is defined and preserve_thinking
is true`, so the server rendered `<think>\n\n</think>\n\n` into history where we did not.

Where the key comes from is the interesting half: **not** the engine and not the request, but
`common_params_parse` in `common/arg.cpp:963-965`, which puts
`default_template_kwargs["preserve_reasoning"] = "true"` into every llama.cpp CLI tool unless
`--no-reasoning-preserve` is given. So the engine must *react* to the key (ported) but must
not *invent* it, and the harness hands both sides the same one — `PRESERVE_REASONING = True`
in the test, sent as `chat_template_kwargs.preserve_reasoning` to the server and set in our
context, matching a default `llama-server` run. Same pattern as the brief's own `bos_token`
/ `eos_token` override, and it exercises the interesting (`preserve_thinking = true`) path.

### Class 5 — `content: null` (2 templates) → **(a), ported (one field only)**

`common_chat_msgs_parse_oaicompat` lowers each message into a `common_chat_msg` whose
`content` is a `std::string`, and `common_chat_msg::to_json_oaicompat` (`common/chat.cpp:186`)
emits `"content": ""` when there is neither content nor content_parts. A template therefore
never sees a null `content` through llama.cpp. `PaddleOCR-VL` branches on
`message["content"] is string` and iterates otherwise, so on `tool_roundtrip` it renders
fine there and died here with `render:Error: Expected iterable or object type in for loop:
got None`.

Ported, deliberately narrowly: **only** the null/absent-`content` → `""` field of that
round-trip. The rest of it (dropping unknown keys, dropping empty
`reasoning_content`/`name`/`tool_call_id`, stringifying
`tool_calls[].function.arguments`) is request *shaping* that would silently rewrite the
caller's context, and it produced **no** divergence anywhere in the corpus — including the
dict-`arguments` case the brief flagged, because every template in the corpus that renders
tool calls has `supports_object_arguments`, so `workaround::func_args_not_string` converts
the server's string back to an object before rendering. That is recorded here so a future
corpus that includes an object-arguments-less tool template knows where to look.

## 3. What was ported into the shim

`engine/shim.cpp`:

- `normalize_messages` gained the `content` materialisation (Class 5), guarded so a
  non-object message element still passes through untouched rather than throwing.
- `render_job` gained `direct_apply_impl`'s remaining context handling (Classes 2, 3, 4),
  each with a comment naming the llama.cpp line it mirrors. All of it is behind the existing
  `normalize` flag, i.e. behind "behave like `direct_apply_impl`".

Module and manifest rebuilt with `engine/build.sh`:

| | before | after |
| --- | --- | --- |
| sha256 | `dca9d673968be24856afe222d2a7af1ac3e033963914f4034451ba36671d65b0` | `830e8722f62e2d597c1dda84002d6c93560c0cd9ea698514620bc9754854c1da` |
| size | 721 494 | 724 963 |

`build_tag` / `commit` / `wasi_sdk` unchanged (`b10775`,
`67a17c17caa95742186f8b1ecadd1b5abd6d5ebb`, `wasi-sdk-34`). Rebuilding after a
comment-only edit reproduced the same sha256, so the build stayed deterministic.

Docs kept truthful alongside: `engine/README.md` now describes the added context handling,
adds a "what the shim deliberately does not reproduce" list, and points the bump checklist
at the conformance suite; `llamacpp_engine.py`'s module docstring lists the same.

## 4. The SKIP table — one entry

`("HauhauCS__Gemma-4-E4B-Uncensored-HauhauCS-Aggressive", "tool_roundtrip")`

`common_chat_try_specialized_template` (`common/chat.cpp:3577`) sniffs this template as an
outdated Gemma4 one (source contains `'<|tool_call>call:'` but not the
`{#- OpenAI Chat Completions:` marker), logs "detected an outdated gemma4 chat template,
applying compatibility workarounds", and runs `workaround::convert_tool_responses_gemma4`
over the message list: `assistant(tool_calls) → tool+` collapses into a single assistant
message carrying a `tool_responses` array, with each result's content JSON-parsed. The
server rendered `<|tool_response>response:get_weather{temp_c:18}<tool_response|>`; we
rendered the ordinary `<|turn>tool\n{"temp_c": 18}<turn|>` turn.

Classified **(b)**: it is one of ~10 per-family message rewrites in `chat.cpp`'s dispatch,
none of which `direct_apply_impl` performs. Reproducing that layer means vendoring
`chat.cpp`'s whole dispatch (including its PEG parsers) into the WASM module — a different
product, not a template linter.

The skip is not a blind spot: skipped pairs are still rendered and compared, and a pair that
*starts* matching is reported as a stale SKIP entry, so the table cannot outlive its reason.

## 5. Real-template expectation changes (`tests/test_real_templates.py`)

Four of ten entries moved, all caused by Classes 2, 3 and 5. Each was re-derived from the
actual finding set and given its own justification in the file; a shared header now states
the `enable_thinking` fork once instead of four times.

| template | change |
| --- | --- |
| `HauhauCS…Gemma-4` | `typed_content` X001 INFO → ERROR (the diff now also carries `<|think|>`, so pre-flattening no longer reproduces llama.cpp and the INFO downgrade correctly stops applying); new X001 ERROR on `user_only`/`multiturn`/`thinking_unset`/`no_generation_prompt` and on `system_user`; new X005 ERROR on `with_tools`/`tool_roundtrip` |
| `PaddlePaddle…PaddleOCR-VL` | new X002 ERROR on `tool_roundtrip` (llama.cpp now renders where jinja2 raises — same class as the HyperCLOVAX entry already documented there: the assistant's tool call vanishes into an empty turn, so one runtime refuses the conversation and the other serves a misleading prompt); new X001 ERROR on `no_generation_prompt` (Class 3) |
| `antirez__deepseek-v4` | `typed_content` X002 INFO → ERROR (same reason as Gemma-4); new X001 ERROR on 4 fixtures, X005 ERROR on 2 |
| `mudler__Laguna-XS` | `typed_content` X001 INFO → ERROR; new X001 ERROR on `user_only`/`system_user`/`thinking_unset`, on `multiturn`, on `no_generation_prompt`; new X005 ERROR on `with_tools` and on `tool_roundtrip` |

`engines_agreed_fixtures` fell to 2, 2, 3 and 7 (of 10) on these four; the closing
`>= 1` assertion still holds and its stale "the minimum is 8 of 10" comment was corrected
to say exactly how thin the margin now is and why (the two at 2 agree only on
`thinking_true` and `thinking_false`, the fixtures that pin the variable on both sides).

One synthetic case in `tests/test_checks_cross_engine.py` also gained a finding:
`test_x002_renders_in_llama_cpp_only_via_normaliser_is_info`'s template guards on
`m.content is not none`, which now passes under llama.cpp and fails under jinja2 on
`tool_roundtrip` → an extra X005 ERROR. Recorded with its reason rather than engineered
away, and the test's own assertions were re-pointed at the X002 finding by id instead of
`found[0]`.

## 6. Files changed

Created: `tests/conformance/__init__.py`, `tests/conformance/llama_server.py`,
`tests/conformance/test_llama_server.py`.

Modified: `pyproject.toml` (markers + addopts), `.github/workflows/ci.yml` (the
`conformance` job, exactly as briefed), `engine/shim.cpp`,
`src/ggufdoctor/engine_data/llamacpp-jinja.wasm`,
`src/ggufdoctor/engine_data/llamacpp-jinja.json`,
`src/ggufdoctor/engines/llamacpp_engine.py` (docstring), `engine/README.md`,
`tests/test_real_templates.py`, `tests/test_checks_cross_engine.py`.

## 7. Proposed rulings for the controller

1. **R-a (Class 1).** A `llama-server` request policy with a documented CLI off switch and no
   rendering analogue is resolved by configuring the oracle, not by skipping the fixture.
   Applied to assistant prefill (`--no-prefill-assistant`). Recorded at the flag.
2. **R-b (Classes 2 and 3).** Anything `common_chat_template_direct_apply_impl` itself does
   to the context is engine behaviour and belongs in the shim, even when it changes what
   ggufdoctor reports. Rendering a context llama.cpp can never produce is an engine bug, not
   a neutral choice.
3. **R-c (Class 4).** A default injected by `common/arg.cpp` (the CLI layer) is not engine
   behaviour: the engine reacts to the key, the harness supplies it symmetrically at the
   value a default `llama-server` run uses.
4. **R-d (Class 5).** Port only the fields of the `common_chat_msg` round-trip that a
   divergence actually demands; the rest is request shaping that would rewrite the caller's
   context unbidden.
5. **R-e (the one that needs a decision, not a record).** The `enable_thinking` fork now
   produces **X001/X005 ERROR** on 4 of 10 corpus templates, on every fixture that does not
   pin `enable_thinking`. The divergence is real and material — the same GGUF, the same
   caller code, two different prompts — but it is a *runtime default* difference, not a
   template defect, and the template author cannot remove it (`mudler`'s template already
   defaults the variable explicitly and llama.cpp overrides it anyway). Since most modern
   models are thinking-capable, the default report will read "ERROR" on most popular models,
   which is the failure mode that kills linters. Options: (i) leave it at ERROR; (ii) extend
   the `_explained_by_normaliser` machinery with a second explanation — "divergence explained
   by llama.cpp's implicit `enable_thinking` default" — and downgrade it to INFO the same
   confirmatory way (re-render jinja2 with `enable_thinking=true` and require byte equality);
   (iii) put `enable_thinking: True` in `BASE_CONTEXT` so both engines see it, which hides
   the fork and makes `thinking_unset` a duplicate of `thinking_true`. My recommendation is
   **(ii)**: it keeps the fact reportable, ranks it by cause the way ruling R7 already ranks
   the normaliser, and does not pretend the two runtimes agree. It is a checks-layer change,
   so I did not make it inside this task.

## 8. Concerns

- **The severity blast radius above (R-e)** is the one item I would not ship without a
  ruling.
- **`common_chat_extra_context()`** (`common/chat.cpp:3472`) injects `datetime` and
  `date_string` from the *wall* clock. No vendored template references `datetime`,
  `date_string` or `strftime_now`, so it is unobservable today — but it is unpinnable by
  construction, and a corpus template that used it would make the conformance suite
  date-dependent. Noted in `engine/README.md`'s "does not reproduce" list.
- **`add_generation_prompt` presence semantics** are now mirrored, but no fixture probes the
  `is defined` shape deliberately — `PaddleOCR-VL` happens to. A fixture pair that renders
  with the key absent versus present-and-false would make Class 3 a first-class assertion
  rather than an incidental one.
- **The corpus does not cover a tool template without `supports_object_arguments`**, which is
  the one place the un-ported half of the `common_chat_msg` round-trip (dict → JSON-string
  `arguments`) would surface. Worth a corpus addition before claiming that half is
  unnecessary.
- **`network` has no tests left.** `pytest -m network --collect-only` collects nothing; the
  marker is retained per the brief but currently guards nothing.
- The default suite makes **no external network calls**: verified by re-running it under a
  `sitecustomize` that raises on any non-loopback `connect`/`getaddrinfo`
  (`247 passed, 10 deselected`). The four `test_http_range.py` tests use a loopback
  `HTTPServer` fixture, not the internet.

---

# Fix report — ruling R9 applied

Status: **DONE**. R9 implemented as specified, in the checks layer; the engines were not
touched for it. One extra correction the ruling called for landed in the shim (the
`normalized` flag, §F3).

## F1. What changed

`src/ggufdoctor/checks/cross_engine.py`

- New `_explained_by_thinking_default(j2, tpl, context, llama_text)`. Returns `False`
  immediately when `"enable_thinking" in context` (the caller pinned it, so both engines saw
  the same value and this explains nothing); otherwise re-renders **jinja2** with
  `{**context, "enable_thinking": True}` and returns whether its text equals `llama_text`.
  Confirmed, not assumed — same discipline as `_explained_by_normaliser`.
- In the both-rendered-but-different branch, the test sits **after** the normaliser
  explanation and **before** the whitespace-only test, so it also precedes the
  `is_tool_fixture` split: a tool divergence this explains lands in the X001 INFO bucket, not
  X005. The comment at the branch says why (the cause outranks both the magnitude and the
  fixture).
- New collapsed bucket: `X001` / `INFO` / `"rendered output differs only because llama.cpp
  defines enable_thinking=true by default while jinja2 (transformers path) leaves it
  undefined; pass enable_thinking explicitly to make the runtimes agree"`, evidence
  `"explained_by": "enable_thinking_default"`.
- The normaliser bucket now also carries `"explained_by": "normaliser"`, so the two classes
  are distinguishable in JSON.
- Module docstring gained the paragraph naming both explanation classes and the evidence key.

`tests/test_checks_cross_engine.py`

- `test_x001_explained_by_llama_cpps_enable_thinking_default_is_info` — real engines, the
  ruling's template. Asserts exactly one collapsed
  `("X001", INFO, NO_THINKING)` where `NO_THINKING` is the eight fixtures that do not pin the
  variable **in corpus order**, `evidence["explained_by"] == "enable_thinking_default"`, the
  fix phrasing in the message, and `engines_agreed_fixtures == 2` (`thinking_true` and
  `thinking_false`, which pin it).
- `test_enable_thinking_default_is_not_the_explanation_when_the_caller_pinned_it` — a
  `{{ none }}` divergence in the same shape must stay ERROR with no `explained_by`, so the
  new downgrade cannot swallow unrelated differences.
- The existing normaliser test now also asserts `evidence["explained_by"] == "normaliser"`.

## F2. Re-derived corpus expectations (`tests/test_real_templates.py`)

Three of the four entries moved; `PaddleOCR-VL` did not (it has no `enable_thinking` branch —
its two ERRORs are the `add_generation_prompt`-presence fact and the null-content X002, both
unrelated to R9). Each entry keeps its own justification quoting the template's own
`enable_thinking` branch.

| template | before R9 | after R9 |
| --- | --- | --- |
| `HauhauCS…Gemma-4` | X001 ERROR ×2 + X005 ERROR | X001 INFO `(user_only, multiturn, thinking_unset, no_generation_prompt)` + X001 INFO `(system_user, with_tools, tool_roundtrip)` |
| `antirez__deepseek-v4` | X001 ERROR ×1 + X005 ERROR | one X001 INFO over all six `(user_only, system_user, multiturn, with_tools, thinking_unset, tool_roundtrip)` |
| `mudler__Laguna-XS` | X001 ERROR ×3 + X005 ERROR ×2 | X001 INFO `(user_only, system_user, with_tools, thinking_unset)` + X001 INFO `(multiturn, tool_roundtrip)` + X001 INFO `(no_generation_prompt)` |

Every X005 the fork produced is gone, as ruled. The buckets split where the *character* diff
signature differs (an added system turn versus a `<|think|>` prepended inside an existing
one; a generation-prompt-only diff versus one that also rewrites history), which is
`collapse_by_signature` working as designed, not a severity difference.

The `EXPECTED` header now states R9 once instead of the old "deliberately NOT downgraded"
paragraph, and the closing `engines_agreed_fixtures` comment notes that R9 changed how the
divergence is *reported*, not whether the engines agree, so its numbers (2, 2, 3) are
unaffected.

**Residue the controller should know about.** Two `typed_content` entries stay ERROR
(`HauhauCS` X001, `mudler` X001) even though the fork is part of their cause: their diff
mixes it with the normaliser's typed-content join, so neither single explanation reproduces
llama.cpp on its own — pre-flattening still leaves the think block missing, and adding
`enable_thinking=True` still leaves the parts joined without a separator. Composing the two
explanations (flatten typed content **and** set `enable_thinking`) would explain both. R9
specifies a single-cause test, so I implemented exactly that and recorded the residue at both
entries and in the header rather than extending the ruling on my own. If those two should be
INFO as well, the composition is a small follow-up in the same function pair.

## F3. The `normalized` flag — confirmed and corrected

The ruling was right, and my first commit was wrong: `6db84b2`'s
`normalize_messages` set `changed = true` for the null/absent-`content` → `""`
materialisation, so it surfaced as `RenderResult.extra["normalized"] = True`. That flag
reports the **content-parts** normaliser (string ↔ typed), which the checks layer reads as
"llama.cpp reshaped the content parts"; the null coercion mirrors `common_chat_msg` *parsing*
instead, so claiming it under that flag misattributes a divergence's cause. Fixed: the
materialisation no longer sets `changed`, with a comment saying why.

Module rebuilt: sha256 `830e8722…` → `2014019410ed53ff901cb118510be8818066091c415ff37478504792dc300567`,
724963 → 724955 bytes. Pin unchanged (`b10775` / `67a17c17…` / `wasi-sdk-34`).

Verified directly against the HyperCLOVAX template: `tool_roundtrip` now renders with
`normalized=False`, `typed_content` with `normalized=True`, `user_only` `False`.

**HyperCLOVAX's expectation did not change — in either direction, at any point.** Its
`("X002", ERROR, ("tool_roundtrip",))` and `("X002", INFO, ("typed_content",))` are byte for
byte what they were before Task 9 (`git show 6db84b2 -- tests/test_real_templates.py`
touches the Paddle and antirez entries, never that one). The reason the spurious flag never
leaked into a finding is that `normalized` is only a *precondition* for calling
`_explained_by_normaliser`, which then re-renders and re-verifies: on
`tool_roundtrip` the pre-flattened jinja2 render does not reproduce llama.cpp's text, so the
downgrade never fired and the X002 stayed ERROR. The flag was misleading in JSON evidence
rather than wrong in outcome — which is exactly why it was worth fixing.

## F4. One consistency question left open

`explained_by` is set only in the both-rendered-but-different branch, as ruled. The one-sided
`_x002` path still records its normaliser explanation as `"normalized": True` with no
`explained_by` — visible on `HyperCLOVAX`/`unsloth`'s `("X002", INFO, ("typed_content",))`.
Adding the key there too would make the evidence uniform across the X family; it is outside
R9's wording, so I left it.

## F5. Verification

```
$ .venv/bin/python -m pytest tests/test_checks_cross_engine.py tests/test_real_templates.py \
      tests/test_engine_semantics.py -q
48 passed
$ .venv/bin/python -m pytest -q                      # under a no-external-network sitecustomize
249 passed, 10 deselected
$ .venv/bin/python -m pytest -m conformance tests/conformance -q
10 passed
```

Conformance is unchanged at 10/10 with the same single documented skip, which is the point:
R9 is a checks-layer ruling and the bundled engine stays byte-faithful to the real
`llama-server`. The default suite is up 2 tests (the two new cross-engine ones) and still
makes no external network call.

## F6. Files changed by this fix

`src/ggufdoctor/checks/cross_engine.py`, `tests/test_checks_cross_engine.py`,
`tests/test_real_templates.py`, `engine/shim.cpp`,
`src/ggufdoctor/engine_data/llamacpp-jinja.wasm`,
`src/ggufdoctor/engine_data/llamacpp-jinja.json`.

---

# Fix report — round 1 of 5 (Important finding + R10, R11, R12)

Status: **DONE**. All four items applied. The Important finding was correct and it paid off
immediately: removing the harness injection and moving the default into the engine surfaced a
real fork the product had been reporting as agreement.

## G1. R11 — `preserve_reasoning` default moved into the engine

`engine/shim.cpp`, after `caps_get` and before the `caps_apply_*` expansions:

```cpp
if (!context.contains("preserve_reasoning") && caps.supports_preserve_reasoning) {
    context["preserve_reasoning"] = true;
}
```

with a comment naming both mirrored locations. Removed `PRESERVE_REASONING` and its use from
`_ours` and `_body`; both functions are now built from the fixture context and the tiny
model's real bos/eos and nothing else, with a comment saying why a harness that hands a
llama.cpp default to *both* sides cannot see that default diverge.

**Conformance is still 10/10 with the injection gone** — which is the real confirmation of
R11: the engine now reproduces a default `llama-server` run on the preserve_reasoning path
without the harness propping it up.

One nuance worth recording, verified at the pin. `server-context.cpp:1493-1497` is a
*logging* block: it reads the caps and emits `SRV_WRN`/`SRV_INF`/`SRV_TRC` lines about
whether the kwarg is supported and enabled. The kwarg itself is passed unconditionally, via
`default_template_kwargs` → `chat_template_kwargs` → `extra_context` → `direct_apply_impl`,
which calls `caps_apply_preserve_reasoning` without consulting caps at all. So gating the
shim's default on `caps.supports_preserve_reasoning` makes ggufdoctor **narrower** than
llama-server, never wider: it can only fail to supply a default llama.cpp would have
supplied, and only for a template that reads one of the four expanded variables without
satisfying the caps probe. No template in the corpus does, and conformance passing 10/10 is
the evidence. I implemented the ruling as written rather than dropping the gate.

Module rebuilt: sha256 `2014019410ed…` → `3445df6504a6d4abf01f00b280e4b57cef4daf54cfd22437042e9c181156fc83`,
724955 → 725251 bytes. Pin unchanged.

### The fork R11 exposed — LuffyTheFox Qwen3.6, `multiturn`, X001 ERROR

`engines_agreed_fixtures` 9 → 8, and a new finding. Line 100 of that template:

```jinja
{%- if (preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index) %}
    {{- '<|im_start|>' + message.role + '\n<think>\n' + reasoning_content + '\n</think>\n\n' + content }}
```

`preserve_thinking` is one of the four variables `jinja::caps_apply_preserve_reasoning` sets
from the defaulted kwarg, so a default `llama-server` emits an empty reasoning block for the
*historical* assistant turn and transformers does not:

```
--- jinja2
+++ llama.cpp
 <|im_start|>assistant
+<think>
+
+</think>
+
 Hey!<|im_end|>
```

Only `multiturn` reports it, and the reason is worth stating because it looks like
under-reporting: it is the only fixture with a historical assistant turn that reaches line
100 with content to render. `no_generation_prompt` has one too, but that turn is the *last*
message, so `loop.index0 > ns.last_query_index` already holds and both engines take the
reasoning branch anyway. Verified per fixture, not inferred.

It stays **ERROR**, and not for want of trying — see G2.

### LiquidAI LFM2.5 — did **not** move, and it is a corpus gap, not a template property

The reviewer expected this one to diverge too. It does not, and the branch says why. Line 2
is `{%- set preserve_thinking = preserve_thinking | default(false) -%}`, line 87
`{%- set keep_thinking = preserve_thinking or loop.index0 > ns.last_user_index -%}` — so the
fork is genuinely there — but line 90 guards the output with:

```jinja
{%- if thinking and keep_thinking -%}
```

where `thinking` is `message.thinking or message.reasoning or message.reasoning_content`. **No
fixture in the corpus carries reasoning content on an assistant message**, so the block is
skipped on both engines whatever `keep_thinking` says. Recorded at the entry: a fixture with
an assistant `reasoning_content` would expose it here too, and would also give LiquidAI's and
LuffyTheFox's forks a shared cause instead of one visible and one hidden. That is the single
most valuable corpus addition I can point at right now.

## G2. R12 — generalised to runtime defaults

`_explained_by_thinking_default` → `_explained_by_runtime_defaults(j2, tpl, context,
llama_text) -> list[str]`, with
`RUNTIME_DEFAULTS = {"enable_thinking": True, "preserve_reasoning": True}` (insertion order
fixes the reported order) and a `_with_runtime_defaults` helper. It adds every default the
context lacks, re-renders jinja2 **once**, and returns the added keys on a byte-exact match,
`[]` otherwise — including `[]` when there was nothing to add. Evidence:
`explained_by = "runtime_defaults"`, `defaults = [...]`. Message is the ruling's, with the
keys interpolated.

Because the message names the keys, the bucket is keyed by the tuple of added keys
(`defaults_only: dict[tuple[str, ...], list[...]]`) so each collapsed finding names exactly
the defaults its fixtures needed, rather than one bucket carrying a message that is wrong for
half of it.

**A limit of this mechanism the controller should know about.** `preserve_reasoning` is a
*switch*, not a value: llama.cpp expands it into `preserve_thinking` / `clear_thinking` /
`truncate_history_thinking` / `drop_thinking` via `jinja::caps_apply_preserve_reasoning`
before rendering. `Jinja2Engine` has no such expansion (nor does transformers — I checked:
the engine has no reference to any of those names), so adding the switch to a jinja2 context
is **inert** unless the template reads that exact name. A template reading the *expanded*
variables — LuffyTheFox — therefore cannot be reproduced by this re-render, and its
divergence stays ERROR. Correct in outcome, since the runtimes really do disagree, and
consistent with the "confirmed, never assumed" rule: nothing is downgraded on a re-render
that did not match. But it means R12 as specified explains the `enable_thinking` fork and not
the `preserve_reasoning` one. If the latter should also downgrade, the faithful change is for
`RUNTIME_DEFAULTS` to carry the four expanded variables (`preserve_thinking: True`,
`clear_thinking: False`, `truncate_history_thinking: False`, `drop_thinking: False`) instead
of the switch, which is what `caps_apply_preserve_reasoning(ctx, true)` actually does. That is
a wording change to R12, so I did not make it. Documented in the function's docstring and at
the LuffyTheFox entry.

Consequence for `defaults`: since no corpus fixture pins either key, every corpus finding
reports `["enable_thinking", "preserve_reasoning"]` — the list says what the confirming
re-render had to add, not which key the template read. The ruling's `defaults ==
["enable_thinking"]` assertion is therefore not applicable to the R9 template, so rather than
weaken it I asserted the true value there and added a dedicated test with a fixture that
pins `preserve_reasoning`, where `defaults == ["enable_thinking"]` genuinely holds.

## G3. R10 — composition

`_explained_by_normaliser_and_runtime_defaults` flattens typed content the way
`_flatten_typed_content` does and then delegates to `_explained_by_runtime_defaults`, so the
composition is one re-render and reuses both single-cause definitions rather than restating
them. Tried **last** of the three, so a divergence one cause explains alone is never
attributed to two. Gated on llama.cpp's own `normalized` flag, like the normaliser-alone
test, so the normaliser is never named as half an explanation on a render where llama.cpp
says it did not normalise. Evidence: `explained_by = "normaliser+runtime_defaults"`,
`defaults`, `normalized: True`, `llamacpp_caps`.

Both mixed-cause corpus entries became INFO, as expected:

| entry | before | after |
| --- | --- | --- |
| `HauhauCS…Gemma-4` `typed_content` | X001 ERROR | X001 INFO, `normaliser+runtime_defaults` |
| `mudler__Laguna-XS` `typed_content` | X001 ERROR | X001 INFO, `normaliser+runtime_defaults` |

Both re-derived with the actual diff quoted and the reason each single explanation falls
short (pre-flattening leaves the think block; filling defaults leaves the parts unjoined, or
in mudler's case leaves jinja2 still dropping list content through
`message.content if message.content is string else ""`).

A real-engine test for the composed case was possible, so it exists rather than being
excused: `test_x001_explained_by_the_normaliser_and_runtime_defaults_together_is_info` uses
`{% if not enable_thinking %}<think>{% endif %}{% for m in messages %}<|{{ m.role }}|>{{ m.content }}{% endfor %}`,
which puts `typed_content` in the composed bucket, the single-cause fixtures in the plain
`runtime_defaults` bucket, and `tool_roundtrip` in an X005 ERROR (its `content: null` prints
`None` under jinja2 — a third cause no explanation covers). Having all three outcomes in one
template is what makes it a real test of the ranking rather than of one branch.

## G4. Minor items

- `add_generation_prompt` absent now means **on**: `chat.h`'s generation param is
  `add_generation_prompt = true`, so a caller who says nothing gets the key defined `true`,
  and only a falsy value erases it.
- Non-boolean values go through a new `json_truthy` helper implementing jinja truthiness
  (`false`, `null`, `0`, `""`, `[]`, `{}` falsy; everything else truthy) instead of
  `!is_null()`. Probed directly: `absent`/`true`/`1`/`"no"` → `defined=True`;
  `false`/`0`/`""`/`[]`/`null` → undefined.
- The stale-SKIP check now decides `agree` in **every** branch — matching text, a server
  error our side also failed on, or our failure against a server render — so a skipped pair
  that has come to agree *by either route* is reported as stale. The wording changed from
  "now matches" to "now agrees" to say so.
- `_ours`/`_body` are symmetric by construction, per G1.

## G5. Verification

```
$ .venv/bin/python -m pytest tests/test_engine_data.py tests/test_engine_llamacpp.py \
      tests/test_engine_semantics.py tests/test_checks_cross_engine.py tests/test_real_templates.py -q
64 passed
$ .venv/bin/python -m pytest -q                      # under a no-external-network sitecustomize
251 passed, 10 deselected
$ .venv/bin/python -m pytest -m conformance tests/conformance -v
10 passed in 2.92s
```

Conformance exact result: **all ten templates PASSED**, 99 of 100 (template × fixture) pairs
byte-equal, the same single documented Gemma4 skip — unchanged by this round, and now
achieved *without* the harness supplying `preserve_reasoning` to either side.

## G6. Files changed by this round

`engine/shim.cpp`, `src/ggufdoctor/engine_data/llamacpp-jinja.wasm`,
`src/ggufdoctor/engine_data/llamacpp-jinja.json`, `engine/README.md`,
`src/ggufdoctor/engines/llamacpp_engine.py`, `src/ggufdoctor/checks/cross_engine.py`,
`tests/conformance/test_llama_server.py`, `tests/test_checks_cross_engine.py`,
`tests/test_real_templates.py`.

## G7. Open, for the controller

1. **R12 and the `preserve_reasoning` switch** (G2): as worded, R12 cannot downgrade the fork
   R11 exposed. Expanding `RUNTIME_DEFAULTS` to the four `caps_apply_preserve_reasoning`
   variables would fix that and is what llama.cpp actually does; it needs a ruling because it
   changes what R12 means.
2. **A fixture with assistant `reasoning_content`** (G1): would expose LiquidAI's fork, give
   LuffyTheFox's a sibling, and is the corpus gap that currently makes one of two identical
   template shapes look clean.
3. The caps gate on the shim's `preserve_reasoning` default is narrower than llama.cpp's
   actual behaviour (G1). Harmless over this corpus and conformance-verified; noted in case
   the intent was an exact mirror.

---

# Fix report — round 2 (R11a, R12a)

Status: **DONE**. Both amendments applied; the last unexplained fork in the corpus is now
correctly classified, and no ERROR in the corpus is attributable to a runtime default any
more.

## H1. R11a — the `preserve_reasoning` default is now ungated

`engine/shim.cpp`: the `caps.supports_preserve_reasoning` condition is gone, so the default
is supplied whenever the key is absent. The comment now cites `common/arg.cpp:963-966` for
the CLI default and says that `direct_apply_impl` feeds it to
`jinja::caps_apply_preserve_reasoning` unconditionally and with no reference to caps, with
`server-context.cpp:1493-1512` named for what it actually is — the block that chooses which
log line to print about the kwarg.

Module rebuilt: sha256 `3445df6504a6…` → `4de88e68f8792347f1328be3ea377aa15100f2df7d2daf07fa6bee067d9c516f`,
725251 → 725239 bytes. Pin unchanged.

**Nothing in the corpus moved as a result**, which is worth stating rather than glossing:
every vendored template that reads a `preserve_reasoning` variable already had caps
reporting `supports_preserve_reasoning`, so the gate had never actually excluded one.
Conformance stayed 10/10 both before and after. The change is a fidelity fix for templates
the corpus does not contain — one that reads an expanded variable without satisfying the caps
probe — not a behaviour change on anything currently tested. Recorded at the LiquidAI entry
and the closing comment in `tests/test_real_templates.py` so nobody later reads the ungating
as having caused a result.

## H2. R12a — `RUNTIME_DEFAULTS` carries the expansion

```python
RUNTIME_DEFAULTS: dict[str, Any] = {
    "enable_thinking": True,
    "preserve_reasoning": True,
    "preserve_thinking": True,
    "clear_thinking": False,
    "truncate_history_thinking": False,
    "drop_thinking": False,
}
```

with a comment quoting the four `ctx.set_val` calls from `common/jinja/caps.cpp:22-27` and
saying why the switch alone is not enough (jinja2 has no expansion, so the bare switch is
inert unless a template reads that exact name). `_with_runtime_defaults` never overrides a
key the caller supplied — now stated in its docstring, and asserted by a test rather than
just claimed. `evidence["defaults"]` still lists only the keys that were added. The obsolete
paragraph in `_explained_by_runtime_defaults`'s docstring — the one explaining why the
preserve_reasoning fork could *not* be downgraded — is replaced by the reason it now can.

### The LuffyTheFox entry, re-derived

`("X001", Severity.ERROR, ("multiturn",))` → `("X001", Severity.INFO, ("multiturn",))`, with
`preserve_thinking` among the reported defaults. The justification quotes the branch:

```jinja
{%- if (preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index) %}
    {{- '<|im_start|>' + message.role + '\n<think>\n' + reasoning_content + '\n</think>\n\n' + content }}
```

and records that the earlier ERROR was an artefact of handing the re-render a switch jinja2
cannot expand, not a property of the divergence; that the divergence itself is unchanged and
real (a reasoning block in one runtime's history and not the other's); and — kept from round
1 because it still explains an apparent under-report — that only `multiturn` reports it,
because `no_generation_prompt`'s historical assistant turn is the *last* message, so
`loop.index0 > ns.last_query_index` already holds there and both engines take the branch.

The header paragraph that previously ended "LuffyTheFox below is that case, and it stays a
reported ERROR" is rewritten to describe R11a's ungated default and R12a's expansion.

### Tests

- `test_runtime_defaults_cover_the_expanded_preserve_reasoning_variables` — real engines, the
  ruling's template. It turned out to be a better test than a single-bucket assertion:
  `engines_agreed_fixtures == 0` (no fixture pins any preserve_reasoning variable, unlike
  `enable_thinking`), and the findings collapse into **two** buckets even though the
  divergence text is identical everywhere, because `thinking_true`/`thinking_false` pin
  `enable_thinking` and so needed one fewer default. Asserts `"preserve_thinking" in
  evidence["defaults"]` on both, `defaults == list(RUNTIME_DEFAULTS)` on the unpinned bucket,
  and `"enable_thinking" not in defaults` on the pinned one — so it covers the expansion and
  the never-override rule in one real-engine case.
- `test_runtime_defaults_reports_only_the_keys_it_had_to_add` now pins *every*
  preserve_reasoning variable, leaving `defaults == ["enable_thinking"]`.
- The two existing `defaults ==` assertions now compare against `list(RUNTIME_DEFAULTS)` and
  the message against `", ".join(RUNTIME_DEFAULTS)`, imported from the module, so the tests
  cannot drift out of step with the source of truth if the list changes again.

## H3. Corpus state after both rounds

Every remaining ERROR in the corpus is a fact about a template or a runtime difference with
no default behind it:

| template | remaining ERROR | cause |
| --- | --- | --- |
| `PaddlePaddle…PaddleOCR-VL` | X001 `no_generation_prompt` | `add_generation_prompt` is absent-not-false under llama.cpp, and the template defaults it back to true |
| `PaddlePaddle…PaddleOCR-VL` | X002 `tool_roundtrip` | llama.cpp renders a null `content` as `""` and drops the tool call into an empty turn; jinja2 raises |
| `antirez__deepseek-v4` | X002 `typed_content` | jinja2 raises on `+` with a list; llama.cpp's normaliser had joined it |
| `rippertnt…HyperCLOVAX` | X002 `tool_roundtrip` | same empty-assistant-turn class as PaddleOCR-VL |

No ERROR anywhere is now attributable to `enable_thinking` or `preserve_reasoning`.
`engines_agreed_fixtures`: 2, 9, 8, 7, 3, 10, 2, 9, 8, 9.

## H4. Verification

```
$ .venv/bin/python -m pytest tests/test_engine_data.py tests/test_engine_llamacpp.py \
      tests/test_engine_semantics.py tests/test_checks_cross_engine.py tests/test_real_templates.py -q
65 passed
$ .venv/bin/python -m pytest -q                      # under a no-external-network sitecustomize
252 passed, 10 deselected
$ .venv/bin/python -m pytest -m conformance tests/conformance -q
10 passed in 3.08s
```

Conformance exact result: **all ten templates PASSED**, 99 of 100 (template × fixture) pairs
byte-equal, the same single documented Gemma4 skip. Unchanged by this round — as it should
be, since R11a widens when the engine supplies a default and R12a only touches the checks
layer.

## H5. Files changed by this round

`engine/shim.cpp`, `src/ggufdoctor/engine_data/llamacpp-jinja.wasm`,
`src/ggufdoctor/engine_data/llamacpp-jinja.json`, `engine/README.md`,
`src/ggufdoctor/checks/cross_engine.py`, `tests/test_checks_cross_engine.py`,
`tests/test_real_templates.py`.

## H6. Still open

Only the corpus gap from round 1: **no fixture carries assistant `reasoning_content`**, which
is why LiquidAI LFM2.5's `preserve_thinking` fork stays invisible while LuffyTheFox's shows.
Both templates gate on the same variable; LiquidAI additionally requires
`{%- if thinking and keep_thinking -%}`, and `thinking` is only ever non-empty when a message
supplies reasoning content. A fixture that does would exercise the expanded defaults on both,
and is the one addition I would still argue for.
