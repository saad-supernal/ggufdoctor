from ggufdoctor.checks.sanity import run_sanity_checks
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


def test_s005_no_false_positive_on_mistral_template():
    # Reviewer's disqualifying case: the real Mistral-7B-Instruct-v0.2
    # template only ever emits EOS via `{{ eos_token }}`, never as a
    # hardcoded literal, and demonstrably renders `</s>` correctly.
    f = run_sanity_checks(ctx(chat_template=MISTRAL_V02_TPL,
                              tokens=["<unk>", "<s>", "</s>"],
                              bos_token_id=1, eos_token_id=2))
    assert "S005" not in ids(f)


def test_s005_no_false_positive_on_llama2_template():
    f = run_sanity_checks(ctx(chat_template=LLAMA2_CHAT_TPL,
                              tokens=["<unk>", "<s>", "</s>"],
                              bos_token_id=1, eos_token_id=2))
    assert "S005" not in ids(f)


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
    c = ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>", "<|im_end|>"])
    findings = run_sanity_checks(c)
    assert "S005" not in ids(findings)
    assert c.checks_not_evaluated == ["S005"]


def test_s005_records_not_evaluated_when_eos_id_out_of_range():
    c = ctx(chat_template=CHAT_TPL, tokens=["<|im_start|>", "<|im_end|>"],
            eos_token_id=99)
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
            eos_token_id=-1)
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
    # add_bos_token=False (the default) means the check correctly doesn't
    # apply -- that's a no-op, not a coverage gap, so S006 specifically
    # should not be recorded (S005 still bails on its own missing eos id,
    # which is exercised separately above).
    c = ctx(chat_template=CHAT_TPL)
    run_sanity_checks(c)
    assert "S006" not in c.checks_not_evaluated
