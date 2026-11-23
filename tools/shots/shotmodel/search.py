"""Minimum number of shots that opens the lock: exhaustive, bounded search (no solver).

Problem: over cycles 0..T-1, with the attacker input sig held constant at some value != KEY and the state starting at
0xF0, choose a set of shots (cycle, disturbance set) with at most K shots in total such that the goal is observed at
some cycle < T. Several shots in one cycle disturb the UNION of their sets. Report the smallest number of shots.

Why exhaustive search is cheap here (the pruning, all exact):
  1. sig classes: two sig values are interchangeable when every cell that reads sig pins computes the same function of
     its remaining inputs; one representative per class is searched (V1/V2: 7 classes instead of 255 values).
  2. state sharing: for a fixed sig the design is an 8-bit state machine, so "fewest shots to be in state s at the
     start of cycle t" is a shortest-path problem; only (state, shots used) matters, not the history.
  3. union levels: the disturbance sets reachable with exactly j shots in one cycle (and not with fewer) are
     de-duplicated once (level j). A state reached with c shots only tries levels j <= K - c.
  4. iterative deepening on K: K = 0, 1, 2, ... stops at the first K with an attack, so the expensive top level is only
     enumerated when all smaller budgets have been exhausted.
All candidates of a level are evaluated at once with numpy (one boolean lane per candidate).
"A result '> K'" means: no attack with up to K shots within T cycles under this model. It is not a proof of security.
"""
import time
import numpy as np
from . import cells, sim
from .design import KEY, INIT

GOALS = ("word", "ok", "word_clean")
# word       : boot_word == 0x96 observed at some cycle < T (the goal of scripts/glitchsat.py)
# ok         : boot_ok == 1 observed at some cycle < T
# word_clean : boot_word == 0x96 observed in a cycle in which NO shot is fired (the accepted word is really held by
#              the state flops and is not just the momentary image of disturbed Q nets)


def sig_classes(design):
    """Partition the 255 wrong sig values; returns list of (representative, [members])."""
    readers = [c for c in design.comb if any(c.pins[p] in design.sig_nets for p in cells.input_pins(c.master))]
    pos = {n: i for i, n in enumerate(design.sig_nets)}
    groups = {}
    for sig in range(256):
        if sig == KEY:
            continue
        signature = []
        for c in readers:
            ins = cells.input_pins(c.master)
            free = [p for p in ins if c.pins[p] not in pos]
            tt = []
            for x in range(1 << len(free)):
                v = {p: (sig >> pos[c.pins[p]]) & 1 for p in ins if c.pins[p] in pos}
                v.update({p: (x >> i) & 1 for i, p in enumerate(free)})
                tt.append(cells.evaluate(c.master, v, lambda a: a ^ 1) & 1)
            signature.append(tuple(tt))
        groups.setdefault(tuple(signature), []).append(sig)
    return [(m[0], m) for m in groups.values()]


