"""The analyses run on a composed problem.

  min_faults      smallest number of faults that makes `bad` true (with must_hold intact) within the horizon
  attack_surface  every smallest attack (up to a cap), counted per fault site and per cycle
  survival        the minimum for every other synthesis flow, compared with the main flow
  merge_lint      ext/checker: do the redundant copies of the RTL still exist as separate logic in each netlist?
  unbounded       is "no attack with <= k faults" true for any number of cycles? (ext/unbounded, k-induction + IC3)
Labels: MEASURED = computed here by this run; every attack is replayed on a gate-level simulator before it is reported.
"""
import os
import shutil
import time

from . import sim as SIM
from .engine import gscale


def backend(spec):
    b = spec['backend']
    if b == 'auto':
        c = shutil.which('cadical')
        return 'dimacs:' + c if c else 'py'
    return b


def _ports_by_bits(X):
    by = {}
    for b, (p, i) in X.circ.inputs.items():
        by.setdefault(p, {})[i] = b
    return by


def render_witness(X, res, ins, faults, ports, N, R=None):
    """Plain description of one attack: faults (site, cycle, type), input values per cycle, and a fault-applied trace."""
    G = gscale()
    rp = G.sim.replay(X.P, ins, faults)
    by = _ports_by_bits(X)
    hit = rp['hit']
    last = hit if hit is not None else N - 1
    inputs = {}
    for p, bits in by.items():
        if res['roles'].get(p) not in ('attacker', 'secret'):
            continue
        w = max(bits) + 1
        vals = []
        for t in range(last + 1):
            v = 0
            for i, b in bits.items():
                md = X.in_mode.get(b)
                bit = ins.get(b, False) if md == 'const' else ins.get((t, b), False)
                v |= int(bool(bit)) << i
            vals.append(v)
        once = X.in_mode.get(next(iter(bits.values()))) == 'const'
        if once:
            vals = vals[:1]
        inputs[p] = dict(width=w, values=['0x%X' % v for v in vals], changes='once' if once else 'every cycle')
    free = {}
    for p, bits in by.items():
        if res['roles'].get(p) is None and '.' in str(p) and not str(p).startswith('powerup:'):
            vals = []
            for t in range(last + 1):
                v = 0
                for i, b in bits.items():
                    v |= int(bool(ins.get((t, b), False))) << i
                vals.append('0x%X' % v)
            free[p] = vals
    pu = {}
    for x, q in X.free_init.items():
        if ins.get(x):
            pu[str(X.circ.names.get(q, q))] = 1
    fl = []
    for t, n in faults:
        m = X.site_meta.get(n, {})
        fl.append(dict(cycle=t, site=m.get('label', str(n)), scope=m.get('scope', ''), kind=m.get('kind'), type=m.get('type', 'flip'),
                       src=m.get('src') or ''))
    # trace of outputs, bad, ok with the faults applied
    c = X.circ
    ordr = SIM.order(c)
    st = {q: (1 if i else 0) for q, (d, i) in c.flops.items()}
    fset = {}
    for t, n in faults:
        fset.setdefault(t, {})[n] = 1
    trace = []
    for t in range(last + 1):
        inw = {}
        for b in c.inputs:
            md = X.in_mode.get(b)
            if md in (0, 1): inw[b] = md
            elif md == 'const': inw[b] = int(bool(ins.get(b, False)))
            else: inw[b] = int(bool(ins.get((t, b), False)))
        v, st = SIM.step(c, ordr, st, inw, 1, fset.get(t))
        row = dict(cycle=t)
        for p, iv in inputs.items():
            row['in:' + p] = int(iv['values'][0 if iv['changes'] == 'once' else t], 16)
        for p, bits in X.out_bits.items():
            row[p] = sum((v.get(b, 0) if isinstance(b, int) else int(b == '1')) << i for i, b in enumerate(bits))
        row['bad'] = v.get(X.bad, 0) if isinstance(X.bad, int) else int(X.bad == '1')
        row['ok'] = v.get(X.ok, 1) if isinstance(X.ok, int) else int(X.ok == '1')
        row['faults'] = [X.site_meta.get(n, {}).get('label', str(n)) for (tt, n) in faults if tt == t]
        trace.append(row)
    return dict(faults=fl, inputs=inputs, free=free, powerup_ones=pu, hit_cycle=hit,
                replayed=rp['hit'] is not None and rp['sites_ok'], trace=trace)


