from ggufdoctor.checks.sanity import run_sanity_checks, s003_render_error
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity


def ctx(**kw):
    model = GgufModel(source_id="t", architecture=kw.pop("arch", "llama"), **kw)
    return CheckContext(model=model, engines=[Jinja2Engine()],
                        fixtures=load_fixtures())


def ids(findings):
    return {f.id for f in findings}


CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}"
            "<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")


def test_s001_chat_arch_without_template():
    assert "S001" in ids(run_sanity_checks(ctx(chat_template=None)))


def test_s001_not_raised_for_non_chat_arch():
    assert "S001" not in ids(run_sanity_checks(ctx(arch="bert", chat_template=None)))


def test_s002_uncompilable_template():
    assert "S002" in ids(run_sanity_checks(ctx(chat_template="{% if %}")))


def test_s003_render_error_on_fixture():
    f = run_sanity_checks(ctx(chat_template="{{ raise_exception('no') }}"))
    assert "S003" in ids(f)


def test_s004_flags_token_absent_from_vocab():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>"]))
    assert "S004" in ids(f)
    finding = next(x for x in f if x.id == "S004")
    assert "<|im_end|>" in finding.evidence["missing"]


def test_s004_silent_when_all_tokens_present():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL,
                              tokens=["<|im_start|>", "<|im_end|>"]))
    assert "S004" not in ids(f)


def test_s004_skipped_when_vocab_unavailable():
    assert "S004" not in ids(run_sanity_checks(ctx(chat_template=CHAT_TPL, tokens=[])))


def test_s006_double_bos():
    # bos_token_id/tokens must be supplied: S006 now renders with the
    # model's *real* BOS string and checks the actual output, so it has
    # nothing to check against without a real token to look for.
    f = run_sanity_checks(ctx(chat_template="{{ bos_token }}hi", add_bos_token=True,
                              tokens=["<s>"], bos_token_id=0))
    assert "S006" in ids(f)


def test_s007_generation_prompt_noop():
    f = run_sanity_checks(ctx(chat_template="{% for m in messages %}{{ m['content'] }}{% endfor %}"))
    assert "S007" in ids(f)


def test_s008_empty_render():
    assert "S008" in ids(run_sanity_checks(ctx(chat_template="{# nothing #}")))


def test_clean_template_produces_no_findings():
    f = run_sanity_checks(ctx(chat_template=CHAT_TPL,
                              tokens=["<|im_start|>", "<|im_end|>"]))
    assert f == []


# --- Regressions: render-based S004/S005/S006, and S003/S008 collapsing ---

# The real Mistral-7B-Instruct-v0.2 default chat template (pre tool-calling
# era). It emits EOS only through `{{ eos_token }}`, never as a literal.
MISTRAL_V02_TPL = (
    "{{ bos_token }}{% for message in messages %}"
    "{% if (message['role'] == 'user') != (loop.index0 % 2 == 0) %}"
    "{{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}"
    "{% endif %}"
    "{% if message['role'] == 'user' %}{{ '[INST] ' + message['content'] + ' [/INST]' }}"
    "{% elif message['role'] == 'assistant' %}{{ message['content'] + eos_token}}"
    "{% else %}{{ raise_exception('Only user and assistant roles are supported!') }}{% endif %}"
    "{% endfor %}"
)

# The real Llama-2-chat template. Also emits EOS only through
# `{{ eos_token }}`.
LLAMA2_CHAT_TPL = (
    "{% if messages[0]['role'] == 'system' %}{% set loop_messages = messages[1:] %}"
    "{% set system_message = messages[0]['content'] %}{% else %}{% set loop_messages = messages %}"
    "{% set system_message = false %}{% endif %}"
    "{% for message in loop_messages %}"
    "{% if (message['role'] == 'user') != (loop.index0 % 2 == 0) %}"
    "{{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}"
    "{% endif %}"
    "{% if loop.index0 == 0 and system_message != false %}"
    "{% set content = '<<SYS>>\\n' + system_message + '\\n<</SYS>>\\n\\n' + message['content'] %}"
    "{% else %}{% set content = message['content'] %}{% endif %}"
    "{% if message['role'] == 'user' %}{{ bos_token + '[INST] ' + content.strip() + ' [/INST]' }}"
    "{% elif message['role'] == 'system' %}{{ '<<SYS>>\\n' + content.strip() + '\\n<</SYS>>\\n\\n' }}"
    "{% elif message['role'] == 'assistant' %}{{ ' '  + content.strip() + ' ' + eos_token }}"
    "{% endif %}{% endfor %}"
)


