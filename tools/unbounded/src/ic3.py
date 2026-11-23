"""IC3 / PDR over the fault-augmented transition system (ts.TS).

Follows Bradley, "SAT-Based Model Checking without Unrolling" (VMCAI 2011), with the frame bookkeeping of Een,
Mishchenko, Brayton, "Efficient Implementation of Property Directed Reachability" (FMCAD 2011): each blocked cube is
stored once, at the highest frame where it is known to be unreachable, and one incremental SAT solver holds the step
relation plus every frame clause behind an activation literal.

The result is either
    an attack (a chain of states from a power-up state to "goal seen", returned as a concrete trace), or
    an inductive invariant: a list of clauses over the state bits that holds at power-up, is preserved by every step
    with any allowed flips, and excludes "goal seen".
check_certificate() re-checks such an invariant in a fresh solver, without any of the IC3 bookkeeping.

Two details that matter for soundness here:
  * The step relation has restrictions (budget not exceeded, input != key). When a predecessor cube is widened
    ("lifting"), the widened cube must still satisfy the restrictions for the chosen flips; the lifting query therefore
    asks for "next state in the target AND restrictions hold", not just "next state in the target".
  * A cube may only be widened while it stays disjoint from the power-up states.
Backends without unsat cores (the pure Python one) fall back to dropping literals one at a time.
"""
import heapq, time

from ts import Unroll


class _Timeout(Exception):
    pass


