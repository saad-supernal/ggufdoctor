"""Complete S + X finding sets on ten real, vendored templates.

Every expected finding below is a true positive with a stated reason. If a
change to the checks alters any set, this test fails loudly -- that is the
point. Never narrow an assertion to a single id to make it pass.

`run()` deliberately builds the model with NO vocabulary (`tokens=[]`, no
bos/eos ids). The Hugging Face `gguf` metadata block these templates were
fetched from carries `bos_token`/`eos_token` *strings* and nothing else -- no
vocab, no `add_bos_token`. An earlier revision of this file synthesised a
two-entry vocab from those two strings, which pinned S004 "template emits
special tokens absent from this file's vocab" at ERROR on six of these ten
working, popular models: against a two-token vocab, an ordinary
`<|im_start|>` is "missing". That is a fabricated finding about a fabricated
vocab, and pinning it would have taught the corpus to expect false positives
(ruling R6). So the checks that ask *which* tokens appear -- S004, S005, S006
-- get nothing to work with and correctly record themselves in
`checks_not_evaluated` for all ten templates. That is an honest coverage gap
in what HF metadata can tell us, not a clean pass, and closing it needs a real
vocab (a local GGUF file), not a cleverer test.

Both engines therefore render with the same fabricated placeholder
`bos_token`/`eos_token` from `Jinja2Engine.BASE_CONTEXT` (`<s>` / `</s>`) --
symmetric, so it cannot manufacture a divergence between them, which is why
the X family is unaffected in kind. The `<s>` visible in some expected diffs
below is that placeholder, not the repo's own BOS.
"""
import json
import pathlib

import pytest

from ggufdoctor.checks.cross_engine import run_cross_engine_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity

DATA = pathlib.Path(__file__).parent / "data" / "templates"

# S004, S005 and S006 cannot evaluate without a vocab -- see the module
# docstring. Every template shares this, so it is named once here.
NO_VOCAB_GAPS = ["S004", "S005", "S006"]


def load(slug):
    tpl = (DATA / f"{slug}.jinja").read_text(encoding="utf-8")
    side = json.loads((DATA / f"{slug}.json").read_text(encoding="utf-8"))
    return tpl, side


def run(slug):
    tpl, side = load(slug)
    # No vocab and no token ids: HF metadata carries neither, and fabricating
    # them produced false S004 errors on working models (see module docstring).
    model = GgufModel(source_id=side["repo"], architecture=side["architecture"],
                      chat_template=tpl, tokens=[], bos_token_id=None,
                      eos_token_id=None, add_bos_token=None)
    ctx = CheckContext(model=model, engines=[Jinja2Engine(), LlamaCppEngine()],
                       fixtures=load_fixtures())
    findings = run_sanity_checks(ctx) + run_cross_engine_checks(ctx)
    def fixtures_of(f):
        return tuple(f.evidence.get("fixtures") or ((f.fixture,) if f.fixture else ()))
    return ({(f.id, f.severity, fixtures_of(f)) for f in findings},
            sorted(ctx.checks_not_evaluated), ctx.stats)


def test_every_vendored_template_has_a_sidecar_and_an_expectation():
    slugs = sorted(p.stem for p in DATA.glob("*.jinja") if not p.name.endswith(".upstream.jinja"))
    assert len(slugs) == 10
    assert set(slugs) == set(EXPECTED), "add an EXPECTED entry for every vendored template"
    for s in slugs:
        assert (DATA / f"{s}.json").exists()


