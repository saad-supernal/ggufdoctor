"""Richer inputs: tool-call round trip, typed content parts, reasoning history. Same 100 templates as probe.py."""
import json, pathlib, collections, sys
import wasmtime
from wasmtime import Store, Module, Linker, WasiConfig, Engine, Config
from ggufdoctor.engines.jinja2_engine import Jinja2Engine, BASE_CONTEXT
from ggufdoctor.hf import HfClient
HERE = pathlib.Path(__file__).parent
TOOLS = [{"type":"function","function":{"name":"get_weather","description":"Get weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]
RICH = {
 "tool_roundtrip_dictargs": {"messages":[{"role":"system","content":"Be brief."},{"role":"user","content":"Weather in Paris?"},
    {"role":"assistant","content":"","tool_calls":[{"id":"call_1","type":"function","function":{"name":"get_weather","arguments":{"city":"Paris"}}}]},
    {"role":"tool","tool_call_id":"call_1","name":"get_weather","content":"{\"temp_c\": 18}"}], "tools": TOOLS, "add_generation_prompt": True},
 "tool_roundtrip_strargs": {"messages":[{"role":"user","content":"Weather in Paris?"},
    {"role":"assistant","content":None,"tool_calls":[{"id":"call_1","type":"function","function":{"name":"get_weather","arguments":"{\"city\": \"Paris\"}"}}]},
    {"role":"tool","tool_call_id":"call_1","content":"{\"temp_c\": 18}"}], "tools": TOOLS, "add_generation_prompt": True},
 "typed_content": {"messages":[{"role":"user","content":[{"type":"text","text":"Hello"},{"type":"text","text":"there"}]}], "add_generation_prompt": True},
 "reasoning_history": {"messages":[{"role":"user","content":"Hi"},{"role":"assistant","content":"Hello!","reasoning_content":"The user greets me."},{"role":"user","content":"Bye"}], "add_generation_prompt": True},
 "no_gen_prompt": {"messages":[{"role":"user","content":"Hi"},{"role":"assistant","content":"Hello!"}], "add_generation_prompt": False},
}
client = HfClient(); j2 = Jinja2Engine()
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
prev = json.load(open(HERE/"probe-result.json"))
ids = [r["id"] for r in prev["records"]]
tally = collections.Counter(); per_fixture = collections.defaultdict(collections.Counter); out = []
for rid in ids:
    tpl = client.gguf_chat_template(rid)
    if not tpl: continue
    names = list(RICH); ctxs = [{**BASE_CONTEXT, **RICH[n]} for n in names]
    a = [j2.render(tpl, c) for c in ctxs]; b = wasm_batch([{"template": tpl, "context": c} for c in ctxs])
    rec = {"id": rid, "fixtures": {}}
    for n, x, y in zip(names, a, b):
        if x.ok and y["ok"]: v = "same" if x.text == y["text"] else ("ws_only" if x.text.split()==y["text"].split() else "diff")
        elif x.ok: v = "j2_ok_llama_fails"
        elif y["ok"]: v = "llama_ok_j2_fails"
        else: v = "both_fail"
        per_fixture[n][v] += 1
        detail = None
        if v == "j2_ok_llama_fails": detail = y["error"].splitlines()[-1][:150]
        elif v == "llama_ok_j2_fails": detail = x.error[:150]
        elif v == "diff":
            import difflib; detail = "\n".join(list(difflib.unified_diff(x.text.splitlines(), y["text"].splitlines(), "j2", "llama", lineterm="", n=0))[2:8])
        rec["fixtures"][n] = {"v": v, "detail": detail}
    out.append(rec)
    interesting = {n: d for n, d in rec["fixtures"].items() if d["v"] not in ("same","both_fail")}
    if interesting:
        print(f"* {rid}")
        for n, d in interesting.items(): print(f"     {n}: {d['v']}\n        " + (d["detail"] or "").replace("\n", "\n        "))
json.dump({"per_fixture": per_fixture, "records": out}, open(HERE/"probe2-result.json","w"), indent=1)
print("\nPER FIXTURE"); [print(f"  {n:26} {dict(c)}") for n, c in per_fixture.items()]
