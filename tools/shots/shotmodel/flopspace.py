"""Reduce a winning shot set to the flop-flip space of the shared interface (schema physical-fault-campaign/1).

A shot disturbs placed cells (flops and combinational cells). Its effect on the lock is fully described by the values
seen on the 8 state-flop Q nets (= boot_word) cycle by cycle. For one sig value:

    Q_obs[t]  = boot_word seen in cycle t of the disturbed run
    E[0]      = INIT;  E[t] = fault-free next state of Q_obs[t-1]   (netlist with no disturbance)
    F[t]      = Q_obs[t] XOR E[t]                                     -> the "flop-flip set" of cycle t

Disturbing only the flops in F[t] at cycle t (no combinational cell) reproduces Q_obs exactly (induction over t, since
the next state is a function of the Q nets and sig only). `check_equivalent` re-runs that flop-only attack and checks
the trace and the goal, so every emitted flip set is verified, not just derived.
Only the goals that read boot_word (word, word_clean) reduce this way; boot_ok is a combinational output.
"""
from . import sim
from .design import GOOD, INIT


def observed_words(design, shots, sig, T, effect="flip"):
    """boot_word seen in each cycle (lane `sig`) with the given (cycle, mask) shots."""
    per = {}
    for t, m in shots:
        per[t] = per.get(t, 0) | m
    st = sim.init_state_int()
    out = []
    for t in range(T):
        _match, _ok, nxt, v = sim.cycle_int(design, st, per.get(t, 0), effect)
        out.append(sum(((v[c.out] >> sig) & 1) << i for i, c in enumerate(design.flops)))
        st = nxt
    return out


def clean_next(design, word, sig):
    st = [sim.ALL if (word >> i) & 1 else 0 for i in range(8)]
    _m, _ok, nxt, _v = sim.cycle_int(design, st, 0, "flip")
    return sim.lane_word(nxt, sig)


def flip_sets(design, shots, sig, T, effect="flip"):
    """[(cycle, F[t] as an 8-bit mask)] for every cycle with F[t] != 0, up to and including the first cycle that shows
    boot_word == GOOD (later cycles do not matter for the attack)."""
    q = observed_words(design, shots, sig, T, effect)
    out = []
    for t in range(T):
        e = INIT if t == 0 else clean_next(design, q[t - 1], sig)
        f = q[t] ^ e
        if f:
            out.append((t, f))
        if q[t] == GOOD:
            break
    return out, q


def check_equivalent(design, shots, sig, T, effect="flip"):
    """True when the flop-only attack built from flip_sets() gives the same boot_word trace (up to the first GOOD) and
    shows GOOD."""
    fs, q = flip_sets(design, shots, sig, T, effect)
    flop_shots = []
    for t, f in fs:
        m = 0
        for i, c in enumerate(design.flops):
            if (f >> i) & 1:
                m |= 1 << c.idx
        flop_shots.append((t, m))
    q2 = observed_words(design, flop_shots, sig, T, "flip")
    n = (q.index(GOOD) + 1) if GOOD in q else T
    return GOOD in q and q[:n] == q2[:n]
