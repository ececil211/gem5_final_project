#include <stdio.h>
#ifdef VECTOR_BINARY
// header file for RISC-V vector extension
#include <riscv_vector.h>
#endif

#define ARRAY_ELEMENTS 65536
static float a[ARRAY_ELEMENTS], b[ARRAY_ELEMENTS], c[ARRAY_ELEMENTS];

// We don't want inlining because the compiler could optimize 
// the vector addition away (we don't use the result elsewhere)
__attribute__((noinline))
void vadd(const float *a, const float *b, float *c, size_t n) {
#ifdef VECTOR_BINARY
    for (size_t i = 0; i < n; ) {
        // vl is the number of elements that can be proccessed at once
        size_t vl = __riscv_vsetvl_e32m1(n - i);
        // va is the first vector to be added, vl elements starting at a[i]
        vfloat32m1_t va = __riscv_vle32_v_f32m1(a + i, vl);
        // vb is the second vector to be added, vl elements starting at b[i]
        vfloat32m1_t vb = __riscv_vle32_v_f32m1(b + i, vl);
        // the actual vector addition, the result is stored in c[i] to c[i+vl-1]
        __riscv_vse32_v_f32m1(c + i, __riscv_vfadd_vv_f32m1(va, vb, vl), vl);
        // increment i by vl
        i += vl;
    }
#else
    for (size_t i = 0; i < n; i++) c[i] = a[i] + b[i];
#endif
}

int main(void) {
    for (int i = 0; i < ARRAY_ELEMENTS; i++) { a[i] = i; b[i] = 2 * i; }
    vadd(a, b, c, ARRAY_ELEMENTS);
    // checking correctness (not measuring this, just running once when I change something)
    #ifdef CHECK
        for (int i = 0; i < ARRAY_ELEMENTS; i++)
            if (c[i] != 3.0f * i) { printf("FAIL at %d\n", i); return 1; }
        printf("PASS\n");
    #endif
    return 0;
}