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
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(0o500)  # read + execute, no write
    target = str(readonly_dir / "r.json")
    try:
        exit_status = main([_model(tmp_path), "--json", target])
    finally:
        readonly_dir.chmod(0o700)  # let tmp_path cleanup remove it afterwards

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
