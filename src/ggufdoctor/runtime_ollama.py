"""Family RT: ask a real Ollama what it actually renders, and check the
prediction against it.

Every other family in this tool is an *argument* about what a runtime would
do: family X reproduces llama.cpp's Jinja path from a pinned WASM build,
family O replays goldens recorded from Ollama's own Go template package at a
pinned commit. Both are careful reconstructions, and both can be wrong in the
one way a reconstruction always can -- by being right about the code it
copied and wrong about which code the runtime chose to run. `ollama create`
picks between the curated Go template and the GGUF's own Jinja via
`template.Named`, `shouldPreferChatTemplate`, the RENDERER/PARSER directives
and `OLLAMA_GO_TEMPLATE`; a prediction that models the first of those and not
the rest is a prediction, not an observation.

So this family makes no argument at all. It creates a throwaway model from
the GGUF with the operator's own `ollama` binary, POSTs every fixture to
`/api/chat` with `_debug_render_only: true` (Ollama renders the prompt and
returns it in `_debug_info.rendered_template` without loading weights or
generating a token), and compares the bytes against whatever ggufdoctor
predicted for that same file:

* the registry golden for the selected template, when family O said Ollama
  recognises this template (`path = "registry:<name>"`), or
* the bundled llama.cpp engine's render of the GGUF's own Jinja, when it did
  not (`path = "llama.cpp engine"`) -- Ollama's miss case is the Jinja path.

**RT001 INFO** is agreement: the oracle confirms the prediction on every
fixture both sides could express. **RT001 WARN** is disagreement, one finding
per distinct divergence (`collapse_by_signature`), with a diff labelled
`predicted (<path>)` versus `ollama <version>`. It is a WARN and not an ERROR
because a disagreement here does not say the template is broken -- it says
ggufdoctor guessed the wrong *path*, and the message names the three routes
(PreferChatTemplate, RENDERER/PARSER, OLLAMA_GO_TEMPLATE) that do exactly
that. The finding's subject is the prediction, and the operator's Ollama is
the authority.

This never runs by default. It needs `--runtime <path to ollama>`, a local
.gguf, and a server the operator is already running: ggufdoctor never starts
`ollama serve`, and reaching the wrong address or failing to create the model
is an operator-fixable condition (`OllamaRuntimeError` -> "ggufdoctor: ..."
and exit 2), never a finding about the template.

Two fixture shapes never reach the wire, because `api.Message` cannot carry
them: `add_generation_prompt: false` (Ollama has no such concept) and typed
content (`Content` is a Go `string`). They are named in `not_comparable`, the
same coverage fact family O records, rather than silently dropped.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ggufdoctor.checks.common import (collapse_by_signature, divergence_signature, render_diff,
                                      with_real_tokens)
from ggufdoctor.checks.ollama_registry import (NO_GENERATION_PROMPT_REASON, NO_GOLDEN_REASON,
                                               OLLAMA_SUFFIX)
from ggufdoctor.models import CheckContext, Finding, Fixture, RenderResult, Severity
from ggufdoctor.ollama import load_goldens, pin

DEFAULT_HOST = "http://127.0.0.1:11434"
HOST_ENV = "OLLAMA_HOST"
RT_IDS = ["RT001"]
LLAMACPP = "llama.cpp"
ENGINE_PATH = "llama.cpp engine"
NO_ENGINE_REASON = "llama.cpp engine unavailable, cannot predict the native path"
NO_TEMPLATE_REASON = "this GGUF embeds no chat template, so there is nothing to predict"
TYPED_CONTENT_REASON = "Ollama's api.Message cannot represent typed content"

# `ollama create` copies and quantises a whole GGUF, and the first render on a
# fresh model is also the first load of it, so both are minutes-scale on a
# large file. `rm` is a metadata delete. All three exist so a wedged server or
# a hung binary ends the run instead of parking it forever.
CREATE_TIMEOUT = 600
RENDER_TIMEOUT = 600
CLI_TIMEOUT = 60
# Enough of a failed CLI/HTTP response to name the cause, bounded because it
# is text from another process on its way into a one-line error message.
ERROR_TAIL = 400
HTTP_BODY_CHARS = 200


class OllamaRuntimeError(Exception):
    """An operator-fixable condition: no binary, no server, create failed.

    Deliberately not a Finding. "I could not ask Ollama" says nothing about
    the template, so it travels the same route as an unreadable GGUF or an
    unwritable --json path -- the CLI's `except Exception` prints
    "ggufdoctor: ..." and exits 2.
    """


def default_host() -> str:
    return normalise_host(os.environ.get(HOST_ENV) or DEFAULT_HOST)


def normalise_host(raw: str) -> str:
    """`OLLAMA_HOST` is set to bare "host:port" as often as to a URL."""
    host = raw.strip() or DEFAULT_HOST
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/")


def not_sendable_reason(fixture: Fixture) -> str | None:
    """Why `api.Message` cannot carry this fixture, or None if it can.

    Both reasons are properties of Ollama's request type, not of the
    template -- see the module docstring.
    """
    context = fixture.context
    if context.get("add_generation_prompt") is False:
        return NO_GENERATION_PROMPT_REASON
    for message in context.get("messages", []):
        if isinstance(message.get("content"), list):
            return TYPED_CONTENT_REASON
    return None


def _message(message: dict[str, Any]) -> dict[str, Any]:
    """One fixture message as an `api.Message`.

    Unknown keys would be dropped by Go's decoder anyway; mapping them here
    keeps what the server receives equal to what the fixture meant. `content`
    is a Go string, so a null content is sent as "" -- which is what
    llama.cpp's own normaliser does with it too, so the two sides of the
    comparison still see the same conversation.
    """
    out: dict[str, Any] = {"role": message.get("role", ""),
                           "content": message.get("content") or ""}
    if message.get("thinking"):
        out["thinking"] = message["thinking"]
    if message.get("images"):
        out["images"] = message["images"]
    calls = message.get("tool_calls")
    if calls:
        out["tool_calls"] = [
            {"id": call.get("id", ""),
             "function": {"index": i,
                          "name": (call.get("function") or {}).get("name", ""),
                          "arguments": (call.get("function") or {}).get("arguments") or {}}}
            for i, call in enumerate(calls)]
    # api.Message spells the tool's name `tool_name`; the fixture corpus (and
    # the OpenAI shape it follows) spells it `name` on a tool message.
    name = message.get("tool_name") or message.get("name")
    if name and message.get("role") == "tool":
        out["tool_name"] = name
    if message.get("tool_call_id"):
        out["tool_call_id"] = message["tool_call_id"]
    return out


def request_body(model: str, fixture: Fixture) -> dict[str, Any] | None:
    """The `/api/chat` request for one fixture, or None if it is not sendable."""
    if not_sendable_reason(fixture) is not None:
        return None
    context = fixture.context
    body: dict[str, Any] = {
        "model": model,
        "messages": [_message(m) for m in context.get("messages", [])],
        "stream": False,
        # Renders the prompt and returns it in _debug_info without loading
        # weights or generating a token (api/types.go).
        "_debug_render_only": True,
    }
    if "tools" in context:
        body["tools"] = context["tools"]
    if "enable_thinking" in context:
        # `think` is a bool on the request; the fixture's Jinja-side spelling
        # is enable_thinking.
        body["think"] = bool(context["enable_thinking"])
    return body


@dataclass
class OllamaRuntime:
    """The operator's own `ollama`: the binary for create/rm, the server for
    rendering. ggufdoctor never starts a server -- if nothing is listening,
    that is a condition for the operator to fix, not a fact about the file.
    """

    # A list, not a string: nothing here ever goes through a shell, and tests
    # drive a fake binary as [sys.executable, script, log].
    command: list[str]
    host: str = field(default_factory=default_host)
    opener: Callable[..., Any] = urllib.request.urlopen
    run: Callable[..., Any] = subprocess.run

    def __post_init__(self) -> None:
        self.host = normalise_host(self.host)

    def _cli(self, args: list[str], timeout: int) -> Any:
        try:
            return self.run(list(self.command) + args, capture_output=True,
                            text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise OllamaRuntimeError(
                f"`{self.command[0]} {args[0]}` timed out after {timeout}s") from e
        except OSError as e:   # not found, not executable, wrong architecture
            raise OllamaRuntimeError(f"cannot run {self.command[0]}: {e}") from e

    def version(self) -> str:
        proc = self._cli(["--version"], CLI_TIMEOUT)
        text = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        first = text.splitlines()[0].strip() if text else ""
        marker = "ollama version is "
        if marker in first:
            return first.split(marker, 1)[1].strip()
        # An `ollama` that words this differently still has a version; report
        # whatever it said rather than claiming not to know.
        return first or "unknown"

    def create(self, gguf_path: str) -> str:
        """Register the GGUF as a throwaway model and return its name."""
        name = f"ggufdoctor-tmp-{secrets.token_hex(4)}"
        with tempfile.TemporaryDirectory(prefix="ggufdoctor-") as directory:
            modelfile = os.path.join(directory, "Modelfile")
            with open(modelfile, "w", encoding="utf-8") as f:
                f.write(f"FROM {os.path.abspath(gguf_path)}\n")
            proc = self._cli(["create", name, "-f", modelfile], CREATE_TIMEOUT)
        if proc.returncode != 0:
            detail = ((proc.stderr or "") + (proc.stdout or "")).strip()[-ERROR_TAIL:]
            raise OllamaRuntimeError(
                f"`ollama create {name}` failed (exit {proc.returncode}): {detail}")
        return name

    def remove(self, model: str) -> None:
        """Best effort, always: this runs in a `finally`, and a failure to
        clean up must never replace whatever the run was actually reporting.
        """
        try:
            self._cli(["rm", model], CLI_TIMEOUT)
        except Exception:
            pass

    def render(self, model: str, fixture: Fixture) -> RenderResult:
        body = request_body(model, fixture)
        if body is None:   # callers skip these; belt and braces
            return RenderResult(None, f"render:ollama: {not_sendable_reason(fixture)}")
        request = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self.opener(request, timeout=RENDER_TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as e:
            # A 4xx/5xx is Ollama answering -- about this request, so it is a
            # render error, not an unreachable server.
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                detail = ""
            return RenderResult(None, f"render:ollama: {e.code} {detail[:HTTP_BODY_CHARS]}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise OllamaRuntimeError(f"cannot reach Ollama at {self.host}: {e}") from e
        try:
            payload = json.loads(raw)
        except ValueError as e:
            return RenderResult(None, f"render:ollama: response was not JSON: {e}")
        rendered = (payload.get("_debug_info") or {}).get("rendered_template")
        if not isinstance(rendered, str):
            return RenderResult(None, "render:ollama: response carries no _debug_info "
                                      "(does this Ollama support _debug_render_only?)")
        return RenderResult(rendered, None)


def _golden_not_comparable(golden: Any, template: str) -> str | None:
    """Why this fixture's registry golden cannot stand in as a prediction."""
    if golden is None:
        return NO_GOLDEN_REASON
    if isinstance(golden, dict) and "unrepresentable" in golden:
        return ("Ollama's api.Message cannot represent this conversation: "
                f"{golden['unrepresentable']}")
    if isinstance(golden, dict) and "error" in golden:
        return (f"Ollama's curated {template} template fails to render this "
                f"conversation ({golden['error']})")
    if not isinstance(golden, str):
        return NO_GOLDEN_REASON
    return None


