"""Hazard probe: how often does the event-driven capture produce a bit that is neither OLD nor NEW?

Under the ASSUMED delays and under random per-cell delay scalings, for every campaign offset (1..T-1),
every sig class and every distinct sample instant of the settling waveform (plus 0), the capture is
compared with the old value S[offset] and the new value S[offset+1]; captures with a bit equal to
neither are counted ("non-mix" captures), and the fault-free continuation from each capture is checked
for a wrong-key accept.  SIMULATED; the delay scalings are ASSUMED (uniform x lo..x hi per cell).

This reproduces the method of the independent review probe (REVIEW_A, rv_vlab_probe.py parts a/b):
200 perturbations, seed 1, x0.3..x3 gave V1 2,071 non-mix captures, V2 0, and 0 wrong-key accepts.
"""
import random

from . import delaymodel, sim, timing
from .netlist import GOOD, KEY


def probe(design, T=8, trials=200, seed=1, lo=0.3, hi=3.0, tail=6):
    rnd = random.Random(seed)
    classes = {}
    for s in range(256):
        classes.setdefault(design.sig_class(s), []).append(s)
    reps = [v[0] for v in classes.values()]
    dm0 = delaymodel.DelayModel(design)
    base = {rep: sim.run_scalar(design, T, rep)[0] for rep in reps}
    rows = []
    tot_nonmix = tot_acc = tot_caps = 0
    examples = []
    for trial in range(trials + 1):
        dm = dm0
        if trial:
            dm = delaymodel.DelayModel(design)
            for k in dm.cell_delay:
                dm.cell_delay[k] *= rnd.uniform(lo, hi)
        nonmix = acc = caps = 0
        lat = max(dm.clk_latency.values())
        for off in range(1, T):
            for rep in reps:
                st = base[rep]
                wf = timing.settle(design, dm, st[off - 1], st[off], rep)
                old, new = st[off], st[off + 1]
                times = sorted({t for w in wf.values() for t, _ in w})
                for P in sorted(set([0.0] + [t + 0.01 for t in times])):
                    cap, _, _ = timing.sample(design, dm, wf, max(0.0, P - lat))
                    caps += 1
                    if (cap ^ old) & (cap ^ new) & 0xFF:
                        nonmix += 1
                        if len(examples) < 3:
                            examples.append(dict(trial=trial, offset=off, sig=hex(rep), old=hex(old),
                                                 new=hex(new), captured=hex(cap)))
                    s2, hit = cap, cap == GOOD
                    for _ in range(off + 1, T + tail):
                        v = sim.step_scalar(design, s2, rep)
                        hit = hit or v["#word"] == GOOD
                        s2 = v["#next"]
                    if hit and rep != KEY:
                        acc += 1
        rows.append(dict(trial=trial, nonmix=nonmix, wrong_key_accepts=acc))
        tot_nonmix += nonmix
        tot_acc += acc
        tot_caps += caps
    return dict(design=design.id, label="SIMULATED (ASSUMED delays and ASSUMED random scalings)",
                trials=trials, seed=seed, scale_range=[lo, hi], captures_checked=tot_caps,
                nonmix_captures=tot_nonmix, nonmix_captures_default_delays=rows[0]["nonmix"],
                wrong_key_accepts=tot_acc, examples=examples,
                note=("trial 0 = ASSUMED default delays; trials 1..N = each cell delay scaled by a uniform "
                      "random factor. Counts are per (trial, offset, sig class, sample instant)."))
