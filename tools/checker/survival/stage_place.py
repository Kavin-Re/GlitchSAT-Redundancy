"""Placement stage: are the redundant copies still apart on the placed chip?

A laser or EM pulse disturbs every cell inside a spot. Copies that survive synthesis as separate cells can still be
defeated together when placement puts them next to each other. For each set of redundant copies this stage reads the
placed design (DEF + cell sizes from LEF + post-route netlist) and measures:

  r_pair   smallest spot radius that reaches cells of two different copies
  r_all    smallest spot radius that reaches a cell of every copy (one shot acts on all copies)

and for a sparse-encoded register the smallest spot that covers all the flops in which two of its codes differ.
Rule "centre" (ASSUMED, as in ext/shots): a cell is reached when its centre lies inside the spot. Rule "overlap"
(ASSUMED, pessimistic): any touch of the cell's box counts.

Verdict at the configured spot radius r:  REMOVED when r >= r_all, WEAKENED when r >= r_pair, else SURVIVED.
This is geometry (MEASURED from the DEF). It says a single shot *reaches* the copies; whether that shot also produces
an accepted wrong input is the job of the shot search in ext/shots (SIMULATED), whose recorded result is attached as
the margin when the layout is one of those it covers.
"""
import itertools
import json
import math
import os

from . import paths
from . import gnet as G
from .model import StageResult, SURVIVED, WEAKENED, REMOVED, UNTRACKED
from .stage_netlist import _lookup, _find_register, _short

DEFAULT_LEF = "research/c4/l2_inputs/lef/sky130_fd_sc_hd_sizes_only.lef"


class Placement:
    def __init__(self, def_path, lef_path=None):
        design = paths.optional("shotmodel.design")
        if design is None:
            raise G.NetlistError("the placement stage needs ext/shots (DEF/LEF readers); set GLITCHSAT_EXT")
        if lef_path is None:
            lef_path = os.path.join(paths.repo_root(), DEFAULT_LEF)
        self.def_path, self.lef_path = str(def_path), str(lef_path)
        d = design.read_def(def_path)
        sizes = design.read_lef_sizes(lef_path)
        self.die = d["die"]
        self.box = {}
        for name, (master, x, y, orient) in d["comps"].items():
            if master not in sizes:
                raise G.NetlistError(f"{lef_path}: no SIZE for cell {master}")
            w, h = sizes[master]
            self.box[name] = (x, y, w, h)
        self.sha256 = paths.optional("shotmodel.paths").sha256(def_path)

    def centre(self, cell):
        x, y, w, h = self.box[cell]
        return (x + w / 2, y + h / 2)


def _mec(points):
    """Radius and centre of the smallest circle enclosing a few points (brute force over pairs and triples)."""
    pts = list(dict.fromkeys(points))
    if len(pts) == 1:
        return 0.0, pts[0]
    best = None

    def covers(c, r):
        return all(math.hypot(p[0] - c[0], p[1] - c[1]) <= r + 1e-9 for p in pts)
    for a, b in itertools.combinations(pts, 2):
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        r = math.hypot(a[0] - b[0], a[1] - b[1]) / 2
        if covers(c, r) and (best is None or r < best[0]):
            best = (r, c)
    for a, b, c3 in itertools.combinations(pts, 3):
        d = 2 * (a[0] * (b[1] - c3[1]) + b[0] * (c3[1] - a[1]) + c3[0] * (a[1] - b[1]))
        if abs(d) < 1e-12:
            continue
        ux = ((a[0] ** 2 + a[1] ** 2) * (b[1] - c3[1]) + (b[0] ** 2 + b[1] ** 2) * (c3[1] - a[1]) + (c3[0] ** 2 + c3[1] ** 2) * (a[1] - b[1])) / d
        uy = ((a[0] ** 2 + a[1] ** 2) * (c3[0] - b[0]) + (b[0] ** 2 + b[1] ** 2) * (a[0] - c3[0]) + (c3[0] ** 2 + c3[1] ** 2) * (b[0] - a[0])) / d
        r = math.hypot(a[0] - ux, a[1] - uy)
        if covers((ux, uy), r) and (best is None or r < best[0]):
            best = (r, (ux, uy))
    return best


