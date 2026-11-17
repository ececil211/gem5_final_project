#include <stdio.h>
#include <stddef.h>
// gem5 magic instructions, lets us reset/dump stats around just the kernel
#include <gem5/m5ops.h>
#ifdef VECTOR_BINARY
// header file for RISC-V vector extension
#include <riscv_vector.h>
#endif

// array size, set with -DN=... (2048 fits L1D, 16384 fits L2, 65536 spills to DRAM)
#ifndef N
#define N 65536
#endif
// repeat the kernel so every size does the same total work (1048576 elements)
#ifndef REPS
#define REPS (1048576 / N)
#endif
// register grouping, set with -DLMUL=1/2/4/8
#ifndef LMUL
#define LMUL 1
#endif

// pasting LMUL into the intrinsic names so one source covers m1..m8
#define CAT_(a, b, c) a##b##c
#define CAT(a, b, c) CAT_(a, b, c)
#define VFLOAT CAT(vfloat32m, LMUL, _t)
#define VSETVL CAT(__riscv_vsetvl_e32m, LMUL, )
#define VLE    CAT(__riscv_vle32_v_f32m, LMUL, )
#define VSE    CAT(__riscv_vse32_v_f32m, LMUL, )
#define VFADD  CAT(__riscv_vfadd_vv_f32m, LMUL, )

// 64 byte aligned so a 512 bit load is exactly one cache line
static float a[N] __attribute__((aligned(64)));
static float b[N] __attribute__((aligned(64)));
static float c[N] __attribute__((aligned(64)));

// We don't want inlining because the compiler could optimize
// the vector addition away (we don't use the result elsewhere)
__attribute__((noinline))
void vadd(const float *a, const float *b, float *c, size_t n) {
#ifdef VECTOR_BINARY
    for (size_t i = 0; i < n; ) {
        // vl is the number of elements that can be proccessed at once
        size_t vl = VSETVL(n - i);
        // va is the first vector to be added, vl elements starting at a[i]
        VFLOAT va = VLE(a + i, vl);
        // vb is the second vector to be added, vl elements starting at b[i]
        VFLOAT vb = VLE(b + i, vl);
        // the actual vector addition, the result is stored in c[i] to c[i+vl-1]
        VSE(c + i, VFADD(va, vb, vl), vl);
        // increment i by vl
        i += vl;
    }
#else
    for (size_t i = 0; i < n; i++) c[i] = a[i] + b[i];
#endif
}

int main(void) {
    for (int i = 0; i < N; i++) { a[i] = i; b[i] = 2 * i; }
    // one warm up pass so the caches hold whatever fits before we measure
    vadd(a, b, c, N);
    // only the stuff between reset and dump ends up in the first stats block
    m5_reset_stats(0, 0);
    for (int r = 0; r < REPS; r++) vadd(a, b, c, N);
    m5_dump_stats(0, 0);
    // checking correctness (not measuring this, just running once when I change something)
    #ifdef CHECK
        for (int i = 0; i < N; i++)
            if (c[i] != 3.0f * i) { printf("FAIL at %d\n", i); return 1; }
        printf("PASS\n");
    #endif
    return 0;
}
