"""Reductions, encoder and search against the exhaustive reference and the recorded minimums."""
import os, random
import pytest
import oracle, designs
from gscale import circuit, unroll, reduce as red, cnf, sat, sim, search, modular, symmetry


def _min(r):
    return r['hi'] if r['status'] == 'EXACT' else None if r['status'] == 'NO_ATTACK_UP_TO_BOUND' else r['status']


@pytest.mark.parametrize('name,want', [('v0', 1), ('v1', 1), ('v2', 3)])
@pytest.mark.parametrize('level', ['time', 'struct', 'full'])
def test_reference_minimums(root, fs, name, want, level):
    nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', name + '.json'), name)
    P = circuit.engine_problem(nl, 6)
    r = search.analyse(P, 3, reduce=level, modules='none', backend='py')
    assert _min(r) == want and r['witness']['replayed']
    assert sim.is_attack(P, *r['_witness_raw'])


def test_v2_no_attack_below_three(root, fs):
    nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', 'v2.json'), 'v2')
    r = search.analyse(circuit.engine_problem(nl, 6), 2, backend='py')
    assert r['status'] == 'NO_ATTACK_UP_TO_BOUND' and r['lo'] == 3 and r['hi'] is None


def test_same_fault_variables_or_fewer_than_fastsat(root, fs):
    """Post-dominator roots are a subset of what single-reader collapsing keeps (it is the special case)."""
    for name in ('v0', 'v1', 'v2'):
        nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', name + '.json'), name)
        U = unroll.unroll(circuit.engine_problem(nl, 6))
        keep, _ = red.structural(U.dag)
        assert len(keep) <= fs.encode(nl, 6).info['fault_vars']


def _random_problem(rng, fs, path):
    import netgen
    while True:
        doc, meta = netgen.random_netlist(rng, *rng.choice([(10, 3, 3), (14, 4, 4), (6, 2, 4), (18, 4, 3)]))
        netgen.write(doc, path)
        try: nl = fs.gs.Netlist(path, 't')
        except fs.NetlistError: continue
        T = rng.randint(1, 4); k = rng.randint(1, 3)
        P = circuit.engine_problem(nl, T, goal_value=rng.randrange(1 << meta['w_out']), key=rng.randrange(1 << meta['w_sig']))
        c = P.circ
        if rng.random() < 0.5:
            for b in c.inputs:
                r = rng.random()
                if b in P.neq[0]: continue
                if r < 0.4: P.in_mode[b] = 'cycle'
                elif r < 0.6: P.in_mode[b] = rng.randint(0, 1)
            if rng.random() < 0.3:
                P.neq = None
                for b in c.inputs:
                    if rng.random() < 0.5: P.in_mode[b] = 'cycle'
        if rng.random() < 0.4:
            P.sites = set(b for b in sorted(P.sites) if rng.random() < 0.6)
        if rng.random() < 0.4:
            pool = list(c.gates) + list(c.flops)
            P.quiet = [(rng.choice(pool), rng.random() < 0.5) for _ in range(rng.randint(1, 2))]
        try: O = oracle.Oracle(P, 12)
        except ValueError: continue
        if O.run(()) and rng.random() < 0.85:
            for gv in rng.sample(range(1 << meta['w_out']), min(8, 1 << meta['w_out'])):
                P.goal = [(b, bool((gv >> i) & 1)) for i, (b, _) in enumerate(P.goal)]
                if not O.run(()): break
            else: continue
        want = O.min_faults(k, limit=40000)
        if want == 'limit': continue
        return P, O, k, want


@pytest.mark.parametrize('seed', [101, 102, 103])
def test_fuzz_against_exhaustive(fs, tmp_path, seed):
    """Random netlists with random input modes, site sets, quiet conditions and module partitions: every reduction
    level, with and without modules and symmetry breaking, gives the exhaustive minimum."""
    rng = random.Random(seed)
    for case in range(100):
        P, O, k, want = _random_problem(rng, fs, str(tmp_path / 'n.json'))
        gates = sorted(P.circ.gates)
        for cfg in range(4):
            level = ['time', 'struct', 'full', rng.choice(['struct', 'full'])][cfg]
            if cfg == 0: mods = 'none'
            elif cfg == 1: mods = 'islands'
            else:
                nm = rng.randint(1, 3); mm = [set() for _ in range(nm)]
                for b in gates:
                    r = rng.randrange(nm + 1)
                    if r < nm: mm[r].add(b)
                mods = [('m%d' % i, s) for i, s in enumerate(mm) if s]
            r = search.analyse(P, k, reduce=level, modules=mods, backend='py', min_module_sites=1, reduce_time_s=5,
                               use_symmetry=(cfg == 3))
            assert _min(r) == want, (seed, case, level, mods, r['status'], r['lo'], r['hi'], want)


