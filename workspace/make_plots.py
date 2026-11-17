#!/usr/bin/env python3
# Makes the three result plots from results.csv.
#   python3 make_plots.py [results.csv] [output dir]

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import pandas as pd
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

CSV = sys.argv[1] if len(sys.argv) > 1 else "results.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "plots"
os.makedirs(OUT, exist_ok=True)

# deck colors
NAVY, TEAL, GOLD, BLUE = "#14213D", "#0E8A8A", "#D89B2B", "#2A64A8"
GRID = "#D5DEE3"

# use Calibri (same as the deck) if this machine has it
for p in ["/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts/Calibri.ttf",
          "/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts/Calibrib.ttf"]:
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)
plt.rcParams.update({
    "font.family": ["Calibri", "Arial", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "axes.edgecolor": NAVY,
    "axes.labelcolor": NAVY,
    "axes.titlecolor": NAVY,
    "text.color": NAVY,
    "xtick.color": NAVY,
    "ytick.color": NAVY,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.5,
    "legend.frameon": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "lines.linewidth": 1.8,
    "lines.markersize": 5,
    "savefig.dpi": 400,
})

SIZES = [2048, 16384, 65536]
SIZE_LABEL = {2048: "2K elements (fits L1D)", 16384: "16K (fits L2)", 65536: "64K (DRAM)"}
SIZE_SHORT = {2048: "2K\n(L1D)", 16384: "16K\n(L2)", 65536: "64K\n(DRAM)"}
SIZE_COLOR = {2048: TEAL, 16384: BLUE, 65536: GOLD}
SIZE_MARKER = {2048: "o", 16384: "s", 65536: "^"}
WL_TITLE = {"vadd": "Vector add", "fir": "FIR (16 taps)"}
WL_STYLE = {"vadd": "-", "fir": "--"}
VLENS = [128, 256, 512, 1024]
# same size as the plot boxes on the slides (5.6 x 3.6 in)
FIG = (5.6, 3.6)

d = pd.read_csv(CSV)
rvv = d[d.config == "rvv"]


def lmul1(wl, n):
    g = rvv[(rvv.workload == wl) & (rvv.n == n) & (rvv.lmul == 1)].sort_values("vlen")
    return g.set_index("vlen")


def knee(wl, n):
    # first VLEN where doubling it gives < 10% more speedup (None if it never happens)
    s = lmul1(wl, n).speedup
    for v in VLENS[:-1]:
        if s[2 * v] / s[v] < 1.10:
            return v
    return None


def vlen_axis(ax):
    ax.set_xscale("log", base=2)
    ax.set_xticks(VLENS)
    ax.set_xticklabels([str(v) for v in VLENS])
    ax.minorticks_off()
    ax.set_xlim(105, 1250)
    ax.set_xlabel("VLEN (bits)")


# ---- 1. speedup vs VLEN at LMUL 1 ----
fig, axes = plt.subplots(1, 2, figsize=FIG, sharey=True)
for ax, wl in zip(axes, ["vadd", "fir"]):
    labeled = []
    for n in SIZES:
        g = lmul1(wl, n)
        # 2K line gets a bigger marker so it still shows when the 16K line sits on top of it
        ax.plot(g.index, g.speedup, color=SIZE_COLOR[n], marker=SIZE_MARKER[n], label=SIZE_LABEL[n],
                markersize=7.5 if n == 2048 else 5)
        end = g.speedup[1024]
        # skip the end label when another line already ends at (nearly) the same spot
        if all(abs(end / e - 1) > 0.05 for e in labeled):
            ax.annotate(f"{end:.1f}x", (1024, end), textcoords="offset points",
                        xytext=(-2, 6), ha="center", fontsize=8, color=SIZE_COLOR[n], fontweight="bold")
            labeled.append(end)
    vlen_axis(ax)
    ax.set_yscale("log", base=2)
    ax.set_yticks([1, 2, 4, 8, 16, 32])
    ax.set_yticklabels(["1", "2", "4", "8", "16", "32"])
    ax.set_ylim(0.8, 56)
    ax.set_title(WL_TITLE[wl])
axes[0].set_ylabel("Speedup over scalar (LMUL = 1)")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), columnspacing=1.4, handlelength=2.2)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(os.path.join(OUT, "plot_speedup_vs_vlen.png"))
plt.close(fig)

