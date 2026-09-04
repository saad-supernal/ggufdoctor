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
def renders(monkeypatch):
    """Install the fake server's render function for the duration of one test.

    _Handler.renderer is a class attribute, so assigning it directly leaks
    the previous test's renderer into every test that forgets to set its
    own -- and the failure that causes looks like a bug in the code under
    test, not in the fixture. monkeypatch puts it back.
    """
    def install(fn):
        monkeypatch.setattr(_Handler, "renderer", staticmethod(fn))
    return install


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
# TPL, plus an author's decline that fires on `tool_roundtrip` and nothing
# else -- so the llama.cpp engine (the prediction side) fails on exactly one
# fixture while a server rendering plain TPL answers all of them.
TPL_REFUSES_TOOLS = TPL.replace(
    "{% for turn in messages %}",
    "{% for turn in messages %}{% if turn['role'] == 'tool' %}"
    "{{ raise_exception('this template refuses tool results') }}{% endif %}")


def cmd_of(fake_ollama):
    return fake_ollama[0]


def _host(server):
    return f"http://127.0.0.1:{server.server_address[1]}"


def _ctx(template=TPL, engines=None, custom_corpus=False):
    model = GgufModel(source_id="m.gguf", architecture="llama", chat_template=template,
                      tokens=["<s>", "</s>"], bos_token_id=0, eos_token_id=1)
    return CheckContext(model=model, engines=engines or [Jinja2Engine(), LlamaCppEngine()],
                        fixtures=load_fixtures(), custom_corpus=custom_corpus)


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


