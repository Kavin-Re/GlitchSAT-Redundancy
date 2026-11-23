"""Compositional analysis: module fault summaries composed at the top level.

A *module* is a set of combinational gates. In every cycle it forms one *instance*: a block with input nodes (read
from outside) and output nodes (read outside, or observed). The abstraction replaces the fault variables inside an
instance by a small unary cost c_1 >= c_2 >= ... :
    cost 0   the outputs equal the fault-free function of the (possibly already corrupted) inputs;
    cost >=1 the outputs are free, subject to the summary facts known for this module:
               ('e', err, m)      any input, output error pattern err (actual XOR fault-free)  ->  cost >= m
               ('xy', x, y, m)    inputs x, outputs y                                            ->  cost >= m
               ('sup', outs, m)   any input, all the listed outputs wrong at once               ->  cost >= m
Each fact is proved on the module alone (all inputs free, or the stated inputs), so it holds wherever the module
is used. The composed formula has the glue fault variables plus the costs under one cardinality bound.

Soundness of the composition (README section 4.3): every real attack with j flips maps to an assignment of the
composed formula with cost <= j, hence "composed formula unsatisfiable at budget j" proves "no attack with <= j
flips". In the other direction an abstract solution is only reported after each broken instance has been realised
by real flips of that module and the whole attack has been replayed on the gate-level simulator.
"""
import re, time
from .circuit import AND, OR, XOR, NOT, MUX
from .unroll import Dag, C0, C1, IN, BUF
from . import fastsat, reduce as red, sim, cnf, sat


_PREFIX = re.compile(r'^(?:\$flatten)?\\?((?:[A-Za-z_][A-Za-z_0-9\[\]]*\.)+)|^\\?([A-Za-z_][A-Za-z_0-9]*)\$')


class Timeout(Exception):
    pass


def find_modules(P, how='auto', min_sites=8, max_outputs=24):
    """Returns [(name, set of gate nets)]. how: 'prefix' (hierarchy prefix of the cell or net name, "A.x" / "A$12"),
    'islands' (groups of gates connected through gate-to-gate wires, i.e. separated by flops and inputs), 'auto'
    (prefix if it finds any module, else islands; in both cases only groups with at most max_outputs output nets
    and at least four fault sites per output), 'none'. The choice affects speed only, never soundness."""
    c = P.circ
    if how in (None, 'none'): return []

    readers = {}
    for b, (op, fi) in c.gates.items():
        for f in fi:
            if isinstance(f, int): readers.setdefault(f, []).append(b)
    ext = {d for d, _ in c.flops.values()} | set(P.observed_nets())
    for _, bits in c.ports.values(): ext.update(x for x in bits if isinstance(x, int))

    def ok(nets, strict=False):
        """Enough fault sites, and (strict) a narrow output interface: only then is one cost per instance a real
        saving over one variable per site."""
        ns = sum(1 for b in nets if b in P.sites)
        if ns < min_sites: return False
        if not strict: return True
        no = sum(1 for b in nets if b in ext or any(r not in nets for r in readers.get(b, ())))
        return no <= max_outputs and ns >= 4 * no
    def stat(nets):
        ns = sum(1 for b in nets if b in P.sites)
        no = sum(1 for b in nets if b in ext or any(r not in nets for r in readers.get(b, ())))
        return ns, no
    out = []
    if how in ('prefix', 'auto'):
        tree = {}                                    # hierarchy path (tuple) -> gates directly or deeper inside
        for b in c.gates:
            path = None
            for nm in (c.cell.get(b, ''), c.names.get(b, '')):
                m = _PREFIX.match(nm)
                if m:
                    path = tuple(m.group(1).rstrip('.').split('.')) if m.group(1) else (m.group(2),)
                    break
            if path:
                for i in range(1, len(path) + 1): tree.setdefault(path[:i], set()).add(b)
        kids = {}
        for p in tree:
            if len(p) > 1: kids.setdefault(p[:-1], []).append(p)

        def best(p):
            """Modules chosen below hierarchy node p: p itself when it is a good module and has more fault sites per
            output than anything chosen inside it, else the choices of its children."""
            sub = [m for k in sorted(kids.get(p, [])) for m in best(k)]
            ns, no = stat(tree[p])
            good = ns >= min_sites and (how == 'prefix' or (no <= max_outputs and ns >= 4 * no))
            if good and all(ns * m[3] > m[2] * max(no, 1) for m in sub):
                return [('.'.join(p), tree[p], ns, max(no, 1))]
            return sub
        out = [(nm, nets) for p in sorted(tree) if len(p) == 1 for nm, nets, _, _ in best(p)]
        if out or how == 'prefix': return out
    if how in ('islands', 'auto'):
        par = {b: b for b in c.gates}

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]; x = par[x]
            return x
        for b, (op, fi) in c.gates.items():
            for f in fi:
                if f in c.gates: par[find(f)] = find(b)
        groups = {}
        for b in c.gates: groups.setdefault(find(b), set()).add(b)
        return [('island%d' % i, v) for i, (k, v) in enumerate(sorted(groups.items(), key=lambda kv: min(kv[1])))
                if ok(v, how == 'auto')]
    raise ValueError('modules must be auto, prefix, islands or none')


