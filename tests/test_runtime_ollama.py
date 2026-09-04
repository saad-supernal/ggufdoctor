import http.server
import json
import sys
import threading

import pytest

from ggufdoctor.checks.ollama_registry import OLLAMA_SUFFIX, run_ollama_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.engines.llamacpp_engine import LlamaCppEngine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.models import CheckContext, GgufModel, Severity
from ggufdoctor.runtime_ollama import (OllamaRuntime, OllamaRuntimeError, not_sendable_reason,
                                       request_body, run_runtime_checks)

FAKE_BIN = '''
import json, pathlib, sys
log = pathlib.Path(sys.argv[1]); args = sys.argv[2:]
log.write_text(log.read_text() + json.dumps(args) + "\\n") if log.exists() else log.write_text(json.dumps(args) + "\\n")
if args[:1] == ["--version"]:
    print("ollama version is 0.33.2"); sys.exit(0)
if args[:1] == ["create"]:
    mf = pathlib.Path(args[args.index("-f") + 1]).read_text()
    assert mf.startswith("FROM "), mf
    sys.exit(int(pathlib.Path(sys.argv[1]).with_suffix(".fail").exists()))
if args[:1] == ["rm"]:
    sys.exit(0)
sys.exit(3)
'''


class _Handler(http.server.BaseHTTPRequestHandler):
    renderer = staticmethod(lambda body: "")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        self.server.requests.append(body)
        assert self.path == "/api/chat" and body["_debug_render_only"] is True
        out = json.dumps({"model": body["model"], "_debug_info": {"rendered_template": self.renderer(body)}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.requests = []
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    t.join(timeout=5)


@pytest.fixture
def fake_ollama(tmp_path):
    script = tmp_path / "fake_ollama.py"; script.write_text(FAKE_BIN)
    log = tmp_path / "calls.log"
    return [sys.executable, str(script), str(log)], log


# Deliberately far from every string in Ollama's index: the whole point of
# these two tests is the *miss* path, where the prediction comes from the
# llama.cpp engine rather than a registry golden. The obvious ChatML spelling
# is not usable here -- it lands 49 edits from the vendored `chatml` entry,
# well inside the cutoff of 100, so the registry would recognise it and
# test_recognised_template_predicts_from_the_golden's path would be exercised
# twice instead of both. run_ollama_checks' verdict is asserted below so a
# future index change cannot quietly swap which path these tests cover.
TPL = ("{% for turn in messages %}[[ SPEAKER {{ turn['role'] | upper }} BEGINS ]]\n"
       "{{ turn['content'] }}\n[[ SPEAKER {{ turn['role'] | upper }} ENDS ]]\n{% endfor %}"
       "{% if add_generation_prompt %}[[ SPEAKER ASSISTANT BEGINS ]]\n{% endif %}")


def _ctx(template=TPL, engines=None):
    model = GgufModel(source_id="m.gguf", architecture="llama", chat_template=template,
                      tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1)
    return CheckContext(model=model, engines=engines or [Jinja2Engine(), LlamaCppEngine()],
                        fixtures=load_fixtures())


def test_request_body_maps_a_fixture_to_api_chat():
    fx = {f.name: f for f in load_fixtures()}
    body = request_body("m", fx["with_tools"])
    assert body["model"] == "m" and body["stream"] is False and body["_debug_render_only"] is True
    assert body["tools"] == fx["with_tools"].context["tools"] and "think" not in body
    assert request_body("m", fx["thinking_false"])["think"] is False
    rt = request_body("m", fx["tool_roundtrip"])
    assert rt["messages"][2]["content"] == "" and rt["messages"][2]["tool_calls"]
    assert request_body("m", fx["typed_content"]) is None
    assert request_body("m", fx["no_generation_prompt"]) is None
    assert "add_generation_prompt" in not_sendable_reason(fx["no_generation_prompt"])
    assert "typed content" in not_sendable_reason(fx["typed_content"])


def test_version_parses_ollama_output(fake_ollama):
    cmd, _ = fake_ollama
    assert OllamaRuntime(cmd).version() == "0.33.2"


def test_agreeing_runtime_yields_one_info_and_cleans_up(server, fake_ollama):
    cmd, log = fake_ollama
    llama = LlamaCppEngine()
    _Handler.renderer = staticmethod(lambda body: llama.render(TPL, {"messages": body["messages"],
                                     "tools": body.get("tools"), "bos_token": "<s>", "eos_token": "</s>",
                                     **({"enable_thinking": body["think"]} if "think" in body else {})}).text)
    ctx = _ctx()
    run_ollama_checks(ctx)   # unrecognised -> predicted path is the llama.cpp engine
    assert ctx.stats["ollama"]["recognised"] is False
    rt = OllamaRuntime(cmd, host=f"http://127.0.0.1:{server.server_address[1]}")
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert [(f.id, f.severity) for f in found] == [("RT001", Severity.INFO)]
    assert found[0].message.startswith("real Ollama 0.33.2 rendered 8 fixtures exactly as predicted via llama.cpp engine")
    assert found[0].message.endswith(OLLAMA_SUFFIX)
    assert set(found[0].evidence["not_comparable"]) == {"typed_content", "no_generation_prompt"}
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    assert calls[0] == ["--version"] and calls[1][:2] == ["create", calls[1][1]] and calls[-1] == ["rm", calls[1][1]]
    assert calls[1][1].startswith("ggufdoctor-tmp-")
    assert len(server.requests) == 8 and ctx.stats["runtime"]["agreed_fixtures"] == 8


def test_disagreeing_runtime_is_a_warn_with_a_labelled_diff(server, fake_ollama):
    cmd, _ = fake_ollama
    _Handler.renderer = staticmethod(lambda body: "SOMETHING ELSE")
    ctx = _ctx()
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is False
    rt = OllamaRuntime(cmd, host=f"http://127.0.0.1:{server.server_address[1]}")
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert all(f.id == "RT001" and f.severity == Severity.WARN for f in found) and found
    assert "rendered differently than ggufdoctor predicted via llama.cpp engine" in found[0].message
    assert found[0].evidence["diff"].startswith("--- predicted (llama.cpp engine)\n+++ ollama 0.33.2")


def test_recognised_template_predicts_from_the_golden(server, fake_ollama):
    from ggufdoctor.ollama import load_goldens, load_index
    cmd, _ = fake_ollama
    chatml = next(t for n, t in load_index() if n == "chatml" and "add_generation_prompt" in t)
    golden = load_goldens()["renders"]["chatml"]
    _Handler.renderer = staticmethod(lambda body: golden[[f.name for f in load_fixtures()
                                     if request_body("m", f) and request_body("m", f)["messages"] == body["messages"]][0]])
    ctx = _ctx(chatml)
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is True
    rt = OllamaRuntime(cmd, host=f"http://127.0.0.1:{server.server_address[1]}")
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert [(f.id, f.severity) for f in found] == [("RT001", Severity.INFO)]
    assert "via registry:chatml" in found[0].message


def test_failed_create_is_an_operator_error(fake_ollama, tmp_path):
    cmd, log = fake_ollama
    log.with_suffix(".fail").write_text("1")
    with pytest.raises(OllamaRuntimeError):
        OllamaRuntime(cmd).create("/tmp/m.gguf")


def test_unreachable_server_is_an_operator_error(fake_ollama):
    cmd, _ = fake_ollama
    ctx = _ctx(); run_ollama_checks(ctx)
    rt = OllamaRuntime(cmd, host="http://127.0.0.1:9")   # discard port: connection refused
    with pytest.raises(OllamaRuntimeError):
        run_runtime_checks(ctx, rt, "/tmp/m.gguf")


def test_engine_unavailable_is_a_coverage_gap_not_a_silent_pass():
    # jinja2 alone cannot stand in for the llama.cpp path Ollama takes on a
    # registry miss, so RT has nothing to predict with. It must say so.
    ctx = _ctx(engines=[Jinja2Engine()])
    run_ollama_checks(ctx)
    calls = []
    rt = OllamaRuntime(["/nonexistent/ollama"], run=lambda *a, **kw: calls.append(a))
    assert run_runtime_checks(ctx, rt, "/tmp/m.gguf") == []
    assert ctx.checks_not_evaluated[-1:] == ["RT001"]
    assert "llama.cpp engine unavailable" in ctx.stats["runtime"]["not_evaluated"]
    assert calls == []   # nothing was created, so nothing needs removing


def test_no_chat_template_is_a_coverage_gap_not_a_warn_storm():
    # Without a template there is no prediction, so every fixture would
    # "differ" from whatever Ollama's own default renders -- eight WARNs
    # blaming a file for a guess ggufdoctor never made.
    ctx = _ctx(template=None)
    run_ollama_checks(ctx)
    rt = OllamaRuntime(["/nonexistent/ollama"], run=lambda *a, **kw: 1 / 0)
    assert run_runtime_checks(ctx, rt, "/tmp/m.gguf") == []
    assert ctx.checks_not_evaluated[-1:] == ["RT001"]
    assert "no chat template" in ctx.stats["runtime"]["not_evaluated"]


def test_cli_runtime_flag_runs_the_family_and_records_it(server, fake_ollama, tmp_path,
                                                        monkeypatch, capsys):
    import shlex

    from ggufdoctor.cli import main
    from tests.test_cli import CHAT_TPL, _model

    llama = LlamaCppEngine()
    _Handler.renderer = staticmethod(lambda body: llama.render(
        CHAT_TPL, {"messages": body["messages"], "tools": body.get("tools"),
                   "bos_token": "<|im_start|>", "eos_token": "<|im_end|>"}).text)
    # The CLI builds its own OllamaRuntime from a single path, so the fake
    # binary (a command *list*) is reached through a one-line shim, and the
    # server address through the documented OLLAMA_HOST route.
    cmd, log = fake_ollama
    shim = tmp_path / "ollama"
    shim.write_text("#!/bin/sh\nexec " + shlex.join(cmd) + ' "$@"\n')
    shim.chmod(0o755)
    monkeypatch.setenv("OLLAMA_HOST", f"127.0.0.1:{server.server_address[1]}")

    js = tmp_path / "r.json"
    assert main([_model(tmp_path), "--runtime", str(shim), "--json", str(js),
                 "--fail-on", "never"]) == 0
    assert "RT001  INFO" in capsys.readouterr().out
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["coverage"]["families_run"][-1] == "RT"
    assert {f["id"] for f in data["findings"]} >= {"RT001"}
    assert [json.loads(l)[0] for l in log.read_text().splitlines()] == ["--version", "create", "rm"]