# The real Gemma-2 chat template (google/gemma-2-9b-it tokenizer_config.json,
# fetched verbatim from the public unsloth/gemma-2-9b-it mirror, which carries
# the identical file). Gemma rejects a leading system role outright and, like
# Mistral/Llama-2, only opens the assistant turn conditionally on
# add_generation_prompt -- so unlike them, S007 does NOT fire here.
GEMMA2_TPL = (
    "{{ bos_token }}{% if messages[0]['role'] == 'system' %}"
    "{{ raise_exception('System role not supported') }}{% endif %}"
    "{% for message in messages %}"
    "{% if (message['role'] == 'user') != (loop.index0 % 2 == 0) %}"
    "{{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}"
    "{% endif %}"
    "{% if (message['role'] == 'assistant') %}{% set role = 'model' %}"
    "{% else %}{% set role = message['role'] %}{% endif %}"
    "{{ '<start_of_turn>' + role + '\n' + message['content'] | trim + '<end_of_turn>\n' }}"
    "{% endfor %}"
    "{% if add_generation_prompt %}{{'<start_of_turn>model\n'}}{% endif %}"
)

# The real Llama-3.1/3.3 tool-calling ("tool_use") chat template, fetched
# verbatim from the public unsloth/Llama-3.3-70B-Instruct mirror of Meta's
# own tokenizer_config.json (Llama 3.3 folded the separate tool_use variant
# into its single default template). Exercises the "with_tools" fixture
# through real `{{ ... | tojson(indent=4) }}` tool-schema rendering.
LLAMA3_TOOLS_TPL = '{{- bos_token }}\n{%- if custom_tools is defined %}\n    {%- set tools = custom_tools %}\n{%- endif %}\n{%- if not tools_in_user_message is defined %}\n    {%- set tools_in_user_message = true %}\n{%- endif %}\n{%- if not date_string is defined %}\n    {%- set date_string = "26 Jul 2024" %}\n{%- endif %}\n{%- if not tools is defined %}\n    {%- set tools = none %}\n{%- endif %}\n\n{#- This block extracts the system message, so we can slot it into the right place. #}\n{%- if messages[0][\'role\'] == \'system\' %}\n    {%- set system_message = messages[0][\'content\']|trim %}\n    {%- set messages = messages[1:] %}\n{%- else %}\n    {%- set system_message = "" %}\n{%- endif %}\n\n{#- System message + builtin tools #}\n{{- "<|start_header_id|>system<|end_header_id|>\\n\\n" }}\n{%- if builtin_tools is defined or tools is not none %}\n    {{- "Environment: ipython\\n" }}\n{%- endif %}\n{%- if builtin_tools is defined %}\n    {{- "Tools: " + builtin_tools | reject(\'equalto\', \'code_interpreter\') | join(", ") + "\\n\\n"}}\n{%- endif %}\n{{- "Cutting Knowledge Date: December 2023\\n" }}\n{{- "Today Date: " + date_string + "\\n\\n" }}\n{%- if tools is not none and not tools_in_user_message %}\n    {{- "You have access to the following functions. To call a function, please respond with JSON for a function call." }}\n    {{- \'Respond in the format {"name": function name, "parameters": dictionary of argument name and its value}.\' }}\n    {{- "Do not use variables.\\n\\n" }}\n    {%- for t in tools %}\n        {{- t | tojson(indent=4) }}\n        {{- "\\n\\n" }}\n    {%- endfor %}\n{%- endif %}\n{{- system_message }}\n{{- "<|eot_id|>" }}\n\n{#- Custom tools are passed in a user message with some extra guidance #}\n{%- if tools_in_user_message and not tools is none %}\n    {#- Extract the first user message so we can plug it in here #}\n    {%- if messages | length != 0 %}\n        {%- set first_user_message = messages[0][\'content\']|trim %}\n        {%- set messages = messages[1:] %}\n    {%- else %}\n        {{- raise_exception("Cannot put tools in the first user message when there\'s no first user message!") }}\n{%- endif %}\n    {{- \'<|start_header_id|>user<|end_header_id|>\\n\\n\' -}}\n    {{- "Given the following functions, please respond with a JSON for a function call " }}\n    {{- "with its proper arguments that best answers the given prompt.\\n\\n" }}\n    {{- \'Respond in the format {"name": function name, "parameters": dictionary of argument name and its value}.\' }}\n    {{- "Do not use variables.\\n\\n" }}\n    {%- for t in tools %}\n        {{- t | tojson(indent=4) }}\n        {{- "\\n\\n" }}\n    {%- endfor %}\n    {{- first_user_message + "<|eot_id|>"}}\n{%- endif %}\n\n{%- for message in messages %}\n    {%- if not (message.role == \'ipython\' or message.role == \'tool\' or \'tool_calls\' in message) %}\n        {{- \'<|start_header_id|>\' + message[\'role\'] + \'<|end_header_id|>\\n\\n\'+ message[\'content\'] | trim + \'<|eot_id|>\' }}\n    {%- elif \'tool_calls\' in message %}\n        {%- if not message.tool_calls|length == 1 %}\n            {{- raise_exception("This model only supports single tool-calls at once!") }}\n        {%- endif %}\n        {%- set tool_call = message.tool_calls[0].function %}\n        {%- if builtin_tools is defined and tool_call.name in builtin_tools %}\n            {{- \'<|start_header_id|>assistant<|end_header_id|>\\n\\n\' -}}\n            {{- "<|python_tag|>" + tool_call.name + ".call(" }}\n            {%- for arg_name, arg_val in tool_call.arguments | items %}\n                {{- arg_name + \'="\' + arg_val + \'"\' }}\n                {%- if not loop.last %}\n                    {{- ", " }}\n                {%- endif %}\n                {%- endfor %}\n            {{- ")" }}\n        {%- else  %}\n            {{- \'<|start_header_id|>assistant<|end_header_id|>\\n\\n\' -}}\n            {{- \'{"name": "\' + tool_call.name + \'", \' }}\n            {{- \'"parameters": \' }}\n            {{- tool_call.arguments | tojson }}\n            {{- "}" }}\n        {%- endif %}\n        {%- if builtin_tools is defined %}\n            {#- This means we\'re in ipython mode #}\n            {{- "<|eom_id|>" }}\n        {%- else %}\n            {{- "<|eot_id|>" }}\n        {%- endif %}\n    {%- elif message.role == "tool" or message.role == "ipython" %}\n        {{- "<|start_header_id|>ipython<|end_header_id|>\\n\\n" }}\n        {%- if message.content is mapping or message.content is iterable %}\n            {{- message.content | tojson }}\n        {%- else %}\n            {{- message.content }}\n        {%- endif %}\n        {{- "<|eot_id|>" }}\n    {%- endif %}\n{%- endfor %}\n{%- if add_generation_prompt %}\n    {{- \'<|start_header_id|>assistant<|end_header_id|>\\n\\n\' }}\n{%- endif %}\n'