def _box_gap(b1, b2):
    """Distance between two cell boxes (0 when they touch)."""
    dx = max(b1[0] - (b2[0] + b2[2]), b2[0] - (b1[0] + b1[2]), 0.0)
    dy = max(b1[1] - (b2[1] + b2[3]), b2[1] - (b1[1] + b1[3]), 0.0)
    return math.hypot(dx, dy)


def _one_from_each(groups, pl, cap=200000):
    """Smallest circle touching one cell centre of every group: (radius, centre, cells)."""
    n = 1
    for g_ in groups:
        n *= len(g_)
    if n > cap:      # keep, per group, the cells nearest to the centroid of all groups
        cx = sum(pl.centre(c)[0] for g_ in groups for c in g_) / sum(len(g_) for g_ in groups)
        cy = sum(pl.centre(c)[1] for g_ in groups for c in g_) / sum(len(g_) for g_ in groups)
        keep = max(2, int(cap ** (1 / len(groups))))
        groups = [sorted(g_, key=lambda c: math.hypot(pl.centre(c)[0] - cx, pl.centre(c)[1] - cy))[:keep] for g_ in groups]
    best = None
    for combo in itertools.product(*groups):
        r, c = _mec([pl.centre(x) for x in combo])
        if best is None or r < best[0]:
            best = (r, c, combo)
    return best


def check(cm, g, pl, stage, radius, rule="centre"):
    if cm.kind in ("redundant_copies", "complement_pair"):
        return _copies(cm, g, pl, stage, radius)
    if cm.kind == "sparse_encoding":
        return _encoding(cm, g, pl, stage, radius)
    return None


def _copies(cm, g, pl, stage, radius):
    nets = _lookup(g, cm.track.get("function"))
    if not nets:
        return StageResult(cm.id, stage, UNTRACKED, evidence=["the copies' function was not found in the placed netlist"])
    r = g.roots(nets)
    if len(r["components"]) < 2:
        return StageResult(cm.id, stage, UNTRACKED, evidence=[
            "fewer than two independent copies in the placed netlist (see the netlist stage); nothing to keep apart"])
    groups = []
    rootmask = [sum(1 << g.idx[x] for x in comp) for comp in r["components"]]
    for ci, comp in enumerate(r["components"]):
        cells = set()
        for root in comp:
            cells |= {g.cell_of(x) for x in g.cone_nets(root)}
        # cells that only this copy drives (its result gates, and flops whose D depends on this copy alone)
        def owners(net):
            c = g.cone.get(net, 0)
            return [j for j, m in enumerate(rootmask) if c & m]
        for x in g.order:
            if owners(x) == [ci]:
                cells.add(g.cell_of(x))
        for q, f in g.flops.items():
            if owners(f.d) == [ci]:
                cells.add(f.cell)
        cells = sorted(c for c in cells if c in pl.box)
        if not cells:
            return StageResult(cm.id, stage, UNTRACKED, evidence=["cells of a copy are missing from the DEF"])
        groups.append(cells)
    pairs = []
    for a, b in itertools.combinations(range(len(groups)), 2):
        best = min(((math.hypot(pl.centre(x)[0] - pl.centre(y)[0], pl.centre(x)[1] - pl.centre(y)[1]), x, y)
                    for x in groups[a] for y in groups[b]))
        gap = min(((_box_gap(pl.box[x], pl.box[y]), x, y) for x in groups[a] for y in groups[b]))
        pairs.append(dict(copies=[a, b], centre_distance_um=round(best[0], 3), cells=[best[1], best[2]],
                          box_gap_um=round(gap[0], 3), gap_cells=[gap[1], gap[2]]))
    r_pair = min(p["centre_distance_um"] for p in pairs) / 2
    r_all, c_all, combo = _one_from_each(groups, pl)
    n_int = cm.intent.get("copies", len(groups))
    meas = dict(copies=len(groups), cells_per_copy=[len(x) for x in groups], r_pair_um=round(r_pair, 3), r_all_um=round(r_all, 3),
                spot_radius_um=radius, aim_all=[round(c_all[0], 3), round(c_all[1], 3)], cells_all=list(combo), pairs=pairs,
                min_box_gap_um=min(p["box_gap_um"] for p in pairs), rule="centre")
    closest = min(pairs, key=lambda p: p["centre_distance_um"])
    ev = [f"closest cells of two different copies: {closest['cells'][0]} and {closest['cells'][1]}, centres "
          f"{closest['centre_distance_um']} um apart (boxes {closest['box_gap_um']} um apart): a spot of radius "
          f"{meas['r_pair_um']} um reaches both",
          f"one spot of radius {meas['r_all_um']} um at ({meas['aim_all'][0]}, {meas['aim_all'][1]}) reaches a cell of "
          f"every copy: {_short(combo)}"]
    if radius >= r_all - 1e-9:
        v = REMOVED
        ev.append(f"configured spot radius {radius} um >= {meas['r_all_um']} um: one shot reaches all {len(groups)} copies")
    elif radius >= r_pair - 1e-9:
        v = WEAKENED
        ev.append(f"configured spot radius {radius} um >= {meas['r_pair_um']} um: one shot reaches two copies, not all")
    else:
        v = SURVIVED
        ev.append(f"configured spot radius {radius} um is below {meas['r_pair_um']} um: one shot reaches one copy at most")
    if len(groups) < n_int:
        ev.append(f"only {len(groups)} of the {n_int} intended copies are independent in this netlist")
    return StageResult(cm.id, stage, v, measured=meas, evidence=ev)


