#include <stdio.h>
#include <stddef.h>
// gem5 magic instructions, lets us reset/dump stats around just the kernel
#include <gem5/m5ops.h>
#ifdef VECTOR_BINARY
// header file for RISC-V vector extension
#include <riscv_vector.h>
#endif

// number of output samples, set with -DN=... (same sizes as vadd_sweep.c)
#ifndef N
#define N 65536
#endif
// filter length, fixed for the whole sweep
#ifndef TAPS
#define TAPS 16
#endif
// repeat the kernel so every size does the same total work (1048576 outputs)
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
#define VFMV   CAT(__riscv_vfmv_v_f_f32m, LMUL, )
#define VFMACC CAT(__riscv_vfmacc_vf_f32m, LMUL, )

// input needs TAPS-1 extra samples at the end
static float x[N + TAPS - 1] __attribute__((aligned(64)));
static float y[N] __attribute__((aligned(64)));
static float h[TAPS];

// y[i] = sum over k of h[k] * x[i+k]
__attribute__((noinline))
void fir(const float *x, const float *h, float *y, size_t n) {
#ifdef VECTOR_BINARY
    for (size_t i = 0; i < n; ) {
        // vl outputs get computed at once
        size_t vl = VSETVL(n - i);
        // only two register groups live (acc and xv), so LMUL 8 still fits
        VFLOAT acc = VFMV(0.0f, vl);
        // no unrolling here: unrolled, clang loads 4 windows up front and at
        // LMUL 8 (only 4 groups) that spills whole registers to the stack
        #pragma clang loop unroll(disable)
        for (int k = 0; k < TAPS; k++) {
            // the input window slid over by k
            VFLOAT xv = VLE(x + i + k, vl);
            // acc += h[k] * xv, tap stays in a scalar fp register
            acc = VFMACC(acc, h[k], xv, vl);
        }
        VSE(y + i, acc, vl);
        i += vl;
    }
#else
    for (size_t i = 0; i < n; i++) {
        float acc = 0.0f;
        for (int k = 0; k < TAPS; k++) acc += h[k] * x[i + k];
        y[i] = acc;
    }
#endif
}

int main(void) {
    // small whole numbers so the float math is exact and easy to check
    for (int i = 0; i < N + TAPS - 1; i++) x[i] = i % 17;
    for (int k = 0; k < TAPS; k++) h[k] = k + 1;
    // one warm up pass so the caches hold whatever fits before we measure
    fir(x, h, y, N);
    // only the stuff between reset and dump ends up in the first stats block
    m5_reset_stats(0, 0);
    for (int r = 0; r < REPS; r++) fir(x, h, y, N);
    m5_dump_stats(0, 0);
    // checking correctness (not measured, the dump already happened)
    #ifdef CHECK
        for (int i = 0; i < N; i++) {
            int ref = 0;
            for (int k = 0; k < TAPS; k++) ref += (k + 1) * ((i + k) % 17);
            if (y[i] != (float)ref) { printf("FAIL at %d\n", i); return 1; }
        }
        printf("PASS\n");
    #endif
    return 0;
}
