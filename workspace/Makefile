CC      = clang-18
TARGET  = --target=riscv64-linux-gnu
SYSROOT = --gcc-toolchain=/usr --sysroot=/usr/riscv64-linux-gnu
CFLAGS  = $(TARGET) $(SYSROOT) -fuse-ld=lld-18 -O3 -static -mabi=lp64d

# Compiler is going to want to automatically vectorize scalar, stop that
NOVEC   = -fno-vectorize -fno-slp-vectorize

all: vadd_scalar vadd_rvv

vadd_scalar: vector_add.c
	$(CC) $(CFLAGS) $(NOVEC) -march=rv64gc vector_add.c -o $@

vadd_rvv: vector_add.c
	$(CC) $(CFLAGS) -march=rv64gcv -DVECTOR_BINARY vector_add.c -o $@

check: vector_add.c
	$(CC) $(CFLAGS) -march=rv64gcv -DVECTOR_BINARY -DCHECK vector_add.c -o vadd_rvv_check
	$(CC) $(CFLAGS) $(NOVEC) -march=rv64gc -DCHECK vector_add.c -o vadd_scalar_check

clean:
	rm -f vadd_scalar vadd_rvv vadd_scalar_check vadd_rvv_check
