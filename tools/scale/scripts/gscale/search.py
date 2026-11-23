"""Search for the smallest attack with bounds that are valid at any moment.

Two numbers are maintained:
    lo   proved: there is NO attack with fewer than lo flips (from UNSAT answers of the exact formula or of the
         composed module formula);
    hi   found: an attack with hi flips, replayed on the gate-level simulator (None while none is known).
They only move towards each other. When the time limit ends the search, the answer is the interval [lo, hi]
("between 2 and 4 flips"), never nothing.

workers=1   one process: a short look for any attack at the full budget, then budgets in ascending order.
workers=2   two processes (portfolio): one raises lo (composed formula first when modules are given, then the exact
            formula), the other lowers hi (exact formula, descending budgets). mode='cubes' instead splits each
            budget of the ascending search into cubes over a few input bits and solves them on both cores.
"""
import multiprocessing as mp
import os, time
from . import fastsat, unroll as unr, reduce as red, cnf, sat, sim, modular, symmetry


class Bounds:
    def __init__(self, kmax):
        self.kmax = kmax; self.lo = 0; self.hi = None; self.witness = None; self.events = []; self.t0 = time.time()
        self.lo_by = 'start'; self.hi_by = None

    def raise_lo(self, v, by):
        if v > self.lo:
            self.lo = v; self.lo_by = by
            self.events.append(dict(t=round(time.time() - self.t0, 3), lo=v, by=by))

    def lower_hi(self, v, wit, by):
        if v > self.kmax: return           # an attack above the asked budget is outside the question
        if self.hi is None or v < self.hi:
            self.hi = v; self.witness = wit; self.hi_by = by
            self.events.append(dict(t=round(time.time() - self.t0, 3), hi=v, by=by))

    def done(self):
        return (self.hi is not None and self.lo >= self.hi) or (self.hi is None and self.lo > self.kmax)

    def status(self):
        if self.hi is not None and self.lo >= self.hi: return 'EXACT'
        if self.hi is None and self.lo > self.kmax: return 'NO_ATTACK_UP_TO_BOUND'
        if self.hi is not None: return 'INTERVAL'
        return 'LOWER_BOUND_ONLY'


def _check(P, ins, faults, n=None):
    """Referee: replay on the scalar simulator; drop flips that are not needed (relaxed encodings, loose abstract
    costs) is NOT done here: the flip list is taken as is."""
    if not sim.is_attack(P, ins, faults, within=n):
        raise AssertionError('internal error: witness does not replay on the gate-level simulator (%d flips)' % len(faults))
    return len(faults)


def _trim(P, ins, faults, n=None):
    """Greedy removal of flips that are not needed (each removal re-checked on the simulator)."""
    fl = list(faults)
    for f in list(fl):
        t = [x for x in fl if x != f]
        if sim.is_attack(P, ins, t, within=n): fl = t
    return fl


def exact_ascend(P, M, s, lo, kmax, emit, deadline=None, n=None, solve=None, by='exact'):
    solve = solve or (lambda a, dl: (s.solve(a, deadline=dl), None))
    for j in range(lo, kmax + 1):
        r, m = solve(M.assume(j, n), deadline)
        if r is None: return None
        if r:
            ins, fl = M.witness(m or s.model())
            _check(P, ins, fl, n)
            emit('hi', len(fl), (ins, fl), by)
            return len(fl)
        emit('lo', j + 1, None, by)
    return kmax + 1


def exact_descend(P, M, s, hi, emit, deadline=None, n=None, floor=0, by='exact'):
    j = hi
    while j >= floor:
        r = s.solve(M.assume(j, n), deadline=deadline)
        if r is None: return None
        if not r:
            emit('lo', j + 1, None, by)
            return j + 1
        ins, fl = M.witness(s.model())
        fl = _trim(P, ins, fl, n)
        _check(P, ins, fl, n)
        emit('hi', len(fl), (ins, fl), by)
        j = len(fl) - 1
    return 0