class IC3:
    def __init__(self, ts, make_backend, deadline=None, log=None):
        self.ts, self.deadline, self.log = ts, deadline, log
        S = ts.S
        self.S = S
        self.cur = list(range(1, S + 1))
        self.nxt = list(range(S + 1, 2 * S + 1))
        self.nv = 2 * S + ts.naux
        m = ts.mapper(self.cur, self.nxt, 2 * S)
        self.fault_var = {b: m(ts.fault[b]) for b in ts.sites}
        # main solver: func + cons + frames
        self.b = make_backend()
        self.b.reserve(self.nv)
        for c in ts.func + ts.cons:
            self.b.add([m(l) for l in c])
        # lifting solver: func only; ok <-> every restriction holds
        self.lb = make_backend()
        self.lb.reserve(self.nv)
        for c in ts.func:
            self.lb.add([m(l) for l in c])
        self.lnv = self.nv
        oks = []
        for c in ts.cons:
            c = [m(l) for l in c]
            if len(c) == 1:
                oks.append(c[0]); continue
            self.lnv += 1; o = self.lnv
            self.lb.add([-o] + c)
            for l in c: self.lb.add([o, -l])
            oks.append(o)
        self.lnv += 1; self.l_ok = self.lnv
        self.lb.add([self.l_ok] + [-o for o in oks])
        for o in oks: self.lb.add([-self.l_ok, o])
        self.act = [self._new()]                      # activation literal of frame 0 = Init
        for c in ts.init:
            self.b.add([-self.act[0]] + list(c))      # init clauses are over current-state template vars 1..S
        self.frames = [[]]                            # frames[i]: cubes (tuples of current-state literals) blocked at level i
        self.init_cube = dict(ts.init_cube) if ts.init_mode == 'known' else None
        self.h = self.cur[ts.h_pos]
        self.stats = dict(obligations=0, blocked_cubes=0, sat_calls=0)
        # order in which generalisation tries to drop literals: inputs first, then flops, counter, goal flag
        self.rank = {}
        for i, p in enumerate(ts.in_pos + ts.q_pos + ts.u_pos + [ts.h_pos]):
            self.rank[p + 1] = i

    def _new(self):
        self.nv += 1
        self.b.reserve(self.nv)
        return self.nv

    def _solve(self, b, assumptions):
        self.stats['sat_calls'] += 1
        r = b.solve(assumptions, deadline=self.deadline)
        if r is None:
            raise _Timeout()
        return r

    def _prime(self, cube):
        S = self.S
        return [l + S if l > 0 else l - S for l in cube]

    def _F(self, i):
        """Assumptions that switch on frame i (frame 0 = Init; frame i >= 1 = every cube blocked at level >= i)."""
        return [self.act[0]] if i == 0 else self.act[i:]

    def _meets_init(self, cube):
        if self.init_cube is not None:
            ic = self.init_cube
            for l in cube:
                v = ic.get(abs(l))
                if v is not None and v != (l > 0):
                    return False
            return True                               # conservative (ignores the input != key restriction)
        return self._solve(self.b, [self.act[0]] + list(cube))

    def _state_cube(self):
        return tuple(v if self.b.val(v) else -v for v in self.cur)

    # ------------------------------------------------------------ queries
    def _rel_ind(self, cube, i, want_pred=False):
        """Is cube unreachable in one step from F_i minus cube?  True, or False (+ predecessor if asked)."""
        t = self._new()
        self.b.add([-t] + [-l for l in cube])
        pr = self._prime(cube)
        r = self._solve(self.b, self._F(i) + [t] + pr)
        out = None
        if r and want_pred:
            out = (self._state_cube(), [b for b, v in self.fault_var.items() if self.b.val(v)])
        core = None
        if not r:
            c = self.b.core()
            if c is not None:
                cs = set(c)
                core = [l for l, p in zip(cube, pr) if p in cs]
        self.b.add([-t])
        return (True, core) if not r else (False, out)

    def _lift(self, pred, faults, target):
        """Widen the full predecessor state: keep only literals needed so that, with these flips, the restrictions
        hold and the next state lies in target."""
        fset = set(faults)
        fa = [v if b in fset else -v for b, v in self.fault_var.items()]
        self.lnv += 1; t = self.lnv
        self.lb.reserve(self.lnv)
        # t -> not(ok and target')
        self.lb.add([-t, -self.l_ok] + [-l for l in self._prime(target)])
        keep = list(pred)
        r = self._solve(self.lb, fa + [t] + keep)
        if r:                                         # cannot happen (step relation is deterministic); keep the full state
            self.lb.add([-t]); return tuple(pred)
        c = self.lb.core()
        if c is not None:
            cs = set(c)
            keep = [l for l in keep if l in cs]
        else:
            for l in sorted(pred, key=lambda l: self.rank[abs(l)]):
                trial = [x for x in keep if x != l]
                if not self._solve(self.lb, fa + [t] + trial):
                    keep = trial
        self.lb.add([-t])
        return tuple(keep)

    def _generalize(self, cube, i, core=None):
        """Drop literals of a cube that is inductive relative to F_{i-1}, keeping it so and disjoint from Init."""
        cube = list(cube)
        if core is not None and len(core) < len(cube):
            cand = list(core)
            if self._meets_init(cand):                # put back one literal that separates it from the power-up states
                for l in cube:
                    if l not in cand and not self._meets_init(cand + [l]):
                        cand.append(l); break
            if not self._meets_init(cand):
                cube = cand
        for l in sorted(cube, key=lambda l: self.rank[abs(l)]):
            if l not in cube or len(cube) == 1:
                continue
            trial = [x for x in cube if x != l]
            if self._meets_init(trial):
                continue
            ok, core2 = self._rel_ind(trial, i - 1)
            if ok:
                cube = trial
                if core2 is not None and len(core2) < len(cube) and not self._meets_init(core2):
                    cube = list(core2)
        return tuple(cube)

    def _add_blocked(self, cube, i):
        self.frames[i].append(cube)
        self.b.add([-self.act[i]] + [-l for l in cube])
        self.stats['blocked_cubes'] += 1

    def _is_blocked(self, cube, i):
        cs = set(cube)
        for j in range(i, len(self.frames)):
            for c in self.frames[j]:
                if cs.issuperset(c):
                    return True
        return False

    # ------------------------------------------------------------ blocking
    def _block(self, cube, level):
        """Try to show cube unreachable within `level` steps. Returns None, or a trace when a real attack exists."""
        n = 0
        heap = [(level, n, cube, None)]               # (level, tie, cube, link = (faults, parent link))
        while heap:
            i, _, s, link = heapq.heappop(heap)
            self.stats['obligations'] += 1
            if self._is_blocked(s, i):
                continue
            ok, x = self._rel_ind(s, i - 1, want_pred=True)
            if ok:
                g = self._generalize(s, i, x)
                j = i
                while j + 1 < len(self.frames) and self._rel_ind(g, j)[0]:
                    j += 1
                self._add_blocked(g, j)
                continue
            full, faults = x
            if i - 1 == 0:                            # the predecessor is a power-up state: real attack
                steps = [faults]
                while link is not None:
                    steps.append(link[0]); link = link[1]
                bits = [l > 0 for l in full]
                s0 = self.ts.decode_state(bits)
                return dict(init_state=s0['flops'], input=s0['input'],
                            faults=[(t, b) for t, fs in enumerate(steps) for b in fs], cycles=len(steps))
            p = self._lift(full, faults, s)
            n += 1; heapq.heappush(heap, (i - 1, n, p, (faults, link)))
            n += 1; heapq.heappush(heap, (i, n, s, link))
        return None

    # ------------------------------------------------------------ main loop
    def run(self, max_frames=200):
        t0 = time.time()
        res = dict(method='IC3', backend=self.b.name, uses_unsat_cores=bool(getattr(self.b, 'has_core', False)))
        try:
            if self._solve(self.b, [self.act[0], self.h]):
                return dict(res, verdict='attack', trace=dict(init_state=0, input=0, faults=[], cycles=0), frames=0,
                            seconds=round(time.time() - t0, 3), **self.stats)
            k = 0
            while k < max_frames:
                k += 1
                self.act.append(self._new()); self.frames.append([])
                tr = self._block((self.h,), k)
                if tr is not None:
                    return dict(res, verdict='attack', trace=tr, frames=k, seconds=round(time.time() - t0, 3), **self.stats)
                # push blocked cubes forward; an empty level means the frame above it is an inductive invariant
                for i in range(1, k):
                    for c in list(self.frames[i]):
                        if not self._solve(self.b, self._F(i) + self._prime(c)):
                            self.frames[i].remove(c)
                            self.frames[i + 1].append(c)
                            self.b.add([-self.act[i + 1]] + [-l for l in c])
                    if not self.frames[i]:
                        inv = [[-l for l in c] for j in range(i + 1, k + 1) for c in self.frames[j]]
                        return dict(res, verdict='proved', invariant=inv, frames=k, seconds=round(time.time() - t0, 3),
                                    **self.stats)
                if self.log: self.log(f'  IC3 frame {k}: {[len(f) for f in self.frames[1:]]} cubes')
        except _Timeout:
            return dict(res, verdict='unknown', reason='time limit', seconds=round(time.time() - t0, 3), **self.stats)
        return dict(res, verdict='unknown', reason=f'frame limit {max_frames}', seconds=round(time.time() - t0, 3), **self.stats)


