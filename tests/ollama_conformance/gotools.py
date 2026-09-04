"""Build and run engine/ollama/gotools against an Ollama checkout at the pin.

Deselected by default (marker `ollama_conformance`): needs a Go toolchain on
PATH and, on first run, the network (module download and the Ollama fetch).
Set OLLAMA_SRC to reuse an existing checkout at the pinned commit.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
GOTOOLS = ROOT / "engine" / "ollama" / "gotools"
DEFAULT_SRC = ROOT / "engine" / "build" / "ollama"


def ollama_src() -> pathlib.Path:
    src = pathlib.Path(os.environ.get("OLLAMA_SRC", DEFAULT_SRC))
    if not (src / ".git").exists():
        subprocess.run([str(ROOT / "engine" / "ollama" / "fetch-ollama.sh"), str(src)], check=True)
    return src


def ensure_replace(src: pathlib.Path) -> None:
    """Point the module's `replace` target at `src`.

    go.mod replaces github.com/ollama/ollama with engine/build/ollama, so an
    OLLAMA_SRC elsewhere is reached by symlinking it there.
    """
    if src.resolve() != DEFAULT_SRC.resolve():
        DEFAULT_SRC.parent.mkdir(parents=True, exist_ok=True)
        if DEFAULT_SRC.is_symlink() or DEFAULT_SRC.exists():
            if DEFAULT_SRC.is_symlink():
                DEFAULT_SRC.unlink()
            else:
                raise RuntimeError(f"{DEFAULT_SRC} exists and is not a symlink; remove it or unset OLLAMA_SRC")
        DEFAULT_SRC.symlink_to(src.resolve(), target_is_directory=True)


def go() -> str:
    exe = shutil.which("go")
    if not exe:
        raise RuntimeError("go toolchain not on PATH")
    return exe


def run_named(templates: list[str], src: pathlib.Path) -> list[dict]:
    proc = subprocess.run([go(), "run", "./cmd/namedcheck", str(src / "template" / "index.json")],
                          cwd=GOTOOLS, input=json.dumps(templates), text=True,
                          capture_output=True, check=True, timeout=1800)
    return json.loads(proc.stdout)


def run_goldengen(src: pathlib.Path, commit: str) -> dict:
    proc = subprocess.run([go(), "run", "./cmd/goldengen",
                           str(ROOT / "src" / "ggufdoctor" / "ollama_data"),
                           str(ROOT / "src" / "ggufdoctor" / "fixture_data" / "corpus.json"), commit],
                          cwd=GOTOOLS, text=True, capture_output=True, check=True, timeout=1800)
    return json.loads(proc.stdout)