def cegar_ascend(P, A, s, lo, kmax, emit, deadline=None, n=None, stats=None, max_iter=200):
    """Ascending budgets on the composed formula with refinement. Returns the proved lower bound reached (kmax + 1 =
    none up to the bound), or the exact minimum when an abstract solution was realised at its own cost."""
    stats = stats if stats is not None else {}
    stats.setdefault('iterations', 0); stats.setdefault('refinements', 0)
    j = lo
    try:
        while j <= kmax:
            r = s.solve(A.assume(j, n), deadline=deadline)
            if r is None: return None
            if not r:
                emit('lo', j + 1, None, 'modules'); j += 1; continue
            stats['iterations'] += 1
            if stats['iterations'] > max_iter:       # summaries too weak for this design: hand over to the exact formula
                stats['gave_up'] = True; return None
            m = s.model()
            faults, within, new = A.concretise(m, deadline)
            stats['refinements'] += new
            if faults is not None:
                ins = A.inputs(m)
                if sim.is_attack(P, ins, faults, within=n):
                    fl = _trim(P, ins, faults, n)
                    emit('hi', len(fl), (ins, fl), 'modules')
                    if len(fl) <= j: return len(fl)
                elif within:
                    raise AssertionError('internal error: realised abstract solution does not replay')
            if within and faults is None:
                raise AssertionError('internal error: abstract solution within cost but not realised')
            if not new and not within:
                raise AssertionError('internal error: refinement made no progress')
    except modular.Timeout:
        return None
    return kmax + 1


# ---------------------------------------------------------------- cube and conquer (2 workers)
def pick_split(M, p=3):
    """Split variables for the cubes: run-constant/per-cycle input variables that occur most often in the clauses."""
    d = M.U.dag
    cand = {abs(M.lit[n]) for n in M.U.in_nodes.values() if n in M.lit and abs(M.lit[n]) > 1}
    if not cand: cand = set(M.F.values())
    cnt = dict.fromkeys(cand, 0)
    for c in M.e.clauses:
        for l in c:
            a = abs(l)
            if a in cnt: cnt[a] += 1
    return [v for v, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:p]]


def _cube_worker(M, backend, tasks, results):
    s = sat.Inc(M.e, backend)
    while True:
        job = tasks.get()
        if job is None: return
        jid, assum, dl = job
        r = s.solve(assum, deadline=dl)
        results.put((jid, r, s.model() if r else None))


class CubePool:
    """Persistent workers, each with its own incremental solver (learned clauses are kept from cube to cube and from
    budget to budget). A query is the conjunction of the caller's assumptions with every sign pattern of the split
    variables; the patterns cover all assignments, so "every cube unsatisfiable" means unsatisfiable."""

    def __init__(self, M, backend='auto', workers=2, p=3):
        self.M = M; self.split = pick_split(M, p)
        ctx = mp.get_context('fork')
        self.tasks = ctx.Queue(); self.results = ctx.Queue()
        self.procs = [ctx.Process(target=_cube_worker, args=(M, backend, self.tasks, self.results), daemon=True)
                      for _ in range(workers)]
        for p_ in self.procs: p_.start()
        self.jid = 0; self.cubes_solved = 0

    def solve(self, assum, deadline=None):
        sv = self.split
        cubes = [[v if (c >> i) & 1 else -v for i, v in enumerate(sv)] for c in range(1 << len(sv))]
        ids = set()
        for cb in cubes:
            self.jid += 1; ids.add(self.jid)
            self.tasks.put((self.jid, list(assum) + cb, deadline))
        unknown = False
        while ids:
            try:
                jid, r, m = self.results.get(timeout=None if deadline is None else max(0.05, deadline - time.time() + 2))
            except Exception:
                self.close(); return None, None
            if jid not in ids: continue
            ids.discard(jid); self.cubes_solved += 1
            if r:
                self.close(); return True, m
            if r is None: unknown = True
        return (None, None) if unknown else (False, None)

    def close(self):
        for p_ in self.procs:
            if p_.is_alive(): p_.terminate()
        self.procs = []


