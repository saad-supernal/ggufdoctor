// Throwaway spike shim: reads a JSON array of jobs on stdin, writes a JSON array of results.
// job: {"template": str, "context": object}
// result: {"ok": true, "text": str} | {"ok": false, "stage": "lexer|parser|raise|render", "error": str}
#include "jinja/lexer.h"
#include "jinja/parser.h"
#include "jinja/runtime.h"
#include "jinja/value.h"
#include "json.h"
#include <nlohmann/json.hpp>
#include <iostream>
#include <iterator>
#include <string>

using njson = nlohmann::ordered_json;

static njson render_one(const std::string & tmpl, const std::string & ctx_json) {
    njson out;
    try {
        jinja::lexer lexer;
        jinja::lexer_result lexed;
        jinja::program prog;
        try {
            lexed = lexer.tokenize(tmpl);
        } catch (const std::exception & e) { out["ok"] = false; out["stage"] = "lexer"; out["error"] = e.what(); return out; }
        try {
            prog = jinja::parse_from_tokens(lexed);
        } catch (const std::exception & e) { out["ok"] = false; out["stage"] = "parser"; out["error"] = e.what(); return out; }
        jinja::context ctx(lexed.source);
        ctx.current_time = 1767225600; // 2026-01-01T00:00:00Z, matches ggufdoctor PINNED_NOW
        common_json inp = common_json::parse(ctx_json);
        jinja::global_from_json(ctx, inp, false);
        jinja::runtime rt(ctx);
        const jinja::value results = rt.execute(prog);
        auto parts = jinja::runtime::gather_string_parts(results);
        out["ok"] = true;
        out["text"] = parts->as_string().str();
    } catch (const jinja::raised_exception & e) {
        out["ok"] = false; out["stage"] = "raise"; out["error"] = e.what();
    } catch (const std::exception & e) {
        out["ok"] = false; out["stage"] = "render"; out["error"] = e.what();
    }
    return out;
}

int main() {
    std::string in((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    njson jobs = njson::parse(in);
    njson results = njson::array();
    for (auto & job : jobs) {
        results.push_back(render_one(job["template"].get<std::string>(), job["context"].dump()));
    }
    std::cout << results.dump() << std::endl;
    return 0;
}
