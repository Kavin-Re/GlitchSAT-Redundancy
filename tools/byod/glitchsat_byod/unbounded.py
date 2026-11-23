"""Unbounded proof for a composed problem: "no attack with at most k faults, after any number of cycles".

The fault-augmented transition system and the two proof methods are those of ext/unbounded (ts.TS, k-induction
with simple-path constraints, IC3 with an independently re-checked inductive invariant). This file only adapts a
composed GlitchSAT problem to it:
  * fault sites: only the selected sites may flip (a unit restriction `not flip` for every other net in the cone);
  * attacker inputs that change every cycle: the "input stays frozen" clauses are removed for those bits, so the
    input part of the state is free in every step;
  * fixed and tied inputs become constants; must_hold conditions are folded into the goal with a sticky "ok so
    far" register; the "attacker input differs from key" condition of the original tool is a dummy input tied by it.
The verdict is PROVED_UNBOUNDED only when both methods agree and the IC3 invariant passes its re-check.
"""
import time

from .engine import unbounded_src


class _NL:
    """The netlist interface ts.TS reads (scripts/glitchsat.py Netlist), built from a primitive Circuit."""

    def __init__(self, c, consts):
        self.names = {}
        self.drivers = {}
        self.ports = {}
        self.init = {}
        self.dq = {}
        self.qs = []
        sub = lambda n: consts.get(n, n)
        for y, (op, fi) in c.gates.items():
            fi = tuple(sub(f) for f in fi)
            if op == 'MUX':
                con = dict(S=[fi[0]], B=[fi[1]], A=[fi[2]], Y=[y])
            elif op == 'NOT':
                con = dict(A=[fi[0]], Y=[y])
            else:
                con = dict(A=[fi[0]], B=[fi[1]], Y=[y])
            self.drivers[y] = ('g%d' % y, '$_%s_' % op, con)
        for q, (d, i) in c.flops.items():
            self.qs.append(q)
            self.dq[q] = sub(d)
            self.init[q] = bool(i)
        self.names = {k: str(v) for k, v in c.names.items()}

    def fanins(self, b):
        if b in self.drivers:
            _, t, con = self.drivers[b]
            return [v[0] for p, v in con.items() if p != 'Y']
        return []


def build_ts(X, k):
    unbounded_src()
    import ts as tsmod
    c = X.circ
    consts = {}
    for b, md in X.in_mode.items():
        if md in (0, 1):
            consts[b] = '1' if md else '0'
    nl = _NL(c, consts)
    top = max([n for n in list(c.gates) + list(c.flops) + list(c.inputs) if isinstance(n, int)] + [0]) + 10
    bad, ok = consts.get(X.bad, X.bad), consts.get(X.ok, X.ok)
    goal = bad
    if X.P.quiet:
        okq = top; top += 1
        okd = top; top += 1
        nl.qs.append(okq); nl.init[okq] = True
        nl.drivers[okd] = ('gs_okd', '$_AND_', dict(A=[okq], B=[ok], Y=[okd]))
        nl.dq[okq] = okd
        g1 = top; top += 1
        nl.drivers[g1] = ('gs_g1', '$_AND_', dict(A=[bad], B=[ok], Y=[g1]))
        g2 = top; top += 1
        nl.drivers[g2] = ('gs_g2', '$_AND_', dict(A=[g1], B=[okq], Y=[g2]))
        goal = g2
    if not isinstance(goal, int):
        g = top; top += 1
        nl.drivers[g] = ('gs_goal', '$_AND_', dict(A=[goal], B=[goal], Y=[g]))
        goal = g
    dummy = top; top += 1
    nl.ports['gs_nokey'] = dict(direction='input', bits=[dummy])
    free_cycle = []
    for b, md in sorted(X.in_mode.items(), key=lambda kv: str(kv[0])):
        if md in (0, 1):
            continue
        nl.ports['in_%d' % b] = dict(direction='input', bits=[b])
        nl.names.setdefault(b, str(c.names.get(b, b)))
        if md == 'cycle':
            free_cycle.append(b)
    nl.ports['gs_bad'] = dict(direction='output', bits=[goal])
    T = tsmod.TS(nl, k, goal_out='gs_bad', goal_value=1, attack_in='gs_nokey', key=1)
    # only the selected sites may flip
    S = T.S
    cur = lambda pos: pos + 1
    nxt = lambda pos: S + pos + 1
    for b, f in T.fault.items():
        if b not in X.sites:
            T.cons.append([-f])
    # per-cycle inputs: drop the freeze clauses
    idx = {b: T.in_pos[i] for i, b in enumerate(T.in_bits)}
    drop = set()
    for b in free_cycle:
        pos = idx[b]
        drop.add((-nxt(pos), cur(pos))); drop.add((nxt(pos), -cur(pos)))
    if drop:
        T.func = [cl for cl in T.func if not (len(cl) == 2 and tuple(cl) in drop)]
    return T, dict(state_bits=T.S, flops=T.nq, input_bits=T.ni, per_cycle_input_bits=len(free_cycle),
                   sites_in_cone=sum(1 for b in T.fault if b in X.sites))


