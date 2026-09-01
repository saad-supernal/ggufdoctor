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
    repo id has the "namespace/name" shape: no leading '.', '/', or '~', no
    '.gguf' suffix, and *exactly* two '/'-separated segments -- a nested
    relative path like "does/not/exist" or "org/sub/repo" has more than
    that and is never mistaken for one.

    Two segments alone isn't enough, though: a mistyped local path such as
    "models/foo" has exactly that shape too, and treating it as a repo id
    would send a typo to the network instead of reporting a clear local
    file-not-found. So when the first segment exists on disk as its own
    entry (a real "models" directory sitting right there), that's a local
    reference whose second component just doesn't exist yet -- never a
    namespace on the Hub -- and resolving it locally (letting the caller's
    file open fail with its own clear error) is the safer default.
    """
    if os.path.exists(target):
        return False
    if target.startswith((".", "/", "~")) or target.endswith(".gguf"):
        return False
    segments = target.split("/")
    if len(segments) != 2 or not all(segments):
        return False
    return not os.path.exists(segments[0])


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
        if not base or base.lower() == target.lower():
            # Mirrors survey.py's guard: a repo can't be its own upstream --
            # comparing a template against itself always scores "identical"
            # and would silently misreport a self-referential base_model tag
            # as a clean, verified comparison instead of no comparison at
            # all.
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