# ---------------------------------------------------------------- one module shape, analysed alone
class Local:
    """A module instance cut out of the DAG: its own small Dag with free inputs. Instances with the same structure
    (other cycles, structurally identical copies) share one Local, so a summary fact is computed once."""

    def __init__(self, sig, ops, n_in, outs):
        self.sig = sig; self.ops = ops; self.n_in = n_in; self.outs = outs      # outs: positions in ops
        d = self.dag = Dag()
        self.inp = [d.new(IN, (), False, ('in', i)) for i in range(n_in)]
        self.pos2node = []
        for k, (op, site, refs) in enumerate(ops):
            fi = tuple(r[1] if r[0] == 'c' else self.inp[r[1]] if r[0] == 'i' else self.pos2node[r[1]] for r in refs)
            self.pos2node.append(d.new(op, fi, site, k))
        self.out_nodes = [self.pos2node[p] for p in outs]
        d.obs = set(self.out_nodes)
        self.n_sites = sum(1 for o in ops if o[1])
        self.facts = []; self._err = {}; self._xy = {}; self.M = None; self.cap = 0
        self.stats = dict(queries=0, time=0.0, facts_e=0, facts_xy=0, eager=0)

    def _build(self, cap):
        if self.M is not None and cap <= self.cap: return
        fs = fastsat()
        d = self.dag
        self.keep, _ = red.structural(d)
        e = fs.Encoding()
        lit0 = {i: e.new_var() for i in self.inp}
        self.in_lits = [lit0[i] for i in self.inp]
        ff, _ = cnf.encode_nodes(e, d, set(), lit=dict(lit0))
        fl, F = cnf.encode_nodes(e, d, self.keep, lit=dict(lit0))
        self.o = [ff[n] for n in self.out_nodes]; self.y = [fl[n] for n in self.out_nodes]
        self.dl = [e.g_xor(a, b) for a, b in zip(self.y, self.o)]
        self.F = F
        e.fault_order = [F[i] for i in sorted(F)]
        fs.add_cardinality(e, cap, 'totalizer')
        self.e = e; self.s = sat.Inc(e, 'py'); self.cap = cap; self.M = True; self.fs = fs

    def _ascend(self, assum, lo, cap, deadline):
        self._build(cap)
        for j in range(max(lo, 0), cap + 1):
            t0 = time.time()
            r = self.s.solve(assum + self.fs.atmost(self.e, j), deadline=deadline)
            self.stats['queries'] += 1; self.stats['time'] += time.time() - t0
            if r is None: raise Timeout()
            if r:
                m = self.s.model()
                return j, [self.dag.key[i] for i, f in self.F.items() if m[f]]
        return None, None

    def min_cost(self, x, y, cap, deadline=None):
        """Least number of flips inside the module that turn inputs x into outputs y (tuples of bool), up to cap.
        Returns (m, [positions of flipped nodes]) or (None, None) when more than cap are needed."""
        k = (x, y)
        if k in self._xy and (self._xy[k][0] is not None or self._xy[k][2] >= cap): return self._xy[k][:2]
        self._build(cap)
        assum = [l if v else -l for l, v in zip(self.in_lits, x)] + [l if v else -l for l, v in zip(self.y, y)]
        m, fl = self._ascend(assum, 0, cap, deadline)
        self._xy[k] = (m, fl, cap)
        return m, fl

    def min_err(self, err, cap, deadline=None):
        """Least number of flips that produce output error pattern err for SOME input, up to cap (None: more)."""
        if err in self._err and (self._err[err][0] is not None or self._err[err][1] >= cap): return self._err[err][0]
        self._build(cap)
        assum = [l if v else -l for l, v in zip(self.dl, err)]
        m, _ = self._ascend(assum, 1, cap, deadline)
        self._err[err] = (m, cap)
        return m

    def eager(self, max_in=12, max_out=10, deadline=None, kmax=3):
        """Summary facts computed once per module shape, before any solving.
        (1) Support facts, any module size: if no fault site of the module can reach both output i and output j,
            an error on both needs two flips; three outputs that pairwise share no site need three.
        (2) One-flip summary by exhaustive fault simulation (small modules only): the set E1 of output error
            patterns that a single flip can cause for some input; every other non-zero pattern needs two flips."""
        if self.stats['eager']: return
        self.stats['eager'] = 1
        t0 = time.time()
        d = self.dag; outs = self.out_nodes; n = len(outs)
        if n >= 2:
            reach = [0] * len(d)
            for i, o in enumerate(outs): reach[o] |= 1 << i
            for i in range(len(d) - 1, 1, -1):
                r = reach[i]
                if r:
                    for f in d.fi[i]: reach[f] |= r
            share = [0] * n                            # share[i]: outputs that some site reaches together with i
            for i in range(2, len(d)):
                if d.site[i] and reach[i]:
                    r = reach[i]; j = 0
                    while r >> j:
                        if (r >> j) & 1: share[j] |= r
                        j += 1
            pairs = [(i, j) for i in range(n) for j in range(i + 1, n) if not (share[i] >> j) & 1]
            for p in pairs[:5000]:
                self.facts.append(('sup', p, 2)); self.stats['facts_sup'] = self.stats.get('facts_sup', 0) + 1
            if kmax >= 3 and pairs and n <= 32:
                ok = set(pairs); cnt = 0
                for (i, j) in pairs:
                    for k in range(j + 1, n):
                        if (i, k) in ok and (j, k) in ok:
                            self.facts.append(('sup', (i, j, k), 3)); cnt += 1
                            if cnt >= 3000: break
                    if cnt >= 3000: break
                self.stats['facts_sup'] = self.stats.get('facts_sup', 0) + cnt
        if self.n_in > max_in or n > max_out or n < 2:
            self.stats['time'] += time.time() - t0; return
        keep, _ = red.structural(d)
        W = 1 << self.n_in; mask = (1 << W) - 1
        inw = {}
        for k, nd in enumerate(self.inp):
            blk = (1 << (1 << k)) - 1; w = 0
            for s in range(1 << k, W, 2 << k): w |= blk << s
            inw[nd] = w
        val = sim.dag_eval(d, inw, mask)
        rd = d.readers()
        E1 = set()
        for a in keep:
            if deadline is not None and time.time() > deadline: return
            new = sim.toggle_effect(d, val, mask, a, rd)
            D = [(new[o] ^ val[o]) if o in new else 0 for o in outs]
            st = [(mask, 0, 0)]
            while st:
                w, i, pat = st.pop()
                if i == len(D):
                    E1.add(pat); continue
                a1 = w & D[i]; a0 = w & ~D[i]
                if a1: st.append((a1, i + 1, pat | (1 << i)))
                if a0: st.append((a0, i + 1, pat))
        for pat in range(1, 1 << n):
            if pat not in E1:
                self.facts.append(('e', tuple(bool((pat >> i) & 1) for i in range(n)), 2)); self.stats['facts_e'] += 1
        self.E1 = E1
        self.stats['time'] += time.time() - t0