def prove(spec, X, k, time_s=60, max_state_bits=400, attack_k=None):
    t0 = time.time()
    try:
        T, info = build_ts(X, k)
    except Exception as e:                       # noqa: BLE001
        return dict(verdict='NOT_RUN', why='could not build the transition system: %s' % e)
    if T.S > max_state_bits:
        return dict(verdict='NOT_RUN', why='GS054: %d state bits (limit %d)' % (T.S, max_state_bits), **info)
    import kind, ic3, sat
    be = 'auto'
    mk = lambda: sat.make_backend(be)
    dl = time.time() + time_s
    out = dict(label='MEASURED', k=k, methods={}, **info)
    try:
        r1 = kind.k_induction(T, mk, max_depth=20, simple_path=True, deadline=time.time() + time_s / 2)
    except Exception as e:                       # noqa: BLE001
        r1 = dict(verdict='unknown', reason=str(e))
    tr = r1.pop('trace', None)
    r1.pop('step_failures', None)
    if tr:
        r1['attack_cycles'] = tr['cycles']; r1['attack_flips'] = len(tr['faults'])
    out['methods']['k_induction'] = r1
    try:
        r2 = ic3.ic3(T, mk, deadline=dl)
        inv = r2.pop('invariant', None)
        tr2 = r2.pop('trace', None)
        if inv is not None:
            r2['invariant_clauses'] = len(inv)
            r2['certificate'] = ic3.check_certificate(T, inv, mk, deadline=dl + 30)
        if tr2:
            r2['attack_cycles'] = tr2['cycles']; r2['attack_flips'] = len(tr2['faults'])
    except Exception as e:                       # noqa: BLE001
        r2 = dict(verdict='unknown', reason=str(e))
    out['methods']['ic3'] = r2
    vs = {m: r.get('verdict') for m, r in out['methods'].items()}
    dec = {v for v in vs.values() if v in ('proved', 'attack')}
    if len(dec) > 1:
        out['verdict'] = 'DISAGREEMENT'
        out['why'] = 'methods disagree: %s (no verdict given)' % vs
    elif dec == {'proved'}:
        cert = (r2.get('certificate') or {}).get('ok')
        if vs.get('ic3') == 'proved' and cert is not True:
            out['verdict'] = 'UNKNOWN'; out['why'] = 'IC3 invariant failed its re-check'
        else:
            out['verdict'] = 'PROVED_UNBOUNDED'
            out['meaning'] = ('no attack with at most %d fault(s) exists after any number of cycles (this netlist, this fault '
                              'model, this power-up and reset assumption)' % k)
    elif dec == {'attack'}:
        out['verdict'] = 'ATTACK_FOUND'
        cyc = r1.get('attack_cycles') or r2.get('attack_cycles')
        out['meaning'] = 'an attack with at most %d fault(s) exists after %s cycles (longer than the horizon?)' % (k, cyc)
    else:
        out['verdict'] = 'UNKNOWN'
        out['why'] = 'time or depth limit (%s)' % '; '.join('%s: %s' % (m, r.get('reason', r.get('verdict'))) for m, r in out['methods'].items())
    out['runtime_s'] = round(time.time() - t0, 3)
    return out
