"""Sequential (bounded, N clock cycles) GlitchSAT model of a whole adapted Nangate45 netlist.

This is GlitchSAT's own fault model applied to a real netlist, not SYNFI's:
  * the adapted primitive netlist (nangate.convert) is unrolled for N cycles; every flop starts from its reset
    value unless `init` overrides it; reset inputs are tied inactive; every other primary input is free in every
    cycle (any input sequence) unless `fixed` gives it a value;
  * a fault is a single-cycle bit flip of a real net: a Nangate cell output or a flop output Q (the adapter's
    `sites`; nets internal to a multi-primitive cell are never faulted). `site_filter` restricts the sites;
  * at most k flips in total (totalizer), at most one per (cycle, net);
  * goal: a caller-supplied condition on the per-cycle literals (goal(lits) -> literal), typically "state equals
    Y at some cycle t and the alert output stayed 0 up to t".
Bounded: a "no attack" verdict holds for N cycles and k flips only.
Every attack is replayed on refsim.RefSim (the original Nangate45 netlist with SYNFI's cell clauses), with the
flips applied to the same nets; a witness that does not reproduce raises."""
import collections
import time

from . import engine, nangate as ng, refsim

fs = engine.fastsat()
T_, F_ = fs.T_, fs.F_


def fs_add_clause(e, be, c):
    """Add a clause to the encoding and to a live incremental backend (the DIMACS backend re-reads e)."""
    e.add(list(c))
    if hasattr(be, 's') and be.s is not None:
        be.s.add_clause(list(c))


class SeqModel:
    def __init__(self, doc, top, N, lib=None, init=None, fixed=None, site_filter=None, reset_mode='deasserted',
                 const_inputs=False):
        self.lib = lib or ng.load_cell_lib()
        self.doc, self.top, self.N = doc, top, N
        self.nd, self.meta = ng.convert(doc, top, lib=self.lib, reset_mode=reset_mode)
        self.nl = engine.netlist_from_doc(self.nd, top)
        self.init = dict((self.meta['flops'][c]['q'], v) for c, v in (init or {}).items())
        self.fixed = dict(fixed or {})
        for r in self.meta['resets']:
            if isinstance(r['net'], int):
                self.fixed.setdefault(r['net'], 1 - r['active'])
        self.sites = {n: s for n, s in self.meta['sites'].items() if site_filter is None or site_filter(n, s)}
        self.const_inputs = const_inputs
        t0 = time.time()
        self._encode()
        self.build_s = time.time() - t0
        self.card = None
        self.be = None

    def _order(self):
        nl = self.nl
        order, state = [], {}
        for root in nl.drivers:
            if root in state:
                continue
            stack = [root]
            while stack:
                b = stack[-1]
                if state.get(b) == 2:
                    stack.pop(); continue
                pend = [f for f in nl.fanins(b) if f in nl.drivers and state.get(f) != 2]
                if pend:
                    state[b] = 1; stack.extend(pend); continue
                state[b] = 2; order.append(b); stack.pop()
        return order

    def _encode(self):
        nl, e = self.nl, fs.Encoding()
        self.e = e
        order = self._order()
        inbits = {}
        for p, x in nl.ports.items():
            if x['direction'] == 'input':
                for i, b in enumerate(x['bits']):
                    if isinstance(b, int):
                        inbits[b] = (p, i)
        self.inbits = inbits
        self.F = {}                        # (t, net) -> fault var
        self.fault_order = []
        self.lits = []                     # per cycle: net -> literal
        self.invars = []
        state = {q: (T_ if self.init.get(q, nl.init[q]) else F_) for q in nl.qs}
        const_in = {}
        for t in range(self.N):
            v = {}
            iv = {}
            for b in inbits:
                if b in self.fixed:
                    iv[b] = T_ if self.fixed[b] else F_
                elif self.const_inputs:
                    if b not in const_in:
                        const_in[b] = e.new_var()
                    iv[b] = const_in[b]
                else:
                    iv[b] = e.new_var()
            self.invars.append(iv)
            v.update(iv)

            def lit(b):
                if b == '0': return F_
                if b == '1': return T_
                return v[b]

            def fvar(b):
                if b not in self.sites:
                    return None
                f = e.new_var(); self.F[(t, b)] = f; self.fault_order.append(f)
                return f
            for q in nl.qs:
                f = fvar(q)
                v[q] = state[q] if f is None else e.g_xor(state[q], f)
            for b in order:
                _, ty, con = nl.drivers[b]
                f = fvar(b)
                if ty == '$_AND_': r = e.g_and(lit(con['A'][0]), lit(con['B'][0]), f)
                elif ty == '$_OR_': r = e.g_or(lit(con['A'][0]), lit(con['B'][0]), f)
                elif ty == '$_XOR_': r = e.g_xor(lit(con['A'][0]), lit(con['B'][0]), f)
                elif ty == '$_NOT_':
                    r = -lit(con['A'][0])
                    if f is not None: r = e.g_xor(r, f)
                else: r = e.g_mux(lit(con['S'][0]), lit(con['B'][0]), lit(con['A'][0]), f)
                v[b] = r
            self.lits.append(v)
            state = {q: lit(d) for q, d in nl.dq.items()}

    def add_goal(self, goal_fn):
        """goal_fn(model) -> literal that must be true (use model.lits[t][net], model.e gates)."""
        g = goal_fn(self)
        self.e.add([g])

    # helpers for goals
    def eq_const(self, t, nets, value):
        e = self.e
        ls = [self.lits[t][n] if (value >> i) & 1 else -self.lits[t][n] for i, n in enumerate(nets)]
        r = T_
        for l in ls:
            r = e.g_and(r, l)
        return r

    def all_of(self, ls):
        r = T_
        for l in ls:
            r = self.e.g_and(r, l)
        return r

    def any_of(self, ls):
        r = F_
        for l in ls:
            r = self.e.g_or(r, l)
        return r

    def backend(self, name='auto'):
        if self.be is None:
            self.be = fs.make_backend(self.e, name)
        return self.be

    def _card(self, kmax):
        if self.card is None:
            self.card = (kmax, fs.totalizer(self.e, self.fault_order, kmax))
            self.be = None
        elif self.card[0] < kmax:
            raise ValueError('cardinality built for a smaller bound')
        return self.card[1]

    def min_faults(self, kmax, backend='auto', timeout_s=None):
        outs = self._card(kmax)
        be = self.backend(backend)
        rows = []
        t0 = time.time()
        deadline = None if timeout_s is None else t0 + timeout_s
        for k in range(kmax + 1):
            ts = time.time()
            r = be.solve([-outs[k]] if k < len(outs) else [], deadline=deadline)
            rows.append(dict(k=k, result={True: 'SAT', False: 'UNSAT', None: 'UNKNOWN'}[r], solve_s=round(time.time() - ts, 3)))
            if r is None:
                return dict(verdict='UNKNOWN', min_faults=None, sweep=rows)
            if r:
                w = self.witness(be.model())
                self.replay(w)
                return dict(verdict='ATTACK_FOUND', min_faults=k, witness=w, sweep=rows, runtime_s=round(time.time() - t0, 3))
        return dict(verdict=f'NO_ATTACK_UP_TO_{kmax}', min_faults=None, sweep=rows, runtime_s=round(time.time() - t0, 3))

    def witness(self, model):
        flips = [dict(cycle=t, net=n, cell=self.sites[n]['cell'], cell_type=self.sites[n]['type'], pin=self.sites[n]['pin'],
                      name=self.nl.names.get(n, str(n))) for (t, n), f in self.F.items() if model[f]]
        ins = [{str(b): bool(model[l]) if l not in (T_, F_) else (l == T_) for b, l in iv.items()} for iv in self.invars]
        return dict(flips=flips, inputs=ins, _model=model)

    def replay(self, w):
        """Re-simulate the witness on the ORIGINAL netlist (refsim.RefSim, SYNFI clause semantics) with the flips
        applied to the same nets; the goal must hold there too (checked by self.goal_check if set)."""
        ref = refsim.RefSim(self.doc, self.top, self.lib)
        ins = [{int(b): (1 if v else 0) for b, v in cyc.items()} for cyc in w['inputs']]
        flips = {(f['cycle'], f['net']): 1 for f in w['flips']}
        init = {c: f['init'] for c, f in self.meta['flops'].items()}
        for c in self.meta['flops']:
            q = self.meta['flops'][c]['q']
            if q in self.init:
                init[c] = self.init[q]
        tr = ref_run_with_flips(ref, self.N, ins, init, flips)
        w['replay_trace'] = tr
        if getattr(self, 'goal_check', None) and not self.goal_check(tr):
            raise RuntimeError('witness does not reproduce on the reference simulator')
        w['replayed'] = True
        return tr

    def all_min_attacks(self, k, backend='auto', cap=5000, timeout_s=None):
        """All flip sets of size k (cycle, net) that reach the goal, by blocking clauses on fault variables."""
        outs = self._card(k)
        be = self.backend(backend)
        found = []
        deadline = None if timeout_s is None else time.time() + timeout_s
        stop = 'exhausted'
        while True:
            if len(found) >= cap:
                stop = 'cap'; break
            r = be.solve([-outs[k]] if k < len(outs) else [], deadline=deadline)
            if r is None:
                stop = 'timeout'; break
            if not r:
                break
            w = self.witness(be.model())
            self.replay(w)
            fl = [(f['cycle'], f['net']) for f in w['flips']]
            found.append(w)
            fs_add_clause(self.e, be, [-self.F[x] for x in fl])
        return found, stop


