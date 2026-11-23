"""Zero-delay, cycle-accurate functional simulator for a placed Design -- the ground-truth oracle.

Cycle semantics (identical to scripts/glitchsat.py and to ext/shots/sim.py):
  at cycle t the flop Q nets hold the current state, the combinational cells are evaluated in
  topological order, boot_word / boot_ok are read, then the flops capture their D values for t+1.

Two back ends share the cell table:
  * run_int : Python big-integers, 256 lanes = all values of sig (bit-parallel, no faults)
  * step_scalar : one concrete (state, sig), returns every net value (used by the timing engine as the
    "settled value" each net must reach, and for the glitch model's old/new comparison)
"""
from . import cells
from .netlist import KEY, GOOD, INIT

LANES = 256
ALL = (1 << LANES) - 1
SIGLANE = [sum(1 << s for s in range(LANES) if (s >> i) & 1) for i in range(8)]  # lane s carries sig=s
BAD = ALL ^ (1 << KEY)                                                           # lanes with sig != KEY


def init_state_int():
    return [ALL if (INIT >> i) & 1 else 0 for i in range(8)]


def cycle_int(design, state):
    """Bit-parallel over all 256 sig values. state: 8 lane-integers. Returns (word_match, ok, next_state)."""
    v = {n: SIGLANE[i] for i, n in enumerate(design.sig_nets)}
    for c, s in zip(design.flops, state):
        v[c.out] = s
    NOT = lambda a: a ^ ALL
    for c in design.comb:
        v[c.out] = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)}, NOT)
    match = ALL
    for i, n in enumerate(design.word_nets):
        match &= v[n] if (GOOD >> i) & 1 else v[n] ^ ALL
    f = cells.FLOP["dfxtp"]
    nxt = [v[c.pins[f["d"]]] for c in design.flops]
    return match, v[design.ok_net], nxt


def run_int(design, T):
    """Returns per-cycle list of (word_match_lanes, ok_lanes, state_at_cycle_start)."""
    st = init_state_int()
    out = []
    for _ in range(T):
        match, ok, nxt = cycle_int(design, st)
        out.append((match, ok, st))
        st = nxt
    return out


def accepts_wrong_key(design, T):
    """Lanes (sig values) for which boot_word==GOOD at some cycle in 0..T-1 AND sig != KEY (fault-free)."""
    hit = 0
    for match, _ok, _st in run_int(design, T):
        hit |= match
    return hit & BAD


def step_scalar(design, state8, sig, forced=None):
    """One cycle for ONE concrete state (int 0..255) and ONE sig (int 0..255).
    forced: optional {net_name: 0/1} overrides applied after evaluating each net (models a held/forced value).
    Returns dict net->0/1 for every flop Q, comb out, and port bit, plus 'next_state' int and 'ok' int."""
    forced = forced or {}
    v = {}
    for i, n in enumerate(design.sig_nets):
        v[n] = (sig >> i) & 1
    for i, c in enumerate(design.flops):
        v[c.out] = forced.get(c.out, (state8 >> i) & 1)
    NOT = lambda a: a ^ 1
    for c in design.comb:
        r = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)}, NOT) & 1
        v[c.out] = forced.get(c.out, r)
    f = cells.FLOP["dfxtp"]
    nxt = 0
    for i, c in enumerate(design.flops):
        nxt |= (v[c.pins[f["d"]]] & 1) << i
    # reserved keys (cannot collide with sky130 net names, which never contain '#')
    v["#next"] = nxt
    v["#ok"] = v[design.ok_net]
    v["#word"] = sum((v[n] & 1) << i for i, n in enumerate(design.word_nets))
    return v


def run_scalar(design, T, sig, forced_by_cycle=None):
    """Concrete run for one sig. forced_by_cycle: {cycle: {net: val}}.
    Returns (states list length T+1, accepted bool over 0..T-1)."""
    forced_by_cycle = forced_by_cycle or {}
    st = INIT
    states = [st]
    accepted = False
    for t in range(T):
        v = step_scalar(design, st, sig, forced_by_cycle.get(t))
        if v["#word"] == GOOD:
            accepted = True
        st = v["#next"]
        states.append(st)
    return states, accepted