def min_faults(spec, res, ch, X, time_s=None, label='MEASURED'):
    G = gscale()
    k = ch['kmax']
    t0 = time.time()
    r = G.search.analyse(X.P, k, time_s=time_s or spec['time_s'], reduce='struct', modules='auto',
                         workers=spec['workers'], backend=backend(spec))
    out = dict(label=label, max_faults=k, horizon=ch['horizon'], status=r['status'], lo=r['lo'], hi=r['hi'],
               runtime_s=round(time.time() - t0, 3), sites=len(X.sites), sites_after_reduction=r['reduction'].get('sites_kept'),
               reduction=r['reduction'], solver=backend(spec))
    if r['status'] == 'EXACT':
        out['verdict'] = 'FAILS_WITHOUT_FAULTS' if r['hi'] == 0 else 'ATTACK_FOUND'
        out['min_faults'] = r['hi']
        out['proved_minimum'] = True
    elif r['status'] == 'NO_ATTACK_UP_TO_BOUND':
        out['verdict'] = 'NO_ATTACK_UP_TO_BOUND'
        out['min_faults'] = None
    elif r['status'] == 'INTERVAL':
        out['verdict'] = 'ATTACK_FOUND'
        out['min_faults'] = r['hi']; out['proved_minimum'] = False
        out['note_interval'] = 'an attack with %d fault(s) was found and replayed; fewer than %d is proved impossible' % (r['hi'], r['lo'])
    else:
        out['verdict'] = 'UNDECIDED'
        out['min_faults'] = None
    if r.get('_witness_raw'):
        ins, fl = r['_witness_raw']
        out['witness'] = render_witness(X, res, ins, fl, None, ch['horizon'])
        if out['witness'].get('hit_cycle') and out.get('proved_minimum'):
            sh = shortest(spec, res, ch, X, out['min_faults'], out['witness']['hit_cycle'])
            if sh == 'first':
                out['witness']['shortest'] = True
            elif sh is not None:
                out['witness'] = sh
    out['_raw'] = r
    return out


def shortest(spec, res, ch, X, m, hit, budget_s=20.0):
    """The attack with m faults that succeeds earliest: search horizons 1, 2, ... below the first witness's hit cycle.
    Returns a witness (with shortest=True), 'first' when the first witness is already the earliest, or None when the
    time budget ran out."""
    G = gscale()
    t0 = time.time()
    for n in range(1, hit + 1):
        left = budget_s - (time.time() - t0)
        if left <= 0.5:
            return None
        r = G.search.analyse(X.P, m, n=n, time_s=left, reduce='struct', modules='auto', workers=spec['workers'],
                             backend=backend(spec))
        if r['status'] == 'EXACT' and r.get('_witness_raw') and r['hi'] <= m:
            ins, fl = r['_witness_raw']
            w = render_witness(X, res, ins, fl, None, ch['horizon'])
            if w.get('replayed'):
                w['shortest'] = True
                return w
        elif r['status'] != 'NO_ATTACK_UP_TO_BOUND':
            return None
    return 'first'


def vacuity(spec, res, ch, X):
    """Is there any fault-free run in which every must_hold condition is true in cycle 0? (non-vacuity)"""
    if not X.P.quiet:
        return dict(ok=True, note='no must_hold conditions')
    G = gscale()
    P2 = G.circuit.Problem(X.circ, 1, [(X.ok, 1)], [], None, X.in_mode, X.sites, label='vacuity')
    r = G.search.analyse(P2, 0, time_s=60, reduce='time', modules='none', backend=backend(spec))
    return dict(ok=r['status'] == 'EXACT', note='a fault-free cycle 0 with every must_hold true exists' if r['status'] == 'EXACT'
                else 'no input satisfies every must_hold condition even without faults')


def attack_surface(spec, ch, X, m, cap=100, time_s=None):
    """Enumerate the attacks of minimum size m (no site reduction, so every site appears under its own name)."""
    G = gscale()
    t0 = time.time()
    deadline = t0 + (time_s or min(spec['time_s'], 45))
    U, keep, info = G.search.prepare(X.P, reduce='time')
    M = G.cnf.Model(U, keep, m)
    s = G.sat.Inc(M.e, backend(spec))
    attacks = []
    stop = 'exhausted'
    while True:
        if len(attacks) >= cap:
            stop = 'cap'; break
        r = s.solve(M.assume(m), deadline=deadline)
        if r is None:
            stop = 'timeout'; break
        if not r:
            break
        mod = s.model()
        ins, fl = M.witness(mod)
        true = [f for f in M.F.values() if mod[f]]
        if not G.sim.is_attack(X.P, ins, fl):
            stop = 'replay_failed'; break
        attacks.append(fl)
        M.e.add([-f for f in true])
    per_site, per_cycle = {}, {}
    for a in attacks:
        for t, n in a:
            lab = X.site_meta.get(n, {}).get('label', str(n))
            per_site[lab] = per_site.get(lab, 0) + 1
            per_cycle[t] = per_cycle.get(t, 0) + 1
    scopes = {}
    for a in attacks:
        for sc in {X.site_meta.get(n, {}).get('scope') or '(top)' for t, n in a}:
            scopes[sc] = scopes.get(sc, 0) + 1
    return dict(label='MEASURED', min_faults=m, count=len(attacks), complete=stop == 'exhausted', stop_reason=stop,
                sites=sorted(([k, v] for k, v in per_site.items()), key=lambda kv: -kv[1])[:50],
                cycles={str(k): v for k, v in sorted(per_cycle.items())}, scopes=scopes,
                attacks=[[dict(cycle=t, site=X.site_meta.get(n, {}).get('label', str(n))) for t, n in a] for a in attacks[:50]],
                runtime_s=round(time.time() - t0, 3))


