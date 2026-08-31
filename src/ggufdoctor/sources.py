from __future__ import annotations

import os

from ggufdoctor.hf import HfClient
from ggufdoctor.models import Coverage, GgufModel
from ggufdoctor.reader import read_gguf_file


def is_repo_id(target: str) -> bool:
    """True when `target` looks like a Hugging Face repo id rather than a path.

    Anything that already exists on disk is a local path, full stop -- that
    check comes first specifically so a real file or directory is never
    mistaken for a repo id no matter what its name looks like. Otherwise a
    repo id has the "namespace/name" shape and doesn't look like a filesystem
    reference (no leading '.', '/', or '~', and no '.gguf' suffix).
    """
    if os.path.exists(target):
        return False
    return ("/" in target and not target.startswith((".", "/", "~"))
            and not target.endswith(".gguf"))


def resolve(target: str, compare_upstream: str | None = None,
            client: object | None = None) -> tuple[GgufModel, str | None, Coverage]:
    """Load a GgufModel from `target` and (optionally) an upstream template.

    `target` is either a local .gguf path or a Hugging Face repo id
    (distinguished by `is_repo_id`). Family S (self-contained sanity checks)
    always runs. Family R (comparison against an upstream source template)
    only runs -- and only touches the network -- when the caller supplies
    `compare_upstream`, or when `target` is itself a repo id whose upstream
    base model can be discovered. This is what keeps a plain local-file run
    fully offline: no HfClient is constructed, let alone used, unless one of
    those two things is true.
    """
    families = ["S"]

    if is_repo_id(target):
        hf = client or HfClient()
        info = hf.model_info(target)
        gg = (info or {}).get("gguf") or {}
        model = GgufModel(source_id=target,
                          architecture=gg.get("architecture"),
                          chat_template=gg.get("chat_template"))
        base = compare_upstream or hf.base_model_of(info)
        if not base:
            return model, None, Coverage("no_base_model", families)
        upstream, why = hf.upstream_template(base)
        if why == "ok":
            families.append("R")
        return model, upstream, Coverage(why, families)

    model = read_gguf_file(target)
    if compare_upstream is None:
        return model, None, Coverage("not_requested", families)

    hf = client or HfClient()
    upstream, why = hf.upstream_template(compare_upstream)
    if why == "ok":
        families.append("R")
    return model, upstream, Coverage(why, families)
