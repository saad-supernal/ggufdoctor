// engine/shim.cpp — reactor-style WASM entry points around llama.cpp's common/jinja engine.
// Mirrors common_chat_template_direct_apply_impl (common/chat.cpp) minus the BOS strip:
//   lex -> parse -> caps_get -> normalise messages -> render at a pinned clock.
// JSON in, JSON out, through linear memory. Never lets a C++ exception escape.
#include "jinja/caps.h"
#include "jinja/lexer.h"
#include "jinja/parser.h"
#include "jinja/runtime.h"
#include "jinja/value.h"
#include "json.h"
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <cstring>
#include <string>

using njson = nlohmann::ordered_json;

// 2026-01-01T00:00:00Z; must equal ggufdoctor.engines.jinja2_engine.PINNED_NOW.
static const std::time_t PINNED_NOW = 1767225600;
static const char * RAISE_MARKER = "Jinja Exception: ";

static std::string g_out;

// ---- port of messages_inp_normalizer from common/chat.cpp (keep in sync on every engine bump) ----

static std::string concat_content_parts(const njson & parts) {
    std::string text;
    bool last_was_media_marker = false;
    for (const auto & part : parts) {
        std::string type = part.value("type", "");
        bool add_new_line = true;
        if (type == "text") {
            add_new_line = !last_was_media_marker && !text.empty();
            last_was_media_marker = false;
        } else if (type == "media_marker") {
            add_new_line = false;
            last_was_media_marker = true;
        } else {
            continue; // chat.cpp logs a warning and drops unknown part types
        }
        if (add_new_line) {
            text += '\n';
        }
        text += part.value("text", "");
    }
    return text;
}

static njson normalize_messages(const njson & messages, const jinja::caps & caps, bool & changed) {
    changed = false;
    const bool only_string = caps.supports_string_content && !caps.supports_typed_content;
    const bool only_typed  = !caps.supports_string_content && caps.supports_typed_content;
    if ((!only_string && !only_typed) || !messages.is_array()) {
        return messages;
    }
    njson out = njson::array();
    for (const auto & msg : messages) {
        njson copy = msg;
        if (copy.contains("content")) {
            njson & it = copy.at("content");
            if (only_typed && it.is_string()) {
                it = njson::array({ njson{{"type", "text"}, {"text", it.get<std::string>()}} });
                changed = true;
            } else if (only_string && it.is_array()) {
                it = concat_content_parts(it);
                changed = true;
            }
        }
        out.push_back(std::move(copy));
    }
    return out;
}

// ---- rendering ----

static njson caps_to_json(const jinja::caps & caps) {
    njson out = njson::object();
    for (const auto & kv : caps.to_map()) {
        out[kv.first] = kv.second;
    }
    return out;
}

static njson render_job(const std::string & job_text) {
    njson out;
    njson caps_json = njson::object();
    bool normalized = false;
    try {
        njson job = njson::parse(job_text);
        const std::string tmpl = job.at("template").get<std::string>();
        const bool normalize = job.value("normalize", true);
        njson context = job.contains("context") ? job.at("context") : njson::object();

        jinja::lexer lexer;
        jinja::lexer_result lexed;
        jinja::program prog;
        try {
            lexed = lexer.tokenize(tmpl);
        } catch (const std::exception & e) {
            return njson{{"ok", false}, {"stage", "lexer"}, {"error", e.what()}};
        }
        try {
            prog = jinja::parse_from_tokens(lexed);
        } catch (const std::exception & e) {
            return njson{{"ok", false}, {"stage", "parser"}, {"error", e.what()}};
        }

        jinja::caps caps = jinja::caps_get(prog);
        caps_json = caps_to_json(caps);
        if (normalize && context.contains("messages")) {
            context["messages"] = normalize_messages(context.at("messages"), caps, normalized);
        }

        jinja::context ctx(lexed.source);
        ctx.current_time = PINNED_NOW;
        common_json inp = common_json::parse(context.dump());
        jinja::global_from_json(ctx, inp, false);

        jinja::runtime rt(ctx);
        const jinja::value results = rt.execute(prog);
        auto parts = jinja::runtime::gather_string_parts(results);
        out = njson{{"ok", true}, {"text", parts->as_string().str()}};
    } catch (const std::exception & e) {
        // raise_exception() throws "Jinja Exception: <author message>", which the
        // runtime re-wraps with source location. Recover the author's message.
        const std::string what = e.what();
        const size_t at = what.find(RAISE_MARKER);
        if (at != std::string::npos) {
            out = njson{{"ok", false}, {"stage", "raise"}, {"error", what.substr(at + std::strlen(RAISE_MARKER))}};
        } else {
            out = njson{{"ok", false}, {"stage", "render"}, {"error", what}};
        }
    } catch (...) {
        out = njson{{"ok", false}, {"stage", "render"}, {"error", "unknown non-standard exception"}};
    }
    out["caps"] = caps_json;
    out["normalized"] = normalized;
    return out;
}

extern "C" {

__attribute__((export_name("gd_alloc")))
char * gd_alloc(size_t n) { return static_cast<char *>(malloc(n)); }

__attribute__((export_name("gd_free")))
void gd_free(char * p) { free(p); }

__attribute__((export_name("gd_out_len")))
size_t gd_out_len() { return g_out.size(); }

__attribute__((export_name("gd_render")))
const char * gd_render(const char * in, size_t len) {
    try {
        g_out = render_job(std::string(in, len)).dump();
    } catch (...) {
        g_out = "{\"ok\":false,\"stage\":\"render\",\"error\":\"shim failure while serialising result\"}";
    }
    return g_out.c_str();
}

} // extern "C"