def run_all(spec, res, ch, crep, flows, main, P, quick=False):
    A = crep['analyses']
    X = crep['flows'][main].get('_X')
    if X is None:
        A['min_faults'] = dict(verdict='NOT_RUN', why='the main flow could not be composed')
        return
    if 'min_faults' in spec['analyses'] or 'attack_surface' in spec['analyses']:
        vac = vacuity(spec, res, ch, X)
        A['non_vacuity'] = vac
        if not vac['ok']:
            A['min_faults'] = dict(verdict='VACUOUS', why='GS052: ' + vac['note'], label='MEASURED')
            return
        P('check `%s`: searching the smallest attack (flow %s, up to %d faults, %d cycles)' % (ch['id'], main, ch['kmax'], ch['horizon']))
        mf = min_faults(spec, res, ch, X)
        mf.pop('_raw', None)
        A['min_faults'] = mf
    m = (A.get('min_faults') or {}).get('min_faults')
    if 'attack_surface' in spec['analyses']:
        if m:
            P('check `%s`: listing every smallest attack' % ch['id'])
            A['attack_surface'] = attack_surface(spec, ch, X, m)
        else:
            A['attack_surface'] = dict(verdict='NOT_RUN', why='no attack within the bound' if m is None else 'the design fails without faults')
    if 'survival' in spec['analyses'] and len(flows) > 1:
        rows = []
        for fl in flows:
            fr = crep['flows'].get(fl, {})
            if fl == main:
                rows.append(dict(flow=fl, min_faults=m, verdict=A['min_faults'].get('verdict'), sites=len(X.sites)))
                continue
            Xf = fr.get('_X')
            if Xf is None:
                rows.append(dict(flow=fl, verdict='NOT_RUN', why=(fr.get('error') or fr.get('validation', {}).get('error') or {}).get('message', 'not composed')))
                continue
            P('check `%s`: smallest attack for flow %s' % (ch['id'], fl))
            r = min_faults(spec, res, ch, Xf)
            rows.append(dict(flow=fl, min_faults=r.get('min_faults'), verdict=r['verdict'], sites=len(Xf.sites),
                             runtime_s=r['runtime_s']))
        base = rows[0].get('min_faults')
        for r in rows[1:]:
            mm = r.get('min_faults')
            if r['verdict'] in ('ATTACK_FOUND', 'FAILS_WITHOUT_FAULTS') and (base is None or (mm is not None and mm < base)):
                r['change'] = 'WEAKER than %s' % main
            elif r['verdict'] == 'NO_ATTACK_UP_TO_BOUND' and base is not None:
                r['change'] = 'stronger than %s' % main
            elif r.get('min_faults') == base:
                r['change'] = 'same'
        A['survival'] = dict(label='MEASURED', rows=rows)
    if 'merge_lint' in spec['analyses']:
        P('check `%s`: merge lint (are redundant copies still separate?)' % ch['id'])
        from . import lint
        A['merge_lint'] = lint.run(spec, flows, main)
    if 'unbounded' in spec['analyses'] and not quick:
        from . import unbounded as UB
        k = m - 1 if m else ch['kmax']
        if m == 0:
            A['unbounded'] = dict(verdict='NOT_RUN', why='the design fails without faults')
        else:
            P('check `%s`: unbounded proof for %d fault(s)' % (ch['id'], k))
            A['unbounded'] = UB.prove(spec, X, k, time_s=float(spec['unbounded'].get('time_s', min(spec['time_s'], 60))),
                                      max_state_bits=int(spec['unbounded'].get('max_state_bits', 400)), attack_k=m)
