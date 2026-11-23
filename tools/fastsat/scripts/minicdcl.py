#!/usr/bin/env python3
"""minicdcl: a small pure-Python CDCL SAT solver (fallback backend of glitchsat_sat.py).

Features: two-watched-literal propagation with a separate binary-clause path, first-UIP clause learning with
recursive-free (local) minimisation, VMTF decision queue, phase saving, Luby restarts, learned-clause database
reduction by LBD, incremental solving under assumptions (learned clauses are kept between calls; they are implied
by the clause database alone, never by the assumptions, so reuse is sound).

It is meant for correctness testing and for small instances when no native solver is installed. It is slow compared
with CaDiCaL/Glucose/Kissat (interpreted Python). No claim about its speed is made anywhere.

API
    s = Solver(nvars)            # variables are 1..nvars, literals are +v / -v
    s.add_clause([1, -2, 3])
    r = s.solve(assumptions=[..], deadline=None)   # True (SAT), False (UNSAT under assumptions), None (deadline hit)
    s.model()                    # list m with m[v] in (True, False) for v = 1..nvars (m[0] unused)
Also usable as a DIMACS command-line solver (SAT-competition output format):  python3 minicdcl.py file.cnf
"""
import sys, time

__all__ = ['Solver', 'parse_dimacs']


def _luby(i):
    """i-th element (1-based) of the Luby sequence 1,1,2,1,1,2,4,..."""
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    while True:
        if i == (1 << k) - 1:
            return 1 << (k - 1)
        i -= (1 << (k - 1)) - 1
        k = 1
        while (1 << k) - 1 < i:
            k += 1


