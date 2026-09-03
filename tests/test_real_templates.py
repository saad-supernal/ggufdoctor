"""Complete S + X finding sets on ten real, vendored templates.

Every expected finding below is a true positive with a stated reason. If a
change to the checks alters any set, this test fails loudly -- that is the
point. Never narrow an assertion to a single id to make it pass.
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


def load(slug):
    tpl = (DATA / f"{slug}.jinja").read_text(encoding="utf-8")
    side = json.loads((DATA / f"{slug}.json").read_text(encoding="utf-8"))
    return tpl, side


def run(slug):
    tpl, side = load(slug)
    tokens = [side["bos_token"] or "<s>", side["eos_token"] or "</s>"]
    model = GgufModel(source_id=side["repo"], architecture=side["architecture"],
                      chat_template=tpl, tokens=tokens, bos_token_id=0, eos_token_id=1,
                      add_bos_token=None)  # HF metadata does not carry add_bos_token
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
# Two facts about `run()` above apply to every entry, so they are stated once
# here instead of ten times below:
#
#   * S006 is in `checks_not_evaluated` for all ten. `run()` passes
#     add_bos_token=None because the Hugging Face `gguf` metadata block the
#     templates were fetched from carries bos_token/eos_token *strings* but no
#     add_bos_token flag, so sanity.s006_double_bos cannot even tell whether
#     it applies and records the coverage gap. That is the honest state of
#     this corpus, not a template property -- do not "fix" it by inventing a
#     flag value.
#
#   * The vocab `run()` builds is exactly two entries -- [bos_token,
#     eos_token] from the sidecar -- because HF metadata carries no vocab.
#     S004 asks whether a template emits `<|...|>` tokens absent from *this
#     file's* vocab, so against a two-token vocab it fires wherever a
#     template emits any other special token, and it fires at ERROR because
#     that is what the check says about the (template, vocab) pair it was
#     handed. Each S004 line below therefore names the exact tokens the check
#     confirmed by rendering, and says which of them are artefacts of this
#     two-token vocab versus a real disagreement with the repo's own declared
#     bos/eos. S004 only reports tokens it observed in real rendered output,
#     never every `<|...|>` in the source -- see the PaddleOCR entry.
EXPECTED = {
    "HauhauCS__Gemma-4-E4B-Uncensored-HauhauCS-Aggressive": (
        {
            # S004: the two tokens listed are the ones this template was
            # observed to emit and that are neither of the declared
            # bos/eos (<bos>, <eos>):
            #   - `<|"|>` from the tool-schema quoting, e.g.
            #     `description:<|"|>{{ value['description'] }}<|"|>`, emitted
            #     on the with_tools/tool_roundtrip fixtures;
            #   - `<|think|>` from `{{- '<|think|>' -}}` inside
            #     `{%- if enable_thinking is defined and enable_thinking -%}`,
            #     emitted on the thinking_true fixture.
            # Both are almost certainly present in the real Gemma-4 vocab;
            # against this corpus's two-token vocab they are absent, which is
            # exactly what the check reports.
            ("S004", Severity.ERROR, ()),
            # S005: the declared eos_token is `<eos>` and this template never
            # emits it. It closes every turn with the literal `{{- '<turn|>\n' -}}`
            # and contains no `eos_token` reference at all (zero occurrences of
            # the string in the file). A genuine metadata/template disagreement,
            # independent of the synthetic vocab.
            ("S005", Severity.WARN, ()),
            # X004: on typed_content the template walks the content list itself --
            # `{%- for item in message['content'] -%}` ... `{{- item['text'] | trim -}}`
            # -- concatenating the two text parts with no separator ("Hellothere"),
            # while llama.cpp's message normaliser had already joined them with
            # "\n" into a single string before rendering ("Hello\nthere"). The
            # renders differ only in that newline, so X004 (whitespace-only)
            # rather than X001. `_whitespace_only` is tested before the
            # normaliser-explained branch in run_cross_engine_checks, which is
            # why this lands at X004 WARN and not X001 INFO.
            ("X004", Severity.WARN, ("typed_content",)),
        },
        ["S006"],
    ),
    "LiquidAI__LFM2.5-2.6B-GGUF": (
        {
            # S004: emits `<|im_start|>` (from
            # `{{- "<|im_start|>" + message.role + "\n" -}}`) plus
            # `<|tool_call_start|>` and `<|tool_call_end|>` (from
            # render_tool_calls' `{{- "<|tool_call_start|>[" + ... +
            # "]<|tool_call_end|>" -}}`, reached on tool_roundtrip). The
            # declared eos `<|im_end|>` is in vocab and is correctly not
            # reported. All three are artefacts of the two-token vocab.
            ("S004", Severity.ERROR, ()),
            # X004: parse_content's iterable branch accumulates text parts with
            # `{%- set _ns.result = _ns.result + ((item.get("text") or "") | string) -%}`
            # -- no separator, so "Hellothere" -- against llama.cpp's
            # normaliser-joined "Hello\nthere". Whitespace-only, same shape as
            # the Gemma-4 entry above.
            ("X004", Severity.WARN, ("typed_content",)),
        },
        ["S006"],
    ),
    "LuffyTheFox__Qwen3.6-35B-A3B-Uncensored-Genesis-Hermes-V13-GGUF": (
        {
            # S004: `<|im_start|>` only, from
            # `{{- '<|im_start|>' + message.role + '\n' + content + '<|im_end|>' + '\n' }}`.
            # The declared eos `<|im_end|>` is in vocab and correctly unreported.
            # An artefact of the two-token vocab.
            ("S004", Severity.ERROR, ()),
            # X004: the template's `render_content` macro loops
            # `{%- for item in content %}` ... `{%- elif 'text' in item %}{{- item.text }}`
            # with no separator, giving "Hellothere" against llama.cpp's
            # normaliser-joined "Hello\nthere". Whitespace-only.
            ("X004", Severity.WARN, ("typed_content",)),
        },
        ["S006"],
    ),
    "PaddlePaddle__PaddleOCR-VL-1.6-GGUF": (
        {
            # S003 INFO on tool_roundtrip: that fixture's assistant message has
            # `content: null`, so `{%- if message["content"] is string -%}` is
            # false and the else branch runs `{%- for content in message["content"] -%}`
            # over None -- "TypeError: 'NoneType' object is not iterable".
            # tool_roundtrip is extended tier, so INFO, never ERROR: this
            # template legitimately predates tool-call round trips (it is an OCR
            # model's template and has no tool branch at all).
            ("S003", Severity.INFO, ("tool_roundtrip",)),
            # S004: `<|begin_of_sentence|>` only. The template supplies it as its
            # own default -- `{%- set cls_token = "<|begin_of_sentence|>" -%}` --
            # and emits it via `{{- cls_token -}}`, while the sidecar declares
            # bos_token `<s>`. Note the template *text* also contains
            # `<|IMAGE_START|><|IMAGE_PLACEHOLDER|><|IMAGE_END|>`, which S004
            # does NOT report: no fixture supplies an image content part, so the
            # check never observed those in rendered output and refuses to guess.
            ("S004", Severity.ERROR, ()),
            # X004: the user branch loops `{%- for content in message["content"] -%}`
            # ... `{{ content["text"] }}` with no separator -- "User: Hellothere"
            # -- against llama.cpp's normaliser-joined "User: Hello\nthere".
            # Whitespace-only.
            ("X004", Severity.WARN, ("typed_content",)),
        },
        ["S006"],
    ),
    "antirez__deepseek-v4-gguf": (
        {
            # S003 INFO on typed_content: the user branch is
            # `{{- '<｜User｜>' + (message['content'] or '') -}}`. A non-empty
            # list is truthy, so `or ''` passes the list straight through and the
            # `+` raises "TypeError: can only concatenate str (not "list") to
            # str". Extended tier, so INFO. tool_roundtrip renders fine here
            # because the same `or ''` idiom does neutralise `content: null`.
            ("S003", Severity.INFO, ("typed_content",)),
            # X002 INFO on typed_content: llama.cpp's normaliser joined the two
            # text parts to "Hello\nthere" before rendering, so its `+` sees a
            # string and succeeds where jinja2's raises. run_cross_engine_checks
            # re-rendered under jinja2 with the content pre-flattened the same
            # way and reproduced llama.cpp's output byte for byte, which is what
            # downgrades this to INFO -- the normaliser is demonstrably the whole
            # explanation, not an unrelated engine difference.
            ("X002", Severity.INFO, ("typed_content",)),
            # No S004: every special token this template emits -- `<｜User｜>`,
            # `<｜Assistant｜>`, `<｜end▁of▁sentence｜>` -- uses the fullwidth
            # vertical line U+FF5C, which SPECIAL_TOKEN_RE (ASCII `<\|...\|>`)
            # does not match, so there are no candidates to confirm.
            # No S005: the template emits the literal `<｜end▁of▁sentence｜>` on
            # every assistant turn, which is exactly the declared eos_token.
        },
        ["S006"],
    ),
    "legraphista__glm-4-9b-chat-IMat-GGUF": (
        {
            # This repo's GGUF chat-template field is not a template at all: it
            # is the eight-byte literal string `ChatGLM4`, i.e. llama.cpp's
            # legacy *named* built-in template, published where a Jinja template
            # belongs. (The real GLM-4 Jinja template is vendored alongside as
            # the .upstream.jinja, fetched from THUDM/glm-4-9b-chat.) It
            # compiles as a constant-output Jinja template, which is why S002
            # and S008 stay silent -- it renders "ChatGLM4", non-empty -- and
            # the two findings below are the ones that catch it.
            #
            # S005: rendering multiturn produces "ChatGLM4", which does not
            # contain the declared eos `<|endoftext|>`. True and serious: this
            # prompt would never terminate a turn.
            ("S005", Severity.WARN, ()),
            # S007 WARN (not INFO): output is a constant, so
            # add_generation_prompt=True and False render identically, and
            # "ChatGLM4" ends with none of _ASSISTANT_OPEN_MARKERS, so nothing
            # suggests the assistant turn is opened by other means. WARN is the
            # correct severity here, unlike the INFO S007 on Mistral/Llama-2
            # whose output ends in "[/INST]".
            #
            # No S004: the string contains no `<|...|>` at all.
            ("S007", Severity.WARN, ("user_only",)),
            # No X findings: both engines render the same constant on all ten
            # fixtures, so engines_agreed_fixtures is 10 -- the only entry in
            # this corpus with full agreement, and only because the "template"
            # ignores its input entirely.
        },
        ["S006"],
    ),
    "mudler__Laguna-XS-2.1-APEX-GGUF": (
        {
            # X001 INFO on typed_content -- the normaliser-explained variant, not
            # the ERROR one. The main loop opens with
            # `{%- set content = message.content if message.content is string else "" -%}`,
            # so under jinja2 a list content fails the `is string` test and is
            # replaced by the empty string: jinja2 renders `<user></user>`, i.e.
            # it silently drops the user's message. llama.cpp's normaliser had
            # already joined the parts into a string, so `is string` holds there
            # and it renders `<user>Hello\nthere</user>`. The diff:
            #     --- jinja2
            #     +++ llama.cpp
            #     @@ -1,3 +1,4 @@
            #      〈|EOS|〉<system>You are a helpful, ...</system>
            #     -<user></user>
            #     +<user>Hello
            #     +there</user>
            #      <assistant></think>
            # Not whitespace-only (jinja2 emits no content whatsoever), so it
            # does not collapse into X004; re-rendering under jinja2 with the
            # content pre-flattened reproduces llama.cpp's text exactly, which
            # is what earns the INFO downgrade.
            ("X001", Severity.INFO, ("typed_content",)),
            # No S004: this template's special tokens use the fullwidth
            # `〈|EOS|〉` (U+2329/U+232A angle brackets) and plain XML-ish tags
            # (`<system>`, `<user>`, `<assistant>`), none of which match
            # SPECIAL_TOKEN_RE's ASCII `<|...|>` shape.
            # No S005: the template's first act is `{{- "〈|EOS|〉" -}}`, and this
            # repo declares that same string as both bos_token and eos_token, so
            # the declared eos is present in every render.
            # No S003: `content is string else ""` and the `{%- if content -%}`
            # guard mean `content: null` and list content both render rather than
            # raise -- the same defensiveness that costs it the X001 above.
        },
        ["S006"],
    ),
    "ornith-ai__Ornith-1.0-9B-GGUF": (
        {
            # S004: `<|im_start|>` only, from
            # `{{- '<|im_start|>' + message.role + '\n' + content + '<|im_end|>' + '\n' }}`;
            # the declared eos `<|im_end|>` is in vocab and correctly unreported.
            # An artefact of the two-token vocab. (This sidecar's bos_token is
            # null, so `run()` substitutes the `<s>` placeholder for vocab slot 0.)
            ("S004", Severity.ERROR, ()),
            # X004: the `render_content` macro loops `{%- for item in content %}`
            # ... `{%- elif 'text' in item %}{{- item.text }}` with no separator,
            # giving "Hellothere" against llama.cpp's normaliser-joined
            # "Hello\nthere". Whitespace-only.
            ("X004", Severity.WARN, ("typed_content",)),
            # No S003: `render_content` handles every shape this corpus offers --
            # `{%- if content is string %}`, the iterable branch, and
            # `{%- elif content is none or content is undefined %}{{- '' }}` for
            # tool_roundtrip's `content: null` -- so nothing raises. Its
            # `raise_exception('Unexpected content type.')` branch is never reached.
        },
        ["S006"],
    ),
    "rippertnt__HyperCLOVAX-SEED-Text-Instruct-1.5B-Q4_K_M-GGUF": (
        {
            # The whole template is one unguarded concatenation:
            #   {{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}
            # which explains four of the five findings below.
            #
            # S003 INFO on tool_roundtrip: that fixture's assistant message has
            # `content: null`, so the `+ message['content'] +` above raises
            # "TypeError: can only concatenate str (not "NoneType") to str".
            # Extended tier, so INFO.
            ("S003", Severity.INFO, ("tool_roundtrip",)),
            # S003 INFO on typed_content: the same `+` with a list content --
            # "TypeError: can only concatenate str (not "list") to str". Reported
            # separately from the line above rather than collapsed, because the
            # two render errors have different signatures ("NoneType" vs "list").
            ("S003", Severity.INFO, ("typed_content",)),
            # S004: `<|im_start|>` AND `<|im_end|>`. `<|im_start|>` is the usual
            # two-token-vocab artefact, but `<|im_end|>` is not: this repo
            # declares eos_token `<|endofturn|>`, so the token the template
            # actually uses to close turns is genuinely not the declared one --
            # the same underlying disagreement S005 reports from the other side.
            ("S004", Severity.ERROR, ()),
            # S005: the declared eos `<|endofturn|>` never appears in the
            # multiturn render; the template emits `<|im_end|>` instead. Real
            # metadata/template disagreement, independent of the synthetic vocab.
            ("S005", Severity.WARN, ()),
            # X002 ERROR on tool_roundtrip -- a real, honest engine divergence,
            # recorded rather than narrowed away. jinja2 (the transformers path)
            # raises the "NoneType" TypeError above; llama.cpp's minja coerces
            # the null to an empty string and renders happily:
            #   '<|im_start|>system\nBe brief.<|im_end|>\n'
            #   '<|im_start|>user\nWeather in Paris?<|im_end|>\n'
            #   '<|im_start|>assistant\n<|im_end|>\n'          <-- empty turn
            #   '<|im_start|>tool\n{"temp_c": 18}<|im_end|>\n'
            #   '<|im_start|>assistant\n'
            # So llama.cpp silently drops the assistant's tool call and feeds
            # the model an empty assistant turn followed by a tool result for a
            # call that was never shown -- while transformers refuses outright.
            # ERROR is right: the two runtimes disagree about a conversation one
            # of them will happily serve, and llama.cpp's answer is wrong.
            # This is the `tool_roundtrip` divergence class the engine spike
            # documented (assistant `content: null`), in its concatenating form.
            # Not X001/X005: only one engine produced output at all, so it is a
            # one-sided X002, and llama.cpp's normaliser is demonstrably not the
            # explanation (evidence "normalized": False -- pre-flattening typed
            # content does not make jinja2 reproduce llama.cpp's text here).
            ("X002", Severity.ERROR, ("tool_roundtrip",)),
            # X002 INFO on typed_content: same one-sided shape, but here the
            # normaliser IS the whole explanation -- it joined the text parts to
            # "Hello\nthere" so llama.cpp's `+` saw a string, and re-rendering
            # under jinja2 with the content pre-flattened reproduces llama.cpp's
            # output exactly. INFO, not ERROR.
            ("X002", Severity.INFO, ("typed_content",)),
            # No S007: `{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}`
            # genuinely changes the output.
        },
        ["S006"],
    ),
    "unsloth__Qwen3-Coder-30B-A3B-Instruct-GGUF": (
        {
            # S003 INFO on typed_content: the user/system/assistant branch is
            # `{{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>' + '\n' }}`
            # -- string concatenation, so a list content raises "TypeError: can
            # only concatenate str (not "list") to str". Extended tier, so INFO.
            # tool_roundtrip does NOT fail here: the tool_calls branch guards its
            # content with
            # `{%- if message.content is defined and message.content is string and message.content | trim | length > 0 %}`,
            # so `content: null` never reaches a `+`.
            ("S003", Severity.INFO, ("typed_content",)),
            # S004: `<|im_start|>` only; the declared eos `<|im_end|>` is in
            # vocab and correctly unreported. An artefact of the two-token vocab.
            # (This sidecar's bos_token is null, so `run()` substitutes `<s>`.)
            ("S004", Severity.ERROR, ()),
            # X002 INFO on typed_content: llama.cpp's normaliser joined the text
            # parts to "Hello\nthere" before rendering, so its `+` saw a string
            # where jinja2's saw a list. Confirmed by re-rendering under jinja2
            # with the content pre-flattened, which reproduces llama.cpp's output
            # byte for byte -- hence INFO.
            ("X002", Severity.INFO, ("typed_content",)),
            # No S005: multiturn's assistant turn emits `<|im_end|>`, the declared
            # eos_token.
        },
        ["S006"],
    ),
}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_complete_finding_set(slug):
    found, not_evaluated, stats = run(slug)
    expected_findings, expected_not_evaluated = EXPECTED[slug]
    assert found == expected_findings
    assert not_evaluated == expected_not_evaluated
    assert stats["engines_agreed_fixtures"] >= 1, "both engines must agree on at least one fixture"
