"""The abstract GlitchSAT bit-flip model, re-implemented on the PLACED netlist in pure Python, and a
diagnostic check under a HAZARD-FREE capture model.

Abstract model (matches scripts/glitchsat.py and validation/netsim.py): a fault at cycle t flips a chosen
net (flop Q or gate output) for that cycle; an attack succeeds if boot_word==GOOD at some cycle while
sig != KEY.  Here we enumerate FLOP-site single-cycle flip sets, the family a single clock glitch acts on
(a glitch corrupts flop capture at one edge, nothing else).

Old/new mix check (`oldnew_mix_check`): under a HAZARD-FREE capture model, a shortened period lets each
state bit capture only its OLD value (the D value before the edge's settling) or its NEW value (the
settled one).  The check asks, for every campaign offset and every wrong-key sig, whether some per-bit
old/new mix equals GOOD, or leads to GOOD in the fault-free continuation.  This is NOT a proof that no
clock glitch works: the event-driven simulator of this lab (timing.settle) models hazards, and on V1 it
does capture values that are neither old nor new (see campaign `nonmix_*` counts and hazard.py).  The
statement this lab supports is the simulated one: 0 wrong-key accepts in the sweep (ASSUMED delays).
"""
from . import sim
from .netlist import KEY, GOOD, INIT

LANES = sim.LANES
ALL = sim.ALL
BAD = sim.BAD


def _cycle_faulted(design, state, flip_mask):
    """One bit-parallel cycle with flop Q bits in flip_mask XORed (abstract flop flip)."""
    from . import cells
    v = {n: sim.SIGLANE[i] for i, n in enumerate(design.sig_nets)}
    for i, c in enumerate(design.flops):
        s = state[i]
        v[c.out] = (s ^ ALL) if (flip_mask >> i) & 1 else s
    NOT = lambda a: a ^ ALL
    for c in design.comb:
        v[c.out] = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)}, NOT)
    match = ALL
    for i, n in enumerate(design.word_nets):
        match &= v[n] if (GOOD >> i) & 1 else v[n] ^ ALL
    f = cells.FLOP["dfxtp"]
    nxt = [v[c.pins[f["d"]]] for c in design.flops]
    return match, nxt


def attack_lanes(design, T, faults):
    """faults: {cycle: flip_mask}. Returns lanes (sig values) that reach GOOD at some cycle AND sig!=KEY."""
    st = sim.init_state_int()
    hit = 0
    for t in range(T):
        match, nxt = _cycle_faulted(design, st, faults.get(t, 0))
        hit |= match
        st = nxt
    return hit & BAD


def enumerate_flop_attacks(design, T):
    """Every single-cycle flop flip set (1..8 flops at one cycle). Returns dict:
       min_flips (None if none), successes = list of (cycle, flip_mask, nflops, n_sig_values)."""
    successes = []
    best = None
    for t in range(T):
        for mask in range(1, 256):
            lanes = attack_lanes(design, T, {t: mask})
            if lanes:
                nf = bin(mask).count("1")
                nsig = bin(lanes).count("1")
                successes.append((t, mask, nf, nsig))
                if best is None or nf < best:
                    best = nf
    return dict(min_flips=best, successes=successes)


def oldnew_mix_check(design, T, offsets=None, continuation=20):
    """Hazard-free capture model (DIAGNOSTIC, not a proof; see module docstring).

    For each campaign offset t (default 1..T-1, as campaign.run) the glitched edge captures, per bit, the
    old value S[t] or the new value S[t+1] (S = fault-free state trajectory of that sig; this matches
    glitch.glitch_shot, which compares the capture with S[t+1]).  For every wrong-key sig (all 255, via
    their sig classes) and every per-bit mix it checks whether the mix is GOOD, or whether the fault-free
    continuation from the mix shows GOOD within `continuation` cycles.  Returns a dict."""
    from .netlist import KEY as _K
    offsets = list(offsets) if offsets else list(range(1, T))
    classes = {}
    for s in range(256):
        if s != _K:
            classes.setdefault(design.sig_class(s), []).append(s)
    trajs = {}
    for s in range(256):
        if s != _K:
            trajs[s] = tuple(sim.run_scalar(design, T, s)[0])
    covered = sum(len(v) for v in classes.values())
    per_edge = []
    for t in offsets:
        rows = {}
        for cls, sigs in classes.items():
            for sg in sigs:
                st = trajs[sg]
                old, new = st[t], st[t + 1]
                key = (old, new, cls)
                if key in rows:
                    rows[key]["sigs"] += 1
                    continue
                rep = sg
                diff = old ^ new
                mixes, sub = [], diff
                while True:
                    mixes.append((old & ~diff) | (new & sub) | (old & diff & ~sub))
                    if sub == 0:
                        break
                    sub = (sub - 1) & diff
                is_mix = GOOD in mixes
                reached = []
                for mix in mixes:
                    s2, hit = mix & 0xFF, mix == GOOD
                    for _ in range(continuation):
                        v = sim.step_scalar(design, s2, rep)
                        hit = hit or v["#word"] == GOOD
                        s2 = v["#next"]
                    if hit:
                        reached.append(mix)
                rows[key] = dict(old=old, new=new, n_mixes=len(mixes), good_is_mix=is_mix,
                                 mixes_reaching_good=sorted(reached), sigs=1)
        for r in rows.values():
            per_edge.append(dict(offset=t, old_state=r["old"], new_state=r["new"], n_mixes=r["n_mixes"],
                                 n_wrong_sigs=r["sigs"], good_is_mix=r["good_is_mix"],
                                 good_reached_from_a_mix=bool(r["mixes_reaching_good"]),
                                 mixes_reaching_good=[hex(m) for m in r["mixes_reaching_good"]]))
    return dict(model="hazard-free capture (each bit old or new); DIAGNOSTIC, not a proof",
                offsets=offsets, continuation_cycles=continuation, wrong_sigs_covered=covered,
                distinct_wrong_key_trajectories=len(set(trajs.values())),
                good_reachable=any(e["good_is_mix"] or e["good_reached_from_a_mix"] for e in per_edge),
                per_edge=per_edge)