def ref_run_with_flips(ref, T, ins, init, flips):
    """RefSim run (1 lane) with bit flips XORed into original nets: flips {(t, net): 1}. Q flips act on the flop
    output in that cycle (the stored state itself is not changed, as in the encoder: next state = D)."""
    cells = ref.m['cells']
    st = {cn: init.get(cn, 0) for cn, _ in ref.flops}
    trace = []
    for t in range(T):
        v = dict(ins[t])

        def g(b):
            if b == '0': return 0
            if b == '1': return 1
            return v[b]
        for cn, c in ref.flops:
            for b in c['connections'].get('Q', []):
                v[b] = st[cn] ^ flips.get((t, b), 0)
            for b in c['connections'].get('QN', []):
                qv = st[cn] ^ flips.get((t, c['connections']['Q'][0]), 0) if c['connections'].get('Q') else st[cn]
                v[b] = (qv ^ 1) ^ flips.get((t, b), 0)
        for b in ref.order:
            _, cn, p = ref.drv[b]
            c = cells[cn]
            pins, ones = ref.tables[(c['type'], p)]
            row = tuple(g(c['connections'][q][0]) for q in pins)
            v[b] = (1 if row in ones else 0) ^ flips.get((t, b), 0)
        trace.append(v)
        nst = {}
        for cn, c in ref.flops:
            dp, rp, sp, scan = ng.FLOP_PINS[c['type']]
            d = g(c['connections'][dp][0])
            if scan:
                d = g(c['connections'][scan[0]][0]) if g(c['connections'][scan[1]][0]) else d
            if rp: d &= g(c['connections'][rp][0])
            if sp: d |= 1 - g(c['connections'][sp][0])
            nst[cn] = d
        st = nst
    return trace
