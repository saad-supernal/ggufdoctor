#!/bin/sh
# Throwaway spike build recipe (2026-09-03). Not the production build.
# Inputs: llama.cpp common/jinja/*.{h,cpp}, common/{json,unicode}.{h,cpp} at commit 67a17c17 (b10775),
#         vendor/nlohmann/json.hpp under include/nlohmann/, ggml-stub.h as include/ggml.h,
#         wasi-sdk-34 (clang 23.1.0), see https://github.com/WebAssembly/wasi-sdk/blob/main/CppExceptions.md
set -e
WS=${WASI_SDK:-./wasi-sdk-34.0-arm64-macos}
SR=$WS/share/wasi-sysroot
SRCS="shim.cpp jinja/lexer.cpp jinja/parser.cpp jinja/runtime.cpp jinja/value.cpp jinja/string.cpp jinja/caps.cpp common/json.cpp common/unicode.cpp"
# NOTE: do not add -Ijinja: jinja/string.h would shadow the C <string.h>.
$WS/bin/clang++ --target=wasm32-wasip1 -std=c++17 -Oz \
  -fwasm-exceptions -mllvm -wasm-use-legacy-eh=false -Wl,-mllvm,-wasm-use-legacy-eh=false \
  -Wl,--strip-all -I. -Iinclude -Icommon -L$SR/lib/wasm32-wasip1/eh $SRCS -lunwind -o shim-oz.wasm
ls -la shim-oz.wasm
