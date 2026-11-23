"""Simulated glitch campaign, organised like a ChipWhisperer offset x period sweep: sweep the glitched
clock period and the glitch offset (which capture edge is shortened) and record the SIMULATED outcome for
every sig as a success/crash/no-effect map (ASSUMED delays unless an SDF is loaded).

Memoisation: with sig held constant the glitch outcome depends on sig only through design.sig_class(sig),
so each (offset, period, class) is simulated once and reused for every sig in the class.
"""
import time
from . import glitch, timing
from .netlist import KEY


def default_periods(design, dm, n=96, margin=1.3):
    """Period axis (ps) from 0 up to margin * the slowest static D-path arrival + clock latency."""
    arr = dm.flop_input_arrival(design)
    clk = max(dm.clk_latency.values()) if dm.clk_latency else 0.0
    top = margin * (max(arr.values()) + clk)
    return [round(top * k / (n - 1), 2) for k in range(n)]


def run(design, dm, T=8, offsets=None, periods=None, xband_ps=0.0):
    """Returns a result dict (schema: interface/README.md). Sweeps offsets x periods over all 256 sigs."""
    offsets = offsets or list(range(1, T))
    periods = periods or default_periods(design, dm)
    classes = {}
    for sig in range(256):
        classes.setdefault(design.sig_class(sig), []).append(sig)
    t0 = time.time()
    cells_out = []
    # per (offset, period): counts and the set of realized-flip signatures that SUCCEED
    from .netlist import INIT
    for offset in offsets:
        # precompute the settle() waveform once per sig class (independent of period)
        wf_by_class, base_by_class = {}, {}
        for cls, sigs in classes.items():
            rep = sigs[0]
            base = glitch.fault_free_states(design, T, rep)
            frm = base[0][offset - 1] if offset >= 1 else INIT
            to = base[0][offset]
            wf_by_class[cls] = timing.settle(design, dm, frm, to, rep)
            base_by_class[cls] = base
        for P in periods:
            memo = {}
            counts = {"SUCCESS": 0, "CRASH": 0, "NO_EFFECT": 0}
            succ_sigs = []
            nonmix_sigs, nonmix_wrong, nonmix_example = 0, 0, None
            for cls, sigs in classes.items():
                rep = sigs[0]
                r = glitch.glitch_shot(design, dm, T, offset, P, rep, xband_ps,
                                       _waveform=wf_by_class[cls], _base=base_by_class[cls])
                memo[cls] = r
                if r["nonmix_mask"]:
                    nonmix_sigs += len(sigs)
                    nonmix_wrong += sum(1 for s in sigs if s != KEY)
                    if nonmix_example is None or (nonmix_example["sig"] == hex(KEY) and rep != KEY):
                        nonmix_example = dict(sig=hex(rep), old=hex(r["old_next"]), new=hex(r["good_next"]),
                                              captured=hex(r["captured"]), bits=hex(r["nonmix_mask"]))
                for s in sigs:
                    out = r["outcome"]
                    # SUCCESS requires sig != KEY; the KEY sig can never be a "wrong-key" success
                    if out == "SUCCESS" and s == KEY:
                        out = "CRASH" if r["captured"] != r["good_next"] else "NO_EFFECT"
                    counts[out] += 1
                    if out == "SUCCESS":
                        succ_sigs.append(s)
            # representative realized flip set among successes (all non-key classes share it here)
            succ_flips = None
            for cls, r in memo.items():
                if r["outcome"] == "SUCCESS" and classes[cls][0] != KEY:
                    succ_flips = r["realized_flips"]
                    break
            cells_out.append(dict(offset=offset, period_ps=P, counts=counts,
                                  n_success_sigs=len(succ_sigs),
                                  success_sig_examples=[hex(s) for s in succ_sigs[:4]],
                                  realized_flips=succ_flips,
                                  n_nonmix_capture_sigs=nonmix_sigs, n_nonmix_capture_wrong_sigs=nonmix_wrong,
                                  nonmix_example=nonmix_example))
    secs = round(time.time() - t0, 3)
    arr = dm.flop_input_arrival(design)
    return dict(
        schema="vlab-glitch-campaign/1",
        tool="vlab (virtual glitch lab)",
        honesty="SIMULATION, not measurement; clock-glitch / timing-violation model on the placed sky130 netlist",
        design=design.id, top=design.top, T=T,
        delay_model=dict(source=dm.source, note="see delaymodel.py; ASSUMED linear model unless SOURCED(sdf)"),
        sta_flop_arrival_ps={str(i): round(arr[i], 2) for i in range(8)},
        clk_latency_ps={design.flops[i].name: round(dm.clk_latency[design.flops[i].out], 2) for i in range(8)},
        offsets=offsets, periods_ps=periods, xband_ps=xband_ps,
        sig_classes=len(classes),
        nonmix_captures=dict(
            note=("captures with >= 1 bit that is neither the old value S[offset] nor the new value "
                  "S[offset+1] (hazard captured mid-settling); they show that the capture is not limited "
                  "to per-bit old/new mixes"),
            cells=sum(1 for c in cells_out if c["n_nonmix_capture_sigs"]),
            cells_wrong_key=sum(1 for c in cells_out if c["n_nonmix_capture_wrong_sigs"]),
            sig_cells=sum(c["n_nonmix_capture_sigs"] for c in cells_out),
            sig_cells_wrong_key=sum(c["n_nonmix_capture_wrong_sigs"] for c in cells_out),
            cells_total=len(cells_out)),
        runtime_s=secs,
        cells=cells_out,
    )