def test_toggle_dominance_by_exhaustive_simulation(fs, tmp_path):
    """The lemma behind the structural reduction, checked directly: for a dropped site a with cover d, flipping a
    on top of any context of up to one other flip changes the observed nodes not at all or exactly like toggling d."""
    rng = random.Random(7); checked = 0
    for case in range(25):
        P, O, k, want = _random_problem(rng, fs, str(tmp_path / 'n.json'))
        U = unroll.unroll(P); d = U.dag
        keep, cover = red.structural(d)
        ins = [i for i in range(2, len(d)) if d.op[i] == 'IN']
        if len(ins) > 10 or not cover: continue
        W = 1 << len(ins); mask = (1 << W) - 1
        inw = {n: sum(1 << s for s in range(W) if (s >> j) & 1) for j, n in enumerate(ins)}
        sites = [i for i in range(2, len(d)) if d.site[i]]
        obs = sorted(d.obs)
        for a, dn in list(cover.items())[:6]:
            for ctx in [None] + rng.sample(sites, min(4, len(sites))):
                if ctx in (a, dn): continue
                base = {ctx: mask} if ctx else {}
                v0 = sim.dag_eval(d, inw, mask, base)
                va = sim.dag_eval(d, inw, mask, {**base, a: mask})
                vd = sim.dag_eval(d, inw, mask, {**base, dn: mask})
                same0 = mask; samed = mask
                for o in obs:
                    same0 &= ~(va[o] ^ v0[o]); samed &= ~(va[o] ^ vd[o])
                assert (same0 | samed) & mask == mask
                checked += 1
    assert checked > 50


def test_functional_reduction_proves_what_structure_cannot():
    P, a = designs.xor_cancel()
    U = unroll.unroll(P)
    ks, _ = red.structural(U.dag)
    kf, cov, info = red.functional(U.dag, ks, time_s=10)
    a_nodes = {i for i in ks if U.dag.key[i][1] == a}
    assert a_nodes and not (a_nodes & kf) and info['proved_noop'] >= len(a_nodes)
    P, (a, b) = designs.twin_sites()
    U = unroll.unroll(P)
    ks, _ = red.structural(U.dag)
    kf, cov, info = red.functional(U.dag, ks, time_s=10)
    assert info['proved_equal'] >= 1 and len(kf) < len(ks)
    for lv in ('time', 'struct', 'full'):
        assert _min(search.analyse(P, 2, reduce=lv, modules='none', backend='py')) == oracle.Oracle(P).min_faults(2)


def test_miter_refutes_wrong_candidates(fs, root):
    """The SAT confirmation must reject pairs that only look equal: two sites of V2 that are not equivalent."""
    nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', 'v2.json'), 'v2')
    U = unroll.unroll(circuit.engine_problem(nl, 4)); d = U.dag
    keep, _ = red.structural(d)
    m = red.Miter(d); ks = sorted(keep)
    res = [m.check(ks[i], ks[j]) for i in range(0, 6) for j in range(len(ks) - 6, len(ks)) if ks[i] < ks[j]]
    assert False in res and None not in res


def test_hard_constants_fold_only_what_no_fault_can_change():
    b = designs.B(); s = b.inp('sig', 1); en = b.inp('en', 1)
    g1 = b.g('AND', s[0], en[0], name='g1'); q = b.ff(g1, name='q')
    b.c.ports['o'] = ('output', [q])
    P = circuit.Problem(b.c, 2, [(q, True)], in_mode={en[0]: 0}, sites={q, g1})
    U = unroll.unroll(P)                        # g1 = sig & 0 is hard 0 before its own flip: a constant site node
    ops = [(U.dag.op[i], U.dag.site[i]) for i in range(2, len(U.dag))]
    assert ('C0', True) in ops and all(op != 'AND' for op, _ in ops)
    assert _min(search.analyse(P, 2, modules='none', backend='py')) == 1 == oracle.Oracle(P).min_faults(2)
    P2 = circuit.Problem(b.c, 2, [(q, True)], in_mode={en[0]: 0}, sites=set())
    assert search.analyse(P2, 2, modules='none', backend='py')['status'] == 'NO_ATTACK_UP_TO_BOUND'
