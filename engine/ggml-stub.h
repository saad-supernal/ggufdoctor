/* engine/ggml-stub.h — common/json.cpp includes ggml.h only for GGML_ASSERT. */
#pragma once
#include <stdio.h>
#include <stdlib.h>
#define GGML_ASSERT(x) do { if (!(x)) { fprintf(stderr, "GGML_ASSERT(%s) failed at %s:%d\n", #x, __FILE__, __LINE__); abort(); } } while (0)
