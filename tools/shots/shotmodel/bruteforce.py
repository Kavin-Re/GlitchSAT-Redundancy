"""Reference enumerator: plain exhaustive enumeration of every set of at most K (cycle, shot) pairs.

Deliberately simple and separate from search.py: Python integers with one lane per sig value (all 256 values at once,
sim.cycle_int), itertools.combinations, depth-first over the cycles; no numpy, no sig classes, no union levels, no
shortest-path argument. It is slow and only used to check search.py and to count attacks.

single_flip(...) is the per-cell single-flip model on the placed netlist: the "shots" are the individual logic cells,
taken straight from the netlist without any geometry.
"""
import itertools
from . import sim


def enumerate_sets(design, shot_masks, T, K, effect="flip"):
    """Returns dict(word={size: number of attacking sets}, ok={...}, word_clean={...}, total={size: sets enumerated},
    first={goal: (size, [(cycle, mask)], sig)}).
    A set attacks when some lane with sig != KEY shows the goal at some cycle < T."""
    shot_masks = [int(m) for m in shot_masks]
    goals = ("word", "ok", "word_clean")
    res = {g: {k: 0 for k in range(K + 1)} for g in goals}
    res.update(total={k: 0 for k in range(K + 1)}, first={})

    def rec(t, state, left, used, hw, hk, hc, chosen):
        if t == T:
            res["total"][used] += 1
            for g, h in (("word", hw), ("ok", hk), ("word_clean", hc)):
                if h:
                    res[g][used] += 1
                    if g not in res["first"] or res["first"][g][0] > used:
                        res["first"][g] = (used, list(chosen), (h & -h).bit_length() - 1)
            return
        for j in range(0, left + 1):
            for sub in itertools.combinations(shot_masks, j):
                m = 0
                for x in sub:
                    m |= x
                match, ok, nxt, _ = sim.cycle_int(design, state, m, effect)
                bad = match & sim.BADLANES
                rec(t + 1, nxt, left - j, used + j, hw | bad, hk | (ok & sim.BADLANES), hc | (bad if m == 0 else 0),
                    chosen + [(t, x) for x in sub])

    rec(0, sim.init_state_int(), K, 0, 0, 0, 0, [])
    res["min"] = {g: next((k for k in range(K + 1) if res[g][k]), None) for g in goals}
    return res


def single_flip(design, T, K, effect="flip", sites="all"):
    """Per-cell single-fault model on the placed netlist: every logic cell output (or only flops / only comb)."""
    cs = {"all": design.logic, "flops": design.flops, "comb": design.comb}[sites]
    return enumerate_sets(design, [1 << c.idx for c in cs], T, K, effect)
