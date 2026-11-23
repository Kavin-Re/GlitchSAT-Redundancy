"""Cycle-accurate evaluation of a placed design with per-cell output disturbances.

One cycle t:  Q nets take the state (a disturbed flop cell changes its Q net in this cycle), the combinational cells are
evaluated in topological order (a disturbed cell changes its output net, seen by every reader, by the flop D pins and by
the output ports), boot_word / boot_ok are read, and the flops capture their D values for cycle t+1.
This is the same cycle semantics as scripts/glitchsat.py (flip of a gate output or flop Q net in one cycle), with the
placed sky130 cells as the gates.

Two back ends share the cell table: Python integers (256 lanes = all values of sig, bit-parallel) and numpy boolean
arrays (one lane per candidate shot combination).
"""
import numpy as np
from . import cells
from .design import KEY, GOOD, INIT

LANES = 256
ALL = (1 << LANES) - 1
SIGLANE = [sum(1 << s for s in range(LANES) if (s >> i) & 1) for i in range(8)]   # lane s carries sig = s
BADLANES = ALL ^ (1 << KEY)
EFFECTS = ("flip", "set0", "set1")


def _disturb_int(v, effect):
    return v ^ ALL if effect == "flip" else 0 if effect == "set0" else ALL


def cycle_int(design, state, hit_mask=0, effect="flip"):
    """Bit-parallel cycle over all 256 sig values.
    state: list of 8 lane-integers (flop i = boot_word[i]); hit_mask: bit c.idx set = cell disturbed in this cycle.
    Returns (word_match_lanes, ok_lanes, next_state, nets)."""
    v = {n: SIGLANE[i] for i, n in enumerate(design.sig_nets)}
    for c, s in zip(design.flops, state):
        v[c.out] = _disturb_int(s, effect) if (hit_mask >> c.idx) & 1 else s
    NOT = lambda a: a ^ ALL
    for c in design.comb:
        r = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)}, NOT)
        if (hit_mask >> c.idx) & 1:
            r = _disturb_int(r, effect)
        v[c.out] = r
    match = ALL
    for i, n in enumerate(design.word_nets):
        match &= v[n] if (GOOD >> i) & 1 else v[n] ^ ALL
    f = cells.FLOP["dfxtp"]
    nxt = [v[c.pins[f["d"]]] for c in design.flops]
    return match, v[design.ok_net], nxt, v


def init_state_int():
    return [ALL if (INIT >> i) & 1 else 0 for i in range(8)]


def run_int(design, T, shots=(), effect="flip"):
    """shots: iterable of (cycle, hit_mask). Several entries in one cycle are OR-ed (a cell hit twice is disturbed once).
    Returns per-cycle list of (word_match_lanes, ok_lanes, state_at_cycle_start)."""
    per = {}
    for t, m in shots:
        per[t] = per.get(t, 0) | m
    st = init_state_int()
    out = []
    for t in range(T):
        match, ok, nxt, _ = cycle_int(design, st, per.get(t, 0), effect)
        out.append((match, ok, st))
        st = nxt
    return out


def lane_word(state, lane):
    return sum(((s >> lane) & 1) << i for i, s in enumerate(state))


def cycle_np(design, state8, sig, masks, effect="flip"):
    """One cycle for ONE concrete state and ONE sig value, vectorised over an array of hit masks (uint64).
    Returns (next_state uint8 array as integers 0..255, word_match bool array, ok bool array)."""
    masks = np.asarray(masks, dtype=np.uint64)
    n = masks.shape[0]
    one = np.uint64(1)

    def hit(c):
        return ((masks >> np.uint64(c.idx)) & one).astype(bool)

    def disturb(val, h):
        if effect == "flip":
            return val ^ h
        if effect == "set0":
            return val & ~h
        return val | h

    v = {nm: np.full(n, bool((sig >> i) & 1)) for i, nm in enumerate(design.sig_nets)}
    for i, c in enumerate(design.flops):
        v[c.out] = disturb(np.full(n, bool((state8 >> i) & 1)), hit(c))
    for c in design.comb:
        r = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)}, np.logical_not)
        v[c.out] = disturb(r, hit(c))
    match = np.ones(n, dtype=bool)
    for i, nm in enumerate(design.word_nets):
        match &= v[nm] if (GOOD >> i) & 1 else ~v[nm]
    f = cells.FLOP["dfxtp"]
    nxt = np.zeros(n, dtype=np.uint16)
    for i, c in enumerate(design.flops):
        nxt |= v[c.pins[f["d"]]].astype(np.uint16) << i
    return nxt, match, v[design.ok_net].copy()