class Solver:
    def __init__(self, nvars=0):
        self.n = 0
        self.ok = True
        self.val = [0]            # val[lit] for lit in -n..n (negative index wraps): 1 true, -1 false, 0 unassigned
        self.watches = [None]     # watches[lit]: long clauses in which lit is one of the two watched literals
        self.bins = [None]        # bins[lit]: literals implied TRUE when lit becomes FALSE (binary clauses)
        self.level = [0]
        self.reason = [None]
        self.phase = [False]
        self.seen = [0]
        self.trail = []
        self.trail_lim = []
        self.qhead = 0
        self.clauses = []         # original long clauses (len >= 3)
        self.learnts = []         # learned long clauses, each has LBD in self.lbd[id(c)]
        self.lbd = {}
        # VMTF queue
        self.vprev = [0]; self.vnext = [0]; self.btime = [0]
        self.qfirst = 0; self.qlast = 0; self.searched = 0; self.stamp = 0
        self.stats = dict(conflicts=0, decisions=0, propagations=0, restarts=0, learned=0, reductions=0)
        self._model = None
        self.max_learnts = 4000
        if nvars:
            self.new_vars(nvars)

    # ------------------------------------------------------------ variables / clauses
    def new_vars(self, upto):
        """Make variables 1..upto exist."""
        if upto <= self.n:
            return
        old, n = self.n, upto
        # arrays indexed by signed literal: size 2n+1, index l (positive) and -l (wraps to 2n+1-l)
        def regrow(arr, fill):
            new = [fill() for _ in range(2 * n + 1)]
            for v in range(1, old + 1):
                new[v] = arr[v]; new[-v] = arr[-v]
            return new
        self.val = regrow(self.val, lambda: 0) if old else [0] * (2 * n + 1)
        self.watches = regrow(self.watches, list) if old else [[] for _ in range(2 * n + 1)]
        self.bins = regrow(self.bins, list) if old else [[] for _ in range(2 * n + 1)]
        ext = n - old
        self.level += [0] * ext; self.reason += [None] * ext; self.phase += [False] * ext; self.seen += [0] * ext
        self.vprev += [0] * ext; self.vnext += [0] * ext; self.btime += [0] * ext
        for v in range(old + 1, n + 1):          # append to the front of the VMTF queue
            self.vprev[v] = self.qlast; self.vnext[v] = 0
            if self.qlast: self.vnext[self.qlast] = v
            else: self.qfirst = v
            self.qlast = v
            self.stamp += 1; self.btime[v] = self.stamp
        self.searched = self.qlast
        self.n = n

    def add_clause(self, lits):
        """Add a clause. Must be called at decision level 0 (i.e. not from inside solve)."""
        if not self.ok:
            return False
        if self.trail_lim:
            self._backtrack(0)
        mx = 0
        for l in lits:
            a = l if l > 0 else -l
            if a > mx: mx = a
        if mx > self.n:
            self.new_vars(mx)
        val = self.val
        out = []; s = set()
        for l in lits:
            if l == 0: raise ValueError('literal 0')
            if val[l] == 1 or -l in s: return True      # satisfied at level 0 / tautology
            if val[l] == -1 or l in s: continue
            s.add(l); out.append(l)
        if not out:
            self.ok = False; return False
        if len(out) == 1:
            self._enqueue(out[0], None)
            if self._propagate() is not None:
                self.ok = False
            return self.ok
        if len(out) == 2:
            self.bins[out[0]].append(out[1]); self.bins[out[1]].append(out[0])
        else:
            self.clauses.append(out)
            self.watches[out[0]].append(out); self.watches[out[1]].append(out)
        return True

    # ------------------------------------------------------------ core
    def _enqueue(self, lit, reason):
        self.val[lit] = 1; self.val[-lit] = -1
        v = lit if lit > 0 else -lit
        self.level[v] = len(self.trail_lim)
        self.reason[v] = reason
        self.trail.append(lit)

    def _propagate(self):
        """Unit propagation. Returns a conflicting clause (list of literals, all false) or None."""
        val = self.val; watches = self.watches; bins = self.bins; trail = self.trail
        level = self.level; reason = self.reason
        dl = len(self.trail_lim)
        qhead = self.qhead
        confl = None
        while qhead < len(trail):
            fl = -trail[qhead]; qhead += 1          # fl just became false
            for o in bins[fl]:                      # binary clauses (fl v o)
                vo = val[o]
                if vo == -1:
                    confl = [o, fl]; break
                if vo == 0:
                    val[o] = 1; val[-o] = -1
                    v = o if o > 0 else -o
                    level[v] = dl; reason[v] = (o, fl)
                    trail.append(o)
            if confl is not None:
                break
            ws = watches[fl]
            i = j = 0; n = len(ws)
            while i < n:
                c = ws[i]; i += 1
                if c[0] == fl:
                    c[0] = c[1]; c[1] = fl
                first = c[0]
                if val[first] == 1:
                    ws[j] = c; j += 1; continue
                for k in range(2, len(c)):
                    l = c[k]
                    if val[l] != -1:
                        c[1] = l; c[k] = fl
                        watches[l].append(c)
                        break
                else:
                    ws[j] = c; j += 1
                    if val[first] == -1:
                        confl = c
                        while i < n:
                            ws[j] = ws[i]; j += 1; i += 1
                        break
                    val[first] = 1; val[-first] = -1
                    v = first if first > 0 else -first
                    level[v] = dl; reason[v] = c
                    trail.append(first)
            del ws[j:]
            if confl is not None:
                break
        self.stats['propagations'] += qhead - self.qhead
        self.qhead = qhead
        return confl

    def _bump(self, v):
        """Move variable v to the front (most recently bumped end) of the VMTF queue."""
        if self.qlast == v:
            return
        p, nx = self.vprev[v], self.vnext[v]
        if p: self.vnext[p] = nx
        else: self.qfirst = nx
        self.vprev[nx] = p                           # nx != 0 because v is not last
        if self.searched == v:
            self.searched = nx
        self.vprev[v] = self.qlast; self.vnext[v] = 0
        self.vnext[self.qlast] = v; self.qlast = v
        self.stamp += 1; self.btime[v] = self.stamp
        if self.val[v] == 0:
            self.searched = v

    def _analyze(self, confl):
        """First-UIP learning. Returns (learned clause with asserting literal first, backtrack level, lbd)."""
        seen = self.seen; level = self.level; reason = self.reason; trail = self.trail
        dl = len(self.trail_lim)
        learnt = [0]; counter = 0; p = 0; idx = len(trail) - 1
        marked = []
        c = confl
        while True:
            for q in c:
                if q == p: continue
                v = q if q > 0 else -q
                if not seen[v] and level[v] > 0:
                    seen[v] = 1; marked.append(v)
                    if level[v] >= dl: counter += 1
                    else: learnt.append(q)
            while not seen[trail[idx] if trail[idx] > 0 else -trail[idx]]:
                idx -= 1
            p = trail[idx]; idx -= 1
            v = p if p > 0 else -p
            counter -= 1
            if counter == 0:
                break
            c = reason[v]
        learnt[0] = -p
        # local minimisation: drop a literal whose reason clause is entirely made of seen (or level-0) literals
        if len(learnt) > 2:
            out = [learnt[0]]
            for q in learnt[1:]:
                r = reason[q if q > 0 else -q]
                if r is None:
                    out.append(q); continue
                for x in r:
                    vx = x if x > 0 else -x
                    if not seen[vx] and level[vx] > 0:
                        out.append(q); break
            learnt = out
        for v in marked:
            seen[v] = 0
        # bump in trail (assignment) order so the most recently assigned ends up in front
        marked.sort(key=self.btime.__getitem__)
        for v in marked:
            self._bump(v)
        if len(learnt) == 1:
            return learnt, 0, 1
        mi = 1; ml = level[learnt[1] if learnt[1] > 0 else -learnt[1]]
        for i in range(2, len(learnt)):
            lv = level[learnt[i] if learnt[i] > 0 else -learnt[i]]
            if lv > ml: ml = lv; mi = i
        learnt[1], learnt[mi] = learnt[mi], learnt[1]
        lbd = len({level[q if q > 0 else -q] for q in learnt})
        return learnt, ml, lbd

    def _backtrack(self, lvl):
        if len(self.trail_lim) <= lvl:
            return
        val = self.val; phase = self.phase; btime = self.btime; trail = self.trail
        start = self.trail_lim[lvl]
        s = self.searched; bs = btime[s]
        for i in range(len(trail) - 1, start - 1, -1):
            l = trail[i]
            val[l] = 0; val[-l] = 0
            if l > 0:
                phase[l] = True
                if btime[l] > bs: s = l; bs = btime[l]
            else:
                phase[-l] = False
                if btime[-l] > bs: s = -l; bs = btime[-l]
        self.searched = s
        del trail[start:]
        del self.trail_lim[lvl:]
        self.qhead = start

    def _reduce_db(self):
        """Delete about half of the learned long clauses (highest LBD first); keep LBD <= 2 and reason clauses."""
        self.stats['reductions'] += 1
        locked = {id(r) for r in self.reason if r is not None}
        lbd = self.lbd
        ls = sorted(self.learnts, key=lambda c: (lbd[id(c)], len(c)))
        keep = []; half = len(ls) // 2
        dead = set()
        for i, c in enumerate(ls):
            if i < half or lbd[id(c)] <= 2 or id(c) in locked:
                keep.append(c)
            else:
                dead.add(id(c)); del lbd[id(c)]
        self.learnts = keep
        if dead:
            for l in range(-self.n, self.n + 1):
                if l == 0: continue
                ws = self.watches[l]
                if ws:
                    self.watches[l] = [c for c in ws if id(c) not in dead]

    def solve(self, assumptions=(), deadline=None, conflict_limit=None):
        """True = satisfiable (model available), False = unsatisfiable under the assumptions, None = limit reached."""
        self._model = None
        if not self.ok:
            return False
        for a in assumptions:
            if abs(a) > self.n: self.new_vars(abs(a))
        self._backtrack(0)
        if self._propagate() is not None:
            self.ok = False; return False
        assumptions = list(assumptions)
        na = len(assumptions)
        val = self.val; vprev = self.vprev; phase = self.phase
        restart_n = 1; budget = 64 * _luby(1); since = 0
        total0 = self.stats['conflicts']
        while True:
            confl = self._propagate()
            if confl is not None:
                self.stats['conflicts'] += 1; since += 1
                if not self.trail_lim:
                    self.ok = False; return False
                learnt, bl, lbd = self._analyze(confl)
                self._backtrack(bl)
                if len(learnt) == 1:
                    self._enqueue(learnt[0], None)
                elif len(learnt) == 2:
                    self.bins[learnt[0]].append(learnt[1]); self.bins[learnt[1]].append(learnt[0])
                    self._enqueue(learnt[0], (learnt[0], learnt[1]))
                else:
                    self.learnts.append(learnt); self.lbd[id(learnt)] = lbd
                    self.watches[learnt[0]].append(learnt); self.watches[learnt[1]].append(learnt)
                    self._enqueue(learnt[0], learnt)
                self.stats['learned'] += 1
                if (self.stats['conflicts'] & 127) == 0:
                    if deadline is not None and time.time() > deadline:
                        self._backtrack(0); return None
                    if conflict_limit is not None and self.stats['conflicts'] - total0 >= conflict_limit:
                        self._backtrack(0); return None
                continue
            if since >= budget:                      # restart
                since = 0; restart_n += 1; budget = 64 * _luby(restart_n)
                self.stats['restarts'] += 1
                self._backtrack(0)
                if len(self.learnts) > self.max_learnts:
                    self._reduce_db(); self.max_learnts = int(self.max_learnts * 1.1) + 100
                if deadline is not None and time.time() > deadline:
                    return None
                continue
            # decide: assumptions first
            dl = len(self.trail_lim)
            lit = 0
            while dl < na:
                a = assumptions[dl]
                if val[a] == 1:
                    self.trail_lim.append(len(self.trail)); dl += 1
                elif val[a] == -1:
                    self._backtrack(0); return False
                else:
                    lit = a; break
            if lit == 0:
                v = self.searched
                while v and val[v] != 0:
                    v = vprev[v]
                if v == 0:                            # all assigned: model
                    self._model = [None] + [val[x] == 1 for x in range(1, self.n + 1)]
                    self._backtrack(0)
                    return True
                self.searched = v
                lit = v if phase[v] else -v
            self.stats['decisions'] += 1
            if deadline is not None and (self.stats['decisions'] & 4095) == 0 and time.time() > deadline:
                self._backtrack(0); return None
            self.trail_lim.append(len(self.trail))
            self._enqueue(lit, None)

    def model(self):
        return self._model


def parse_dimacs(text):
    nvars = 0; clauses = []; cur = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in 'c%':
            continue
        if line[0] == 'p':
            nvars = int(line.split()[2]); continue
        for tok in line.split():
            x = int(tok)
            if x == 0:
                clauses.append(cur); cur = []
            else:
                cur.append(x)
    if cur:
        clauses.append(cur)
    return nvars, clauses


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: minicdcl.py FILE.cnf', file=sys.stderr); return 2
    nvars, clauses = parse_dimacs(open(argv[0]).read())
    s = Solver(nvars)
    for c in clauses:
        s.add_clause(c)
    r = s.solve()
    print('c minicdcl', ' '.join(f'{k}={v}' for k, v in s.stats.items()))
    if r:
        print('s SATISFIABLE')
        m = s.model(); lits = [v if m[v] else -v for v in range(1, s.n + 1)] + [0]
        for i in range(0, len(lits), 20):
            print('v', ' '.join(map(str, lits[i:i + 20])))
        return 10
    print('s UNSATISFIABLE')
    return 20


if __name__ == '__main__':
    sys.exit(main())