def _encoding(cm, g, pl, stage, radius):
    nm, reg = _find_register(g, cm)
    codes = cm.intent.get("codes") or []
    if reg is None or len(codes) < 2:
        return StageResult(cm.id, stage, UNTRACKED, evidence=["state flops or codes not available at the placed stage"])
    cells = [g.flops[q].cell for q in reg]
    if any(c not in pl.box for c in cells):
        return StageResult(cm.id, stage, UNTRACKED, evidence=["state flops missing from the DEF"])
    best = None
    for a, b in itertools.combinations(sorted(codes), 2):
        bits = [i for i in range(len(reg)) if ((a ^ b) >> i) & 1]
        r, c = _mec([pl.centre(cells[i]) for i in bits])
        if best is None or r < best[0]:
            best = (r, c, a, b, bits)
    r_code, c, a, b, bits = best
    spacing = min(math.hypot(pl.centre(x)[0] - pl.centre(y)[0], pl.centre(x)[1] - pl.centre(y)[1])
                  for x, y in itertools.combinations(cells, 2))
    meas = dict(r_code_um=round(r_code, 3), codes=[f"0x{a:x}", f"0x{b:x}"], flops=[cells[i] for i in bits],
                min_flop_spacing_um=round(spacing, 3), spot_radius_um=radius, rule="centre")
    ev = [f"codes 0x{a:x} and 0x{b:x} differ in {len(bits)} flops ({_short(meas['flops'])}); one spot of radius "
          f"{meas['r_code_um']} um covers all of them (the spot must cover exactly these state flops to turn one code "
          "into the other; other cells in the spot are not considered here)"]
    v = WEAKENED if radius >= r_code - 1e-9 else SURVIVED
    ev.append(f"configured spot radius {radius} um " + (">=" if v == WEAKENED else "<") + f" {meas['r_code_um']} um")
    return StageResult(cm.id, stage, v, measured=meas, evidence=ev)


def recorded_shots(pl, radius, rule="centre", aim="grid"):
    """Minimum number of shots recorded by ext/shots for this exact DEF (matched by SHA-256), at this radius.
    Returns dict(min_shots, design, curve, label) or None."""
    p = os.path.join(paths.ext_root(), "shots", "results", "shots_results.json")
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        d = json.load(f)
    did = next((k for k, v in d.get("designs", {}).items() if v.get("sha256", {}).get("def") == pl.sha256), None)
    if did is None:
        return None
    best = None
    for c in d.get("curves", []):
        if (c["design"], c["rule"], c["aim"], c["effect"], c["targets"], c["goal"], c["T"]) != (did, rule, aim, "flip", "all", "word", 6):
            continue
        if c.get("clk") != "ignore":
            continue
        for s in c["steps"]:
            if s["r_from"] - 1e-9 <= radius <= s["r_last"] + 1e-9:
                best = dict(min_shots=s["min"], searched_k=s.get("searched_k"), design=did, curve=c["id"],
                            label="SIMULATED (recorded by ext/shots)")
    return best
