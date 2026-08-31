import json

from ggufdoctor.cli import main
from tests.helpers.gguf_builder import build_gguf

CHAT_TPL = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}"
            "<|im_end|>\n{% endfor %}"
            "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")


def _model(tmp_path, **kv):
    base = {"general.architecture": ("string", "llama"),
            "tokenizer.chat_template": ("string", CHAT_TPL),
            "tokenizer.ggml.tokens": ("array_string",
                                      ["<|im_start|>", "<|im_end|>"])}
    base.update(kv)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf(base))
    return str(p)


def test_clean_model_exits_zero(tmp_path, capsys):
    assert main([_model(tmp_path)]) == 0
    assert "no findings" in capsys.readouterr().out


def test_missing_vocab_token_exits_one(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path]) == 1


def test_json_output_written(tmp_path):
    out = tmp_path / "r.json"
    main([_model(tmp_path), "--json", str(out)])
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1"


def test_fail_on_never_always_zero(tmp_path):
    path = _model(tmp_path,
                  **{"tokenizer.ggml.tokens": ("array_string", ["<|im_start|>"])})
    assert main([path, "--fail-on", "never"]) == 0


def test_unreadable_file_exits_two(tmp_path):
    bad = tmp_path / "x.gguf"
    bad.write_bytes(b"NOPE")
    assert main([str(bad)]) == 2


def test_checks_not_evaluated_reaches_the_reports(tmp_path, capsys):
    # _model() never sets tokenizer.ggml.eos_token_id, so S005 records
    # itself on ctx.checks_not_evaluated (no eos id to compare against) and
    # returns no finding -- a "clean" run that is not actually a clean bill
    # of health. resolve() builds `coverage` before any check has run, so
    # this only reaches the reports if main() copies ctx.checks_not_evaluated
    # onto coverage afterwards. Without that merge this test fails: the human
    # report says a bare "no findings" and the JSON's checks_not_evaluated
    # stays empty, silently hiding that S005 never ran.
    out_path = tmp_path / "r.json"
    exit_status = main([_model(tmp_path), "--json", str(out_path)])
    assert exit_status == 0

    human = capsys.readouterr().out
    assert "S005 not evaluated" in human
    assert "no findings (partial:" in human

    data = json.loads(out_path.read_text())
    assert data["coverage"]["checks_not_evaluated"] == ["S005"]