# ---------------------------------------------------------------- top level
def prepare(P, reduce='struct', reduce_time_s=20.0):
    t0 = time.time()
    U = unr.unroll(P)
    t1 = time.time()
    keep, info = red.reduce_sites(U, reduce, time_s=reduce_time_s)
    c = P.circ
    info.update(sites_total=len(P.sites) * P.N, dag=U.dag.stats(), unroll_s=round(t1 - t0, 3),
                reduce_s=round(time.time() - t1, 3))
    return U, keep, info


def _lower_worker(conn, P, U, keep, kmax, mods, backend, n, deadline, sym):
    lo = [0]

    def emit(kind, v, wit, by):
        if kind == 'lo': lo[0] = max(lo[0], v)
        conn.send((kind, v, wit, by))
    try:
        st = {}
        if mods:
            A = modular.Abstraction(U, keep, mods, kmax, deadline=deadline)
            s = sat.Inc(A.e, backend)
            r = cegar_ascend(P, A, s, 0, kmax, emit, deadline, n, st)
            conn.send(('info', 'modules', dict(size=A.size, instances=len(A.inst), shapes=len(A.store.locals),
                                               facts=A.n_facts, sat_calls=s.calls, sat_time=round(s.time, 3), **st), None))
            if r is not None:
                conn.send(('done', r, None, 'modules')); return
        M = cnf.Model(U, keep, kmax)
        if sym: symmetry.add_breaking(M, sym)
        s = sat.Inc(M.e, backend)
        r = exact_ascend(P, M, s, lo[0], kmax, emit, deadline, n)
        conn.send(('done', r, None, 'exact'))
    except Exception as ex:            # reported to the parent, which decides
        conn.send(('error', repr(ex), None, None))


def _upper_worker(conn, P, U, keep, kmax, backend, n, deadline, sym):
    def emit(kind, v, wit, by):
        conn.send((kind, v, wit, by))
    try:
        M = cnf.Model(U, keep, kmax)
        if sym: symmetry.add_breaking(M, sym)
        s = sat.Inc(M.e, backend)
        r = exact_descend(P, M, s, kmax, emit, deadline, n)
        conn.send(('done', r, None, 'exact'))
    except Exception as ex:
        conn.send(('error', repr(ex), None, None))


