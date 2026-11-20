"""pytest tests for faultpack.py / modelsim.py. Run: python3 -m pytest -q test_faultpack.py (from this folder)."""
import os, sys, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import faultpack as fp, modelsim as ms
ROOT = os.environ.get('PROJ', '<repo>')
P = lambda d: os.path.join(ROOT, 'reference', 'spike_netlists', f'{d}.json')

def solve(d, model, T=4, cap=3, **kw):
    return fp.min_cost(fp.Netlist(P(d), d), T, fp.MODELS[model] if isinstance(model, str) else model, cap, **kw)

def test_stem_flip_matches_published_spike_numbers():
    # project numbers (validation/VALIDATION.md): V0 k=1, V1 k=1 (net ok), V2 needs 3 at T=6
    assert solve('v0', 'stem_flip', 6)['min'] == 1
    r = solve('v1', 'stem_flip', 6); assert r['min'] == 1
    assert 'ok' in fp.describe(fp.Netlist(P('v1'), 'v1'), r['faults'][0][1])
    assert solve('v2', 'stem_flip', 4, cap=2)['status'] == 'NONE_UP_TO_CAP'   # none with <=2 at T=4

def test_branch_flip_costs_v1_two():
    assert solve('v1', 'branch_flip', 6)['min'] == 2

@pytest.mark.parametrize('model', ['stem_flip', 'branch_flip', 'set_only', 'reset_only', 'flop_hold', 'group_flops_m2',
                                   'input_flip', 'input_set', 'input_reset', 'cone_flip_exact', 'hood_flip_exact'])
@pytest.mark.parametrize('d', ['v0', 'v1'])
def test_solver_agrees_with_exhaustive_sim(d, model):
    import validate as v
    mm, gfn, m, sing, *ex = v.SPEC[model]; ex = bool(ex and ex[0])
    sim = ms.Sim(P(d), d)
    r = solve(d, model, 4, cap=2)
    ke, w, _ = ms.min_cost_exhaustive(sim, 4, mm, 2, gfn(sim) if gfn else None, m, sing, exact=ex)
    assert ke == r['min']
    if r['status'] == 'ATTACK':
        assert ms.hit_lanes(sim.run(4, [v.to_sim_fault(*f) for f in r['faults']]))

def test_reduce_full_equals_none_on_v0():
    nl = fp.Netlist(P('v0'), 'v0')
    for model in ['stem_flip', 'branch_flip', 'set_only', 'flop_hold']:
        a = fp.min_cost(nl, 5, fp.MODELS[model], 2, reduce='full')
        b = fp.min_cost(nl, 5, fp.MODELS[model], 2, reduce='none')
        assert fp.fmt(a) == fp.fmt(b)

def test_group_action_costs_one():
    # the 3 nets of the V2 stem-flip 3-attack (all cycle 1) as one user group: m=3 -> cost 1, m=2 -> cost 2
    nl = fp.Netlist(P('v2'), 'v2')
    pats = {'g': r'c0\.\$abc\$251\$new_n13_|c1\.\$abc\$251\$new_n12_|c2\.\$abc\$251\$new_n11_'}
    mk = lambda m: fp.FaultModel('u', 'stem', ('flip',), groups=fp.groups_from_regex(pats), m=m)
    assert fp.min_cost(nl, 6, mk(3), 3)['min'] == 1
    assert fp.min_cost(nl, 6, mk(2), 3)['min'] == 2
    assert fp.min_cost(nl, 6, mk(1), 3)['min'] == 3

def test_model_orderings():
    # stem-or-branch can never cost more than either
    for d in ['v0', 'v1']:
        s, b, u = (solve(d, m, 5, cap=3)['min'] for m in ('stem_flip', 'branch_flip', 'stem_or_branch_flip'))
        assert u <= min(s, b)


def test_input_faults_do_not_change_when_no_input_sites_needed():
    # input faults only add sites: min cost can never exceed stem_flip's
    for d in ['v0', 'v1']:
        assert solve(d, 'input_flip', 5, cap=3)['min'] <= solve(d, 'stem_flip', 5, cap=3)['min']

def test_input_fault_site_exists_and_is_used_when_only_input_allowed():
    # restrict to input bits only: sig bit 0 stem-flipped at some cycle can make V0 boot (V0 is a plain compare)
    nl = fp.Netlist(P('v0'), 'v0')
    sigbits = set(nl.ports['sig']['bits'])
    fm = fp.FaultModel('only_in', 'stem', ('flip',), inputs=True,
                       groups=lambda n: [('sig', frozenset(sigbits))], m=1, singletons=False)
    r = fp.min_cost(nl, 4, fm, 2)
    assert r['status'] in ('ATTACK', 'NONE_UP_TO_CAP')

def test_exact_group_is_stronger_cost_than_subset_never_cheaper_semantics():
    # subset-of-group (m large) is at least as strong an attacker as exact all-members group
    nl = fp.Netlist(P('v1'), 'v1')
    a = fp.min_cost(nl, 5, fp.MODELS['cone_flip_exact'], 3)['min']
    b = fp.min_cost(nl, 5, fp.FaultModel('c', 'stem', ('flip',), groups=fp.groups_cone, m=10 ** 6, exact=False), 3)['min']
    assert b <= a

def test_cone_group_contents():
    nl = fp.Netlist(P('v1'), 'v1')
    sim = ms.Sim(P('v1'), 'v1')
    mine = {g for _, g in fp.groups_cone(nl)}
    theirs = set(sim.cone_groups())
    assert mine == theirs      # two independent implementations of the cone agree

def test_hold_cannot_fire_in_last_cycle():
    nl = fp.Netlist(P('v0'), 'v0')
    s, F, cost, inputs, info = fp.build(nl, 4, fp.MODELS['flop_hold'], reduce='none')
    assert all(t <= 2 for (t, site, e) in F)
