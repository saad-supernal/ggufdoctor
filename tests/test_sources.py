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