def analyse(P, kmax, time_s=None, reduce='struct', modules='auto', workers=1, mode='race', backend='auto',
            n=None, use_symmetry=False, reduce_time_s=None, prepared=None, min_module_sites=8):
    """Smallest number of flips (<= kmax) that reaches the goal within n cycles (default: the problem horizon).
    Returns a dict: status (EXACT / NO_ATTACK_UP_TO_BOUND / INTERVAL / LOWER_BOUND_ONLY), lo, hi, witness, events,
    sizes. See the module text for the meaning of lo and hi."""
    t0 = time.time()
    deadline = None if time_s is None else t0 + time_s
    if reduce_time_s is None:
        reduce_time_s = 20.0 if time_s is None else max(1.0, 0.2 * time_s)
    U, keep, info = prepared or prepare(P, reduce, reduce_time_s)
    B = Bounds(kmax); B.t0 = t0
    out = dict(label=P.label, k=kmax, cycles=P.N if n is None else n, reduction=info, workers=workers, mode=mode)
    mods = modules if isinstance(modules, list) else modular.find_modules(P, modules, min_module_sites)
    out['modules'] = [dict(name=nm, gates=len(v)) for nm, v in mods]
    sym = symmetry.find(U, keep) if use_symmetry else []
    out['symmetry'] = dict(requested=bool(use_symmetry), automorphisms=len(sym))

    def emit(kind, v, wit, by):
        if kind == 'lo': B.raise_lo(v, by)
        elif kind == 'hi':
            _check(P, wit[0], wit[1], n)                 # the parent replays every witness it accepts
            B.lower_hi(v, wit, by)
    out['parts'] = {}
    if all(h is None for h in U.hit[:(P.N if n is None else n)]):
        B.raise_lo(kmax + 1, 'structure')                # the goal is impossible by hard constants alone
    elif workers >= 2 and mode == 'race':
        ctx = mp.get_context('fork')
        pl, cl = ctx.Pipe(duplex=False); pu, cu = ctx.Pipe(duplex=False)
        procs = [ctx.Process(target=_lower_worker, args=(cl, P, U, keep, kmax, mods, backend, n, deadline, sym), daemon=True),
                 ctx.Process(target=_upper_worker, args=(cu, P, U, keep, kmax, backend, n, deadline, sym), daemon=True)]
        for p_ in procs: p_.start()
        cl.close(); cu.close()
        live = {pl: 'lower', pu: 'upper'}
        errors = []
        while live and not B.done():
            if deadline is not None and time.time() > deadline + 1.0: break
            ready = mp.connection.wait(list(live), timeout=0.2)
            for c_ in ready:
                try: kind, v, wit, by = c_.recv()
                except EOFError:
                    del live[c_]; continue
                if kind in ('lo', 'hi'): emit(kind, v, wit, by)
                elif kind == 'info': out['parts'][v] = wit
                elif kind == 'error': errors.append(v); del live[c_]
                elif kind == 'done': del live[c_]
        for p_ in procs:
            if p_.is_alive(): p_.terminate()
        if errors: out['errors'] = errors
        if errors and not B.done(): raise RuntimeError('worker failed: ' + '; '.join(errors))
    else:
        st = {}
        if mods:
            A = modular.Abstraction(U, keep, mods, kmax, deadline=deadline)
            s = sat.Inc(A.e, backend)
            cegar_ascend(P, A, s, 0, kmax, emit, deadline, n, st)
            out['parts']['modules'] = dict(size=A.size, instances=len(A.inst), shapes=len(A.store.locals),
                                           facts=A.n_facts, sat_calls=s.calls, sat_time=round(s.time, 3), **st)
        if not B.done() and (deadline is None or time.time() < deadline):
            M = cnf.Model(U, keep, kmax)
            if sym: symmetry.add_breaking(M, sym)
            out['parts']['exact'] = dict(size=M.size, fault_vars=len(M.F))
            if workers >= 2 and mode == 'cubes':
                pool = CubePool(M, backend, workers)
                try:
                    exact_ascend(P, M, None, B.lo, kmax, emit, deadline, n, solve=pool.solve)
                finally:
                    pool.close()
                out['parts']['exact'].update(cubes_solved=pool.cubes_solved, split_vars=len(pool.split))
            else:
                s = sat.Inc(M.e, backend)
                if deadline is not None and B.hi is None and B.lo <= kmax:
                    # anytime: a short look for any attack at the full budget, so that an upper bound exists early
                    r = s.solve(M.assume(kmax, n), deadline=min(deadline, time.time() + 0.25 * (deadline - time.time())))
                    if r:
                        ins, fl = M.witness(s.model()); fl = _trim(P, ins, fl, n)
                        emit('hi', len(fl), (ins, fl), 'exact')
                    elif r is False:
                        emit('lo', kmax + 1, None, 'exact')
                if not B.done():
                    top = kmax if B.hi is None else B.hi - 1
                    r = exact_ascend(P, M, s, B.lo, top, emit, deadline, n)
                    if r == top + 1 and B.hi is not None: B.raise_lo(B.hi, 'exact')
                out['parts']['exact'].update(sat_calls=s.calls, sat_time=round(s.time, 3), solver=s.name)
    out.update(status=B.status(), lo=B.lo, hi=B.hi, lo_by=B.lo_by, hi_by=B.hi_by, events=B.events,
               runtime_s=round(time.time() - t0, 3), timed_out=bool(deadline is not None and not B.done()))
    if B.witness:
        ins, fl = B.witness
        rp = sim.replay(P, ins, fl)
        out['witness'] = dict(faults=[dict(cycle=t, net=b, name=P.circ.name(b)) for t, b in fl], hit_cycle=rp['hit'],
                              inputs={(('%s' % P.circ.name(k)) if not isinstance(k, tuple) else '%s@%d' % (P.circ.name(k[1]), k[0])): int(v)
                                      for k, v in sorted(ins.items(), key=str)},
                              replayed=True)
        out['_witness_raw'] = B.witness
    out['text'] = describe(out)
    return out


