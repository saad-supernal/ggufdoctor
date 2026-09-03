"""Fetch, start and query the real `llama-server` at the pinned build tag.

This module owns every process and download concern for the conformance
suite; the comparison itself lives in test_llama_server.py. Nothing here is
imported by the default test run -- the whole package is deselected by the
`conformance` marker.
"""
from __future__ import annotations

import json
import os
import pathlib
import platform
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile

BUILD_TAG = "b10775"
CACHE = pathlib.Path(os.environ.get("GGUFDOCTOR_CONFORMANCE_CACHE",
                                    pathlib.Path.home() / ".cache" / "ggufdoctor-conformance")) / BUILD_TAG
MODEL_URL = "https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf"
# The tiny model's own special tokens; llama-server passes these to the template.
MODEL_BOS, MODEL_EOS = "<s>", "</s>"


def _release_asset() -> str:
    sysname, machine = platform.system(), platform.machine().lower()
    if sysname == "Linux" and machine in ("x86_64", "amd64"):
        return f"llama-{BUILD_TAG}-bin-ubuntu-x64.tar.gz"
    if sysname == "Darwin" and machine == "arm64":
        return f"llama-{BUILD_TAG}-bin-macos-arm64.tar.gz"
    if sysname == "Windows" and machine in ("x86_64", "amd64"):
        return f"llama-{BUILD_TAG}-bin-win-cpu-x64.zip"
    raise RuntimeError(f"no llama.cpp release asset for {sysname}/{machine}; set GGUFDOCTOR_LLAMA_SERVER")


def _download(url: str, dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    return dest


def server_binary() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_LLAMA_SERVER")
    if override:
        return pathlib.Path(override)
    asset = _release_asset()
    archive = _download(f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD_TAG}/{asset}",
                        CACHE / asset)
    extracted = CACHE / "bin"
    if not extracted.exists():
        extracted.mkdir(parents=True)
        if asset.endswith(".zip"):
            zipfile.ZipFile(archive).extractall(extracted)
        else:
            tarfile.open(archive).extractall(extracted)
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    found = next(extracted.rglob(name), None)
    if found is None:
        raise RuntimeError(f"{name} not found in {archive}")
    found.chmod(0o755)
    return found


def model_path() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_CONFORMANCE_MODEL")
    if override:
        return pathlib.Path(override)
    return _download(MODEL_URL, CACHE / "stories260K.gguf")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LlamaServer:
    def __init__(self, template_path: pathlib.Path):
        self.template_path = template_path
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None

    def __enter__(self):
        binary, model = server_binary(), model_path()
        env = dict(os.environ)
        # the release tarballs put shared libs next to the binary
        env["LD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = str(binary.parent) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
        self.proc = subprocess.Popen(
            [str(binary), "-m", str(model), "--jinja", "--chat-template-file", str(self.template_path),
             # With prefill on (the default), oaicompat_chat_params_parse sets
             # continue_final_message=AUTO whenever the last message is an assistant
             # one, and common_chat_templates_apply_jinja then renders messages[:-1]
             # plus a generation prompt and appends that message's content verbatim.
             # That is a serving policy for resuming a half-finished turn, not chat
             # template application -- the template never sees the last message. A
             # rendering engine has no analogue, so we ask the oracle the question we
             # actually ask it: apply this template to this whole conversation.
             "--no-prefill-assistant",
             "--host", "127.0.0.1", "--port", str(self.port), "-c", "512", "--no-webui", "--log-disable"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server exited: " + self.proc.stderr.read().decode(errors="replace")[-2000:])
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1) as r:
                    if r.status == 200:
                        return self
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("llama-server did not become healthy in 60s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def apply_template(self, body: dict) -> str:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/apply-template",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["prompt"]
