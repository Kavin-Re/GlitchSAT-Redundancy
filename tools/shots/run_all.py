#!/usr/bin/env python3
"""Run the whole shot-model study and write results/shots_results.json (schema: README.md, section "JSON").

usage: python3 run_all.py [--quick] [--procs N] [--out results/shots_results.json]
  --quick : small subset (V1 and V2 only, coarse radii) for a smoke run; the committed results are the full run.
Inputs are read from the GlitchSAT repository (see shotmodel/paths.py; set GLITCHSAT_REPO if this folder is elsewhere).
"""
import argparse
import datetime
import json
import math
import multiprocessing as mp
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                                                    # noqa: E402
from shotmodel import (__version__, bruteforce, cells, design as dsg, equiv, paths, search, shots, sim, smt,   # noqa: E402
                       switchlevel)

T_MAIN, K_CELL, K_GRID, PITCH = 6, 4, 3, 0.1


def frange(a, b, s):
    return [round(a + i * s, 6) for i in range(int(round((b - a) / s)) + 1)]


def cover_radius(D):
    x0, y0, x1, y1 = D.die
    return math.ceil(math.hypot(x1 - x0, y1 - y0))


def sample_radii(D, quick=False):
    R = cover_radius(D)
    if quick:
        return [0, 0.5, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, R]
    rs = frange(0, 6, 0.25) + frange(6.5, 16, 0.5) + [float(r) for r in range(18, R + 1, 2)]
    if rs[-1] != R:
        rs.append(float(R))
    return rs


def witness_json(D, table, w, r):
    if w is None:
        return None
    pt = {int(m): p for m, p in zip(table["masks"], table["points"])}
    return dict(sig=w["sig"], sig_class_size=len(w["sig_class"]), hit_cycle=w["hit_cycle"],
                shots=[dict(cycle=t, x=round(pt[m][0], 3), y=round(pt[m][1], 3), r=r, cells=D.names(m))
                       for t, m in w["shots"]])


def run_curve(design_id, rule, aim, effect, targets, clk, T, kmax, radii, exact):
    """One curve family (all three goals) over a list of radii. Returns list of curve dicts."""
    D = dsg.Design(design_id)
    t_start = time.time()
    per_goal = {g: [] for g in search.GOALS}
    memo = {}
    n_tables = 0
    for r in radii:
        table = shots.shot_table(D, r, rule, aim, targets, clk, PITCH)
        key = table["masks"].tobytes()
        if key not in memo:
            S = search.Searcher(D, table["masks"], effect)
            res = {}
            for g in search.GOALS:
                x = S.min_shots(T, kmax, g)
                if x["witness"] is not None and not search.replay(D, x["witness"], T, effect, g):
                    raise RuntimeError("witness does not replay: %s r=%s %s" % (design_id, r, g))
                res[g] = x
            memo[key] = (res, S.stats(), table)
            n_tables += 1
        res, st, tab0 = memo[key]
        for g in search.GOALS:
            x = res[g]
            per_goal[g].append(dict(r=float(r), min=x["min"], searched_k=x["searched_k"], n_shot_sets=int(len(table["masks"])),
                                    witness=witness_json(D, tab0, x["witness"], float(r))))
    secs = round(time.time() - t_start, 2)
    out = []
    for g in search.GOALS:
        pts = per_goal[g]
        steps = []
        for p in pts:                       # run-length encode on (min, searched_k)
            if steps and steps[-1]["min"] == p["min"] and steps[-1]["searched_k"] == p["searched_k"]:
                steps[-1]["r_last"] = p["r"]
                steps[-1]["n_radii"] += 1
            else:
                steps.append(dict(r_from=p["r"], r_last=p["r"], min=p["min"], searched_k=p["searched_k"], n_radii=1,
                                  n_shot_sets=p["n_shot_sets"], witness=p["witness"]))
        out.append(dict(id="%s/%s/%s/%s/%s/clk-%s/T%d/%s" % (design_id, rule, aim, effect, targets, clk, T, g),
                        design=design_id, rule=rule, aim=aim, effect=effect, targets=targets, clk=clk, T=T, kmax=kmax,
                        goal=g, exact_steps=bool(exact), n_radii=len(pts), n_distinct_shot_tables=n_tables,
                        r_max=float(radii[-1]), secs_family=secs, steps=steps,
                        samples=[[p["r"], p["min"], p["searched_k"]] for p in pts] if not exact else None))
    return out


