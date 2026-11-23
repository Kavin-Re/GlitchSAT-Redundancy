"""Compare the abstract GlitchSAT bit-flip attacks with what the simulated clock-glitch campaign of this
lab produces, and emit the comparison record (schema: interface/README.md). SIMULATED, ASSUMED delays.

For each design we report:
  * engine_abstract_min_flips : GlitchSAT's cheapest attack over ALL sites (flop + gate) on the REFERENCE
    netlist (reference/spike_netlists/<d>.json), read from the repo's results/reproduce/*.json. It is not
    recomputed on the placed netlist that this lab simulates (`engine_abstract_min_flips_source`).
  * abstract_flop_only_min    : cheapest single-cycle flip set restricted to the 8 state flops of the
    PLACED netlist (the family a clock glitch acts on).
  * glitch_realizable         : did ANY (offset, period, sig) in the simulated campaign accept a wrong key?
  * oldnew_mix_check          : DIAGNOSTIC under a hazard-free capture model (each bit old or new), with
    the fault-free continuation, over all 255 wrong-key sigs. Not a proof: the campaign's own event-driven
    capture produces values outside old/new on V1 (`nonmix_captures`).
"""
import json
import os
from . import abstract, campaign, delaymodel, netlist


def engine_min(design_id, root=None):
    """Read GlitchSAT's min-fault result (all sites, REFERENCE netlist) from results/reproduce."""
    root = root or netlist.repo_root()
    best = None
    kinds = None
    sites = None
    for k in range(0, 4):
        p = os.path.join(root, "results/reproduce/%s_spike_given-netlist_k%d.json" % (design_id, k))
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        if d.get("verdict") == "ATTACK_FOUND" and d.get("min_faults") is not None:
            if best is None or d["min_faults"] < best:
                best = d["min_faults"]
                kinds = [f.get("kind") for f in d.get("faults", [])]
                sites = [dict(net=f.get("net"), cycle=f.get("cycle")) for f in d.get("faults", [])]
    return best, kinds, sites


def compare_design(design_id, T=8, campaign_result=None, root=None):
    D = netlist.Design(design_id, root=root)
    dm = delaymodel.DelayModel(D)
    fa = abstract.enumerate_flop_attacks(D, T)
    emin, ekinds, esites = engine_min(design_id, root=root)
    if campaign_result is None:
        campaign_result = campaign.run(D, dm, T=T)
    mix = abstract.oldnew_mix_check(D, T, offsets=campaign_result.get("offsets"))
    succ_cells = [c for c in campaign_result["cells"] if c["counts"]["SUCCESS"] > 0]
    return dict(
        design=design_id,
        horizon_T=T,
        engine_abstract_min_flips=emin,
        engine_abstract_min_flips_source=("reference netlist reference/spike_netlists/%s.json via "
                                          "results/reproduce/%s_spike_given-netlist_k*.json (not the placed "
                                          "netlist simulated here)" % (design_id, design_id)),
        engine_attack_site_kinds=ekinds,
        engine_attack_sites_reference_netlist=esites,
        abstract_flop_only_single_cycle_min=fa["min_flips"],
        abstract_flop_only_success_sets=len(fa["successes"]),
        abstract_flop_only_examples=[
            dict(cycle=t, flip_mask=hex(m), n_flops=nf) for (t, m, nf, _n) in fa["successes"][:3]],
        glitch_campaign=dict(
            delay_model=campaign_result["delay_model"]["source"],
            n_offsets=len(campaign_result["offsets"]),
            n_periods=len(campaign_result["periods_ps"]),
            cells_with_success=len(succ_cells),
            glitch_realizable_wrong_key_accept=bool(succ_cells),
            nonmix_captures=campaign_result.get("nonmix_captures"),
        ),
        oldnew_mix_check=dict(
            model=mix["model"],
            good_reachable=mix["good_reachable"],
            offsets=mix["offsets"],
            continuation_cycles=mix["continuation_cycles"],
            wrong_sigs_covered=mix["wrong_sigs_covered"],
            distinct_wrong_key_trajectories=mix["distinct_wrong_key_trajectories"],
            per_edge=[dict(offset=e["offset"], old=hex(e["old_state"]), new=hex(e["new_state"]),
                           n_wrong_sigs=e["n_wrong_sigs"], good_is_mix=e["good_is_mix"],
                           good_reached_from_a_mix=e["good_reached_from_a_mix"]) for e in mix["per_edge"]],
        ),
        realizable_by_single_clock_glitch=bool(succ_cells),
        note=("SIMULATED, %s delays. The cheapest GlitchSAT attack on the reference netlist flips %s; a clock "
              "glitch acts only on flop capture. The simulated sweep found %d wrong-key accepts. This is a "
              "result of the sweep, not a proof for other delays." %
              (campaign_result["delay_model"]["source"],
               ", ".join(sorted(set(ekinds))) if ekinds else "n/a", len(succ_cells))),
    )
