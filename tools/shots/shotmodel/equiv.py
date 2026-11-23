"""Exhaustive equivalence of a placed netlist with the RTL behaviour (no faults).

Two checks, both complete enumerations:
  transition : for every one of the 256 state values and every one of the 256 sig values, the placed netlist's next
               state equals the RTL next state, and boot_word / boot_ok equal the RTL outputs (65,536 cases).
  boot       : from the power-up state 0xF0, for every sig value, the boot_word / boot_ok traces over T cycles are
               equal (256 x T cases); this is the "boot sequence over all 256 keys" check.
"""
from . import rtlref, sim
from .design import KEY, GOOD


def check_transition(design, rtl=None):
    nxt_fn = rtlref.NEXT[rtl or design.top]
    bad = 0
    for st in range(256):
        state = [sim.ALL if (st >> i) & 1 else 0 for i in range(8)]
        match, ok, nxt, _ = sim.cycle_int(design, state)
        for sig in range(256):
            got = sim.lane_word(nxt, sig)
            exp = nxt_fn(st, sig)
            w, okr = rtlref.out(st)
            if got != exp or ((ok >> sig) & 1) != okr or ((match >> sig) & 1) != (1 if w == GOOD else 0):
                bad += 1
    return dict(cases=256 * 256, mismatches=bad)


def check_boot(design, T=8, rtl=None):
    nxt_fn = rtlref.NEXT[rtl or design.top]
    trace = sim.run_int(design, T)
    bad = 0
    accepted = set()
    for sig in range(256):
        st = 0xF0
        for t in range(T):
            match, ok, state = trace[t]
            w, okr = rtlref.out(st)
            if sim.lane_word(state, sig) != w or ((ok >> sig) & 1) != okr:
                bad += 1
            if (match >> sig) & 1:
                accepted.add(sig)
            st = nxt_fn(st, sig)
    return dict(cases=256 * T, mismatches=bad, accepted_sig=sorted(accepted), only_key_accepted=accepted == {KEY})
