from ggufdoctor.sources import is_repo_id, resolve
from tests.helpers.gguf_builder import build_gguf


def test_repo_id_detection():
    assert is_repo_id("unsloth/Qwen3-8B-GGUF")
    assert not is_repo_id("./model.gguf")
    assert not is_repo_id("/abs/model.gguf")


def test_local_resolve_is_offline(tmp_path, monkeypatch):
    import urllib.request

    def explode(*a, **k):
        raise AssertionError("network access during local run")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p))
    assert model.architecture == "llama"
    assert upstream is None
    assert coverage.upstream == "not_requested"
    assert coverage.families_run == ["S"]


def test_local_with_compare_upstream_runs_r_family(tmp_path):
    class FakeClient:
        def upstream_template(self, repo):
            return "{{ 'up' }}", "ok"

    p = tmp_path / "m.gguf"
    p.write_bytes(build_gguf({"general.architecture": ("string", "llama"),
                              "tokenizer.chat_template": ("string", "{{ 'x' }}")}))
    model, upstream, coverage = resolve(str(p), compare_upstream="Qwen/Qwen3-8B",
                                        client=FakeClient())
    assert upstream == "{{ 'up' }}"
    assert coverage.families_run == ["S", "R"]
    assert coverage.upstream == "ok"


# --- Fix round 1 ---

def test_multi_segment_path_is_not_a_repo_id():
    # A real Hub repo id is always exactly "namespace/name". Three or more
    # segments is a nested path shape no repo id ever has -- e.g. a typo'd
    # relative path like "does/not/exist" -- and must never be sent to the
    # network as though it might be one.
    assert not is_repo_id("org/sub/repo")
    assert not is_repo_id("does/not/exist")


def test_nonexistent_path_under_an_existing_local_directory_is_not_a_repo_id(
        tmp_path, monkeypatch):
    # "models/foo" has the same two-segment shape as a real repo id, but if
    # a "models" directory genuinely exists relative to where the tool is
    # run, that's overwhelmingly a mistyped local reference (the file inside
    # it doesn't exist yet), not a Hub namespace -- resolving locally so the
    # caller reports a clear local file-not-found is the safer default.
    monkeypatch.chdir(tmp_path)

    # Before any "checkpoints" directory exists, "checkpoints/model" is a
    # perfectly plausible two-segment repo id shape, same as
    # "unsloth/Qwen3-8B-GGUF" -- nothing local shadows it yet.
    assert is_repo_id("checkpoints/model")

    (tmp_path / "models").mkdir()
    assert not is_repo_id("models/foo")

    # Once a same-named local directory shows up, the same string flips to
    # local -- the directory's mere existence is the signal, regardless of
    # whether the specific file inside it exists.
    (tmp_path / "checkpoints").mkdir()
    assert not is_repo_id("checkpoints/model")


def test_existing_local_path_is_never_a_repo_id(tmp_path):
    d = tmp_path / "myorg" / "myrepo"
    d.mkdir(parents=True)
    assert not is_repo_id(str(d))
