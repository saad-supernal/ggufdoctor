#pragma once
#include <cstdio>
#include <cstdlib>
#define GGML_ASSERT(x) do { if (!(x)) { fprintf(stderr, "GGML_ASSERT(%s) failed at %s:%d\n", #x, __FILE__, __LINE__); abort(); } } while (0)
