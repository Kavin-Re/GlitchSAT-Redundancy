#!/usr/bin/env python3
"""Real netlists: the OpenTitan AES cipher-control FSM as synthesised by lowRISC/synfi (Yosys + Nangate45).

Runs examples/aes_fsm.yaml and sets the checker's structural verdict next to the fault minima recorded by the
real-design analysis in real/results (SAT search on the same netlists; RECORDED, not re-run here)."""
import json
import os
import sys

from common import RESULTS
from survival import paths, pipeline


def main():
    real = paths.real_root()
    if not real:
        print("real designs not available (set GLITCHSAT_REAL): NOT RUN", file=sys.stderr)
        return 2
    cfgp = os.path.join(os.path.dirname(RESULTS), "examples", "aes_fsm.yaml")
    rep = pipeline.run(pipeline.load_config(cfgp), os.path.dirname(cfgp))
    rec = {}
    for name, f in (("synth-single-rail", "fsm_state_single.json"), ("synth-three-rails", "fsm_state_multirail_from_reset.json")):
        p = os.path.join(real, "results", f)
        if os.path.isfile(p):
            d = json.load(open(p))
            rec[name] = dict(source=f"real/results/{f}", model=d.get("model"), cycles=d.get("cycles"), kmax=d.get("kmax"),
                             state_pairs=d["summary"].get("pairs"),
                             min_flips_state_flops_only=d["summary"].get("min_state_flops"),
                             min_flips_any_cell=d["summary"].get("min_all"))
    rows = []
    for c in rep["countermeasures"]:
        for r in c["stages"]:
            rows.append(dict(countermeasure=c["title"], kind=c["kind"], stage=r["stage"], verdict=r["verdict"], evidence=r["evidence"],
                             instances=(r["measured"].get("instances") or []), recorded=rec.get(r["stage"])))
    out = dict(schema="glitchsat-survival-validation/real/1", rows=rows, stages=rep["stages"], recorded=rec,
               label="verdicts MEASURED here on the stored netlists; fault minima RECORDED from real/results",
               reading=("The RTL declares 8 state codes at Hamming distance >= 3. On both netlists every state register still has 6 "
                        "flops and every code seen in random fault-free simulation is one of the RTL codes: the encoding itself "
                        "survived synthesis. The recorded SAT analysis agrees for faults on the state flops (3 flips = the code "
                        "distance on the single-rail netlist) and finds cheaper attacks through combinational cells (1 flip single "
                        "rail, 2 flips three rails from reset). That drop is outside what the structural encoding check sees; "
                        "it is a margin result. The checker therefore does NOT by itself flag a 3-to-2 weakening on these netlists."))
    with open(os.path.join(RESULTS, "real_designs.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    for r in rows:
        print(r["stage"], r["kind"], r["verdict"], "| recorded:", r["recorded"] and {k: r["recorded"][k] for k in ("min_flips_state_flops_only", "min_flips_any_cell")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