# slug -> (expected finding set, expected checks_not_evaluated)
#
# Recurring shapes, stated once here rather than ten times below:
#
#   * `typed_content` (extended tier) supplies content as a list of text parts.
#     A template that concatenates `message['content']` into a string raises
#     under jinja2 -- S003 INFO, plus a one-sided X002 INFO where llama.cpp's
#     normaliser (alone, or composed with its runtime defaults) accounts for
#     the whole of what llama.cpp rendered. A template that walks the list
#     itself renders under both engines but joins the parts with no separator
#     ("Hellothere") where llama.cpp's normaliser joined them with "\n"
#     ("Hello\nthere") -- X001 INFO. That INFO (rather than X004 WARN) is
#     ruling R7: run_cross_engine_checks tests the normaliser explanation
#     before the whitespace-only test, because the cause of a divergence
#     outranks its magnitude.
#   * Every X001/X002 INFO below is confirmed, not assumed: the check
#     re-renders under jinja2 with the typed content pre-flattened the way
#     llama.cpp's normaliser does, and only downgrades to INFO if that
#     reproduces llama.cpp's output byte for byte
#     (cross_engine._explained_by_normaliser). A bare "normalized" flag is not
#     enough. X001 and X002 walk the identical ladder --
#     cross_engine._explain, normaliser then runtime defaults then both -- so
#     a divergence is graded by its cause and not by whether jinja2 limped
#     through the un-normalised input or raised on it (ruling R13).
#   * THE `enable_thinking` FORK, which three of these ten entries are dominated
#     by. common_chat_template_direct_apply_impl (common/chat.cpp) writes
#     `{"enable_thinking", inputs.enable_thinking}` into the render context
#     unconditionally, from a generation param whose default is true. There is
#     no path through llama.cpp that leaves the variable undefined --
#     `--reasoning-budget 0` makes it *false*, not absent -- so llama.cpp
#     renders every thinking-capable template in its thinking form unless the
#     caller says otherwise. transformers injects nothing: `enable_thinking` is
#     undefined there unless the caller passes it, which is why every model card
#     tells you to. The engine mirrors llama.cpp (Task 9 ported this after the
#     conformance suite caught it against the real llama-server), so on every
#     fixture that does not set `enable_thinking` the two runtimes render
#     different prompts for the same GGUF.
#
#     Per ruling R9 that lands as X001 **INFO** with the fix in the message,
#     never ERROR and never X005: it is a runtime default, not a template
#     defect, and the author cannot remove it (`mudler`'s template already
#     defaults the variable explicitly and llama.cpp overrides it anyway). Like
#     the normaliser INFO it is confirmed, not assumed -- the check re-renders
#     under jinja2 with `enable_thinking=True` and downgrades only if that
#     reproduces llama.cpp byte for byte (cross_engine.
#     _explained_by_runtime_defaults) -- and its evidence carries
#     `"explained_by": "runtime_defaults"`, against `"normaliser"` for
#     the other class. Tool fixtures it explains stay in this X001 bucket
#     because the cause outranks the fixture. `thinking_true` and
#     `thinking_false` pin both runtimes to the same value and agree everywhere,
#     which is what keeps `engines_agreed_fixtures` non-zero on these three.
#
#     Ruling R12 generalised that explanation to every value llama.cpp supplies
#     on its own -- `enable_thinking` and `preserve_reasoning` -- so the bucket
#     is `explained_by: "runtime_defaults"` with the keys it had to add under
#     `defaults`, and ruling R10 added the composition: where a divergence has
#     both this cause *and* the normaliser's join, one re-render with the typed
#     content pre-flattened AND the defaults filled in confirms it, and the
#     finding is `explained_by: "normaliser+runtime_defaults"` rather than an
#     ERROR earned only by having two causes.
#
#   * `preserve_reasoning`, the other runtime default, is a *switch* rather than
#     a value: common_params_parse sets it to "true" for every llama.cpp CLI
#     tool whenever it was not given (common/arg.cpp:963-966), and
#     direct_apply_impl hands it -- unconditionally, with no reference to caps --
#     to jinja::caps_apply_preserve_reasoning, which expands it into
#     preserve_thinking / clear_thinking / truncate_history_thinking /
#     drop_thinking (common/jinja/caps.cpp:22-27). The engine supplies that
#     default the same ungated way (ruling R11a), so it renders what a default
#     `llama-server` renders. The transformers path has no such expansion at
#     all, so a template reading an *expanded* name diverges -- and because
#     RUNTIME_DEFAULTS carries the expansion and not just the switch (ruling
#     R12a), the confirming re-render can reproduce it and the divergence lands
#     in the same X001 INFO bucket. LuffyTheFox below is that case.
EXPECTED = {
    "HauhauCS__Gemma-4-E4B-Uncensored-HauhauCS-Aggressive": (
        {
            # X001 INFO on typed_content: the template walks the content list
            # itself --
            #   {%- for item in message['content'] -%}
            #     {%- if item['type'] == 'text' -%} ... {{- item['text'] | trim -}}
            # -- concatenating the two text parts with no separator, against
            # llama.cpp's normaliser-joined "Hello\nthere":
            #     --- jinja2
            #     +++ llama.cpp
            #     @@ -1,3 +1,4 @@
            #      <s><|turn>user
            #     -Hellothere<turn|>
            #     +Hello
            #     +there<turn|>
            #      <|turn>model
            # (The leading `<s>` is BASE_CONTEXT's placeholder bos_token, from
            # the template's `{{ bos_token }}` on line 155 -- not Gemma's <bos>,
            # which this corpus has no vocab to supply.)
            #
            # A two-cause divergence, and the reason ruling R10 exists. The diff
            # is the normaliser's join *and* the `<|think|>` system turn below:
            #     --- jinja2
            #     +++ llama.cpp
            #     -<s><|turn>user
            #     -Hellothere<turn|>
            #     +<s><|turn>system
            #     +<|think|><turn|>
            #     +<|turn>user
            #     +Hello
            #     +there<turn|>
            # Neither explanation reproduces that alone -- pre-flattening leaves
            # the think turn missing, filling the defaults leaves the parts
            # joined with no separator -- so before R10 it was reported at ERROR
            # purely for having two causes. Composing them in one re-render
            # reproduces llama.cpp byte for byte, so INFO with
            # explained_by "normaliser+runtime_defaults".
            ("X001", Severity.INFO, ("typed_content",)),
            # The enable_thinking fork, X001 INFO per ruling R9. Line 157 opens
            # a system turn for `(enable_thinking is defined and
            # enable_thinking) or tools or messages[0]['role'] in ['system',
            # 'developer']` and line 161 emits `<|think|>` inside it, so with
            # llama.cpp's default the whole prompt gains a turn that
            # transformers never renders:
            #     --- jinja2
            #     +++ llama.cpp
            #     -<s><|turn>user
            #     +<s><|turn>system
            #     +<|think|><turn|>
            #     +<|turn>user
            ("X001", Severity.INFO,
             ("user_only", "multiturn", "thinking_unset", "no_generation_prompt")),
            # Same cause, second bucket: these three already had a system turn
            # (`system_user` supplies one; the two tools fixtures get one from
            # line 157's `or tools`), so the `<|think|>` is merely *prepended*
            # inside an existing turn rather than adding one, and the character
            # diff signature differs (checks.common.collapse_by_signature).
            # `with_tools` and `tool_roundtrip` sit here rather than in an X005
            # because the cause outranks the fixture (R9).
            ("X001", Severity.INFO, ("system_user", "with_tools", "tool_roundtrip")),
            # Not reported, and worth recording because the previous revision of
            # this file did report them:
            #   - No S003: the content branches (`is string` / `is sequence`)
            #     plus tool_roundtrip's unmatched `content: null` falling
            #     through both mean nothing raises.
            #   - No S005 finding: this template genuinely never emits an EOS
            #     token -- it closes turns with `{{- '<turn|>\n' -}}` and the
            #     file contains zero occurrences of `eos_token` -- but with no
            #     vocab, S005 has no declared EOS string to look for and
            #     records the gap instead. The fact about the template is real;
            #     ggufdoctor cannot establish it from HF metadata alone.
            #   - No S007: `{%- if add_generation_prompt -%}` emits
            #     `'<|turn>model\n'`, so the flag changes the output.
        },
        NO_VOCAB_GAPS,
    ),
    "LiquidAI__LFM2.5-2.6B-GGUF": (
        {
            # X001 INFO on typed_content: `parse_content`'s iterable branch
            # accumulates text parts with
            #   {%- set _ns.result = _ns.result + ((item.get("text") or "") | string) -%}
            # -- no separator, so "Hellothere" against llama.cpp's
            # normaliser-joined "Hello\nthere":
            #     -Hellothere<|im_end|>
            #     +Hello
            #     +there<|im_end|>
            ("X001", Severity.INFO, ("typed_content",)),
            # No `preserve_reasoning` finding, unlike LuffyTheFox below, and the
            # reason is a corpus gap rather than a property of the template.
            # (The engine supplies that default here too -- ruling R11a removed
            # the caps gate, and this template's caps say it is supported
            # anyway -- so the difference is not in what the engine renders.)
            # Line 2 is `{%- set preserve_thinking = preserve_thinking |
            # default(false) -%}` and line 87
            #   {%- set keep_thinking = preserve_thinking or loop.index0 > ns.last_user_index -%}
            # so the fork is present -- but line 90 guards the block with
            #   {%- if thinking and keep_thinking -%}
            # where `thinking` comes from `message.thinking or message.reasoning
            # or message.reasoning_content`. No fixture in this corpus carries
            # reasoning content on an assistant message, so the block is skipped
            # on both engines whatever `keep_thinking` says. A fixture with an
            # assistant `reasoning_content` would expose it here too.
            # No S003: parse_content handles string, mapping and iterable
            # content, and the `{%- if message.get("content") -%}` guards keep
            # tool_roundtrip's null away from it entirely.
        },
        NO_VOCAB_GAPS,
    ),
    "LuffyTheFox__Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-V13-GGUF": (
        {
            # X001 INFO on typed_content: the `render_content` macro loops
            #   {%- for item in content %} ... {%- elif 'text' in item %}{{- item.text }}
            # with no separator -- "Hellothere" against llama.cpp's
            # "Hello\nthere".
            ("X001", Severity.INFO, ("typed_content",)),
            # X001 INFO on multiturn: the `preserve_reasoning` fork (see the
            # header), and the one finding in this corpus that ruling R11
            # uncovered -- before it, the conformance harness handed the default
            # to *both* sides, so the two engines appeared to agree here and
            # this template reported nothing but the typed_content INFO above.
            # Line 100 gates the reasoning block on
            #   {%- if (preserve_thinking is defined and preserve_thinking is true)
            #          or (loop.index0 > ns.last_query_index) %}
            #     {{- '<|im_start|>' + message.role + '\n<think>\n'
            #         + reasoning_content + '\n</think>\n\n' + content }}
            # and `preserve_thinking` is one of the four variables
            # jinja::caps_apply_preserve_reasoning sets from the
            # `preserve_reasoning` kwarg that common_params_parse defaults to
            # "true". So a default `llama-server` emits an empty reasoning block
            # for the *historical* assistant turn and transformers does not:
            #     --- jinja2
            #     +++ llama.cpp
            #      <|im_start|>assistant
            #     +<think>
            #     +
            #     +</think>
            #     +
            #      Hey!<|im_end|>
            # INFO, with `preserve_thinking` among the reported `defaults`:
            # RUNTIME_DEFAULTS carries the four variables
            # caps_apply_preserve_reasoning sets, not just the switch, so the
            # confirming re-render hands jinja2 `preserve_thinking = true` and
            # reproduces llama.cpp byte for byte (ruling R12a). Before that it
            # was an ERROR only because the re-render was given a switch jinja2
            # has no way to expand. The divergence itself is real either way --
            # the same GGUF, the same caller code, a reasoning block in one
            # runtime's history and not the other's -- and it is a runtime
            # default rather than a template defect, which is what INFO says.
            #
            # Only `multiturn` reports it: it is the only fixture with a
            # historical assistant turn that reaches line 100 with content to
            # render. `no_generation_prompt` has one too, but it is the *last*
            # message, so `loop.index0 > ns.last_query_index` already holds and
            # both engines take the reasoning branch.
            ("X001", Severity.INFO, ("multiturn",)),
            # No S003: `render_content` covers `content is string`, the
            # iterable branch, and `{%- elif content is none or content is
            # undefined %}{{- '' }}` for tool_roundtrip's null, so its
            # `raise_exception('Unexpected content type.')` branch is never
            # reached by this corpus.
        },
        NO_VOCAB_GAPS,
    ),
    "PaddlePaddle__PaddleOCR-VL-1.6-GGUF": (
        {
            # S003 INFO on tool_roundtrip: that fixture's assistant message has
            # `content: null`, so `{%- if message["content"] is string -%}` is
            # false and the else branch runs
            # `{%- for content in message["content"] -%}` over None --
            # "TypeError: 'NoneType' object is not iterable". tool_roundtrip is
            # extended tier, so INFO, never ERROR: this is an OCR model's
            # template with no tool branch at all, and it legitimately predates
            # tool-call round trips.
            ("S003", Severity.INFO, ("tool_roundtrip",)),
            # X001 INFO on typed_content: the user branch loops
            # `{%- for content in message["content"] -%}` ... `{{ content["text"] }}`
            # with no separator:
            #     --- jinja2
            #     +++ llama.cpp
            #     @@ -1,2 +1,3 @@
            #     -<|begin_of_sentence|>User: Hellothere
            #     +<|begin_of_sentence|>User: Hello
            #     +there
            #      Assistant:
            # `<|begin_of_sentence|>` is the template's own default
            # (`{%- set cls_token = "<|begin_of_sentence|>" -%}`), emitted via
            # `{{- cls_token -}}`, not a token this corpus supplied.
            ("X001", Severity.INFO, ("typed_content",)),
            # X002 ERROR on tool_roundtrip -- the S003 above, seen from the
            # cross-engine side, and it exists only because the engine got more
            # faithful. Every llama.cpp path lowers a message through
            # common_chat_msg (content is a std::string) and back out through
            # common_chat_msg::to_json_oaicompat, which emits `"content": ""`
            # when there is neither content nor content_parts, so a template
            # never sees a null there. The engine now does the same (Task 9),
            # which means llama.cpp renders this fixture where jinja2 raises,
            # and the divergence is finally reported instead of both engines
            # failing. The prompt llama.cpp produces is still wrong for the
            # conversation -- the assistant's tool call vanishes into an empty
            # turn, exactly the class documented on the HyperCLOVAX entry below
            # -- so ERROR is right: one runtime refuses the conversation and the
            # other serves a misleading prompt. Evidence carries
            # "normalized": false and no "explained_by": the whole ladder was
            # walked and none of its three rungs reproduces llama.cpp's text --
            # there is no typed content to pre-flatten on this fixture, and
            # filling in llama.cpp's runtime defaults leaves the `for content
            # in message["content"]` loop iterating None exactly as before --
            # so no INFO downgrade applies.
            ("X002", Severity.ERROR, ("tool_roundtrip",)),
            # X001 ERROR on no_generation_prompt: direct_apply_impl writes the
            # key only when the flag is on (`if (inputs.add_generation_prompt)
            # inp["add_generation_prompt"] = true;`), so under llama.cpp the
            # variable is *absent* when generation prompting is off, never
            # false. This template's first two lines are
            #   {%- if not add_generation_prompt is defined -%}
            #     {%- set add_generation_prompt = true -%}
            # so llama.cpp defaults it back to true and appends the assistant
            # opener anyway, while transformers -- which passes
            # add_generation_prompt=False through -- does not:
            #     --- jinja2
            #     +++ llama.cpp
            #     -Hello!</s>
            #     +Hello!</s>Assistant:
            # A genuine fork: llama.cpp cannot render this template without a
            # generation prompt at all. Caught by the conformance suite against
            # the real llama-server, which does exactly this.
            ("X001", Severity.ERROR, ("no_generation_prompt",)),
        },
        NO_VOCAB_GAPS,
    ),
    "antirez__deepseek-v4-gguf": (
        {
            # S003 INFO on typed_content: the user branch is
            #   {{- '<｜User｜>' + (message['content'] or '') -}}
            # A non-empty list is truthy, so `or ''` passes the list straight
            # through and the `+` raises "TypeError: can only concatenate str
            # (not "list") to str". Extended tier, so INFO. tool_roundtrip does
            # NOT fail: the same `or ''` idiom does neutralise `content: null`.
            ("S003", Severity.INFO, ("typed_content",)),
            # X002 INFO on typed_content: one-sided, because only llama.cpp
            # produced output at all -- its normaliser joined the parts to
            # "Hello\nthere" first, so the same `+` saw a string.
            #
            # Two causes, exactly like the Gemma-4 and mudler X001 entries: the
            # normaliser's join is not the whole explanation, because
            # llama.cpp's output also carries the enable_thinking `<think>`
            # described below. Pre-flattening alone leaves jinja2 emitting
            # `</think>`; filling the runtime defaults alone leaves the `+`
            # looking at a list and still raising "TypeError: can only
            # concatenate str (not "list") to str". Composed in one re-render
            # they reproduce llama.cpp byte for byte, so INFO with
            # explained_by "normaliser+runtime_defaults" and all six
            # RUNTIME_DEFAULTS keys under `defaults`.
            #
            # This entry is why ruling R13 exists. _x002 used to try only the
            # normaliser rung, so this landed at ERROR while the structurally
            # identical two-cause divergences on Gemma-4 and mudler -- where
            # jinja2 happened to *limp through* the un-normalised input instead
            # of raising on it -- were INFO. Same template defect (none), same
            # two runtime causes, graded by which engine raised. The one-sided
            # fact is still in the message: jinja2 does not merely differ here,
            # it refuses the original input.
            ("X002", Severity.INFO, ("typed_content",)),
            # The enable_thinking fork, X001 INFO per ruling R9, in its sharpest
            # form. Lines 4-9 read
            #   {%- if not thinking is defined -%}
            #     {%- if enable_thinking is defined -%}{%- set thinking = enable_thinking -%}
            #     {%- else -%}{%- set thinking = false -%}
            # so the template's own fallback is *no thinking*, and llama.cpp's
            # unconditional `enable_thinking` overrides it. Line 91 then emits
            # `<think>` where transformers emits `</think>`:
            #     -<s><｜User｜>Hello<｜Assistant｜></think>
            #     +<s><｜User｜>Hello<｜Assistant｜><think>
            # One token, opposite meaning: llama.cpp opens a reasoning block the
            # transformers prompt closes immediately. All six fixtures collapse
            # into one bucket -- the `<think>`/`</think>` swap is the whole diff
            # everywhere, including the two tools fixtures, which therefore do
            # not become an X005 (the cause outranks the fixture).
            ("X001", Severity.INFO, ("user_only", "system_user", "multiturn",
                                     "with_tools", "thinking_unset", "tool_roundtrip")),
            # No S005/S004 findings (and none possible here anyway): every
            # special token this template emits -- `<｜User｜>`,
            # `<｜Assistant｜>`, `<｜end▁of▁sentence｜>` -- uses the fullwidth
            # vertical line U+FF5C, which sanity.SPECIAL_TOKEN_RE's ASCII
            # `<\|...\|>` shape does not match. It does emit a literal
            # end-of-sentence token on every assistant turn, so unlike the
            # Gemma-4 entry there is no latent S005 fact hiding behind the
            # missing vocab.
        },
        NO_VOCAB_GAPS,
    ),
    "legraphista__glm-4-9b-chat-IMat-GGUF": (
        {
            # This repo's GGUF chat-template field is not a template at all: it
            # is the eight-byte literal `ChatGLM4`, i.e. llama.cpp's legacy
            # *named* built-in template, published where a Jinja template
            # belongs. (The real GLM-4 Jinja template is vendored alongside as
            # the .upstream.jinja, from THUDM/glm-4-9b-chat.) It compiles as a
            # constant-output template, so S002 stays silent, and it renders
            # "ChatGLM4" -- non-empty -- so S008 does too.
            #
            # S007 WARN, and WARN rather than INFO is the whole point: a
            # constant cannot respond to add_generation_prompt, so
            # `on.text == off.text`, and "ChatGLM4" ends with none of
            # sanity._ASSISTANT_OPEN_MARKERS, so nothing suggests the assistant
            # turn is opened by other means. Contrast the INFO S007 on
            # Mistral/Llama-2 in tests/test_checks_sanity.py, whose output ends
            # in "[/INST]".
            ("S007", Severity.WARN, ("user_only",)),
            # The far worse property of this "template" -- that it can never
            # emit an EOS token, so the prompt would never terminate a turn --
            # is exactly what S005 exists to catch, and it is in
            # checks_not_evaluated rather than reported, because with no vocab
            # there is no declared EOS string to look for. The most defective
            # entry in this corpus is the one the missing vocab costs us most
            # on; that is the honest state of a metadata-only fetch.
            #
            # No X findings: both engines render the same constant on all ten
            # fixtures, so engines_agreed_fixtures is 10 -- the only full
            # agreement in this corpus, and only because the "template" ignores
            # its input entirely.
        },
        NO_VOCAB_GAPS,
    ),
    "mudler__Laguna-XS-2.1-APEX-GGUF": (
        {
            # X001 INFO on typed_content, and the most interesting one here.
            # The main loop opens with
            #   {%- set content = message.content if message.content is string else "" -%}
            # so under jinja2 a list content fails the `is string` test and is
            # replaced by the empty string: jinja2 silently drops the user's
            # message entirely. llama.cpp's normaliser had already joined the
            # parts into a string, so `is string` holds there:
            #     --- jinja2
            #     +++ llama.cpp
            #     @@ -1,3 +1,4 @@
            #      〈|EOS|〉<system>You are a helpful, ...</system>
            #     -<user></user>
            #     +<user>Hello
            #     +there</user>
            #      <assistant></think>
            # The second two-cause divergence (ruling R10). Not whitespace-only
            # -- jinja2 emits no content whatsoever -- and the diff carries the
            # enable_thinking `<think>` (below) on top of the dropped content:
            #     -<user></user>
            #     -<assistant></think>
            #     +<user>Hello
            #     +there</user>
            #     +<assistant><think>
            # Pre-flattening alone leaves the `</think>`; filling the defaults
            # alone leaves jinja2 still dropping the list content via
            # `message.content if message.content is string else ""`. Composed
            # in one re-render they reproduce llama.cpp exactly, so INFO with
            # explained_by "normaliser+runtime_defaults".
            ("X001", Severity.INFO, ("typed_content",)),
            # The enable_thinking fork, X001 INFO per ruling R9. Line 4 is
            #   {%- set enable_thinking = enable_thinking | default(false) -%}
            # -- an explicit template-side default of *off*, which llama.cpp's
            # unconditional true overrides, which is precisely why R9 calls this
            # a runtime default and not a template defect: the author already
            # said what they wanted and llama.cpp overrode it. Line 88 then
            # opens `<think>` where transformers closes `</think>`:
            #     -<assistant></think>
            #     +<assistant><think>
            # `with_tools` shares that exact diff, so it collapses in here
            # rather than becoming an X005.
            ("X001", Severity.INFO, ("user_only", "system_user", "with_tools", "thinking_unset")),
            # Same cause, separate bucket: these two contain a past assistant
            # message, where line 54's `{%- if enable_thinking -%}{{- '<think>'
            # + reasoning_content + '</think>' -}}` adds an empty reasoning
            # block to the *history* too, so the character diff signature
            # differs:
            #     -<assistant></think>Hey!</assistant>
            #     +<assistant><think></think>Hey!</assistant>
            ("X001", Severity.INFO, ("multiturn", "tool_roundtrip")),
            # And `no_generation_prompt` again separately: it has the history
            # block above but no trailing generation prompt, so its diff is the
            # history half alone.
            ("X001", Severity.INFO, ("no_generation_prompt",)),
            # No S003: `content is string else ""` plus the `{%- if content -%}`
            # guard mean `content: null` and list content both render rather
            # than raise -- the same defensiveness that costs it the X001 above.
            # No S004 possible: its tokens are the CJK-bracketed `〈|EOS|〉`
            # (U+3008 LEFT ANGLE BRACKET / U+3009 RIGHT ANGLE BRACKET -- not
            # the mathematical U+2329/U+232A they resemble) and plain XML-ish tags
            # (`<system>`, `<user>`, `<assistant>`), none matching the ASCII
            # `<|...|>` shape.
        },
        NO_VOCAB_GAPS,
    ),
    "ornith-ai__Ornith-1.0-9B-GGUF": (
        {
            # X001 INFO on typed_content: the `render_content` macro's
            #   {%- for item in content %} ... {%- elif 'text' in item %}{{- item.text }}
            # concatenates the text parts with no separator -- "Hellothere"
            # against llama.cpp's normaliser-joined "Hello\nthere".
            ("X001", Severity.INFO, ("typed_content",)),
            # No S003: same macro coverage as the LuffyTheFox entry (this
            # template and that one share the Qwen-family render_content
            # macro), including the `content is none or content is undefined`
            # branch that absorbs tool_roundtrip's null.
        },
        NO_VOCAB_GAPS,
    ),
    "rippertnt__HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF": (
        {
            # The entire template is one unguarded concatenation:
            #   {{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}
            # which is responsible for all four findings below.
            #
            # S003 INFO on tool_roundtrip: that `+ message['content'] +` meets
            # the assistant message's `content: null` and raises "TypeError:
            # can only concatenate str (not "NoneType") to str". Extended tier,
            # so INFO.
            ("S003", Severity.INFO, ("tool_roundtrip",)),
            # S003 INFO on typed_content: the same `+` with list content --
            # "TypeError: can only concatenate str (not "list") to str".
            # Reported separately rather than collapsed with the line above
            # because the two render errors have different signatures
            # ("NoneType" vs "list"), which is what
            # checks.common.collapse_by_signature keys on.
            ("S003", Severity.INFO, ("typed_content",)),
            # X002 ERROR on tool_roundtrip -- a real engine divergence,
            # recorded rather than narrowed away. jinja2 (the transformers
            # path) raises the "NoneType" TypeError above; llama.cpp's minja
            # coerces the null to an empty string and renders happily:
            #   '<|im_start|>system\nBe brief.<|im_end|>\n'
            #   '<|im_start|>user\nWeather in Paris?<|im_end|>\n'
            #   '<|im_start|>assistant\n<|im_end|>\n'          <-- empty turn
            #   '<|im_start|>tool\n{"temp_c": 18}<|im_end|>\n'
            #   '<|im_start|>assistant\n'
            # So llama.cpp silently drops the assistant's tool call and feeds
            # the model an empty assistant turn followed by a tool result for a
            # call that was never shown, while transformers refuses the
            # conversation outright. ERROR is right: the runtimes disagree
            # about a conversation one of them will serve, and llama.cpp's
            # answer is wrong. This is the `tool_roundtrip` divergence class the
            # engine spike documented (assistant `content: null`), in its
            # concatenating form -- because this template concatenates rather
            # than prints, jinja2 raises instead of printing "None", which
            # turns what would be a two-sided X001/X005 into a one-sided X002.
            # Evidence carries "normalized": False and no "explained_by" --
            # none of the ladder's three rungs makes jinja2 reproduce
            # llama.cpp's text here: this fixture has no typed content to
            # pre-flatten, and llama.cpp's runtime defaults leave the `+
            # message['content']` looking at the same null. So neither cause is
            # the explanation and no INFO downgrade applies.
            ("X002", Severity.ERROR, ("tool_roundtrip",)),
            # X002 INFO on typed_content: same one-sided shape, but here the
            # normaliser IS the whole explanation -- it joined the text parts to
            # "Hello\nthere" so llama.cpp's `+` saw a string, and the
            # pre-flattened jinja2 re-render reproduces llama.cpp's output
            # exactly. INFO, not ERROR.
            ("X002", Severity.INFO, ("typed_content",)),
            # Not reported, but true of the repo and worth recording: this GGUF
            # declares eos_token `<|endofturn|>` while its template closes every
            # turn with `<|im_end|>`. S005 is exactly the check for that, and it
            # is in checks_not_evaluated because there is no vocab to resolve a
            # declared EOS from. No S007 either: the trailing
            # `{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}`
            # genuinely changes the output.
        },
        NO_VOCAB_GAPS,
    ),
    "unsloth__Qwen3-Coder-30B-A3B-Instruct-GGUF": (
        {
            # S003 INFO on typed_content: the user/system/assistant branch is
            #   {{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>' + '\n' }}
            # -- string concatenation, so list content raises "TypeError: can
            # only concatenate str (not "list") to str". Extended tier, so INFO.
            # tool_roundtrip does NOT fail here, unlike the HyperCLOVAX entry
            # above, because the tool_calls branch guards its content with
            #   {%- if message.content is defined and message.content is string
            #        and message.content | trim | length > 0 %}
            # so `content: null` never reaches a `+`.
            ("S003", Severity.INFO, ("typed_content",)),
            # X002 INFO on typed_content: one-sided (jinja2 raised, llama.cpp
            # rendered), explained by the normaliser's join and confirmed by the
            # pre-flattened re-render.
            ("X002", Severity.INFO, ("typed_content",)),
        },
        NO_VOCAB_GAPS,
    ),
}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_complete_finding_set(slug):
    found, not_evaluated, stats = run(slug)
    expected_findings, expected_not_evaluated = EXPECTED[slug]
    assert found == expected_findings
    assert not_evaluated == expected_not_evaluated
    # Kept per ruling R6: no template in this corpus agrees on zero fixtures,
    # so this stays a real assertion rather than a tautology -- it would catch
    # an engine or corpus change that made the two engines stop agreeing
    # anywhere. The margin is much thinner than it was: the enable_thinking fork
    # (see the EXPECTED header) took the three thinking templates down to 2, 2
    # and 3 agreeing fixtures out of 10, and the two that sit at 2 agree only on
    # `thinking_true` and `thinking_false`, the fixtures that pin the variable
    # on both sides. Rulings R9, R10 and R12 changed how those divergences are
    # *reported*, not whether the engines agree, so they leave this number
    # alone; ruling R11 does move it, taking LuffyTheFox from 9 to 8.
    # (R11a's removal of the caps gate moved nothing further: every template
    # here that reads a preserve_reasoning variable already had caps saying so.)
    assert stats["engines_agreed_fixtures"] >= 1, "both engines must agree on at least one fixture"