class Store:
    """Module shapes seen so far (keyed by structure)."""
    def __init__(self):
        self.locals = {}

    def get(self, ops, n_in, outs):
        sig = (tuple(ops), n_in, tuple(outs))
        L = self.locals.get(sig)
        if L is None:
            L = self.locals[sig] = Local(sig, ops, n_in, outs)
        return L


class Instance:
    pass


# ---------------------------------------------------------------- the composed (abstract) formula
class Abstraction:
    def __init__(self, U, keep, modules, kmax, store=None, eager=True, deadline=None):
        fs = self.fs = fastsat()
        self.U, self.kmax = U, kmax
        self.store = store or Store()
        d = U.dag
        net2mod = {}
        for mi, (name, nets) in enumerate(modules):
            for b in nets: net2mod[b] = mi
        inst_of = {}; members = {}
        for i in range(2, len(d)):
            k = d.key[i]
            if d.op[i] == IN or k is None or k[0] == 'in': continue
            mi = net2mod.get(k[1])
            if mi is not None:
                inst_of[i] = (mi, k[0]); members.setdefault((mi, k[0]), []).append(i)
        rd = d.readers()
        self.inst = []
        byid = {}
        for key_, nodes in sorted(members.items()):
            if not any(d.site[n] for n in nodes):
                for n in nodes: del inst_of[n]
                continue
            I = Instance(); I.key = key_; I.name = '%s@%d' % (modules[key_[0]][0], key_[1]); I.nodes = nodes
            pos = {n: p for p, n in enumerate(nodes)}
            ins = []; inpos = {}; ops = []
            for n in nodes:
                refs = []
                for f in d.fi[n]:
                    if f < 2: refs.append(('c', f))
                    elif f in pos: refs.append(('n', pos[f]))
                    else:
                        if f not in inpos:
                            inpos[f] = len(ins); ins.append(f)
                        refs.append(('i', inpos[f]))
                ops.append((d.op[n], d.site[n], tuple(refs)))
            outs = [pos[n] for n in nodes if n in d.obs or any(inst_of.get(r) != key_ for r in rd[n])]
            I.ins = ins; I.outs = [nodes[p] for p in outs]; I.outset = set(I.outs)
            I.local = self.store.get(ops, len(ins), outs)
            I.applied = 0
            if eager: I.local.eager(deadline=deadline, kmax=kmax)
            self.inst.append(I); byid[key_] = I
        e = self.e = fs.Encoding()
        lit = self.lit = {0: fs.F_, 1: fs.T_}
        self.F = {}
        leaves = []
        for I in self.inst:
            I.cap = max(1, min(kmax, I.local.n_sites))
        ff = {}
        started = set()
        for i in range(2, len(d)):
            key_ = inst_of.get(i)
            if key_ is None:
                f = None
                if i in keep:
                    f = e.new_var(); self.F[i] = f; leaves.append((i, f))
                lit[i] = cnf.gate_lit(e, d.op[i], [lit[j] for j in d.fi[i]], f)
                continue
            I = byid[key_]
            if key_ not in started:
                started.add(key_)
                I.c = [e.new_var() for _ in range(I.cap)]
                for a, b in zip(I.c, I.c[1:]): e.add([-b, a])
                leaves += [(i, v) for v in I.c]
                I.y = {}; I.o = {}
            o = cnf.gate_lit(e, d.op[i], [ff[j] if inst_of.get(j) == key_ else lit[j] for j in d.fi[i]])
            ff[i] = o
            if i in I.outset:
                y = e.new_var()
                e.add([I.c[0], -y, o]); e.add([I.c[0], y, -o])
                lit[i] = y; I.y[i] = y; I.o[i] = o
            else:
                lit[i] = o
        for I in self.inst:
            I.in_lits = [lit[g] for g in I.ins]
            I.y_lits = [I.y[n] for n in I.outs]; I.o_lits = [I.o[n] for n in I.outs]
            I.d_lits = None
        self.prefix = cnf.add_goal(e, U, lit)
        e.fault_order = [v for _, v in sorted(leaves)]
        self.core = e.stats()
        fs.add_cardinality(e, kmax, 'totalizer')
        self.size = e.stats()
        self.n_facts = 0
        self.apply_facts()

    def assume(self, j, n=None):
        n = len(self.prefix) - 1 if n is None else n
        return [self.prefix[n]] + self.fs.atmost(self.e, j)

    def apply_facts(self):
        """Add the clauses of every summary fact that an instance has not seen yet."""
        e = self.e; T_, F_ = self.fs.T_, self.fs.F_
        for I in self.inst:
            L = I.local
            while I.applied < len(L.facts):
                kind, a, b = L.facts[I.applied][0], L.facts[I.applied][1:-1], L.facts[I.applied][-1]
                I.applied += 1
                if b <= 1: continue
                if kind in ('e', 'sup') and I.d_lits is None:
                    I.d_lits = [e.g_xor(y, o) for y, o in zip(I.y_lits, I.o_lits)]
                if kind == 'e':
                    cl = [(-l if v else l) for l, v in zip(I.d_lits, a[0])]
                elif kind == 'sup':
                    cl = [-I.d_lits[i] for i in a[0]]
                else:
                    cl = [(-l if v else l) for l, v in zip(I.in_lits, a[0])] + [(-l if v else l) for l, v in zip(I.y_lits, a[1])]
                if T_ in cl: continue
                cl = [l for l in cl if l != F_]
                if b <= I.cap: cl.append(I.c[b - 1])
                e.add(cl); self.n_facts += 1

    def _val(self, m, l):
        if l == self.fs.T_: return True
        if l == self.fs.F_: return False
        return bool(m[l]) if l > 0 else not m[-l]

    def inputs(self, m):
        ins = {}
        for (b, t), n in self.U.in_nodes.items():
            v = self.lit.get(n)
            if v is not None: ins[b if t is None else (t, b)] = self._val(m, v)
        return ins

    def concretise(self, m, deadline=None):
        """Try to realise an abstract solution by real flips. Returns (faults or None, within_cost, n_new_facts).
        faults is None when some instance cannot be realised within kmax flips; within_cost tells whether every
        instance was realised within its abstract cost (then the attack is as cheap as the abstract solution)."""
        d = self.U.dag
        faults = [d.key[i] for i, f in self.F.items() if m[f]]
        within = True; possible = True; new = 0
        for I in self.inst:
            if not m[I.c[0]]: continue
            L = I.local
            x = tuple(self._val(m, l) for l in I.in_lits)
            y = tuple(self._val(m, l) for l in I.y_lits)
            o = tuple(self._val(m, l) for l in I.o_lits)
            if y == o: continue
            c = sum(1 for v in I.c if m[v])
            ms, fl = L.min_cost(x, y, self.kmax, deadline)
            if ms is not None:
                faults += [d.key[I.nodes[p]] for p in fl]
            else:
                possible = False
            if ms is None or ms > c:
                within = False
                err = tuple(a != b for a, b in zip(y, o))
                top = self.kmax if ms is None else ms - 1
                g = L.min_err(err, top, deadline) if top >= 1 else None
                bound = (top + 1) if g is None else g          # proved: error err needs >= bound flips for any input
                if bound > c:
                    L.facts.append(('e', err, bound)); L.stats['facts_e'] += 1; new += 1
                if g is not None:                               # the input-specific fact is the stronger one here
                    L.facts.append(('xy', x, y, self.kmax + 1 if ms is None else ms)); L.stats['facts_xy'] += 1; new += 1
        self.apply_facts()
        return (sorted(set(faults)) if possible else None), within, new