def _severities(findings):
    return {(f.id, f.severity) for f in findings}


def test_mistral_v02_full_suite_matches_documented_real_world_footguns():
    # Fix round 4 (coordinator ruling on final-fix-a): the previous version
    # of this test used add_bos_token=False to keep the assertion tidy --
    # but the real mistralai/Mistral-7B-Instruct-v0.2 tokenizer_config.json
    # sets add_bos_token: true (confirmed against the live file), and the
    # template also emits `{{ bos_token }}` itself. Faking the metadata to
    # dodge that combination is exactly the move that let the S003 bug ship
    # in the first place: a test that narrows what it looks at will keep
    # missing whatever it wasn't looking for. So this carries the genuine
    # published metadata and asserts the complete finding set, not a
    # filtered subset.
    #
    # Every finding here is a true positive, independently documented:
    #   - S003 INFO: the template's OWN alternation guard (identical to
    #     transformers) rejects the "system_user" fixture -- the author's
    #     deliberate, documented behaviour, quoted verbatim, not an error.
    #     Task 4 (corpus v2): the same alternation guard also rejects
    #     "tool_roundtrip" (system, user, assistant, tool -- four turns, so
    #     the guard's even/odd check falls out of sync exactly like a
    #     five-message conversation would) via the identical raise_exception
    #     call, so it collapses into this same finding rather than adding a
    #     new one. "typed_content" (single user turn, list content) does not
    #     trip the alternation guard but does fail differently -- see below.
    #   - S003 INFO on `typed_content`: the template does
    #     `message['content']` concatenated with `+` (`message['content'] +
    #     eos_token` for the assistant branch, `'[INST] ' + message['content']
    #     + ' [/INST]'` for the user branch) -- string concatenation, which
    #     raises `TypeError: can only concatenate str (not "list") to str`
    #     for typed_content's list content. `typed_content` is extended
    #     tier, so this reports at INFO, never ERROR, per this task's rule.
    #     `no_generation_prompt` renders cleanly (plain string content,
    #     alternates correctly) and adds nothing.
    #   - S006 INFO: add_bos_token=true (real) + the template's own
    #     `{{ bos_token }}` (real) is the double-BOS combination -- but
    #     current mainline llama.cpp's own chat-template application
    #     (common/chat.cpp, common_chat_template_direct_apply_impl) strips
    #     exactly this leading duplicate before tokenizing, so the risk is
    #     real only for callers that render this template themselves and
    #     tokenize with add_special_tokens=True outside llama.cpp's own
    #     template glue -- not a WARN-worthy near-certainty on llama.cpp
    #     itself. S006 still exists precisely to catch this combination.
    #   - S007 INFO: add_generation_prompt is genuinely never referenced in
    #     this template -- true and unavoidable for this exact upstream
    #     text -- but the rendered output already ends in "[/INST]", which
    #     plainly opens the assistant turn some other way, so INFO not WARN.
    # A future change to any of Mistral's real template/metadata that
    # altered this set should break this test loudly -- that's the point.
    f = run_sanity_checks(ctx(chat_template=MISTRAL_V02_TPL,
                              tokens=["<unk>", "<s>", "</s>"],
                              bos_token_id=1, eos_token_id=2,
                              add_bos_token=True))
    assert _severities(f) == {
        ("S003", Severity.INFO),
        ("S006", Severity.INFO),
        ("S007", Severity.INFO),
    }


