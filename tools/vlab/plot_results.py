"""Plots for the virtual glitch lab. PNGs only (matplotlib). Colours are a colourblind-safe status set
(NO_EFFECT neutral, CRASH amber, SUCCESS red) plus the categorical ramp for per-flop lines; identity is
carried by position/label as well as hue, and every axis is labelled in picoseconds."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt       # noqa: E402
import numpy as np                    # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlab import delaymodel, netlist   # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
# status: NO_EFFECT neutral gray, CRASH amber(orange), SUCCESS red (reserved status hues, with labels)
STATUS = {"NO_EFFECT": "#d9d8d4", "CRASH": "#eb6834", "SUCCESS": "#e34948"}
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


def _dominant(cell):
    c = cell["counts"]
    if c["SUCCESS"] > 0:
        return "SUCCESS"
    if c["CRASH"] > 0:
        return "CRASH"
    return "NO_EFFECT"


def sweep_map(campaign_result, path):
    offsets = campaign_result["offsets"]
    periods = campaign_result["periods_ps"]
    grid = np.zeros((len(offsets), len(periods)), dtype=int)   # 0 no-effect,1 crash,2 success
    code = {"NO_EFFECT": 0, "CRASH": 1, "SUCCESS": 2}
    by = {(c["offset"], c["period_ps"]): c for c in campaign_result["cells"]}
    for i, off in enumerate(offsets):
        for j, P in enumerate(periods):
            grid[i, j] = code[_dominant(by[(off, P)])]
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([STATUS["NO_EFFECT"], STATUS["CRASH"], STATUS["SUCCESS"]])
    fig, ax = plt.subplots(figsize=(9, 3.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=2, origin="lower",
              extent=[periods[0], periods[-1], offsets[0] - 0.5, offsets[-1] + 0.5],
              interpolation="nearest")
    ax.set_yticks(offsets)
    ax.set_xlabel("glitched clock period  P_glitch  (ps)  — shorter = more aggressive", color=INK2)
    ax.set_ylabel("glitch offset (capture edge / cycle)", color=INK2)
    title = "%s  virtual clock-glitch campaign  —  outcome over offset × period" % \
            campaign_result["design"].upper()
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=26)
    # static-timing reference line: slowest D-path arrival (period below which STA predicts a violation)
    arr = campaign_result["sta_flop_arrival_ps"]
    worst = max(arr.values())
    ax.axvline(worst, color=INK, lw=1.2, ls="--")
    ax.text(worst, offsets[0] - 0.42, " STA worst D-path", color=INK, fontsize=8, va="bottom", ha="left")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=STATUS[k]) for k in ("NO_EFFECT", "CRASH", "SUCCESS")]
    ax.legend(handles, ["no effect", "crash / wrong boot", "SUCCESS (wrong-key accept)"],
              loc="lower left", ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0, 1.005))
    note = "delay model: %s — SIMULATION, not measurement" % campaign_result["delay_model"]["source"]
    fig.text(0.995, 0.005, note, ha="right", color=INK2, fontsize=7)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=130)
    plt.close(fig)


def slack_plot(design_id, path, T=8):
    D = netlist.Design(design_id)
    dm = delaymodel.DelayModel(D)
    arr = dm.flop_input_arrival(D)
    clk = max(dm.clk_latency.values())
    launch = max(dm.clk_latency[f.out] + dm.tcq(f) for f in D.flops)
    req = {i: launch + arr[i] - dm.clk_latency[D.flops[i].out] for i in range(8)}  # min period per flop
    fig, ax = plt.subplots(figsize=(7.5, 3.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    order = sorted(range(8), key=lambda i: req[i])
    vals = [req[i] for i in order]
    bars = ax.barh([str(i) for i in order], vals, color=[CAT[i] for i in order], height=0.6)
    for b, i in zip(bars, order):
        ax.text(b.get_width() + 6, b.get_y() + b.get_height() / 2, "%.0f ps" % req[i],
                va="center", color=INK2, fontsize=8)
    ax.set_xlabel("minimum safe clock period for this flop  (launch + D-path − skew, ps)", color=INK2)
    ax.set_ylabel("state flop (boot_word bit)", color=INK2)
    ax.set_title("%s  static-timing fault model  —  per-flop setup limit" % design_id.upper(),
                 color=INK, fontsize=11, loc="left")
    ax.text(0.995, -0.22, "below a flop's bar, a glitch of that period makes that flop miss its new value"
            "  —  %s delay model, SIMULATION" % dm.source,
            transform=ax.transAxes, ha="right", color=INK2, fontsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def comparison_bar(comparison, path):
    designs = [c["design"].upper() for c in comparison["designs"]]
    engine = [c["engine_abstract_min_flips"] for c in comparison["designs"]]
    floponly = [c["abstract_flop_only_single_cycle_min"] for c in comparison["designs"]]
    realiz = [c["realizable_by_single_clock_glitch"] for c in comparison["designs"]]
    x = np.arange(len(designs))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.5, 3.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    b1 = ax.bar(x - w / 2, engine, w, color=CAT[0], label="GlitchSAT min flips (all sites, reference netlist)")
    b2 = ax.bar(x + w / 2, floponly, w, color=CAT[2], label="min flips, flops only (1 cycle, placed netlist)")
    for bars, vals in ((b1, engine), (b2, floponly)):
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.05, str(v), ha="center", color=INK2, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(designs)
    ax.set_ylabel("minimum simultaneous bit flips", color=INK2)
    ax.set_ylim(0, max(engine + floponly) + 1.4)
    ax.set_title("Abstract attack cost vs. simulated clock-glitch sweep (ASSUMED delays)", color=INK, fontsize=11, loc="left")
    for xi, r in zip(x, realiz):
        ax.text(xi, max(engine + floponly) + 0.9,
                "simulated sweep:\n%s" % ("wrong-key accept" if r else "0 wrong-key accepts"),
                ha="center", color=(STATUS["SUCCESS"] if r else INK2), fontsize=8,
                fontweight="bold" if r else "normal")
    ax.legend(loc="upper left", frameon=False, fontsize=8, bbox_to_anchor=(0, -0.12), ncol=2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.text(0.995, 0.01, "SIMULATION, not measurement", ha="right", color=INK2, fontsize=7)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(path, dpi=130)
    plt.close(fig)