def _task(a):
    try:
        return run_curve(*a)
    except Exception as e:                                             # keep the pool alive, report loudly
        import traceback
        return dict(error="%s: %s" % (a, traceback.format_exc()))


def cell_checks(root):
    subs = switchlevel.read_subckts(root / paths.SPICE)
    import re
    masters = set()
    for _, (_top, _d, nl, _n) in paths.DESIGNS.items():
        masters |= set(re.findall(r"sky130_fd_sc_hd__\w+", open(root / nl).read()))
    rows = []
    for m in sorted(masters):
        k = cells.kind(m)
        if k == "comb":
            ins = cells.input_pins(m)
            ok = switchlevel.comb_truth_table(subs[m], ins, cells.output_pin(m)) == cells.truth_table(m)
            rows.append(dict(cell=m, kind=k, inputs=ins, vectors=1 << len(ins), matches_transistor_netlist=ok))
        elif k == "flop":
            import random
            rnd = random.Random(1)
            seq, c = [(0, 0), (1, 0), (0, 0)], 0
            for _ in range(2000):
                if rnd.random() < 0.5:
                    c ^= 1
                    seq.append((c, seq[-1][1]))
                else:
                    seq.append((seq[-1][0], rnd.randint(0, 1)))
            got = switchlevel.flop_trace(subs[m], seq)
            q, ok = 0, True
            for i, (cc, _dd) in enumerate(seq):
                if i > 0 and seq[i - 1][0] == 0 and cc == 1:
                    q = seq[i - 1][1]
                if i >= 2 and got[i] != q:
                    ok = False
            rows.append(dict(cell=m, kind=k, vectors=len(seq), matches_transistor_netlist=ok))
        else:
            rows.append(dict(cell=m, kind=k, vectors=0, matches_transistor_netlist=None))
    return rows


def validation(designs, quick):
    """r = 0 against the per-cell single-fault model, and search.py against the plain enumerator."""
    out = dict(r0=[], cross=[])
    for d in designs:
        D = dsg.Design(d)
        for rule in shots.RULES:
            tab = shots.shot_table(D, 0.0, rule, "cell")
            singles = sorted(1 << c.idx for c in D.logic)
            out["r0"].append(dict(design=d, rule=rule, check="r=0 shot table == one set per logic cell",
                                  ok=sorted(int(m) for m in tab["masks"]) == singles))
        for effect in sim.EFFECTS:
            t0 = time.time()
            tab = shots.shot_table(D, 0.0, "centre", "cell")
            S = search.Searcher(D, tab["masks"], effect)
            dp = {g: S.min_shots(T_MAIN, 2, g)["min"] for g in search.GOALS}
            bf = bruteforce.single_flip(D, T_MAIN, 2, effect)
            out["r0"].append(dict(design=d, effect=effect, T=T_MAIN, K=2, check="shot search at r=0 vs single-fault enumeration",
                                  shot_search_min=dp, single_fault_min=bf["min"],
                                  single_fault_attacking_sets={g: bf[g] for g in search.GOALS},
                                  sets_enumerated=sum(bf["total"].values()), ok=dp == bf["min"],
                                  secs=round(time.time() - t0, 1)))
        if d in ("v1", "v2"):
            for rule in shots.RULES:
                for r in ([1.0, 3.0] if quick else [1.0, 2.0, 3.0, 5.0, 10.0]):
                    for effect in sim.EFFECTS:
                        tab = shots.shot_table(D, r, rule, "cell")
                        t0 = time.time()
                        S = search.Searcher(D, tab["masks"], effect)
                        dp = {g: S.min_shots(4, 2, g)["min"] for g in search.GOALS}
                        bf = bruteforce.enumerate_sets(D, tab["masks"], 4, 2, effect)
                        out["cross"].append(dict(design=d, rule=rule, r=r, effect=effect, T=4, K=2, shot_search_min=dp,
                                                 enumerator_min=bf["min"], sets_enumerated=sum(bf["total"].values()),
                                                 ok=dp == bf["min"], secs=round(time.time() - t0, 1)))
    return out


