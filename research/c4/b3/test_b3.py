"""pytest for b3pack.py (z3) vs bf_b3.py (brute force). Run from this folder: python3 -m pytest -q test_b3.py
Toy netlists are built in-code (no project files needed except V0 spike netlist for the agreement tests: env PROJ)."""
import os, sys, json, tempfile, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import faultpack as fp, b3pack as bp, bf_b3 as bf, modelsim as ms
PROJ = os.environ.get('PROJ', '/home/user/project')

def toy(init, dcfg, gates=()):
    """flops q0,q1 (nets 10,11). dcfg: D source of q0,q1 (net id or '0'/'1'). gates: list of (type, out, A, B)."""
    cells = {}
    for i, (ty, y, a, b) in enumerate(gates):
        cn = {'A': [a], 'Y': [y]}
        if b is not None: cn['B'] = [b]
        cells[f'g{i}'] = {'type': ty, 'connections': cn}
    for i, (d, q) in enumerate([(dcfg[0], 10), (dcfg[1], 11)]):
        cells[f'f{i}'] = {'type': '$_DFF_P_', 'connections': {'D': [d], 'Q': [q], 'C': [1]}}
    ports = {'clk': {'direction': 'input', 'bits': [1]}, 'sig': {'direction': 'input', 'bits': list(range(2, 10))},
             'boot_word': {'direction': 'output', 'bits': [10, 11, '0', '0', '0', '0', '0', '0']}}
    nets = {'q0': {'bits': [10], 'attributes': {'init': '1' if init[0] else '0'}}, 'q1': {'bits': [11], 'attributes': {'init': '1' if init[1] else '0'}}}
    d = tempfile.mkdtemp(); p = os.path.join(d, 't.json')
    json.dump({'modules': {'t': {'ports': ports, 'cells': cells, 'netnames': nets}}}, open(p, 'w')); return p

def z(p, ev, T, goal, cap=2):
    nl = fp.Netlist(p, 't'); M = bp.models(nl)
    return bp.min_cost(nl, T, M[ev], cap, 30000, goal_out='boot_word', goal_value=goal)

def test_early_capture_is_skip_ahead():
    p = toy((0, 0), ('1', 10))      # q0 <= 1 ; q1 <= q0.  Normal: t0 00, t1 10, t2 11
    assert z(p, 'early_one', 2, 0b11)['min'] == 1      # early on q0 at t0: q0 visible 1 at t0, q1 captures 1 -> 11 at t1
    assert z(p, 'hold_one', 2, 0b11)['status'] == 'NONE_UP_TO_CAP'      # a hold only delays
    sim = bf.Sim2(p, 't'); w = sim.run2(3, [(0, 'e', 10)]); assert [(x[0] & 1, x[1] & 1) for x in w] == [(1, 0), (1, 1), (1, 1)]

def test_hold_delays():
    p = toy((0, 0), ('1', 10))
    sim = bf.Sim2(p, 't'); w = sim.run2(4, [(0, 'h', 10)]); assert [(x[0] & 1, x[1] & 1) for x in w] == [(0, 0), (0, 0), (1, 0), (1, 1)]

def test_dip_D_capture_forces_zero_not_one():
    p = toy((1, 0), ('1', 10))      # q0 init 1, D=1 (const), q1 <= q0.  goal word 0: q0=q1=0 at some cycle < 3
    # normal: 10 -> 11 -> 11. rail_all dips flop D pins: q0 captures 0 at t0 -> t1 q0=0; q1 captured q0=1 at t0 -> t1 q1=1. need both 0 at t2:
    assert z(p, 'rail_all', 2, 0b00)['min'] == 1
    sim = bf.Sim2(p, 't'); w = sim.run2(2, [(0, 'd', 10, 'reset'), (0, 'd', 11, 'reset')]); assert [(x[0] & 1, x[1] & 1) for x in w] == [(1, 0), (0, 0)]
    nl = fp.Netlist(p, 't'); ev = bp.models(nl)['rail_all'][0]
    assert ev.d0 == set(nl.qs) and not ev.gates0

def test_dip_never_sets_a_flop_q_directly():
    # q0 init 0, D=1: goal q0=1 at t=1 is the NORMAL behaviour; with a dip at t0 it is lost; no event can make q0 1 earlier than normal
    p = toy((0, 0), ('1', 10))
    assert z(p, 'rail_all', 1, 0b01)['status'] == 'NONE_UP_TO_CAP'        # T=1: only the init state (00) is observed, dips cannot set 1

def test_dip_inverter_makes_one():
    # g = NOT(q1): q1 init 0 -> g=1 normally; q0 <= g. goal q0=0... instead check a dipped gate feeding an inverter yields 1
    g = [('$_NOT_', 12, 11, None), ('$_NOT_', 13, 12, None)]   # g12 = !q1 = 1 ; g13 = !g12 = 0 ; q0 <= g13 ; q1 <= 0
    p = toy((0, 0), (13, '0'), g)
    # normal: q0 stays 0. dip of g12 only (cone of q1... gates only) -> g13 = 1 -> q0 captures 1: a 1->0 dip creates a 1 via inversion
    nl = fp.Netlist(p, 't'); M = bp.models(nl)
    ev = [bp.Event('dip_g12', gates0={12})]
    r = bp.min_cost(nl, 2, ev, 2, 30000, goal_out='boot_word', goal_value=0b01)
    assert r['min'] == 1
    assert bp.min_cost(nl, 2, M['rail_all'], 2, 30000, goal_out='boot_word', goal_value=0b01)['status'] == 'NONE_UP_TO_CAP'  # whole-rail dip also zeroes g13

@pytest.mark.parametrize('d', ['v0'])
@pytest.mark.parametrize('model', ['stem_flip', 'rail_all', 'rail_half', 'rail_unions', 'rail_cone', 'early_one', 'early_all', 'early_subset', 'hold_one', 'hold_subset'])
def test_z3_equals_bruteforce_spike(d, model):
    path = os.path.join(PROJ, 'reference', 'spike_netlists', d + '.json')
    nl = fp.Netlist(path, d); sim = bf.Sim2(path, d)
    r = bp.min_cost(nl, 3, bp.models(nl)[model], 2, 120000)
    kb, w, _ = bf.min_cost(sim, 3, model, 2)
    assert r['status'] != 'UNKNOWN' and r['min'] == kb

def test_stem_flip_control_matches_b1():
    path = os.path.join(PROJ, 'reference', 'spike_netlists', 'v1.json')
    nl = fp.Netlist(path, 'v1')
    assert bp.min_cost(nl, 6, bp.models(nl)['stem_flip'], 2, 60000)['min'] == fp.min_cost(nl, 6, fp.MODELS['stem_flip'], 2)['min']
