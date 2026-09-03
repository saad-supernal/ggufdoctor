import json, time, pathlib, collections, sys
import wasmtime
from wasmtime import Store, Module, Linker, WasiConfig, Engine, Config
from ggufdoctor.engines.jinja2_engine import Jinja2Engine, BASE_CONTEXT
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.hf import HfClient
from ggufdoctor.survey import sample_repos
HERE = pathlib.Path(__file__).parent
client = HfClient(); fixtures = load_fixtures(); j2 = Jinja2Engine()
cfg = Config(); cfg.wasm_exceptions = True; eng = Engine(cfg)
mod = Module.from_file(eng, str(HERE / "shim-oz.wasm")); linker = Linker(eng); linker.define_wasi()
def wasm_batch(jobs):
    (HERE/"pin.json").write_text(json.dumps(jobs)); store = Store(eng)
    wc = WasiConfig(); wc.stdin_file=str(HERE/"pin.json"); wc.stdout_file=str(HERE/"pout.json"); wc.inherit_stderr(); store.set_wasi(wc)
    inst = linker.instantiate(store, mod)
    try: inst.exports(store)["_start"](store)
    except wasmtime.ExitTrap as e:
        if e.code: return [{"ok":False,"stage":"crash","error":f"exit {e.code}"}]*len(jobs)
    return json.loads((HERE/"pout.json").read_text())
repos = sample_repos(client, int(sys.argv[1]), 2)
print(len(repos), "repos sampled")
tally = collections.Counter(); records = []
for r in repos:
    rid = r["id"] if isinstance(r, dict) else r
    try: tpl = client.gguf_chat_template(rid)
    except Exception as e: tally["fetch_error"] += 1; continue
    if not tpl: tally["no_template"] += 1; continue
    ctxs = [{**BASE_CONTEXT, **f.context} for f in fixtures]
    a = [j2.render(tpl, c) for c in ctxs]; b = wasm_batch([{"template": tpl, "context": c} for c in ctxs])
    rec = {"id": rid, "fixtures": {}}
    for f, x, y in zip(fixtures, a, b):
        if x.ok and y["ok"]: v = "same" if x.text == y["text"] else ("ws_only" if x.text.split()==y["text"].split() else "diff")
        elif x.ok: v = "j2_ok_llama_fails"
        elif y["ok"]: v = "llama_ok_j2_fails"
        else: v = "both_fail"
        rec["fixtures"][f.name] = v if v not in ("j2_ok_llama_fails","llama_ok_j2_fails") else (v, (y["error"] if v.startswith("j2") else x.error).splitlines()[-1][:140])
    kinds = {v if isinstance(v,str) else v[0] for v in rec["fixtures"].values()}
    key = "all_same" if kinds == {"same"} else ("same_or_both_fail" if kinds <= {"same","both_fail"} else "|".join(sorted(k for k in kinds if k not in ("same","both_fail"))))
    tally[key] += 1; rec["class"] = key; records.append(rec)
    if key not in ("all_same","same_or_both_fail"):
        print(f"* {rid}: {key}")
        for fn, v in rec["fixtures"].items():
            if v not in ("same","both_fail"): print(f"     {fn}: {v}")
        tpl_path = HERE/"divergent"/(rid.replace("/","__")+".jinja"); tpl_path.parent.mkdir(exist_ok=True); tpl_path.write_text(tpl)
json.dump({"tally": tally, "records": records}, open(HERE/"probe-result.json","w"), indent=1)
print("\nTALLY", dict(tally))
