#!/usr/bin/env python3
"""Run the whole virtual glitch lab and write results + plots.

  python3 run_vlab.py [--T 8] [--out results] [--plots plots] [--designs v1,v2] [--derate-sweep]

Outputs (schemas documented in interface/README.md):
  results/<design>_campaign.json      vlab-glitch-campaign/1  (full offset x period sweep)
  results/<design>_shared.json        physical-fault-campaign/1 (the shared interface record)
  results/comparison.json             vlab-comparison/1 (abstract vs clock-glitch, both designs)
  plots/<design>_sweep.png            success/crash/no-effect map over offset x period
  plots/<design>_slack.png            static setup slack per flop vs period; STA arrivals
  plots/comparison.png                abstract min-flips vs clock-glitch realizability
Nothing here needs an EDA tool or a solver; everything runs on the repo's placed layout outputs.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlab import campaign, compare, delaymodel, interface, netlist, sdf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--T", type=int, default=8)
    ap.add_argument("--out", default="results")
    ap.add_argument("--plots", default="plots")
    ap.add_argument("--designs", default="v1,v2")
    ap.add_argument("--derate-sweep", action="store_true",
                    help="also sweep a uniform supply-droop derating factor")
    ap.add_argument("--hazard-trials", type=int, default=0,
                    help="also run vlab.hazard.probe with N random delay scalings -> results/hazard_probe.json")
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, args.out)
    plots = os.path.join(here, args.plots)
    os.makedirs(out, exist_ok=True)
    os.makedirs(plots, exist_ok=True)
    designs = args.designs.split(",")

    campaigns = {}
    comparisons = []
    for did in designs:
        D = netlist.Design(did)
        # use a true SDF if eda/regen_sdf.sh wrote one next to the netlist
        sdf_path = os.path.join(netlist.repo_root(), os.path.dirname(netlist.DESIGNS[did][2]),
                                "%s.sdf" % did)
        sdf_data = sdf.load_sdf(sdf_path) if os.path.exists(sdf_path) else None
        dm = delaymodel.DelayModel(D, sdf=sdf_data)
        res = campaign.run(D, dm, T=args.T)
        # provenance: repo-relative input paths + SHA-256 (the `generated` timestamp is not a compared field)
        res["inputs"] = input_hashes(did, sdf_path if sdf_data else None)
        res["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if args.derate_sweep:
            res["derate_sweep"] = derate_sweep(D)
        campaigns[did] = res
        json.dump(res, open(os.path.join(out, "%s_campaign.json" % did), "w"), indent=1)
        shared = interface.from_vlab_campaign(res)
        json.dump(shared, open(os.path.join(out, "%s_shared.json" % did), "w"), indent=1)
        cmp = compare.compare_design(did, T=args.T, campaign_result=res)
        comparisons.append(cmp)

    comparison = dict(schema="vlab-comparison/1",
                      honesty="SIMULATION, not measurement",
                      generated=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      designs=comparisons)
    json.dump(comparison, open(os.path.join(out, "comparison.json"), "w"), indent=1)
    if args.hazard_trials:
        from vlab import hazard
        hz = dict(schema="vlab-hazard-probe/1", honesty="SIMULATION, not measurement",
                  designs=[hazard.probe(netlist.Design(did), T=args.T, trials=args.hazard_trials)
                           for did in designs])
        json.dump(hz, open(os.path.join(out, "hazard_probe.json"), "w"), indent=1)
        for r in hz["designs"]:
            print("  %s: hazard probe, %d trials: non-mix captures %d (default delays %d), wrong-key accepts %d"
                  % (r["design"], r["trials"], r["nonmix_captures"], r["nonmix_captures_default_delays"],
                     r["wrong_key_accepts"]))

    import plot_results
    for did in designs:
        plot_results.sweep_map(campaigns[did], os.path.join(plots, "%s_sweep.png" % did))
        plot_results.slack_plot(did, os.path.join(plots, "%s_slack.png" % did), T=args.T)
    plot_results.comparison_bar(comparison, os.path.join(plots, "comparison.png"))
    print("wrote results to", os.path.relpath(out), "and plots to", os.path.relpath(plots))
    for c in comparisons:
        print("  %s: engine min-flips (reference netlist)=%s (%s), flop-only min (placed)=%s, "
              "simulated clock-glitch accept=%s" % (
            c["design"], c["engine_abstract_min_flips"],
            "+".join(sorted(set(c["engine_attack_site_kinds"] or []))),
            c["abstract_flop_only_single_cycle_min"], c["realizable_by_single_clock_glitch"]))


def input_hashes(did, sdf_path=None):
    import hashlib
    root = netlist.repo_root()
    _top, def_rel, nl_rel = netlist.DESIGNS[did]
    rels = [nl_rel, def_rel, netlist.LEF]
    if sdf_path:
        rels.append(os.path.relpath(sdf_path, root))
    out = {}
    for rel in rels:
        with open(os.path.join(root, rel), "rb") as fh:
            out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def derate_sweep(D, factors=None):
    """Supply-droop proxy: uniformly slow every cell by `derate` at a fixed nominal period, record the
    worst outcome seen over the offset sweep. ASSUMED uniform slow-down; see delaymodel.py."""
    factors = factors or [1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
    dm0 = delaymodel.DelayModel(D)
    arr = dm0.flop_input_arrival(D)
    clk = max(dm0.clk_latency.values())
    nominal = 1.15 * (max(arr.values()) + clk)       # a period that is safe at derate 1.0
    rows = []
    for f in factors:
        dm = delaymodel.DelayModel(D, derate=f)
        res = campaign.run(D, dm, T=8, periods=[nominal])
        tot = {k: sum(c["counts"][k] for c in res["cells"]) for k in ("SUCCESS", "CRASH", "NO_EFFECT")}
        rows.append(dict(derate=f, nominal_period_ps=round(nominal, 1), counts=tot))
    return dict(note="fixed nominal period, uniform cell-delay derating (supply-droop proxy, ASSUMED)",
                rows=rows)


if __name__ == "__main__":
    main()