def describe(o):
    k, n = o['k'], o['cycles']
    if o['status'] == 'EXACT':
        return 'ATTACK_FOUND: the smallest attack uses %d flip(s) within %d cycles (minimum proved).' % (o['hi'], n)
    if o['status'] == 'NO_ATTACK_UP_TO_BOUND':
        return 'NO_ATTACK_UP_TO_BOUND: no attack with up to %d flip(s) within %d cycles.' % (k, n)
    if o['status'] == 'INTERVAL':
        return ('ATTACK_FOUND, minimum not proved: the smallest attack uses between %d and %d flips within %d cycles '
                '(an attack with %d was found and replayed; fewer than %d is proved impossible).' % (o['lo'], o['hi'], n, o['hi'], o['lo']))
    return ('UNDECIDED above the proved part: no attack with fewer than %d flip(s) within %d cycles; budgets %d..%d were '
            'not decided in the time given.' % (o['lo'], n, o['lo'], k))


def deepen(P, kmax, reduce='struct', backend='auto', time_s=None, prepared=None):
    """Minimum number of flips for every horizon n = 1..N from ONE formula (built for N; horizons are prefix
    assumptions). The minimum cannot grow with n, so each horizon starts just below the previous answer.
    Returns rows [dict(cycles, min_faults or None, proved)]."""
    t0 = time.time(); deadline = None if time_s is None else t0 + time_s
    U, keep, info = prepared or prepare(P, reduce)
    M = cnf.Model(U, keep, kmax)
    s = sat.Inc(M.e, backend)
    rows = []; best = None
    for n in range(1, P.N + 1):
        j = kmax if best is None else best - 1
        proved = True
        while j >= 0:
            r = s.solve(M.assume(j, n), deadline=deadline)
            if r is None: proved = False; break
            if not r: break
            ins, fl = M.witness(s.model()); fl = _trim(P, ins, fl, n); _check(P, ins, fl, n)
            best = len(fl); j = best - 1
        rows.append(dict(cycles=n, min_faults=best, proved=proved, t=round(time.time() - t0, 3)))
        if not proved: break
    return dict(rows=rows, size=M.size, fault_vars=len(M.F), reduction=info, sat_calls=s.calls, solver=s.name,
                runtime_s=round(time.time() - t0, 3))


def sizes(P, kmax, modules='auto', levels=('time', 'struct', 'full'), reduce_time_s=20.0, min_module_sites=8):
    """CNF sizes of the same question under each reduction level, and of the composed module formula."""
    out = {}
    U = unr.unroll(P)
    out['sites_total'] = len(P.sites) * P.N
    out['dag'] = U.dag.stats()
    keep = None
    for lv in levels:
        t0 = time.time()
        keep, info = red.reduce_sites(U, lv, time_s=reduce_time_s)
        M = cnf.Model(U, keep, kmax)
        out[lv] = dict(fault_vars=len(M.F), reduce_s=round(time.time() - t0, 3), **M.size)
        if 'functional' in info: out[lv]['functional'] = info['functional']
    mods = modules if isinstance(modules, list) else modular.find_modules(P, modules, min_module_sites)
    if mods:
        A = modular.Abstraction(U, keep, mods, kmax)
        out['modules'] = dict(fault_vars=len(A.F), cost_vars=sum(len(I.c) for I in A.inst), instances=len(A.inst),
                              shapes=len(A.store.locals), facts=A.n_facts, names=[m[0] for m in mods], **A.size)
    return out
