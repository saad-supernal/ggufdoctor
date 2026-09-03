// engine/shim.cpp — reactor-style WASM entry points around llama.cpp's common/jinja engine.
// Mirrors common_chat_template_direct_apply_impl (common/chat.cpp) minus the BOS strip:
//   lex -> parse -> caps_get -> normalise messages -> apply that function's own
//   context handling (enable_thinking, add_generation_prompt, the two caps_apply_*
//   expansions) -> render at a pinned clock.
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
//
// Every path from a request to a rendered prompt in llama.cpp lowers each message
// into a common_chat_msg (common_chat_msgs_parse_oaicompat, common/chat.cpp), whose
// `content` is a std::string, and then serialises it back with
// common_chat_msg::to_json_oaicompat -- which emits `"content": ""` whenever there is
// neither content nor content_parts. So a null (or absent) `content` never reaches a
// template through llama.cpp: it always arrives as an empty string. Templates that
// branch on `message["content"] is string` before iterating it (PaddleOCR-VL does)
// render fine there and die here without this. We port only this one field of the
// round-trip: the rest of it (dropping unknown keys, dropping empty reasoning_content
// / name / tool_call_id, stringifying tool_calls[].function.arguments) is request
// *shaping*, would silently rewrite the caller's context, and showed no divergence
// against the real llama-server over the conformance corpus.

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
    if (!messages.is_array()) {
        return messages;
    }
    const bool only_string = caps.supports_string_content && !caps.supports_typed_content;
    const bool only_typed  = !caps.supports_string_content && caps.supports_typed_content;
    njson out = njson::array();
    for (const auto & msg : messages) {
        njson copy = msg;
        if (!copy.is_object()) {  // a malformed context is the caller's business, not ours
            out.push_back(std::move(copy));
            continue;
        }
        // common_chat_msg::to_json_oaicompat: no content and no content_parts -> "".
        // Deliberately does NOT set `changed`: that flag reports the content-parts
        // normaliser (string <-> typed) to the caller, and the checks layer reads it
        // as "llama.cpp reshaped the content parts before rendering". This is a
        // different rewrite, from message *parsing*, and claiming it under the same
        // flag would misattribute a divergence's cause (ruling R9).
        if (!copy.contains("content") || copy.at("content").is_null()) {
            copy["content"] = "";
        }
        if (only_string || only_typed) {
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
        if (normalize) {
            // The rest of common_chat_template_direct_apply_impl's own context
            // handling. These are not defaults ggufdoctor invents: they are what
            // that function does to every context on its way to the runtime, so a
            // template can never see anything else when llama.cpp renders it.

            // `{"enable_thinking", inputs.enable_thinking}` is set unconditionally,
            // from a generation param that defaults to true (autoparser::
            // generation_params, common/chat.h). There is no llama.cpp path that
            // leaves it undefined; --reasoning-budget 0 makes it false, not absent.
            if (!context.contains("enable_thinking")) {
                context["enable_thinking"] = true;
            }
            // `if (inputs.add_generation_prompt) inp["add_generation_prompt"] = true;`
            // -- so llama.cpp defines the key only when it is on. A template asking
            // `add_generation_prompt is defined` (PaddleOCR-VL does, to default it to
            // true) sees a *missing* key there, never a false one.
            if (context.contains("add_generation_prompt")) {
                if (context.at("add_generation_prompt").is_boolean()
                        ? context.at("add_generation_prompt").get<bool>()
                        : !context.at("add_generation_prompt").is_null()) {
                    context["add_generation_prompt"] = true;
                } else {
                    context.erase("add_generation_prompt");
                }
            }
            // The two caps-driven context expansions, applied to the jinja context
            // before global_from_json. llama.cpp does not invent either key -- the
            // CLI layer does (common_params_parse defaults preserve_reasoning to
            // "true" in common/arg.cpp) -- so we react to it and do not add it.
            if (context.contains("preserve_reasoning") && context.at("preserve_reasoning").is_boolean()) {
                jinja::caps_apply_preserve_reasoning(ctx, context.at("preserve_reasoning").get<bool>());
            }
            if (context.contains("reasoning_effort") && context.at("reasoning_effort").is_string()
                    && !context.at("reasoning_effort").get<std::string>().empty()) {
                jinja::caps_apply_reasoning_effort(ctx, context.at("reasoning_effort").get<std::string>());
            }
        }
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