def test_llama2_chat_full_suite_matches_documented_real_world_footguns():
    # Same fix as above, applied to Llama-2-chat: the real
    # meta-llama/Llama-2-7b-chat-hf tokenizer_config.json also sets
    # add_bos_token: true (confirmed against the live file), and its
    # template prepends `{{ bos_token }}` to every user turn, including the
    # first -- the same real double-BOS footgun, independently documented
    # for Llama-2 GGUF conversions. Its template special-cases a leading
    # system role (folding it into the first user turn) rather than
    # rejecting it outright, so system_user never raises and there is no
    # S003 here. add_generation_prompt is still never referenced, so S007
    # still fires; the rendered output still ends in "[/INST]", so INFO.
    # S006 is INFO here for the same reason as Mistral above: llama.cpp's
    # own chat-template application strips this exact leading duplicate.
    #   - S003 INFO on `tool_roundtrip` and `typed_content` (two distinct
    #     findings, same severity): the template always does
    #     `content.strip()` on a non-first-turn message's content, and here
    #     `content = message['content']` unchanged -- `None` (tool_roundtrip's
    #     assistant turn) and a `list` (typed_content's single turn) both
    #     lack `.strip()`, so Jinja2 raises `UndefinedError` on the attribute
    #     access. Both fixtures are extended tier, so both report at INFO,
    #     never ERROR, per this task's tier rule. `no_generation_prompt` is
    #     also extended but has plain string content throughout, so it
    #     renders cleanly and adds nothing here.
    f = run_sanity_checks(ctx(chat_template=LLAMA2_CHAT_TPL,
                              tokens=["<unk>", "<s>", "</s>"],
                              bos_token_id=1, eos_token_id=2,
                              add_bos_token=True))
    assert _severities(f) == {
        ("S003", Severity.INFO),
        ("S006", Severity.INFO),
        ("S007", Severity.INFO),
    }


def test_gemma2_full_suite_matches_documented_real_world_quirks():
    # Real Gemma-2 tokenizer_config.json / generation_config.json / config
    # values (fetched from the public unsloth/gemma-2-9b-it mirror, cross-
    # checked against three separate files): add_bos_token is true,
    # bos_token_id=2 and eos_token_id=1 are the model's genuine published
    # ids (not renumbered for convenience -- pad=0, eos=1, bos=2 is
    # Gemma-2's real special-token layout), and the model's own vocab holds
    # a separate "<eos>" special token distinct from the "<end_of_turn>"
    # the chat template actually emits at every turn boundary. Both S005
    # and S006 below are well-documented real-world Gemma-2 GGUF conversion
    # issues (generation_config.json for Gemma-2 instruct models has
    # historically had to list *two* eos token ids for exactly this reason,
    # and "double BOS" was an open llama.cpp issue for Gemma conversions)
    # -- not artifacts of this tool's fix. S006 is INFO, not WARN: current
    # mainline llama.cpp's own chat-template application strips the leading
    # duplicate before tokenizing (see sanity.s006_double_bos), so the risk
    # is real for callers outside that path, not for llama.cpp itself.
    f = run_sanity_checks(ctx(chat_template=GEMMA2_TPL,
                              tokens=["<pad>", "<eos>", "<bos>",
                                      "<start_of_turn>", "<end_of_turn>"],
                              bos_token_id=2, eos_token_id=1,
                              add_bos_token=True))
    assert _severities(f) == {
        # S003 INFO: declines a leading system role, by design ("system_user").
        # Task 4 (corpus v2): "tool_roundtrip" also opens with a system
        # message, so it hits the identical `raise_exception('System role
        # not supported')` call and collapses into the same finding.
        # "typed_content" and "no_generation_prompt" both render cleanly --
        # the template's `| trim` filter stringifies non-string content
        # instead of raising, and no_generation_prompt's messages are plain
        # strings that alternate correctly -- so neither adds a finding.
        ("S003", Severity.INFO),
        ("S005", Severity.WARN),   # template only ever emits <end_of_turn>, never <eos>
        ("S006", Severity.INFO),   # add_bos_token=True + template's own {{ bos_token }}
    }