# ---- 2. spatial vs temporal, VLEN x LMUL = 512 (16 fp32 per instruction) ----
PAIRS = [(512, 1, "512 / m1 (spatial)"), (256, 2, "256 / m2"), (128, 4, "128 / m4 (temporal)")]
ALPHA = [1.0, 0.62, 0.30]
HATCH = [None, None, "////"]
fig, axes = plt.subplots(1, 2, figsize=FIG)
for ax, wl in zip(axes, ["vadd", "fir"]):
    top = 0
    for i, n in enumerate(SIZES):
        for j, (v, m, _) in enumerate(PAIRS):
            s = rvv[(rvv.workload == wl) & (rvv.n == n) & (rvv.vlen == v) & (rvv.lmul == m)].speedup.iloc[0]
            x = i + (j - 1) * 0.27
            ax.bar(x, s, width=0.25, color=SIZE_COLOR[n], alpha=ALPHA[j], hatch=HATCH[j],
                   edgecolor=SIZE_COLOR[n] if j == 2 else "none", linewidth=0.6)
            ax.text(x, s, f"{s:.1f}", ha="center", va="bottom", fontsize=7.5)
            top = max(top, s)
    ax.set_xticks(range(len(SIZES)))
    ax.set_xticklabels([SIZE_SHORT[n] for n in SIZES])
    ax.set_ylim(0, top * 1.14)
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=6))
    ax.set_title(WL_TITLE[wl])
    ax.grid(axis="x", visible=False)
axes[0].set_ylabel("Speedup over scalar")
legend = [Patch(facecolor=NAVY, alpha=ALPHA[j], hatch=HATCH[j], edgecolor=NAVY if j == 2 else "none",
                linewidth=0.6, label=PAIRS[j][2]) for j in range(3)]
fig.legend(handles=legend, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), columnspacing=1.4,
           title="VLEN / LMUL, all 16 fp32 elements per instruction", title_fontsize=8.5)
fig.tight_layout(rect=(0, 0.13, 1, 1))
fig.savefig(os.path.join(OUT, "plot_spatial_vs_temporal.png"))
plt.close(fig)

# ---- 3. bottleneck: L1D / L2 miss rate and DRAM bandwidth vs VLEN ----
# slide 7 box is a touch narrower (5.5 x 3.6 in)
fig, axes = plt.subplots(1, 3, figsize=(5.5, 3.6))
PANELS = [("l1d_miss_rate", "L1D miss rate (%)", 100.0),
          ("l2_miss_rate", "L2 miss rate (%)", 100.0),
          ("dram_bw_mbs", "DRAM bandwidth (GB/s)", 1e-3)]
for ax, (col, title, scale) in zip(axes, PANELS):
    for wl in ["vadd", "fir"]:
        for n in SIZES:
            g = lmul1(wl, n)
            y = g[col] * scale
            if col == "l2_miss_rate":
                # with almost no L2 traffic the rate is noise (1 miss / 1 access), show it as 0
                y = y.where(g.l2_accesses >= 1000, 0.0)
            ax.plot(g.index, y, color=SIZE_COLOR[n], marker=SIZE_MARKER[n], linestyle=WL_STYLE[wl],
                    markersize=4, linewidth=1.5)
            k = knee(wl, n)
            if k is not None:
                ax.plot([k], [y[k]], marker="o", markersize=10, markerfacecolor="none",
                        markeredgecolor=NAVY, markeredgewidth=1.2, linestyle="none", zorder=5,
                        clip_on=False)
    vlen_axis(ax)
    ax.set_xticklabels(["128", "256", "512", "1024"], fontsize=7.5)
    ax.set_title(title, fontsize=9)
    ax.set_ylim(bottom=0)
peak = d.dram_bw_mbs.max() / d.dram_bw_util.max() / 1e3
axes[2].axhline(peak, color=NAVY, linewidth=1, linestyle=":")
axes[2].text(1200, peak - 0.3, "DDR3 peak", ha="right", va="top", fontsize=7.5)
axes[2].set_ylim(0, peak * 1.08)
axes[0].set_ylim(0, 105)
axes[1].set_ylim(0, 105)
size_h = [Line2D([], [], color=SIZE_COLOR[n], marker=SIZE_MARKER[n], markersize=4, label=SIZE_SHORT[n].replace("\n", " "))
          for n in SIZES]
other_h = [Line2D([], [], color=NAVY, linestyle="-", label="vadd"),
           Line2D([], [], color=NAVY, linestyle="--", label="FIR"),
           Line2D([], [], marker="o", markersize=8, markerfacecolor="none", markeredgecolor=NAVY,
                  linestyle="none", label="next doubling < 10%")]
# legend fills column by column, interleave so sizes end up on the top row
legend = [h for pair in zip(size_h, other_h) for h in pair]
fig.legend(handles=legend, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0), columnspacing=1.2,
           handlelength=2.4, fontsize=8)
fig.tight_layout(rect=(0, 0.15, 1, 1), w_pad=0.6)
fig.savefig(os.path.join(OUT, "plot_bottleneck.png"))
plt.close(fig)

print("diminishing returns point at LMUL 1 (first VLEN where doubling gives < 10%):")
for wl in ["vadd", "fir"]:
    for n in SIZES:
        s = lmul1(wl, n).speedup
        steps = ", ".join(f"{v}->{2*v}: {100 * (s[2*v] / s[v] - 1):+.1f}%" for v in VLENS[:-1])
        print(f"  {wl:4s} N={n:<6d} knee={knee(wl, n)}   ({steps})")
print(f"plots written to {OUT}/")