def run_runtime_checks(ctx: CheckContext, runtime: OllamaRuntime,
                       gguf_path: str) -> list[Finding]:
    ollama_stats = ctx.stats.get("ollama") or {}
    recognised = bool(ollama_stats.get("recognised"))
    template_name = ollama_stats.get("template")

    def not_evaluated(reason: str) -> list[Finding]:
        # Nothing to compare against. Saying "Ollama agreed" would be a lie
        # and saying nothing would read as a clean run, so an RT that cannot
        # predict is a coverage gap with a stated reason -- never a pile of
        # WARNs blaming the file for a prediction ggufdoctor never made.
        ctx.checks_not_evaluated.extend(RT_IDS)
        ctx.stats["runtime"] = {"not_evaluated": reason}
        return []

    engine = None
    renders: dict[str, Any] = {}
    if recognised:
        # Family O already decided Ollama would serve its curated template
        # for this file; the golden *is* the prediction, so no engine runs.
        path = f"registry:{template_name}"
        renders = load_goldens()["renders"].get(template_name, {})
    else:
        path = ENGINE_PATH
        if not ctx.model.chat_template:
            return not_evaluated(NO_TEMPLATE_REASON)
        engine = next((e for e in ctx.engines
                       if getattr(e, "name", None) == LLAMACPP
                       and getattr(e, "available", True)), None)
        if engine is None:
            return not_evaluated(NO_ENGINE_REASON)

    version = runtime.version()
    model = runtime.create(gguf_path)

    not_comparable: dict[str, str] = {}
    render_errors: dict[str, str] = {}
    differs: list[tuple[str, Any, dict[str, Any]]] = []
    agreed = 0
    try:
        for fx in ctx.fixtures:
            reason = not_sendable_reason(fx)
            if reason is not None:
                not_comparable[fx.name] = reason
                continue
            if recognised:
                golden = renders.get(fx.name)
                reason = _golden_not_comparable(golden, template_name)
                if reason is not None:
                    not_comparable[fx.name] = reason
                    continue
                pred = RenderResult(golden, None)
            else:
                pred = engine.render(ctx.model.chat_template,
                                     with_real_tokens(ctx, fx.context))

            real = runtime.render(model, fx)
            if not real.ok:
                render_errors[fx.name] = real.error
                continue
            if pred.ok and pred.text == real.text:
                agreed += 1
                continue
            # A prediction that failed to render is still a prediction, and
            # the operator needs to see what it was; carrying the error text
            # into the diff says so without pretending it was output.
            pred_text = pred.text if pred.ok else f"<no render: {pred.error}>"
            differs.append((fx.name, divergence_signature(pred_text, real.text),
                            {"diff": render_diff(pred_text, real.text,
                                                 f"predicted ({path})", f"ollama {version}")}))
    finally:
        runtime.remove(model)

    ctx.stats["runtime"] = {"version": version, "predicted_path": path,
                            "agreed_fixtures": agreed,
                            "compared_fixtures": agreed + len(differs)}
    base_evidence = {"ollama_version": version, "predicted_path": path,
                     "not_comparable": not_comparable, "render_errors": render_errors,
                     "agreed_fixtures": agreed, "ollama_commit": pin().commit}

    findings = collapse_by_signature(
        "RT001", Severity.WARN,
        f"real Ollama {version} rendered differently than ggufdoctor predicted via {path}; "
        f"PreferChatTemplate, RENDERER/PARSER or OLLAMA_GO_TEMPLATE may have chosen "
        f"another path{OLLAMA_SUFFIX}",
        [(name, sig, {**base_evidence, **extra}) for name, sig, extra in differs])
    if not differs and agreed:
        findings.append(Finding(
            "RT001", Severity.INFO,
            f"real Ollama {version} rendered {agreed} fixtures exactly as predicted "
            f"via {path}{OLLAMA_SUFFIX}",
            evidence=dict(base_evidence)))
    return findings
