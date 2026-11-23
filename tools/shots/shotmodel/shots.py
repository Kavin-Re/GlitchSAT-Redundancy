"""Geometry of a shot: which placed cells does a disc of radius r around the aim point disturb?

rule  "centre"  : a cell is hit when its CENTRE lies within r of the aim point (same rule as the radius discs of
                  research/c4/layout in this repository, so the two can be compared).
      "overlap" : a cell is hit when the disc touches its bounding box (distance from the aim point to the cell
                  rectangle <= r). This is the larger footprint: any part of the cell inside the spot counts.
aim   "cell"    : the aim point is the centre of a placed logic cell (35 or 36 sites); exact, no discretisation.
      "grid"    : free aim: every point of a square grid over the die (pitch `pitch`, default 0.1 um, offset by half
                  a pitch so that no point lies on a cell edge) plus the centre of every placed component (logic,
                  clock buffer, tap, fill). A discretisation of "any point"; it contains every "cell" site.
A comparison uses a tolerance of 1e-9 um (distances are sums of multiples of 5 nm, so ties are decided as "inside").

Only logic cells (combinational cells and flops) are disturbed. Clock buffers are placed cells too, but a disturbed
clock is not expressible in a cycle-accurate model; policy clk="ignore" leaves them untouched (default), policy
clk="forbid" removes every shot whose disc reaches a clock buffer.
"""
import numpy as np

EPS = 1e-9
RULES = ("centre", "overlap")
AIMS = ("cell", "grid")
TARGETS = ("all", "flops", "comb")


def _dist2(px, py, cells, rule):
    """squared distance from points (arrays) to each cell; result shape (npoints, ncells)"""
    px = np.asarray(px, dtype=float)[:, None]
    py = np.asarray(py, dtype=float)[:, None]
    if rule == "centre":
        cx = np.array([c.cx for c in cells])[None, :]
        cy = np.array([c.cy for c in cells])[None, :]
        return (px - cx) ** 2 + (py - cy) ** 2
    if rule == "overlap":
        x0 = np.array([c.x for c in cells])[None, :]
        y0 = np.array([c.y for c in cells])[None, :]
        x1 = np.array([c.x + c.w for c in cells])[None, :]
        y1 = np.array([c.y + c.h for c in cells])[None, :]
        dx = np.maximum(np.maximum(x0 - px, px - x1), 0.0)
        dy = np.maximum(np.maximum(y0 - py, py - y1), 0.0)
        return dx ** 2 + dy ** 2
    raise ValueError("rule must be one of %s" % (RULES,))


def aim_points(design, aim, pitch=0.1):
    if aim == "cell":
        return np.array([c.cx for c in design.logic]), np.array([c.cy for c in design.logic])
    if aim == "grid":
        x0, y0, x1, y1 = design.die
        gx = np.arange(x0 + pitch / 2, x1, pitch)
        gy = np.arange(y0 + pitch / 2, y1, pitch)
        X, Y = np.meshgrid(gx, gy)
        px = np.concatenate([[c.cx for c in design.all_cells], X.ravel()])
        py = np.concatenate([[c.cy for c in design.all_cells], Y.ravel()])
        return px, py
    raise ValueError("aim must be one of %s" % (AIMS,))


def shot_table(design, r, rule="centre", aim="cell", targets="all", clk="ignore", pitch=0.1):
    """Distinct non-empty disturbance sets reachable with ONE shot of radius r.
    Returns dict(masks=uint64 array (sorted), points=[(x, y)] one representative aim point per mask, n_points=...)."""
    if targets not in TARGETS:
        raise ValueError("targets must be one of %s" % (TARGETS,))
    px, py = aim_points(design, aim, pitch)
    lim = (r + EPS) ** 2
    inside = _dist2(px, py, design.logic, rule) <= lim              # (npoints, n logic cells)
    weights = (np.uint64(1) << np.arange(design.n, dtype=np.uint64))
    tmask = {"all": design.flop_mask | design.comb_mask, "flops": design.flop_mask, "comb": design.comb_mask}[targets]
    masks = (inside.astype(np.uint64) * weights[None, :]).sum(axis=1, dtype=np.uint64) & np.uint64(tmask)
    keep = masks != 0
    if clk == "forbid" and design.clkbufs:
        keep &= ~(_dist2(px, py, design.clkbufs, rule) <= lim).any(axis=1)
    elif clk != "ignore" and clk != "forbid":
        raise ValueError("clk must be ignore or forbid")
    idx = np.nonzero(keep)[0]
    um, first = np.unique(masks[idx], return_index=True)
    pts = [(float(px[idx[i]]), float(py[idx[i]])) for i in first]
    return dict(masks=um, points=pts, n_points=int(len(px)), r=r, rule=rule, aim=aim, targets=targets, clk=clk,
                pitch=pitch if aim == "grid" else None)


def breakpoints(design, rule="centre"):
    """Radii at which the cell-aimed shot table can change (sorted, distinct): every centre-to-cell distance."""
    px, py = aim_points(design, "cell")
    d = np.sqrt(_dist2(px, py, design.logic, rule))
    return np.unique(np.round(d[d > EPS], 6))
