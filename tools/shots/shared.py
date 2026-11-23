#!/usr/bin/env python3
"""Write the shot-model results in the shared schema "physical-fault-campaign/1" (ext/vlab/interface/README.md).

usage: python3 shared.py [results/shots_results.json] [outdir]
One record per placed design: results/<design>_shared.json, mechanism "laser_em", cost unit "shot_radius_um".

  realizable_wrong_key_accept : a wrong key is accepted (boot_word == 0x96) with at most kmax shots at some radius
  min_cost                    : smallest radius at which ONE shot is enough (rule "centre", free aim; see extra for
                                the other rules and aims)
  realized_flip_sets          : for every step of every bit-flip curve (goal word, T = 6), the smallest winning shot
                                set reduced to flop-flip space (shotmodel/flopspace.py), one entry per cycle; entries
                                of one attack share "attack" (index into extra.attacks); a flop-space effect already listed is not repeated; each attack is re-run as a flop-only attack and checked
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shotmodel import design as dsg, flopspace, literature   # noqa: E402

SCHEMA = "physical-fault-campaign/1"
REQUIRED = ["schema", "mechanism", "design", "top", "realizable_wrong_key_accept", "realized_flip_sets"]


def validate(rec):
    """Same checks as vlab.interface.validate (copied so this folder runs on its own)."""
    for k in REQUIRED:
        if k not in rec:
            raise ValueError("record missing %r" % k)
    if rec["schema"] != SCHEMA or rec["mechanism"] not in ("clock_glitch", "laser_em"):
        raise ValueError("bad schema or mechanism")
    for fs in rec["realized_flip_sets"]:
        if "cycle" not in fs or "flops" not in fs:
            raise ValueError("flip set needs cycle and flops")
        if not all(isinstance(b, int) and 0 <= b < 8 for b in fs["flops"]):
            raise ValueError("flop indices must be 0..7")
    return True


def _curve(doc, **kw):
    out = [c for c in doc["curves"] if all(c.get(k) == v for k, v in kw.items())]
    return out[0] if len(out) == 1 else None


def build(doc, design_id):
    D = dsg.Design(design_id)
    byname = {c.name: c for c in D.logic}
    base = dict(design=design_id, effect="flip", targets="all", clk="ignore", T=6)
    sets, attacks, summary = [], [], {}
    seen = set()
    one_shot_r = {}
    for rule in ("centre", "overlap"):
        for aim in ("cell", "grid"):
            c = _curve(doc, rule=rule, aim=aim, goal="word", **base)
            if c is None:
                continue
            summary["%s/%s" % (rule, aim)] = dict(
                kmax=c["kmax"], exact_steps=c["exact_steps"],
                steps=[dict(r_from=s["r_from"], r_last=s["r_last"], min_shots=s["min"], searched_k=s["searched_k"])
                       for s in c["steps"]])
            one_shot_r["%s/%s" % (rule, aim)] = next((s["r_from"] for s in c["steps"] if s["min"] == 1), None)
            for s in c["steps"]:
                w = s["witness"]
                if w is None:
                    continue
                shots = [(x["cycle"], sum(1 << byname[n].idx for n in x["cells"])) for x in w["shots"]]
                fs, q = flopspace.flip_sets(D, shots, w["sig"], c["T"], "flip")
                ok = flopspace.check_equivalent(D, shots, w["sig"], c["T"], "flip")
                if not ok:
                    raise RuntimeError("flop-space reduction does not replay: %s %s/%s r=%s" %
                                       (design_id, rule, aim, s["r_from"]))
                aid = len(attacks)
                attacks.append(dict(attack=aid, rule=rule, aim=aim, r_from_um=s["r_from"], r_last_um=s["r_last"],
                                    n_shots=s["min"], sig="0x%02x" % w["sig"],
                                    boot_word_trace=["0x%02x" % v for v in q], shots=w["shots"],
                                    flop_flip_sets=[dict(cycle=t, flops=[i for i in range(8) if (f >> i) & 1])
                                                    for t, f in fs],
                                    flop_only_replay_ok=ok))
                key = tuple(fs)
                if key in seen:                     # same flop-space effect as an earlier attack: listed once
                    continue
                seen.add(key)
                for t, f in fs:
                    sets.append(dict(cycle=t, flops=[i for i in range(8) if (f >> i) & 1], sig="0x%02x" % w["sig"],
                                     outcome="SUCCESS", attack=aid, r_um=s["r_from"], n_shots=s["min"],
                                     rule=rule, aim=aim))
    realizable = any(st["min_shots"] is not None for v in summary.values() for st in v["steps"])
    min_cost = one_shot_r.get("centre/grid")
    rec = dict(schema=SCHEMA, mechanism="laser_em", design=design_id, top=D.top, key=dsg.KEY, good=dsg.GOOD,
               init=dsg.INIT, realizable_wrong_key_accept=realizable, min_cost=min_cost,
               cost_unit="shot_radius_um" if min_cost is not None else None, realized_flip_sets=sets,
               honesty="SIMULATION, not measurement",
               extra=dict(
                   model="disc of radius r disturbs every placed logic cell within r (bit-flip of its output in one "
                         "clock cycle); placement from the sky130 DEF; exhaustive bounded search, T = 6 cycles",
                   min_cost_meaning="smallest radius (um) at which one shot opens the lock, rule centre, free aim",
                   one_shot_radius_um=one_shot_r,
                   min_shots_vs_radius=summary,
                   attacks=attacks,
                   source_results="results/shots_results.json (%s)" % doc["generated"],
                   spot_size_sources=[dict(id=s["id"], label=s["label"], url=s["url"]) for s in literature.SOURCES],
                   placement_note=D.note))
    validate(rec)
    return rec


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "shots_results.json")
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results")
    doc = json.load(open(src))
    try:                                                    # also validate with the lab's own checker when present
        sys.path.insert(0, os.path.join(HERE, "..", "vlab"))
        from vlab.interface import validate as vvalidate
    except Exception:
        vvalidate = None
    for d in doc["designs"]:
        rec = build(doc, d)
        if vvalidate is not None:
            vvalidate(rec)
        p = os.path.join(outdir, "%s_shared.json" % d)
        with open(p, "w") as f:
            json.dump(rec, f, indent=1)
        print("%s: %d flip-set entries from %d attacks, one shot from r = %s um" %
              (p, len(rec["realized_flip_sets"]), len(rec["extra"]["attacks"]), rec["min_cost"]))


if __name__ == "__main__":
    main()