class UnionLevels:
    """levels[j] = sorted uint64 array of disturbance sets that need exactly j shots in one cycle (level 0 = {empty}).
    parent[j][i] = (index in level j-1, index of the added shot) for witness reconstruction."""

    def __init__(self, shot_masks, chunk=4_000_000):
        self.shots = np.asarray(shot_masks, dtype=np.uint64)
        self.levels = [np.zeros(1, dtype=np.uint64), np.unique(self.shots[self.shots != 0])]
        self.parent = [None, None]
        self.chunk = chunk

    def level(self, j):
        while len(self.levels) <= j:
            prev, base = self.levels[-1], self.levels[1]
            if len(prev) == 0 or len(base) == 0:
                self.levels.append(np.zeros(0, dtype=np.uint64))
                self.parent.append((np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)))
                continue
            lower = np.concatenate(self.levels)
            rows = max(1, self.chunk // len(base))
            acc_m = np.zeros(0, dtype=np.uint64)
            acc_p = np.zeros(0, dtype=np.int64)
            acc_s = np.zeros(0, dtype=np.int64)
            for a in range(0, len(prev), rows):
                blk = prev[a:a + rows, None] | base[None, :]
                flat = blk.ravel()
                u, first = np.unique(flat, return_index=True)
                keep = ~np.isin(u, lower)
                u, first = u[keep], first[keep]
                m = np.concatenate([acc_m, u])
                p = np.concatenate([acc_p, a + first // len(base)])
                s = np.concatenate([acc_s, first % len(base)])
                um, fi = np.unique(m, return_index=True)
                acc_m, acc_p, acc_s = um, p[fi], s[fi]
            self.levels.append(acc_m)
            self.parent.append((acc_p, acc_s))
        return self.levels[j]

    def decompose(self, j, i):
        """indices (into level 1) of j shots whose union is level j entry i"""
        out = []
        while j >= 2:
            p, s = self.parent[j]
            out.append(int(s[i]))
            i = int(p[i])
            j -= 1
        if j == 1:
            out.append(int(i))
        return out[::-1]


class Searcher:
    """Exhaustive bounded search for one (design, shot table, effect). Evaluations are shared between goals and T."""

    def __init__(self, design, shot_masks, effect="flip", classes=None, max_level_size=20_000_000, chunk=1_000_000):
        if effect not in sim.EFFECTS:
            raise ValueError("effect must be one of %s" % (sim.EFFECTS,))
        self.design, self.effect = design, effect
        self.U = UnionLevels(shot_masks)
        self.classes = classes or sig_classes(design)
        self.max_level_size, self.chunk = max_level_size, chunk
        self.cache = {}
        self.evals = 0
        self.secs = 0.0

    def _step(self, sig, s, j):
        """(distinct next states with the first candidate index for each,
            index of a candidate showing boot_word == GOOD or -1, index of a candidate showing boot_ok or -1)"""
        key = (sig, s, j)
        r = self.cache.get(key)
        if r is None:
            lv = self.U.level(j)
            hw = hk = -1
            best = {}
            for a in range(0, len(lv), self.chunk):
                nxt, match, ok = sim.cycle_np(self.design, s, sig, lv[a:a + self.chunk], self.effect)
                self.evals += len(nxt)
                if hw < 0 and match.any():
                    hw = a + int(np.argmax(match))
                if hk < 0 and ok.any():
                    hk = a + int(np.argmax(ok))
                un, fi = np.unique(nxt, return_index=True)
                for sn, i in zip(un.tolist(), fi.tolist()):
                    best.setdefault(sn, a + i)
            r = (list(best.items()), hw, hk)
            self.cache[key] = r
        return r

    def stats(self):
        return dict(secs=round(self.secs, 3), candidates_evaluated=self.evals,
                    level_sizes=[int(len(x)) for x in self.U.levels], sig_classes=len(self.classes))

    def min_shots(self, T=6, kmax=4, goal="word"):
        """Smallest number of shots (<= kmax) that reaches the goal within T cycles.
        Returns dict(min, searched_k, witness):
          min        : the minimum, or None when no attack exists with up to searched_k shots
          searched_k : largest budget searched exhaustively (kmax, or less if a level exceeded max_level_size)
          witness    : dict(sig, sig_class, shots=[(cycle, mask)], hit_cycle) for the minimum."""
        if goal not in GOALS:
            raise ValueError("goal must be one of %s" % (GOALS,))
        t0 = time.time()
        U = self.U
        searched = -1
        try:
            for K in range(0, kmax + 1):
                if len(U.level(K)) > self.max_level_size:
                    break
                for rep, members in self.classes:
                    layer = {INIT: (0, None)}                      # state -> (shots used, back pointer)
                    for t in range(T):
                        nxt_layer = {}
                        for s, (c, back) in layer.items():
                            for j in range(0, K - c + 1):
                                succ, hw, hk = self._step(rep, s, j)
                                h = hk if goal == "ok" else hw if (goal == "word" or j == 0) else -1
                                if h >= 0:
                                    path = [(t, j, h)]
                                    b = back
                                    while b is not None:
                                        path.append(b[:3])
                                        b = b[3]
                                    shots = []
                                    for (tt, jj, ii) in reversed(path):
                                        for si in U.decompose(jj, ii):
                                            shots.append((tt, int(U.levels[1][si])))
                                    if len(shots) != c + j or c + j != K:
                                        raise RuntimeError("internal error: witness size")
                                    return dict(min=K, searched_k=K,
                                                witness=dict(sig=rep, sig_class=members, shots=shots, hit_cycle=t))
                                for sn, i in succ:
                                    old = nxt_layer.get(sn)
                                    if old is None or old[0] > c + j:
                                        nxt_layer[sn] = (c + j, (t, j, i, back))
                        layer = nxt_layer
                searched = K
            return dict(min=None, searched_k=searched, witness=None)
        finally:
            self.secs += time.time() - t0


def min_shots(design, shot_masks, T=6, kmax=4, effect="flip", goal="word", **kw):
    """One-call form of Searcher(...).min_shots(...); adds stats."""
    s = Searcher(design, shot_masks, effect, **kw)
    r = s.min_shots(T, kmax, goal)
    r["stats"] = s.stats()
    return r


def replay(design, witness, T, effect="flip", goal="word"):
    """Independent re-run of a witness with the integer back end; True when the goal is observed for witness['sig']."""
    per = {}
    for t, m in witness["shots"]:
        per[t] = per.get(t, 0) | m
    lane = 1 << witness["sig"]
    for t, (match, ok, _st) in enumerate(sim.run_int(design, T, witness["shots"], effect)):
        g = ok if goal == "ok" else match
        if goal == "word_clean" and per.get(t, 0):
            continue
        if g & lane & sim.BADLANES:
            return True
    return False
