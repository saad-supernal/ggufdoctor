"""Fetch, start and query the real `llama-server` at the pinned build tag.

This module owns every process and download concern for the conformance
suite; the comparison itself lives in test_llama_server.py. Nothing here is
imported by the default test run -- the whole package is deselected by the
`conformance` marker.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import shutil
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

# The model repo is pinned by commit, not by `main`: a moving ref means the
# oracle's vocabulary -- and therefore the bos/eos every rendered prompt
# carries -- can change under a test that asserts byte equality, with nothing
# in the repo recording which bytes it was pinned to.
MODEL_REVISION = "499bc8821c6b12b4e53c5bffcb21ec206f212d81"
MODEL_URL = (f"https://huggingface.co/ggml-org/models/resolve/{MODEL_REVISION}"
             "/tinyllamas/stories260K.gguf")

# sha256 of every file this helper downloads, keyed by the name it is cached
# under. This suite fetches an archive from the public internet, unpacks it and
# *executes* the binary inside it, so the download is pinned by content and not
# only by URL: a replaced release asset, a hijacked CDN response or a poisoned
# cache directory is refused instead of run.
#
# Computed on 2026-09-03 by downloading each asset once from the canonical URL
# below (`shasum -a 256`). To refresh after a BUILD_TAG or MODEL_REVISION bump,
# see "Bumping the pin" in engine/README.md.
SHA256 = {
    "llama-b10775-bin-ubuntu-x64.tar.gz":
        "faac52e16e5749713d33531ab7e4161fd0f09e7f2dccb4ed7527162d4c3bd103",
    "llama-b10775-bin-macos-arm64.tar.gz":
        "cd91a87f6e00dddeab16469cf5fc3bf09ee535705a0d09e8cd2e8ef7da4d2cac",
    "llama-b10775-bin-win-cpu-x64.zip":
        "1da037557b6bb588fc48a8d371b948ed6c4334831f23af8a0b084319e7e81a9b",
    "stories260K.gguf":
        "270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d",
}

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


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: pathlib.Path) -> pathlib.Path:
    """Fetch `url` to `dest` if absent, then verify it against SHA256.

    The digest is checked on every call, not only after a fresh download: CI
    restores this directory from a cache key, so a cached file has to earn the
    same trust a new one does. A mismatch deletes the file -- leaving it in
    place would mean the next run reuses a copy that just failed -- and raises,
    before anything is unpacked or executed. An asset with no entry in SHA256
    raises KeyError rather than being fetched unverified.
    """
    expected = SHA256[dest.name]
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    actual = _sha256(dest)
    if actual != expected:
        dest.unlink()
        raise RuntimeError(f"{dest.name}: sha256 {actual} does not match the pinned "
                           f"{expected} — refusing to use it (deleted; re-run to re-fetch)")
    return dest


def _extract_zip(archive: pathlib.Path, target: pathlib.Path) -> None:
    """zipfile has no `filter="data"`, so do that filter's job by hand: reject
    any member whose resolved destination would land outside `target` (an
    absolute path, a `..` segment, a Windows drive letter) instead of trusting
    the archive's own member names. Checked for every member before a single
    one is written, so a hostile archive cannot half-extract.
    """
    root = target.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            dest = (root / member.filename).resolve()
            if dest != root and root not in dest.parents:
                raise RuntimeError(f"{archive.name}: member {member.filename!r} "
                                   f"resolves outside {target}")
        zf.extractall(target)


def server_binary() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_LLAMA_SERVER")
    if override:
        # A path the user handed us: their own build, their own trust decision.
        # Nothing is downloaded, so there is no pinned digest to check.
        return pathlib.Path(override)
    asset = _release_asset()
    archive = _download(f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD_TAG}/{asset}",
                        CACHE / asset)
    extracted = CACHE / "bin"
    if not extracted.exists():
        # Unpack into a staging directory and rename: a run interrupted
        # mid-extraction must not leave a half-populated `bin` that the next
        # one treats as complete.
        staging = CACHE / "bin.part"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        if asset.endswith(".zip"):
            _extract_zip(archive, staging)
        else:
            # filter="data" refuses absolute/traversing paths, device nodes,
            # links pointing outside the tree and setuid bits.
            with tarfile.open(archive) as tf:
                tf.extractall(staging, filter="data")
        staging.replace(extracted)
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    found = next(extracted.rglob(name), None)
    if found is None:
        raise RuntimeError(f"{name} not found in {archive}")
    found.chmod(0o755)
    return found


def model_path() -> pathlib.Path:
    override = os.environ.get("GGUFDOCTOR_CONFORMANCE_MODEL")
    if override:
        return pathlib.Path(override)   # user-supplied, like GGUFDOCTOR_LLAMA_SERVER
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
