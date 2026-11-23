#!/usr/bin/env python3
"""Draw the figures of README.md from results/shots_results.json.

usage: python3 plots.py [results.json] [outdir]
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.patches import Circle, Rectangle                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shotmodel import design as dsg, literature, search, shots as shotgeo   # noqa: E402
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False})


def curve(doc, design, rule, aim, goal, effect="flip", targets="all", clk="ignore", T=6):
    cid = "%s/%s/%s/%s/%s/clk-%s/T%d/%s" % (design, rule, aim, effect, targets, clk, T, goal)
    for c in doc["curves"]:
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def step_xy(c, xmax, top):
    """x, y arrays of the step curve; a value 'none up to k' is drawn at level `top`."""
    xs, ys = [], []
    st = c["steps"]
    for i, s in enumerate(st):
        x1 = st[i + 1]["r_from"] if i + 1 < len(st) else max(xmax, s["r_last"])
        y = s["min"] if s["min"] is not None else top
        xs += [s["r_from"], x1]
        ys += [y, y]
    return xs, ys


def _marks(ax, xmax, top):
    """published laser spot radii (SOURCED, see shotmodel/literature.py) as thin vertical lines"""
    for m in literature.MARKS:
        if m["r"] <= xmax:
            ax.axvline(m["r"], color=INK2, lw=0.7, ls=":", zorder=0)
            ax.text(m["r"] + 0.08, top + 0.35, m["label"], rotation=90, va="top", ha="left", fontsize=6.3,
                    color=INK2)


def fig_curves(doc, goal, out, xmax=16.0):
    series = [("v1", "cell", BLUE, "-", "V1, aimed at a cell"), ("v1", "grid", ORANGE, "--", "V1, free aim"),
              ("v2", "cell", AQUA, "-", "V2, aimed at a cell"), ("v2", "grid", YELLOW, "--", "V2, free aim")]
    fig, axes = plt.subplots(2, 1, figsize=(7.6, 6.2), sharex=True)
    top = 5
    for ax, rule, ttl in zip(axes, ("centre", "overlap"),
                             ("Rule \"centre\": a cell is hit when its centre is inside the spot",
                              "Rule \"overlap\": a cell is hit when the spot touches any part of it")):
        for k, (d, aim, col, ls, lab) in enumerate(series):
            try:
                c = curve(doc, d, rule, aim, goal)
            except KeyError:
                continue
            xs, ys = step_xy(c, xmax, top)
            off = (k - 1.5) * 0.045                      # small vertical offset so coinciding steps stay visible
            ax.plot(xs, [y + off for y in ys], color=col, ls=ls, lw=2, label=lab, solid_capstyle="butt")
        ax.set_yticks([1, 2, 3, 4, top])
        ax.set_yticklabels(["1", "2", "3", "4", "none\nfound"])
        ax.set_ylim(0.5, top + 0.5)
        ax.set_xlim(0, xmax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_ylabel("fewest shots")
        ax.set_title(ttl, loc="left", fontsize=9.5, color=INK)
        _marks(ax, xmax, top)
    axes[1].set_xlabel("shot radius r (um)")
    axes[0].legend(loc="upper right", frameon=False, ncol=2, fontsize=8.5)
    gl = {"word": "boot_word = 0x96 seen in any cycle", "word_clean": "boot_word = 0x96 seen in a cycle without a shot",
          "ok": "boot_ok = 1 seen in any cycle"}[goal]
    fig.suptitle("Fewest shots that open the lock, by shot radius (modelled; goal: %s)" % gl, x=0.01, ha="left",
                 fontsize=10.5)
    fig.text(0.01, 0.005, "Bit-flip of every hit cell output, T = 6 cycles. Lines are shifted slightly so that equal values "
             "stay visible. Free aim: 0.1 um grid, searched up to 3 shots. Dotted lines: published laser spot radii (SOURCED); "
             "a 1 mm EM probe (SOURCED) is far off the right edge (die is about 30 um).", wrap=True, fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_variants(doc, out, goal="word", rule="centre", xmax=30.0):
    ds = [d for d in ("v2", "v2_v8", "v2_s8", "v2_v15", "v2_rr") if d in doc["designs"]]
    if len(ds) < 2:
        return False
    fig, axes = plt.subplots(len(ds), 1, figsize=(7.6, 1.45 * len(ds) + 1.0), sharex=True)
    top = 4
    for ax, d in zip(axes, ds):
        for aim, col, ls, lab in (("cell", BLUE, "-", "aimed at a cell"), ("grid", ORANGE, "--", "free aim")):
            c = curve(doc, d, rule, aim, goal)
            xs, ys = step_xy(c, xmax, top if aim == "grid" else 5)
            ax.plot(xs, [min(y, top) + (0.05 if aim == "grid" else -0.05) for y in ys], color=col, ls=ls, lw=2, label=lab)
        ax.set_yticks([1, 2, 3, top])
        ax.set_yticklabels(["1", "2", "3", "none"])
        ax.set_ylim(0.5, top + 0.5)
        ax.set_xlim(0, xmax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        die = doc["designs"][d]["die_um"]
        ax.set_title("%s   (die %.1f um)   %s" % (d, die[2] - die[0], doc["designs"][d]["note"]), loc="left", fontsize=8.5,
                     color=INK)
    axes[0].legend(loc="upper right", frameon=False, ncol=2, fontsize=8)
    axes[-1].set_xlabel("shot radius r (um)")
    axes[len(ds) // 2].set_ylabel("fewest shots")
    fig.suptitle("V2 placements compared: fewest shots by radius (modelled; rule \"%s\", goal boot_word = 0x96)" % rule,
                 x=0.01, ha="left", fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return True


def _cell_style(c):
    n = c["name"]
    if c["role"] == "physical":
        return "#f0efec", "#d6d5d0", None
    if c["role"] == "clkbuf":
        return "#e4e3df", INK2, "clk"
    for pre, col in (("c0/", BLUE), ("c1/", ORANGE), ("c2/", AQUA)):
        if n.startswith(pre):
            return col, INK, n
    if c["role"] == "flop":
        return "#c9c8c2", INK, "FF" + c["out"][-2:-1]
    return "#ffffff", INK2, n.strip("_")


def draw_layout(ax, doc, design, witness, title):
    D = doc["designs"][design]
    x0, y0, x1, y1 = D["die_um"]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=INK2, lw=0.8))
    hit = set()
    for s in (witness or {}).get("shots", []):
        hit |= set(s["cells"])
    for c in D["cells"]:
        fc, ec, lab = _cell_style(c)
        ax.add_patch(Rectangle((c["x"], c["y"]), c["w"], c["h"], fc=fc, ec=ec, lw=0.5, zorder=2))
        if c["name"] in hit:
            ax.add_patch(Rectangle((c["x"], c["y"]), c["w"], c["h"], fill=False, ec=INK, lw=2.0, zorder=5))
        if lab and c["role"] != "physical":
            ax.text(c["x"] + c["w"] / 2, c["y"] + c["h"] / 2, lab, ha="center", va="center", fontsize=4.6,
                    color=INK, zorder=4, rotation=90 if c["w"] < 2.0 else 0)
    for i, s in enumerate((witness or {}).get("shots", [])):
        r = max(s["r"], 0.35)
        ax.add_patch(Circle((s["x"], s["y"]), r, fill=False, ec="#d03b3b", lw=1.6, zorder=6,
                            ls="-" if s["r"] > 0 else ":"))
        ax.plot([s["x"]], [s["y"]], marker="+", color="#d03b3b", ms=6, mew=1.4, zorder=7)
        ax.annotate("shot %d, cycle %d" % (i + 1, s["cycle"]), (s["x"], s["y"] + r), xytext=(0, 4 + 10 * i),
                    textcoords="offset points", ha="center", fontsize=6.5, color=INK, zorder=8,
                    bbox=dict(fc=SURFACE, ec="none", pad=0.6, alpha=0.9))
    ax.set_xlim(x0 - 1, x1 + 1)
    ax.set_ylim(y0 - 1, y1 + 1)
    ax.set_aspect("equal")
    ax.set_title(title, loc="left", fontsize=8.5, color=INK)
    ax.set_xlabel("x (um)")


def fig_layout(doc, design, out, rule="centre", aim="cell", goal="word"):
    c = curve(doc, design, rule, aim, goal)
    picks, seen = [], set()
    for s in c["steps"]:                      # first radius reaching each value, in order of appearance
        if s["min"] is not None and s["min"] not in seen:
            seen.add(s["min"])
            picks.append(s)
    picks = picks[:3]
    fig, axes = plt.subplots(1, len(picks), figsize=(4.6 * len(picks), 5.3), squeeze=False)
    for ax, s in zip(axes[0], picks):
        w = s["witness"]
        draw_layout(ax, doc, design, w, "r = %.2f um: %d shot%s (sig = 0x%02X)" %
                    (s["r_from"], s["min"], "" if s["min"] == 1 else "s", w["sig"]))
    axes[0][0].set_ylabel("y (um)")
    fig.suptitle("%s placement with a smallest winning shot set (modelled; rule \"%s\", %s aim, goal boot_word = 0x96)"
                 % (design.upper(), rule, "cell" if aim == "cell" else "free"), x=0.01, ha="left", fontsize=10.5)
    fig.text(0.01, 0.01, "Red circle = spot (dotted: r = 0, drawn enlarged); thick outline = disturbed cell. Blue / orange / "
             "green = compare copies c0 / c1 / c2 (V1: c1 / c2);\ngrey = state flops (FF bit); white = other logic; "
             "pale = fill, tap.", fontsize=7.2, color=INK2)
    fig.tight_layout(rect=(0, 0.11, 1, 0.95))
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_layout_at(design, r, out, rule="centre", aim="grid", goal="word", T=6, kmax=4):
    """layout with a smallest winning shot set computed here at one given radius (e.g. a published spot radius)"""
    D = dsg.Design(design)
    tab = shotgeo.shot_table(D, r, rule, aim)
    res = search.min_shots(D, tab["masks"], T, kmax if aim == "cell" else 3, "flip", goal)
    w = res["witness"]
    pt = {int(m): p for m, p in zip(tab["masks"], tab["points"])}
    wj = None if w is None else dict(sig=w["sig"], shots=[dict(cycle=t, x=pt[m][0], y=pt[m][1], r=r, cells=D.names(m))
                                                          for t, m in w["shots"]])
    docd = dict(cells=[dict(name=c.name, master=c.master, role=c.role, x=c.x, y=c.y, w=c.w, h=c.h,
                            out=c.out or "") for c in D.all_cells], die_um=D.die)
    fig, ax = plt.subplots(figsize=(5.4, 5.6))
    ttl = ("r = %.2f um: %s" % (r, "no attack up to %d shots" % res["searched_k"] if w is None else
                                "%d shot%s (sig = 0x%02X)" % (res["min"], "" if res["min"] == 1 else "s", w["sig"])))
    draw_layout(ax, {"designs": {design: docd}}, design, wj, ttl)
    ax.set_ylabel("y (um)")
    fig.suptitle("%s at a published laser spot radius (modelled; rule \"%s\", %s aim)" %
                 (design.upper(), rule, "free" if aim == "grid" else "cell"), x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return res


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "shots_results.json")
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "plots")
    os.makedirs(outdir, exist_ok=True)
    doc = json.load(open(src))
    made = []
    for goal in ("word", "word_clean"):
        p = os.path.join(outdir, "min_shots_vs_radius_%s.png" % goal)
        fig_curves(doc, goal, p)
        made.append(p)
    p = os.path.join(outdir, "v2_placement_variants.png")
    if fig_variants(doc, p):
        made.append(p)
    for d, rule, aim in (("v2", "centre", "cell"), ("v2", "overlap", "grid"), ("v1", "centre", "cell")):
        p = os.path.join(outdir, "layout_%s_%s_%s.png" % (d, rule, aim))
        fig_layout(doc, d, p, rule, aim)
        made.append(p)
    for d in ("v1", "v2"):
        for r in (0.5, 2.5):
            p = os.path.join(outdir, "layout_%s_r%s_centre_grid.png" % (d, ("%g" % r).replace(".", "p")))
            fig_layout_at(d, r, p)
            made.append(p)
    print("\n".join(made))


if __name__ == "__main__":
    main()
