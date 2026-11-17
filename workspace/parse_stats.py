#!/usr/bin/env python3
# Turns every results/out_*/stats.txt into one CSV.
#   python3 parse_stats.py [results dir] [output csv]
# Only the FIRST stats block is used, that's the reset->dump region (kernel only).

import csv
import os
import re
import sys

RESULTS = sys.argv[1] if len(sys.argv) > 1 else "results"
OUT_CSV = sys.argv[2] if len(sys.argv) > 2 else "results.csv"

# every size does this many elements total (N * REPS in the C files)
TOTAL_ELEMENTS = 1048576
# L1D hit time in cycles (tag/data latency = 1 in the stdlib L1DCache)
L1_HIT_CYCLES = 1

CORE = "board.processor.cores.core"
L1D = "board.cache_hierarchy.l1d-cache-0"
L2 = "board.cache_hierarchy.l2-cache-0"
MEM = "board.memory.mem_ctrl"

# the exact gem5 stat names we read
STATS = {
    "sim_ticks": "simTicks",
    "sim_seconds": "simSeconds",
    "insts": "simInsts",
    "cycles": f"{CORE}.numCycles",
    "micro_ops": "simOps",
    "ipc": f"{CORE}.ipc",
    "cpi": f"{CORE}.cpi",
    "l1d_accesses": f"{L1D}.demandAccesses::total",
    "l1d_misses": f"{L1D}.demandMisses::total",
    "l1d_miss_latency": f"{L1D}.demandMissLatency::total",
    "l2_accesses": f"{L2}.demandAccesses::total",
    "l2_misses": f"{L2}.demandMisses::total",
    "l1d_pf_issued": f"{L1D}.prefetcher.pfIssued",
    "l2_pf_issued": f"{L2}.prefetcher.pfIssued",
    "dram_bytes_read": f"{MEM}.dram.bytesRead::total",
    "dram_bytes_written": f"{MEM}.dram.bytesWritten::total",
    "dram_peak_bw_mbs": f"{MEM}.dram.peakBW",
    "clock_ticks": "board.processor.clk_domain.clock",
    "lsq_full_events": f"{CORE}.iew.lsqFullEvents",
    "iq_full_events": f"{CORE}.iew.iqFullEvents",
}

DIR_RE = re.compile(r"out_(\w+?)_N(\d+)_(scalar|vlen(\d+)_m(\d+))$")


def first_block(path):
    # gem5 leaves a stat out when it's zero, so missing means 0
    vals = {}
    blocks = 0
    with open(path) as f:
        for line in f:
            if "Begin Simulation Statistics" in line:
                blocks += 1
                if blocks > 1:
                    break
                continue
            parts = line.split()
            if len(parts) >= 2:
                vals[parts[0]] = parts[1]
    return vals


def num(vals, name):
    try:
        return float(vals.get(name, 0))
    except ValueError:
        return 0.0


rows = []
for d in sorted(os.listdir(RESULTS)):
    m = DIR_RE.match(d)
    stats_path = os.path.join(RESULTS, d, "stats.txt")
    if not m or not os.path.isfile(stats_path):
        continue
    vals = first_block(stats_path)
    r = {k: num(vals, name) for k, name in STATS.items()}
    r["workload"] = m.group(1)
    r["n"] = int(m.group(2))
    r["config"] = "scalar" if m.group(3) == "scalar" else "rvv"
    r["vlen"] = int(m.group(4)) if m.group(4) else 0
    r["lmul"] = int(m.group(5)) if m.group(5) else 0
    rows.append(r)

scalar_ticks = {(r["workload"], r["n"]): r["sim_ticks"] for r in rows if r["config"] == "scalar"}
scalar_insts = {(r["workload"], r["n"]): r["insts"] for r in rows if r["config"] == "scalar"}

for r in rows:
    key = (r["workload"], r["n"])
    r["speedup"] = scalar_ticks[key] / r["sim_ticks"]
    r["inst_reduction"] = scalar_insts[key] / r["insts"]
    # elements each vector instruction covers (0 for scalar)
    r["elems_per_inst"] = r["vlen"] * r["lmul"] // 32
    r["l1d_miss_rate"] = r["l1d_misses"] / r["l1d_accesses"] if r["l1d_accesses"] else 0.0
    r["l2_miss_rate"] = r["l2_misses"] / r["l2_accesses"] if r["l2_accesses"] else 0.0
    # miss rate per access shifts with VLEN (wider = fewer accesses), per element doesn't
    r["l1d_mpke"] = 1000.0 * r["l1d_misses"] / TOTAL_ELEMENTS
    r["l2_mpke"] = 1000.0 * r["l2_misses"] / TOTAL_ELEMENTS
    # AMAT = L1 hit time + L1D miss rate * avg L1D miss penalty (penalty already includes L2 + DRAM)
    penalty_cycles = (r["l1d_miss_latency"] / r["l1d_misses"] / r["clock_ticks"]) if r["l1d_misses"] else 0.0
    r["l1d_miss_penalty_cycles"] = penalty_cycles
    r["amat_cycles"] = L1_HIT_CYCLES + r["l1d_miss_rate"] * penalty_cycles
    # DRAM traffic over the kernel region
    r["dram_bw_mbs"] = (r["dram_bytes_read"] + r["dram_bytes_written"]) / r["sim_seconds"] / 1e6
    r["dram_bw_util"] = r["dram_bw_mbs"] / r["dram_peak_bw_mbs"] if r["dram_peak_bw_mbs"] else 0.0
    r["elems_per_cycle"] = TOTAL_ELEMENTS / r["cycles"]
    r["uops_per_inst"] = r["micro_ops"] / r["insts"]

COLS = [
    "workload", "n", "config", "vlen", "lmul", "elems_per_inst",
    "sim_ticks", "cycles", "speedup", "insts", "inst_reduction", "micro_ops", "uops_per_inst",
    "ipc", "cpi", "elems_per_cycle",
    "l1d_accesses", "l1d_misses", "l1d_miss_rate", "l1d_mpke",
    "l2_accesses", "l2_misses", "l2_miss_rate", "l2_mpke",
    "l1d_miss_penalty_cycles", "amat_cycles",
    "dram_bytes_read", "dram_bytes_written", "dram_bw_mbs", "dram_bw_util",
    "l1d_pf_issued", "l2_pf_issued", "lsq_full_events", "iq_full_events",
]

rows.sort(key=lambda r: (r["workload"], r["n"], r["vlen"], r["lmul"]))
with open(OUT_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(COLS)
    for r in rows:
        out = []
        for c in COLS:
            v = r[c]
            if isinstance(v, float):
                v = int(v) if v == int(v) and abs(v) > 50 else round(v, 6)
            out.append(v)
        w.writerow(out)

print(f"{len(rows)} runs -> {OUT_CSV}")
print("\ngem5 stat names used (first stats block only):")
for k, name in STATS.items():
    print(f"  {k:20s} {name}")
print("\nderived columns:")
print("  speedup            scalar sim_ticks / sim_ticks (same workload and size)")
print("  inst_reduction     scalar insts / insts")
print("  uops_per_inst      micro_ops / insts")
print("  l1d/l2_miss_rate   demandMisses / demandAccesses")
print("  l1d/l2_mpke        misses per 1000 elements")
print("  amat_cycles        1 + l1d_miss_rate * (l1d demandMissLatency / demandMisses / clock)")
print("  dram_bw_mbs        (dram bytesRead + bytesWritten) / simSeconds / 1e6")
print("  dram_bw_util       dram_bw_mbs / dram.peakBW")
print(f"  elems_per_cycle    {TOTAL_ELEMENTS} / numCycles")
