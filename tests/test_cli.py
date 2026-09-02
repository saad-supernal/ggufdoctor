import json

import pytest

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


def test_too_short_to_hold_the_magic_reports_not_a_gguf_file(tmp_path, capsys):
    bad = tmp_path / "x.gguf"
    bad.write_bytes(b"NO")  # shorter than the 4-byte "GGUF" magic
    assert main([str(bad)]) == 2
    err = capsys.readouterr().err
    assert "missing GGUF magic" in err
    assert "needed 4 bytes" not in err


def test_checks_not_evaluated_reaches_the_reports(tmp_path, capsys):
    # _model() never sets tokenizer.ggml.eos_token_id or
    # tokenizer.ggml.add_bos_token, so both S005 (no eos id to compare
    # against) and S006 (no way to know whether the tokenizer itself adds a
    # BOS) record themselves on ctx.checks_not_evaluated and return no
    # finding -- a "clean" run that is not actually a clean bill of health.
    # resolve() builds `coverage` before any check has run, so this only
    # reaches the reports if main() copies ctx.checks_not_evaluated onto
    # coverage afterwards. Without that merge this test fails: the human
    # report says a bare "no findings" and the JSON's checks_not_evaluated
    # stays empty, silently hiding that neither check ever ran.
    out_path = tmp_path / "r.json"
    exit_status = main([_model(tmp_path), "--json", str(out_path)])
    assert exit_status == 0

    human = capsys.readouterr().out
    assert "S005, S006 not evaluated" in human
    assert "no findings (partial:" in human

    data = json.loads(out_path.read_text())
    assert data["coverage"]["checks_not_evaluated"] == ["S005", "S006"]


# --- Fix round 1 ---

def test_unwritable_json_path_exits_two_without_traceback(tmp_path, capsys):
    # Make the write fail on every OS by putting a regular *file* where a
    # directory has to be: POSIX raises NotADirectoryError, Windows raises an
    # OSError of its own. A chmod-based "read-only directory" is not portable
    # -- Windows ignores POSIX mode bits for the owner and the write succeeds.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    target = str(blocker / "r.json")
    exit_status = main([_model(tmp_path), "--json", target])

    assert exit_status == 2
    err = capsys.readouterr().err
    assert err.startswith("ggufdoctor: ")
    # A one-line message, not a multi-line traceback.
    assert err.count("\n") == 1


def test_default_local_run_headline_is_not_alarming(tmp_path, capsys):
    # A valid eos_token_id (index 1 -> "<|im_end|>", which the template does
    # emit) lets S005 fully evaluate, and an explicit add_bos_token=False
    # lets S006 resolve too (metadata confidently says no BOS is added, so
    # there's nothing to check). The only thing "missing" from this run is
    # then the upstream comparison the user never asked for. That must read
    # as complete-for-what-was-asked, not as a coverage warning.
    path = _model(tmp_path, **{"tokenizer.ggml.eos_token_id": ("u32", 1),
                               "tokenizer.ggml.add_bos_token": ("bool", False)})
    assert main([path]) == 0
    human = capsys.readouterr().out
    assert "no findings — local checks only" in human
    assert "--compare-upstream" in human
    assert "partial" not in human


def test_gated_upstream_produces_a_partial_headline(tmp_path, monkeypatch, capsys):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def upstream_template(self, repo):
            return None, "gated"

    monkeypatch.setattr("ggufdoctor.sources.HfClient", FakeClient)
    path = _model(tmp_path, **{"tokenizer.ggml.eos_token_id": ("u32", 1)})
    assert main([path, "--compare-upstream", "some/repo"]) == 0
    human = capsys.readouterr().out
    assert "no findings (partial: upstream gated" in human
    assert "local checks only" not in human


def test_require_upstream_without_compare_upstream_is_a_usage_error(tmp_path):
    path = _model(tmp_path)
    assert main([path, "--require-upstream"]) == 2


# --- Final fix B: survey subcommand dispatch/visibility ---

def test_survey_appears_in_top_level_help(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "survey" in out


def test_survey_subcommand_dispatches_without_touching_the_real_hub(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def list_gguf_models(self, skip, limit):
            return []

    monkeypatch.setattr("ggufdoctor.hf.HfClient", FakeClient)
    assert main(["survey", "--top", "5"]) == 0
    out = capsys.readouterr().out
    assert "GGUF chat-template survey" in out


def test_survey_help_documents_its_own_flags(capsys):
    with pytest.raises(SystemExit):
        main(["survey", "--help"])
    out = capsys.readouterr().out
    assert "--per-org" in out
    assert "--markdown" in out


# --- Final fix C: a template that declines every fixture must not read as
# a clean pass end to end through the CLI. ---

def test_template_declining_everything_is_not_clean_end_to_end(tmp_path, capsys):
    tpl = "{{ raise_exception('nope') }}<|im_start|><|im_end|>"
    path = _model(tmp_path, **{
        "tokenizer.chat_template": ("string", tpl),
        "tokenizer.ggml.tokens": ("array_string", ["<unk>", "<s>", "</s>"]),
        "tokenizer.ggml.bos_token_id": ("u32", 1),
        "tokenizer.ggml.eos_token_id": ("u32", 2),
        "tokenizer.ggml.add_bos_token": ("bool", True),
    })
    out_path = tmp_path / "r.json"
    exit_status = main([path, "--json", str(out_path)])

    human = capsys.readouterr().out
    # Before this fix: a single "S003 INFO", "0 error, 0 warn", exit 0, and
    # no "not evaluated" note at all -- indistinguishable from a template
    # this tool actually checked and found clean.
    assert exit_status == 0
    assert "S003" in human
    for check_id in ("S004", "S005", "S006", "S007"):
        assert f"note: {check_id} not evaluated" in human

    data = json.loads(out_path.read_text())
    assert data["coverage"]["checks_not_evaluated"] == [
        "S004", "S005", "S006", "S007"]
    assert data["summary"] == {"error": 0, "warn": 0, "info": 1}


def test_file_literally_named_survey_is_linted_not_dispatched(tmp_path, monkeypatch):
    # A local file (or repo) that happens to be named exactly "survey" must
    # still be treated as a lint target, the same way is_repo_id() always
    # prefers an on-disk path over guessing at a name's shape.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "survey").write_bytes(build_gguf({
        "general.architecture": ("string", "llama"),
        "tokenizer.chat_template": ("string", CHAT_TPL),
        "tokenizer.ggml.tokens": ("array_string", ["<|im_start|>", "<|im_end|>"]),
    }))
    assert main(["survey"]) == 0