def test_llama3_tool_calling_full_suite_matches_documented_real_world_quirk():
    # Real Llama-3.3 metadata (fetched from the public
    # unsloth/Llama-3.3-70B-Instruct mirror of Meta's own files):
    # add_bos_token is true, bos_token_id=128000 and eos_token_id=128009
    # are the model's genuine published ids (config.json/generation_config
    # .json), at the same positions Meta's own tokenizer assigns them --
    # not renumbered down to small convenience indices. The vocab below is
    # a real, sparse *prefix-and-suffix* of the actual 128256-entry
    # tokenizer: every slot that matters to these checks holds its real
    # token at its real id; the filler positions are never looked up by any
    # check (S004 only tests set membership of literal `<|...|>` strings
    # found in the template source; S005/S006 only ever index the two
    # tokens named above) so a placeholder there doesn't affect coverage.
    #
    # add_bos_token=true + the template's own `{{- bos_token }}` at the top
    # is the same double-BOS pattern as Gemma-2 above -- INFO, not WARN, for
    # the same reason (llama.cpp's own chat-template application strips the
    # leading duplicate before tokenizing). Everything else about this
    # template -- including the "with_tools" fixture's real
    # `| tojson(indent=4)` tool-schema rendering -- is clean.
    #
    # Task 4 (corpus v2): this template is exactly the shape the three new
    # extended fixtures model (it explicitly branches on `'tool_calls' in
    # message`, on `message.role == 'tool'`, and stringifies non-mapping
    # content via `| tojson`/plain emission), so it renders all three --
    # "tool_roundtrip", "typed_content", "no_generation_prompt" -- cleanly
    # with no new findings. No assertion change needed; verified directly.
    tokens = ["<unk>"] * 128011
    tokens[128000] = "<|begin_of_text|>"
    tokens[128001] = "<|end_of_text|>"
    tokens[128006] = "<|start_header_id|>"
    tokens[128007] = "<|end_header_id|>"
    tokens[128008] = "<|eom_id|>"
    tokens[128009] = "<|eot_id|>"
    tokens[128010] = "<|python_tag|>"
    f = run_sanity_checks(ctx(
        chat_template=LLAMA3_TOOLS_TPL,
        tokens=tokens,
        bos_token_id=128000, eos_token_id=128009, add_bos_token=True))
    assert _severities(f) == {("S006", Severity.INFO)}


def test_s005_flags_template_that_never_emits_eos():
    f = run_sanity_checks(ctx(chat_template="{% for m in messages %}{{ m['content'] }}{% endfor %}",
                              tokens=["<unk>", "<s>", "</s>"], eos_token_id=2))
    assert "S005" in ids(f)


def test_s006_silent_when_bos_mentioned_only_in_comment():
    tpl = ("{# BOS is added by the tokenizer, deliberately not here #}"
           "{% for m in messages %}{{ m['content'] }}{% endfor %}")
    f = run_sanity_checks(ctx(chat_template=tpl, add_bos_token=True,
                              tokens=["<s>"], bos_token_id=0))
    assert "S006" not in ids(f)


def test_s006_silent_when_bos_only_in_untaken_branch():
    tpl = ("{% if false %}{{ bos_token }}{% endif %}"
           "{% for m in messages %}{{ m['content'] }}{% endfor %}")
    f = run_sanity_checks(ctx(chat_template=tpl, add_bos_token=True,
                              tokens=["<s>"], bos_token_id=0))
    assert "S006" not in ids(f)