def ic3(ts, make_backend, deadline=None, log=None, max_frames=200):
    return IC3(ts, make_backend, deadline, log).run(max_frames)


def check_certificate(ts, inv, make_backend, deadline=None):
    """Independent re-check of an invariant (list of clauses over current-state template literals 1..S):
         1. every power-up state satisfies it
         2. it excludes "goal seen"
         3. one step from any state that satisfies it (any allowed flips) lands in a state that satisfies it
       Returns dict(ok, init, safe, inductive). Uses a fresh solver per part and none of the IC3 data structures."""
    S = ts.S
    out = {}
    # 1
    b = make_backend(); un = Unroll(ts, b, with_init=True); un.extend()     # extend: state restrictions (cons) apply
    out['init'] = True
    m0 = lambda l: un.X[0][abs(l) - 1] * (1 if l > 0 else -1)
    for c in inv:
        r = b.solve([-m0(l) for l in c], deadline=deadline)
        if r is None: return dict(ok=None, reason='time limit')
        if r: out['init'] = False; break
    # 2 and 3
    b = make_backend(); un = Unroll(ts, b, with_init=False); un.extend()
    m0 = lambda l: un.X[0][abs(l) - 1] * (1 if l > 0 else -1)
    m1 = lambda l: un.X[1][abs(l) - 1] * (1 if l > 0 else -1)
    for c in inv:
        b.add([m0(l) for l in c])
    r = b.solve([un.h(0)], deadline=deadline)
    if r is None: return dict(ok=None, reason='time limit')
    out['safe'] = not r
    out['inductive'] = True
    for c in inv:
        r = b.solve([-m1(l) for l in c], deadline=deadline)
        if r is None: return dict(ok=None, reason='time limit')
        if r: out['inductive'] = False; break
    out['ok'] = out['init'] and out['safe'] and out['inductive']
    out['clauses'] = len(inv)
    return out
