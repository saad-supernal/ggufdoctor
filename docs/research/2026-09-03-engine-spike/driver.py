"""Throwaway spike driver: Jinja2Engine (transformers-faithful) vs llama.cpp common/jinja compiled to WASM."""
import json, sys, time, difflib, importlib.util, pathlib
import wasmtime
from wasmtime import Store, Module, Linker, WasiConfig, Engine, Config
from ggufdoctor.engines.jinja2_engine import Jinja2Engine, BASE_CONTEXT
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.hf import HfClient

HERE = pathlib.Path(__file__).parent
REPO = pathlib.Path("/Users/saad/Silvergrain/Agent Tools/ggufdoctor")
spec = importlib.util.spec_from_file_location("tcs", REPO / "tests/test_checks_sanity.py")
tcs = importlib.util.module_from_spec(spec); spec.loader.exec_module(tcs)

templates = {
    "chatml_min": tcs.CHAT_TPL, "mistral_v02": tcs.MISTRAL_V02_TPL, "llama2_chat": tcs.LLAMA2_CHAT_TPL,
    "gemma2": tcs.GEMMA2_TPL, "llama3_tools": tcs.LLAMA3_TOOLS_TPL,
}
live = {}
client = HfClient()
for label, repo in [("qwen25_3b_gguf", "Qwen/Qwen2.5-3B-Instruct-GGUF"), ("qwen3coder_unsloth_gguf", "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF")]:
    try:
        t = client.gguf_chat_template(repo)
        if t: live[label] = t
        else: print("no gguf template for", repo)
    except Exception as e: print("fetch failed", repo, type(e).__name__, e)
for label, repo in [("qwen25_3b_upstream", "Qwen/Qwen2.5-3B-Instruct"), ("qwen3coder_upstream", "Qwen/Qwen3-Coder-30B-A3B-Instruct")]:
    try:
        t, reason = client.upstream_template(repo)
        if t: live[label] = t
        else: print("no upstream template", repo, reason)
    except Exception as e: print("fetch failed", repo, type(e).__name__, e)
templates.update(live)
json.dump(templates, open(HERE / "templates-used.json", "w"), indent=1)

fixtures = load_fixtures()
j2 = Jinja2Engine()

cfg = Config(); cfg.wasm_exceptions = True
eng = Engine(cfg)
t0 = time.perf_counter(); mod = Module.from_file(eng, str(HERE / "shim-oz.wasm")); t_compile = time.perf_counter() - t0
linker = Linker(eng); linker.define_wasi()

def wasm_render_batch(jobs):
    (HERE / "in.json").write_text(json.dumps(jobs))
    store = Store(eng)
    wc = WasiConfig(); wc.stdin_file = str(HERE / "in.json"); wc.stdout_file = str(HERE / "out.json"); wc.inherit_stderr()
    store.set_wasi(wc)
    inst = linker.instantiate(store, mod)
    try: inst.exports(store)["_start"](store)
    except wasmtime.ExitTrap as e:
        if e.code != 0: return [{"ok": False, "stage": "crash", "error": f"exit {e.code}"}] * len(jobs)
    return json.loads((HERE / "out.json").read_text())

print(f"wasm module JIT compile: {t_compile*1000:.0f} ms")
summary = {}
for name, tpl in templates.items():
    ctxs = [{**BASE_CONTEXT, **f.context} for f in fixtures]
    t0 = time.perf_counter(); j2_res = [j2.render(tpl, c) for c in ctxs]; t_j2 = time.perf_counter() - t0
    t0 = time.perf_counter(); w_res = wasm_render_batch([{"template": tpl, "context": c} for c in ctxs]); t_w = time.perf_counter() - t0
    print(f"\n=== {name}   jinja2 {t_j2*1000:.1f} ms / 7   wasm(instantiate+7 renders) {t_w*1000:.1f} ms")
    for f, a, b in zip(fixtures, j2_res, w_res):
        if a.ok and b["ok"]:
            if a.text == b["text"]: verdict = "SAME"
            elif a.text.split() == b["text"].split(): verdict = "WS-ONLY"
            else: verdict = "DIFF"
        elif a.ok and not b["ok"]: verdict = f"J2 ok / WASM {b['stage']}: {b['error'].splitlines()[-1][:110]}"
        elif not a.ok and b["ok"]: verdict = f"J2 {a.error[:60]} / WASM ok"
        else: verdict = f"both fail: J2 {a.error[:50]!r} | WASM {b['stage']}: {b['error'].splitlines()[-1][:80]}"
        print(f"  {f.name:15} {verdict}")
        summary.setdefault(verdict.split()[0], 0); summary[verdict.split()[0]] += 1
        if verdict == "DIFF":
            for line in list(difflib.unified_diff(a.text.splitlines(), b["text"].splitlines(), "jinja2", "llama.cpp", lineterm="", n=0))[:14]:
                print("      " + line[:160])
print("\nSUMMARY", summary)
