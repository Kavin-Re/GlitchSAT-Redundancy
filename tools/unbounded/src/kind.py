"""k-induction over the fault-augmented transition system (ts.TS), with optional simple-path constraints and
optional strengthening invariant.

Iteration N (N = 0, 1, 2, ...):
    base  Init(X0), N steps, goal seen at frame N        satisfiable -> an attack of N cycles (returned as a trace)
    step  any N+1 steps, goal not seen at frames 0..N, goal seen at frame N+1
                                                         unsatisfiable -> proved for every number of cycles
"goal seen" is sticky, so asking at one frame covers all earlier frames.

simple_path=True adds "all N+2 states of the step query are pairwise different". This is sound (a shortest attack never
repeats a state) and makes the method complete (Sheeran, Singh, Stalmarck, FMCAD 2000). The pairwise constraints are
added only when a model violates them (Een, Sorensson, 2003).
invariant: clauses over the state that are known to hold in every reachable state (for example the IC3 result after
ic3.check_certificate); they are asserted on every frame of the step query.
"""
import time

from ts import Unroll


def _distinct(un, i, j):
    """Clauses for X[i] != X[j]."""
    b = un.b
    ds = []
    for a, c in zip(un.X[i], un.X[j]):
        d = un.new_var()
        b.add([-d, a, c]); b.add([-d, -a, -c])
        ds.append(d)
    b.add(ds)


def k_induction(ts, make_backend, max_depth=30, simple_path=True, invariant=None, deadline=None, log=None):
    """Returns dict(verdict='proved'|'attack'|'unknown', depth, ...). 'unknown' = depth or time limit reached."""
    t0 = time.time()
    base = Unroll(ts, make_backend(), with_init=True)
    step = Unroll(ts, make_backend(), with_init=False)
    inv = [list(c) for c in (invariant or [])]

    def add_inv(un, t):
        m = ts.mapper(un.X[t], un.X[t], 0)
        for c in inv:
            un.b.add([m(l) for l in c])
    add_inv(step, 0)
    step.extend()
    info = dict(method='k-induction', simple_path=simple_path, invariant_clauses=len(inv), distinct_pairs=0,
                step_failures=[], backend=base.b.name)
    constrained = set()
    for N in range(max_depth + 1):
        # base case at depth N
        r = base.b.solve([base.h(N)], deadline=deadline)
        if r is None:
            return dict(info, verdict='unknown', reason='time limit in base case', depth=N, seconds=round(time.time() - t0, 3))
        if r:
            return dict(info, verdict='attack', depth=N, trace=base.trace(N), seconds=round(time.time() - t0, 3))
        base.b.add([-base.h(N)])
        # step case: frames 0..N+1
        add_inv(step, N)
        while True:
            r = step.b.solve([-step.h(N), step.h(N + 1)], deadline=deadline)
            if r is None:
                return dict(info, verdict='unknown', reason='time limit in step case', depth=N, seconds=round(time.time() - t0, 3))
            if not r:
                return dict(info, verdict='proved', depth=N, seconds=round(time.time() - t0, 3))
            if not simple_path:
                break
            states = [tuple(step.state(t)) for t in range(N + 2)]
            seen, new = {}, []
            for t, s in enumerate(states):
                if s in seen and (seen[s], t) not in constrained:
                    new.append((seen[s], t))
                seen.setdefault(s, t)
            if not new:
                break
            for i, j in new:
                constrained.add((i, j)); _distinct(step, i, j)
            info['distinct_pairs'] = len(constrained)
        # step failed at this depth: record the first state of the counterexample-to-induction
        s0 = ts.decode_state(step.state(0))
        info['step_failures'].append(dict(depth=N, start_flops=s0['flops'], start_used=s0['used'], input=s0['input'],
                                          repeats_a_state=len(set(tuple(step.state(t)) for t in range(N + 2))) < N + 2))
        if log: log(f'  depth {N}: base holds, step fails (start state 0x{s0["flops"]:X}, used {s0["used"]})')
        base.extend()
        step.extend()
    return dict(info, verdict='unknown', reason=f'not inductive up to depth {max_depth}', depth=max_depth,
                seconds=round(time.time() - t0, 3))