def test_agreeing_runtime_yields_one_info_and_cleans_up(server, fake_ollama, renders):
    cmd, log = fake_ollama
    llama = LlamaCppEngine()
    renders(lambda body: llama.render(TPL, {"messages": body["messages"],
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


def test_disagreeing_runtime_is_a_warn_with_a_labelled_diff(server, fake_ollama, renders):
    cmd, _ = fake_ollama
    renders(lambda body: "SOMETHING ELSE")
    ctx = _ctx()
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is False
    rt = OllamaRuntime(cmd, host=f"http://127.0.0.1:{server.server_address[1]}")
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert all(f.id == "RT001" and f.severity == Severity.WARN for f in found) and found
    assert "rendered differently than ggufdoctor predicted via llama.cpp engine" in found[0].message
    assert found[0].evidence["diff"].startswith("--- predicted (llama.cpp engine)\n+++ ollama 0.33.2")


def test_recognised_template_predicts_from_the_golden(server, fake_ollama, renders):
    from ggufdoctor.ollama import load_goldens, load_index
    cmd, _ = fake_ollama
    chatml = next(t for n, t in load_index() if n == "chatml" and "add_generation_prompt" in t)
    golden = load_goldens()["renders"]["chatml"]
    renders(lambda body: golden[[f.name for f in load_fixtures()
                                 if request_body("m", f)
                                 and request_body("m", f)["messages"] == body["messages"]][0]])
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


def test_nothing_compared_is_a_coverage_gap_not_a_clean_run(server, fake_ollama, renders):
    # An Ollama that answers but renders nothing -- the shape of a build
    # without _debug_render_only. Reporting no findings here would read as
    # "agreed with every prediction" on a run that compared nothing.
    renders(lambda body: None)
    ctx = _ctx()
    run_ollama_checks(ctx)
    rt = OllamaRuntime(cmd_of(fake_ollama), host=_host(server))
    assert run_runtime_checks(ctx, rt, "/tmp/m.gguf") == []
    assert ctx.checks_not_evaluated[-1:] == ["RT001"]
    reason = ctx.stats["runtime"]["not_evaluated"]
    assert reason.startswith("no fixture could be compared: real Ollama failed to render")
    assert "_debug_render_only" in reason        # the errors themselves, not just a count
    assert ctx.stats["runtime"]["compared_fixtures"] == 0
    assert len(server.requests) == 8             # it really did ask


def test_recognised_template_without_goldens_is_a_coverage_gap(fake_ollama, monkeypatch):
    import ggufdoctor.runtime_ollama as ro
    from ggufdoctor.ollama import load_index
    chatml = next(t for n, t in load_index() if n == "chatml" and "add_generation_prompt" in t)
    monkeypatch.setattr(ro, "load_goldens", lambda: {"renders": {}})
    ctx = _ctx(chatml)
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is True
    # No server: every fixture is ruled out before anything is sent.
    rt = OllamaRuntime(cmd_of(fake_ollama), host="http://127.0.0.1:9")
    assert run_runtime_checks(ctx, rt, "/tmp/m.gguf") == []
    assert ctx.checks_not_evaluated[-1:] == ["RT001"]
    assert ctx.stats["runtime"]["not_evaluated"] == (
        "no fixture could be compared: no Ollama goldens were recorded for the chatml template")


def test_a_failed_prediction_is_not_reported_as_a_divergence(server, fake_ollama, renders):
    # The prediction side raised; PreferChatTemplate, RENDERER/PARSER and
    # OLLAMA_GO_TEMPLATE had nothing to do with it, so the WARN that names
    # them must not be emitted for this fixture.
    llama = LlamaCppEngine()
    renders(lambda body: llama.render(TPL, {
        "messages": body["messages"], "tools": body.get("tools"),
        "bos_token": "<s>", "eos_token": "</s>",
        **({"enable_thinking": body["think"]} if "think" in body else {})}).text)
    ctx = _ctx(TPL_REFUSES_TOOLS)
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is False
    rt = OllamaRuntime(cmd_of(fake_ollama), host=_host(server))
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert [(f.id, f.severity) for f in found] == [("RT001", Severity.INFO)]
    assert found[0].message.startswith("real Ollama 0.33.2 rendered 7 fixtures exactly as predicted")
    errors = found[0].evidence["prediction_errors"]
    assert list(errors) == ["tool_roundtrip"] and "refuses tool results" in errors["tool_roundtrip"]
    assert "tool_roundtrip" not in found[0].evidence["not_comparable"]
    assert found[0].evidence["render_errors"] == {}
    # Nothing was sent for a fixture there was no prediction to compare against.
    assert len(server.requests) == 7
    assert ctx.stats["runtime"]["compared_fixtures"] == 7


def test_cli_runtime_flag_runs_the_family_and_records_it(server, fake_ollama, tmp_path,
                                                        monkeypatch, renders, capsys):
    import shlex

    from ggufdoctor.cli import main
    from tests.test_cli import CHAT_TPL, _model

    llama = LlamaCppEngine()
    renders(lambda body: llama.render(
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
    out = capsys.readouterr().out
    assert "RT001  INFO" in out
    assert ("  runtime: ollama 0.33.2 agreed with the prediction on 8 of 8 compared "
            "fixtures via llama.cpp engine") in out
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["coverage"]["families_run"][-1] == "RT"
    assert data["coverage"]["runtime"] == {"version": "0.33.2",
                                           "predicted_path": "llama.cpp engine",
                                           "agreed_fixtures": 8, "compared_fixtures": 8,
                                           "not_evaluated": None}
    assert {f["id"] for f in data["findings"]} >= {"RT001"}
    assert [json.loads(l)[0] for l in log.read_text().splitlines()] == ["--version", "create", "rm"]


def test_cli_runtime_not_evaluated_is_not_a_family_that_ran(server, fake_ollama, tmp_path,
                                                            monkeypatch, renders, capsys):
    # The same run as above against an Ollama that renders nothing: RT must
    # be absent from families_run and present in checks_not_evaluated, or the
    # report claims a comparison that never happened.
    import shlex

    from ggufdoctor.cli import main
    from tests.test_cli import _model

    renders(lambda body: None)
    cmd, _ = fake_ollama
    shim = tmp_path / "ollama"
    shim.write_text("#!/bin/sh\nexec " + shlex.join(cmd) + ' "$@"\n')
    shim.chmod(0o755)
    monkeypatch.setenv("OLLAMA_HOST", _host(server))

    js = tmp_path / "r.json"
    assert main([_model(tmp_path), "--runtime", str(shim), "--json", str(js),
                 "--fail-on", "never"]) == 0
    out = capsys.readouterr().out
    assert "RT001 not evaluated" in out and "partial" in out
    data = json.loads(js.read_text(encoding="utf-8"))
    assert "RT" not in data["coverage"]["families_run"]
    assert "RT001" in data["coverage"]["checks_not_evaluated"]
    assert {f["id"] for f in data["findings"]}.isdisjoint({"RT001"})
    # "note: RT001 not evaluated" names the check; the operator also needs
    # the cause, which travels on coverage.runtime and prints as its own line.
    reason = data["coverage"]["runtime"]["not_evaluated"]
    assert reason.startswith("no fixture could be compared: real Ollama failed to render")
    assert "_debug_render_only" in reason
    assert f"  runtime: not evaluated — {reason}" in out
    assert "agreed with the prediction" not in out


# --- Final review round: "O did not evaluate" is not "Ollama would miss" ---


def test_registry_hit_with_unevaluated_goldens_is_a_coverage_gap():
    # `--fixtures custom.json --runtime ollama` on a template Ollama *does*
    # recognise. Family O declines (its goldens were recorded against the
    # bundled corpus), leaving recognised=None. Reading that as a miss sent
    # RT down the llama.cpp path and then blamed PreferChatTemplate /
    # RENDERER/PARSER / OLLAMA_GO_TEMPLATE for a difference that was only
    # ever the wrong path. RT must say it cannot predict this one instead.
    from ggufdoctor.ollama import load_index
    chatml = next(t for n, t in load_index() if n == "chatml" and "add_generation_prompt" in t)
    ctx = _ctx(chatml, custom_corpus=True)
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is None
    assert ctx.stats["ollama"]["not_evaluated"] is not None
    calls = []
    rt = OllamaRuntime(["/nonexistent/ollama"], run=lambda *a, **kw: calls.append(a))
    assert run_runtime_checks(ctx, rt, "/tmp/m.gguf") == []
    assert ctx.checks_not_evaluated[-1:] == ["RT001"]
    reason = ctx.stats["runtime"]["not_evaluated"]
    assert reason.startswith("registry recognised chatml but its goldens were not evaluated (")
    assert reason.endswith("); cannot predict the registry path")
    assert ctx.stats["ollama"]["not_evaluated"] in reason
    assert calls == []                  # no model was created, so none needs removing
    assert ctx.stats["runtime"]["predicted_path"] is None


def test_registry_miss_with_unevaluated_goldens_labels_the_path_honestly(server, fake_ollama,
                                                                         renders):
    # Same decline, a template the registry genuinely misses: llama.cpp is
    # the real path, so RT runs -- but the label has to say on whose
    # authority, because family O never made the call.
    llama = LlamaCppEngine()
    renders(lambda body: llama.render(TPL, {
        "messages": body["messages"], "tools": body.get("tools"),
        "bos_token": "<s>", "eos_token": "</s>",
        **({"enable_thinking": body["think"]} if "think" in body else {})}).text)
    ctx = _ctx(custom_corpus=True)
    run_ollama_checks(ctx)
    assert ctx.stats["ollama"]["recognised"] is None
    rt = OllamaRuntime(cmd_of(fake_ollama), host=_host(server))
    found = run_runtime_checks(ctx, rt, "/tmp/m.gguf")
    assert [(f.id, f.severity) for f in found] == [("RT001", Severity.INFO)]
    path = ctx.stats["runtime"]["predicted_path"]
    assert path.startswith("llama.cpp engine (registry not evaluated: ")
    assert path.endswith(")") and ctx.stats["ollama"]["not_evaluated"] in path
    assert f"via {path}" in found[0].message
    assert found[0].evidence["predicted_path"] == path