def test_s006_flags_llama3_style_conditional_bos():
    tpl = ("{% for m in messages %}{% if loop.index0 == 0 %}{{ bos_token }}{% endif %}"
           "{{ m['content'] }}{% endfor %}")
    f = run_sanity_checks(ctx(chat_template=tpl, add_bos_token=True,
                              tokens=["<s>"], bos_token_id=0))
    assert "S006" in ids(f)


def test_s004_comment_only_marker_silent_but_rendered_missing_marker_flags():
    # A marker that appears only inside a Jinja comment never survives to
    # any render, so it is not evidence of anything.
    comment_only = ("{# <|reserved|> #}"
                    "{% for m in messages %}<|im_start|>{{ m['content'] }}<|im_end|>{% endfor %}")
    f = run_sanity_checks(ctx(chat_template=comment_only,
                              tokens=["<|im_start|>", "<|im_end|>"]))
    assert "S004" not in ids(f)

    # A marker that actually renders and is absent from the vocab is real
    # evidence and must still be flagged.
    f2 = run_sanity_checks(ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>"]))
    assert "S004" in ids(f2)
    finding = next(x for x in f2 if x.id == "S004")
    assert "<|im_end|>" in finding.evidence["missing"]


def test_s003_collapses_repeats_across_fixtures():
    f = run_sanity_checks(ctx(chat_template="{{ raise_exception('boom') }}"))
    s003 = [x for x in f if x.id == "S003"]
    assert len(s003) == 1
    assert set(s003[0].evidence["fixtures"]) == {fx.name for fx in load_fixtures()}


def test_s004_and_s006_skipped_when_template_does_not_compile():
    f = run_sanity_checks(ctx(chat_template="{% if %}", add_bos_token=True,
                              tokens=["<s>"], bos_token_id=0))
    assert "S002" in ids(f)
    assert "S004" not in ids(f)
    assert "S006" not in ids(f)


# --- Fix round 1: coverage gaps for S005/S006 when token metadata is
# missing or out of range, so Task 10 can report "not evaluated" instead
# of silently letting these look like clean passes. ---

def test_s005_records_not_evaluated_when_eos_id_missing():
    # add_bos_token=False isolates this from S006's own (correct) coverage
    # gap when add_bos_token is absent -- see the S006 tests below.
    c = ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>", "<|im_end|>"],
            add_bos_token=False)
    findings = run_sanity_checks(c)
    assert "S005" not in ids(findings)
    assert c.checks_not_evaluated == ["S005"]


def test_s005_records_not_evaluated_when_eos_id_out_of_range():
    c = ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>", "<|im_end|>"],
            eos_token_id=99, add_bos_token=False)
    findings = run_sanity_checks(c)
    # The out-of-range id is still worth flagging on its own...
    assert "S005" in ids(findings)
    # ...but the deeper "does the template emit EOS" comparison never ran.
    assert c.checks_not_evaluated == ["S005"]


def test_s005_negative_eos_id_takes_the_out_of_range_warn_path():
    # Fix round 2: a negative eos_token_id used to slip past the
    # `eos_token_id >= len(tokens)` guard, land on `_real_token`'s
    # `0 <= id < len` bound instead, and bail out with no finding at all --
    # the check stayed "safe" only by accident. It must now hit the same
    # out-of-range WARN path a too-large id does.
    c = ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>", "<|im_end|>"],
            eos_token_id=-1, add_bos_token=False)
    findings = run_sanity_checks(c)
    s005 = [f for f in findings if f.id == "S005"]
    assert len(s005) == 1
    assert s005[0].severity == Severity.WARN
    assert s005[0].message == "eos_token_id is out of range for this file's vocab"
    assert c.checks_not_evaluated == ["S005"]


def test_s006_records_not_evaluated_when_bos_id_missing():
    # tokens/eos_token_id are supplied purely to keep S005 from also
    # bailing here, so this test isolates the S006 behaviour.
    c = ctx(chat_template=CHAT_TPL, add_bos_token=True,
            tokens=["<|im_start|>", "<|im_end|>"], eos_token_id=1)
    findings = run_sanity_checks(c)
    assert "S006" not in ids(findings)
    assert c.checks_not_evaluated == ["S006"]


def test_s006_not_recorded_when_add_bos_token_is_false():
    # add_bos_token *explicitly* False means the metadata confidently says
    # the tokenizer does not add its own BOS -- the check correctly doesn't
    # apply, that's a no-op, not a coverage gap, so S006 specifically
    # should not be recorded (S005 still bails on its own missing eos id,
    # which is exercised separately above).
    c = ctx(chat_template=CHAT_TPL, add_bos_token=False)
    run_sanity_checks(c)
    assert "S006" not in c.checks_not_evaluated


