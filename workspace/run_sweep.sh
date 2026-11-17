#!/bin/bash
# Runs the whole sweep, a few sims at a time. One output dir per config.
#   ./run_sweep.sh [path to gem5.opt] [parallel jobs] [check]
# e.g. nohup ./run_sweep.sh ../build/RISCV/gem5.opt 8 > sweep.log 2>&1 &

GEM5=${1:-../build/RISCV/gem5.opt}
JOBS=${2:-8}
MODE=${3:-sweep}
OUT=results

WORKLOADS="vadd fir"
SIZES="2048 16384 65536"
VLENS="128 256 512 1024"
LMULS="1 2 4 8"

mkdir -p $OUT
CMDS=$OUT/commands_$MODE.txt
: > $CMDS

# each line is "outdir binary extra-args"
if [ "$MODE" = "check" ]; then
    # correctness only, smallest and largest VLEN is enough to hit every LMUL path
    for w in $WORKLOADS; do
        echo "$OUT/check_${w}_scalar bin/${w}_scalar_check" >> $CMDS
        for l in $LMULS; do
            for v in 128 1024; do
                echo "$OUT/check_${w}_vlen${v}_m${l} bin/${w}_rvv_m${l}_check --vlen $v" >> $CMDS
            done
        done
    done
else
    for w in $WORKLOADS; do
        for n in $SIZES; do
            echo "$OUT/out_${w}_N${n}_scalar bin/${w}_scalar_N${n}" >> $CMDS
            for v in $VLENS; do
                for l in $LMULS; do
                    echo "$OUT/out_${w}_N${n}_vlen${v}_m${l} bin/${w}_rvv_m${l}_N${n} --vlen $v" >> $CMDS
                done
            done
        done
    done
fi

echo "$(wc -l < $CMDS) sims, $JOBS at a time"

run_one() {
    dir=$1; shift
    # skip anything that already finished so the sweep can be restarted
    if [ -f "$dir/done" ]; then return; fi
    mkdir -p "$dir"
    if "$GEM5" -d "$dir" run_se.py "$@" > "$dir/log.txt" 2>&1; then
        touch "$dir/done"
        echo "ok   $dir"
    else
        echo "FAIL $dir"
    fi
}
export -f run_one
export GEM5

# nice so we don't hog the shared server
xargs -P "$JOBS" -L 1 nice -n 10 bash -c 'run_one $0 "$@"' < $CMDS

echo "finished: $(ls -d $OUT/*/done 2>/dev/null | wc -l) done dirs total"
if [ "$MODE" = "check" ]; then
    bad=$(grep -L PASS $OUT/check_*/log.txt)
    if [ -z "$bad" ]; then echo "all checks PASS"; else echo "did NOT pass:"; echo "$bad"; fi
fi