def _bf_job(a):
    d, T, K = a
    D = dsg.Design(d)
    t0 = time.time()
    bf = bruteforce.single_flip(D, T, K, "flip")
    tab = shots.shot_table(D, 0.0, "centre", "cell")
    S = search.Searcher(D, tab["masks"], "flip")
    dp = {g: S.min_shots(T, K, g)["min"] for g in search.GOALS}
    return dict(design=d, effect="flip", T=T, K=K, check="shot search at r=0 vs single-fault enumeration (deep)",
                shot_search_min=dp, single_fault_min=bf["min"], single_fault_attacking_sets={g: bf[g] for g in search.GOALS},
                sets_enumerated=sum(bf["total"].values()), ok=dp == bf["min"], secs=round(time.time() - t0, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "shots_results.json"))
    ap.add_argument("--no-deep", action="store_true", help="skip the r=0 single-fault enumeration with K=3 (T=3; a few minutes)")
    a = ap.parse_args()
    root = paths.repo_root()
    t_all = time.time()
    designs = ["v1", "v2"] if a.quick else list(paths.DESIGNS)
    timing = {}

    t0 = time.time()
    cc = cell_checks(root)
    timing["cell_function_check_s"] = round(time.time() - t0, 2)
    t0 = time.time()
    eq = {}
    dinfo = {}
    for d in designs:
        D = dsg.Design(d)
        eq[d] = dict(transition=equiv.check_transition(D), boot=equiv.check_boot(D, 8))
        dinfo[d] = dict(note=D.note, top=D.top, files=D.files, sha256=D.sha256, die_um=D.die,
                        rows=[dict(y=y, orient=o) for y, o in D.rows],
                        n_components=len(D.all_cells), overlapping_components=D.overlaps(), n_logic_cells=D.n, n_flops=len(D.flops), n_comb=len(D.comb),
                        n_clkbuf=len(D.clkbufs), cover_radius_um=cover_radius(D), sig_classes=len(search.sig_classes(D)),
                        cells=[dict(name=c.name, master=c.master.replace("sky130_fd_sc_hd__", ""), role=c.role,
                                    x=c.x, y=c.y, w=c.w, h=c.h, orient=c.orient, idx=c.idx, out=c.out)
                               for c in D.all_cells])
    timing["equivalence_s"] = round(time.time() - t0, 2)

    tasks = []
    for d in designs:
        D = dsg.Design(d)
        rs = sample_radii(D, a.quick)
        for rule in shots.RULES:
            bp = [0.0] + [float(x) for x in shots.breakpoints(D, rule)]
            exact = (not a.quick) and d in ("v1", "v2")     # every breakpoint for the two base layouts; sampled otherwise
            tasks.append((d, rule, "cell", "flip", "all", "ignore", T_MAIN, K_CELL, bp if exact else rs, exact))
            tasks.append((d, rule, "grid", "flip", "all", "ignore", T_MAIN, K_GRID, rs, False))
        if d in ("v1", "v2"):
            vr = [0, 1, 2, 3, 5, 8] if a.quick else frange(0, 12, 0.5) + [14.0, 16.0, 20.0, 24.0, 32.0, float(cover_radius(D))]
            for rule in shots.RULES:
                for effect in sim.EFFECTS:
                    for targets in shots.TARGETS:
                        if (effect, targets) != ("flip", "all"):
                            tasks.append((d, rule, "cell", effect, targets, "ignore", T_MAIN, K_CELL, vr, False))
                tasks.append((d, rule, "cell", "flip", "all", "forbid", T_MAIN, K_CELL, vr, False))
                for T in (2, 3, 4, 8):
                    tasks.append((d, rule, "cell", "flip", "all", "ignore", T, K_CELL, vr, False))
    tasks.sort(key=lambda t: (t[2] != "cell" or len(t[8]) < 100, t[0]))
    t0 = time.time()
    curves, errors = [], []
    deep = []
    with mp.Pool(a.procs) as pool:
        deep_async = None
        if not a.quick and not a.no_deep:
            deep_async = pool.map_async(_bf_job, [("v2", 3, 3), ("v1", 3, 3)])
        for i, res in enumerate(pool.imap_unordered(_task, tasks)):
            if isinstance(res, dict):
                errors.append(res["error"])
            else:
                curves += res
            print("curve family %d/%d done (%.0f s)" % (i + 1, len(tasks), time.time() - t0), flush=True)
        if deep_async is not None:
            deep = deep_async.get()
    timing["curves_s"] = round(time.time() - t0, 2)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    curves.sort(key=lambda c: c["id"])
    t0 = time.time()
    val = validation(designs, a.quick)
    val["r0"] += deep
    timing["validation_s"] = round(time.time() - t0, 2)

    # SMT-LIB files for an external SMT solver (a few representative instances; no solver is run here)
    formal = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formal")
    os.makedirs(formal, exist_ok=True)
    smt_files = []
    for d, r, k in (("v2", 0.0, 2), ("v2", 0.0, 3), ("v2", 2.0, 1), ("v2", 2.0, 2), ("v2", 3.0, 1), ("v1", 0.0, 1), ("v1", 2.5, 1)):
        D = dsg.Design(d)
        tab = shots.shot_table(D, r, "centre", "cell")
        name = "%s_centre_cell_r%s_T%d_k%d_word.smt2" % (d, ("%g" % r).replace(".", "p"), T_MAIN, k)
        open(os.path.join(formal, name), "w").write(smt.emit(D, tab, T_MAIN, k, "flip", "word"))
        exp = search.min_shots(D, tab["masks"], T_MAIN, k, "flip", "word")["min"]
        smt_files.append(dict(file="formal/" + name, expected="sat" if exp is not None else "unsat",
                              expected_from="exhaustive search of this folder (no solver run)"))
    timing["total_s"] = round(time.time() - t_all, 2)
    timing["procs"] = a.procs

    doc = dict(
        schema="glitchsat-shots/1",
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tool=dict(name="shotmodel", version=__version__, python=platform.python_version(), numpy=np.__version__,
                  quick=a.quick),
        labels=dict(results="SIMULATED on MEASURED placement: modelled disturbances, bounded search, toy designs",
                    not_claimed="no physical validation, no timing or supply effects, nothing claimed as new"),
        model=dict(key=dsg.KEY, good_word=dsg.GOOD, init_state=dsg.INIT, T=T_MAIN, kmax_cell_aim=K_CELL, kmax_grid_aim=K_GRID,
                   grid_pitch_um=PITCH, tolerance_um=shots.EPS,
                   rules=dict(centre="cell hit when its centre is within r of the aim point",
                              overlap="cell hit when the disc touches its bounding box"),
                   aims=dict(cell="aim point = centre of a placed logic cell", grid="aim point on a %.2f um grid over the die plus every component centre" % PITCH),
                   effects=dict(flip="output net of every hit cell inverted in that cycle", set0="forced to 0", set1="forced to 1"),
                   targets=dict(all="flops and combinational cells", flops="only flops", comb="only combinational cells"),
                   clk=dict(ignore="clock buffers are never disturbed", forbid="shots whose disc reaches a clock buffer are not allowed"),
                   goals=dict(word="boot_word == 0x96 observed at some cycle < T with sig != 0xC3",
                              ok="boot_ok == 1 observed at some cycle < T with sig != 0xC3",
                              word_clean="as word, but observed in a cycle in which no shot is fired"),
                   min_null="min = null means: no attack with up to searched_k shots (bounded; not a proof of security)"),
        unplaced_designs=paths.UNPLACED,
        cell_function_check=cc,
        equivalence=eq,
        designs=dinfo,
        curves=curves,
        validation=val,
        smt_files=smt_files,
        runtime=timing,
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    bad = [v for v in val["r0"] + val["cross"] if not v["ok"]] + [c for c in cc if c["matches_transistor_netlist"] is False]
    print("wrote %s (%d curves, %.0f s); validation failures: %d" % (a.out, len(curves), timing["total_s"], len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