def test_s006_records_not_evaluated_when_add_bos_token_absent():
    # Fix round 3 (final whole-branch review): add_bos_token *absent*
    # (None, the GgufModel default -- e.g. a remote org/repo target with no
    # tokenizer_config info at all) is not the same claim as an explicit
    # False. We don't know whether the tokenizer adds its own BOS, so the
    # check cannot even tell whether it applies -- previously this was
    # conflated with the explicit-False case and silently treated as a
    # clean no-op, hiding a real coverage gap.
    c = ctx(chat_template=CHAT_TPL)
    findings = run_sanity_checks(c)
    assert "S006" not in ids(findings)
    assert "S006" in c.checks_not_evaluated


def test_s004_records_not_evaluated_when_vocab_unavailable():
    # Fix round 3: S004 used to return [] with no trace when the file has
    # no vocab at all (e.g. a remote org/repo target) -- indistinguishable
    # from "checked and found nothing wrong". It must now say it never ran.
    c = ctx(chat_template=CHAT_TPL, tokens=[])
    findings = run_sanity_checks(c)
    assert "S004" not in ids(findings)
    assert "S004" in c.checks_not_evaluated


def test_s005_records_not_evaluated_when_multiturn_fixture_missing():
    # Fix round 3: a custom --fixtures corpus that lacks "multiturn" leaves
    # S005 with nothing to render; that must be a recorded coverage gap,
    # not a silent pass.
    custom_fixtures = [f for f in load_fixtures() if f.name != "multiturn"]
    model = GgufModel(source_id="t", architecture="llama", chat_template=CHAT_TPL,
                      tokens=["<unk>", "<s>", "</s>", "<|im_start|>", "<|im_end|>"],
                      eos_token_id=2, add_bos_token=False)
    c = CheckContext(model=model, engines=[Jinja2Engine()], fixtures=custom_fixtures)
    findings = run_sanity_checks(c)
    assert "S005" not in ids(findings)
    assert "S005" in c.checks_not_evaluated


def test_s006_records_not_evaluated_when_user_only_fixture_missing():
    custom_fixtures = [f for f in load_fixtures() if f.name != "user_only"]
    model = GgufModel(source_id="t", architecture="llama", chat_template=CHAT_TPL,
                      tokens=["<s>", "<|im_start|>", "<|im_end|>"],
                      bos_token_id=0, add_bos_token=True)
    c = CheckContext(model=model, engines=[Jinja2Engine()], fixtures=custom_fixtures)
    findings = run_sanity_checks(c)
    assert "S006" not in ids(findings)
    assert "S006" in c.checks_not_evaluated


def test_s007_records_not_evaluated_when_user_only_fixture_missing():
    custom_fixtures = [f for f in load_fixtures() if f.name != "user_only"]
    model = GgufModel(source_id="t", architecture="llama", chat_template=CHAT_TPL)
    c = CheckContext(model=model, engines=[Jinja2Engine()], fixtures=custom_fixtures)
    findings = run_sanity_checks(c)
    assert "S007" not in ids(findings)
    assert "S007" in c.checks_not_evaluated


# --- Fix round 3 (final whole-branch review): S003 splits author-declined
# renders from genuine engine failures; S007's message states only the
# observable fact. ---

def test_s003_author_decline_is_info_not_error_and_quotes_the_message():
    f = run_sanity_checks(ctx(chat_template=(
        "{{ raise_exception('Only user and assistant roles are supported!') }}")))
    s003 = [x for x in f if x.id == "S003"]
    assert len(s003) == 1
    assert s003[0].severity == Severity.INFO
    assert "Only user and assistant roles are supported!" in s003[0].message


def test_s003_genuine_render_failure_stays_error():
    # An undefined-variable access is a real engine failure, not an author
    # decline, and must keep S003's original ERROR severity -- for the core
    # fixtures. Task 4 (corpus v2): this template's failure only ever
    # touches `messages[0]['role']`, present and identical in shape on every
    # one of the ten fixtures, so the *signature* is the same everywhere --
    # but S003 buckets render failures by tier before collapsing by
    # signature, so the seven core fixtures still produce one ERROR finding
    # and the three extended fixtures still produce their own separate INFO
    # finding, even though the underlying error text is identical.
    f = run_sanity_checks(ctx(chat_template="{{ messages[0]['role'].nonexistent.deeper }}"))
    s003 = [x for x in f if x.id == "S003"]
    assert len(s003) == 2
    core = next(x for x in s003 if x.severity == Severity.ERROR)
    extended = next(x for x in s003 if x.severity == Severity.INFO)
    assert set(core.evidence["fixtures"]) == {
        "user_only", "system_user", "multiturn", "with_tools",
        "thinking_unset", "thinking_true", "thinking_false"}
    assert set(extended.evidence["fixtures"]) == {
        "tool_roundtrip", "typed_content", "no_generation_prompt"}


