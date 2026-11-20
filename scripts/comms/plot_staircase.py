#!/usr/bin/env python3
"""plot_staircase.py - Reads results/comms/distance_sweep.csv, writes docs/comms/staircase.png.
usage: plot_staircase.py <distance_sweep.csv> <out.png>
x = d(I,W) (Hamming distance idle word -> accept word); y = measured minimum modelled flips (product CLI, stem rule, T=6).
'>k' cells (no attack found up to k) are drawn as open upward triangles at k: a lower bound within the bound, not 'safe'."""
import csv, sys, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#1f1f1e", "#6b6b68", "#e4e4e0", "#fcfcfb"


def main(src, out):
    rows = [r for r in csv.DictReader(open(src)) if r["status"].startswith("measured")]
    main_rows = [r for r in rows if r["kind"] in ("named", "family")]      # d(I,W) is the nearest non-accept word; 3-copy grouping
    side = [r for r in rows if r["kind"] in ("ceiling", "control")]
    fig, ax = plt.subplots(figsize=(8.6, 6.2), dpi=150)
    fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    ax.plot([0, 8], [0, 8], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(6.55, 6.95, "y = d", color=MUTED, fontsize=9, rotation=38, ha="center")
    ax.axhline(3, color=MUTED, lw=1, ls=(0, (1, 2)), zorder=1)
    ax.text(0.1, 3.08, "ceiling 3 = number of comparator copies", color=MUTED, fontsize=9, va="bottom")
    for col, colr, dx, label in (("min_flops", BLUE, -0.09, "flops only"), ("min_all", ORANGE, 0.09, "all nets (yosys 0.33, flow plain)")):
        cnt = collections.Counter((int(r["d_to_accept"]), r[col]) for r in main_rows)
        first = {"exact": True, "bound": True}
        for (d, v), n in sorted(cnt.items()):
            bound = v.startswith(">")
            y = int(v.lstrip(">"))
            ax.scatter([d + dx], [y], s=80, marker="^" if bound else "o", facecolor=SURF if bound else colr, edgecolor=colr if bound else SURF,
                       linewidth=1.8 if bound else 1.5, zorder=3,
                       label=(label + (", no attack found up to 6 (lower bound)" if bound else "")) if first["bound" if bound else "exact"] else None)
            first["bound" if bound else "exact"] = False
            if n > 1:
                if dx > 0: ax.text(d + dx + 0.13, y - 0.05, f"x{n}", fontsize=8, color=INK, ha="left", va="center")
                else: ax.text(d + dx - 0.02, y + 0.2, f"x{n}", fontsize=8, color=INK, ha="right", va="bottom")
    for r in side:   # codebooks where d(I,W) is NOT the governing distance, or one copy owns all bits
        d = int(r["d_to_accept"])
        for col, colr, dx in (("min_flops", BLUE, -0.36), ("min_all", ORANGE, 0.36)):
            ax.scatter([d + dx], [int(r[col])], s=70, marker="s", facecolor=SURF, edgecolor=colr, linewidth=1.8, zorder=3)
    ax.scatter([], [], s=70, marker="s", facecolor=SURF, edgecolor=INK, linewidth=1.5,
               label="side cases: fail word nearer than idle, or one copy owns all bits")
    ax.annotate("fail word B at distance 3 / 6\n(B xor W inside 1 / 2 copies)", xy=(7.64, 3.1), xytext=(5.6, 4.45), fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.annotate("one copy owns all 8 bits", xy=(4.36, 0.93), xytext=(4.75, 0.35), fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xlim(0, 8.75); ax.set_ylim(0, 8.3); ax.set_xticks(range(0, 9)); ax.set_yticks(range(0, 9))
    ax.set_xlabel("d(I,W): Hamming distance from idle word to accept word", color=INK)
    ax.set_ylabel("measured minimum number of modelled flips", color=INK)
    ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.set_title("Code distance as fault budget, decoder as ceiling (19 measured codebooks of rtl/v2.v variants)", fontsize=10.5, color=INK, loc="left")
    fig.text(0.01, 0.01, "Modelled flips on a toy design; observed, not a theorem. Single-cycle bit flips, stem rule, goal boot_word == W, T = 6, k <= min(d,6); MEASURED with\n"
             "faultbound-wt analyze via scripts/comms/distance_sweep.py (results/comms/distance_sweep.csv). 'x3' = three codebooks on one point. Triangles: bounded, not 'safe'.\n"
             "With the no-ABC structural flow the d = 4 all-nets points at 2 become 3 (see CSV column min_all_struct). ", fontsize=7.2, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(out, facecolor=SURF)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