def test_s007_info_when_output_already_opens_assistant_turn():
    # Ends in "[/INST]" -- the assistant turn is plainly opened some other
    # way, so the no-op flag is informational, not a working problem.
    tpl = "{% for m in messages %}[INST] {{ m['content'] }} [/INST]{% endfor %}"
    f = run_sanity_checks(ctx(chat_template=tpl))
    s007 = next(x for x in f if x.id == "S007")
    assert s007.severity == Severity.INFO
    assert s007.message == "add_generation_prompt has no effect on the rendered output"


def test_s007_warn_when_output_does_not_open_assistant_turn():
    f = run_sanity_checks(ctx(chat_template="{% for m in messages %}{{ m['content'] }}{% endfor %}"))
    s007 = next(x for x in f if x.id == "S007")
    assert s007.severity == Severity.WARN


# --- Final fix C: a template that declines every fixture must say so, not
# read as clean. S004/S005/S006/S007 all bail on "no render succeeded" (or,
# for S007, "the flag's on/off render failed") without recording that as a
# coverage gap -- indistinguishable, from the finding list alone, from
# "checked and found nothing wrong". Splitting the author's deliberate
# raise_exception out of S003 (fix round 3) was correct, but it means a
# template that declines everything now produces a single S003 INFO and
# *nothing else* unless these four checks also speak up. ---

# Special tokens live in the raw template text (S004 regex-scans the
# template source, not rendered output), so they still count as candidates
# even though raise_exception fires before any of this text could ever be
# emitted.
DECLINES_EVERYTHING_TPL = "{{ raise_exception('nope') }}<|im_start|><|im_end|>"


def test_template_declining_every_fixture_is_not_reported_as_clean():
    c = ctx(chat_template=DECLINES_EVERYTHING_TPL,
            tokens=["<unk>", "<s>", "</s>"],
            bos_token_id=1, eos_token_id=2, add_bos_token=True)
    findings = run_sanity_checks(c)
    # S003 alone has something to say -- the author's declaration that this
    # template declines every conversation shape the corpus offers. Nothing
    # downstream of that render ever observed any output at all.
    assert ids(findings) == {"S003"}
    s003 = next(f for f in findings if f.id == "S003")
    assert s003.severity == Severity.INFO
    # Before this fix: none of these record anything, findings == the
    # single S003 INFO, and the report reads as a clean pass with an empty
    # checks_not_evaluated -- the exact silence this project keeps fighting.
    assert set(c.checks_not_evaluated) == {"S004", "S005", "S006", "S007"}


# --- Task 4: corpus v2 extended-tier fixtures downgrade S003 to INFO ---

def _model_with(template, **kw):
    return GgufModel(source_id="t", architecture="llama", chat_template=template,
                     tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1,
                     add_bos_token=False, **kw)


def test_s003_on_extended_fixture_is_info_not_error():
    # `'x' + None` raises TypeError under Jinja2 only on tool_roundtrip
    # (assistant content is null there). That is the fixture asking a shape
    # the template predates -- reported, but never as an error.
    # Core fixtures all have string content, so only the two extended
    # fixtures fail -- with two different TypeErrors (NoneType vs list), so
    # they collapse into two findings, not one.
    tpl = "{% for m in messages %}<|{{ m.role }}|>{{ 'x' + m.content }}{% endfor %}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    findings = s003_render_error(ctx)
    found = {(f.id, f.severity, tuple(f.evidence.get("fixtures", ()))) for f in findings}
    assert found == {("S003", Severity.INFO, ("tool_roundtrip",)),
                     ("S003", Severity.INFO, ("typed_content",))}
    for f in findings:
        assert "extended" in f.message and "broken" not in f.message


def test_s003_on_core_fixture_stays_error():
    tpl = "{{ messages[0].content + none }}"
    ctx = CheckContext(model=_model_with(tpl), engines=[Jinja2Engine()], fixtures=load_fixtures())
    severities = {f.severity for f in s003_render_error(ctx)
                  if "user_only" in f.evidence.get("fixtures", ())}
    assert severities == {Severity.ERROR}
