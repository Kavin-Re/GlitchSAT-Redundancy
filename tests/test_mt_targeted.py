"""Targeted tests for mutation survivors temporal_off2, coi_nolast, dist_goal_none, honest_nofix, inport_drv_off. Engine: scripts/glitchsat.py."""
import json, os, sys
import pytest
pytest.importorskip('z3', reason='z3-solver is not installed: pip install z3-solver')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g

SIG, OUT, KEY = [3, 4], [5, 6], 3

def net(gates, flops=(), outbits=OUT):
    pins = {'$_AND_': 'AB', '$_OR_': 'AB', '$_XOR_': 'AB', '$_NOT_': 'A', '$_MUX_': 'ABS'}
    cells = {}
    for n, (ty, o, ins) in enumerate(gates):
        c = {p: [i] for p, i in zip(pins[ty], ins)}; c['Y'] = [o]
        cells['g%d' % n] = dict(type=ty, connections=c)
    for n, (d, q) in enumerate(flops):
        cells['f%d' % n] = dict(type='$_DFF_P_', connections=dict(C=[2], D=[d], Q=[q]))
    ports = dict(clk=dict(direction='input', bits=[2]), sig=dict(direction='input', bits=SIG),
                 boot_word=dict(direction='output', bits=outbits))
    return dict(modules=dict(t=dict(ports=ports, cells=cells, netnames={})))

def load(tmp, doc):
    p = os.path.join(str(tmp), 'n.json'); json.dump(doc, open(p, 'w'))
    return g.Netlist(p, 't')

def only_last_cycle_comb(tmp):
    # out0 = sig0 XOR sig1 (=1 for sig 1,2), out1 = const-0 via AND(sig0, NOT sig0)... use AND(sig0,0) -> '0'.
    # goal 0b01 is reached by input 1 or 2 without any fault; to make a FAULT necessary use goal 0b10:
    # out1 = AND(sig0, sig1) is 1 only for sig==3 == key (forbidden), so an attack needs a flip of that gate (or of out0).
    d = net([('$_AND_', 5, [3, 4]), ('$_AND_', 6, [3, 4])])
    return load(tmp, d)

# The only attack in this 1-cycle design is a combinational fault at cycle 0 == the last cycle (N-1). Kills temporal_off2
# (`t + dist <= N-2` drops it), dist_goal_none (goal dist 1 instead of 0) and coi_nolast (`t > 0` drops cycle 0 in 'coi').
@pytest.mark.parametrize('reduce', ['none', 'coi', 'full'])
def test_single_cycle_comb_fault_found(reduce, tmp_path):
    nl = only_last_cycle_comb(tmp_path)
    assert g.solve(nl, 1, 0, reduce=reduce, key=KEY, goal_value=1)[0] == 'NO_ATTACK_UP_TO_BOUND'
    v, info, res = g.solve(nl, 1, 1, reduce=reduce, key=KEY, goal_value=1)
    assert v == 'ATTACK_FOUND', (reduce, info)
    assert res['faults'] == [(0, 5)] or (len(res['faults']) == 1 and res['faults'][0][0] == 0)

def test_reductions_agree_two_cycles(tmp_path):
    """Same design, N=2: the verdict and the minimal size must not depend on the reduction level."""
    nl = only_last_cycle_comb(tmp_path)
    out = {r: g.solve(nl, 2, 1, reduce=r, key=KEY, goal_value=1)[0] for r in ('none', 'coi', 'full')}
    assert set(out.values()) == {'ATTACK_FOUND'}

def test_sequential_site_needs_full_reach(tmp_path):
    # out0 = q10 (flop), q10.D = g20 = AND(sig0,sig1) (0 unless sig==key). A flip of g20 at cycle 0 sets q10 at cycle 1 (dist 1);
    # with N=2 that is the last cycle. Attack found with k=1 under every reduction (kills dist_goal_none / off2 for dist>0 sites).
    d = net([('$_AND_', 20, [3, 4]), ('$_AND_', 6, ['0', '0'])], flops=[(20, 10)], outbits=[10, 6])
    nl = load(tmp_path, d)
    for r in ('none', 'coi', 'full'):
        v, _, res = g.solve(nl, 2, 1, reduce=r, key=KEY, goal_value=1)
        assert v == 'ATTACK_FOUND', r
        assert len(res['faults']) == 1

def test_honest_boots_requires_the_legitimate_key(tmp_path):
    # out0 = sig0 XOR sig1, out1 = 0. Goal 1 is hit by sig 1 or 2 but NOT by the legitimate key 3, so the honest key does not boot.
    # Kills honest_nofix (honest_boots ignoring fixed_in=key would report True because some other input boots).
    d = net([('$_XOR_', 5, [3, 4]), ('$_AND_', 6, ['0', '0'])])
    nl = load(tmp_path, d)
    assert g.honest_boots(nl, 2, key=KEY, goal_value=1) is False
    assert g.honest_boots(nl, 2, key=1, goal_value=1) is True

def test_gate_driving_input_port_bit_rejected(tmp_path):
    # a gate whose output is the module input bit 3 is a multiple-driver error. Kills inport_drv_off.
    d = net([('$_AND_', 3, [4, 4]), ('$_AND_', 5, [3, 4]), ('$_AND_', 6, [3, 4])])
    with pytest.raises(g.NetlistError, match='input port'):
        load(tmp_path, d)

def test_goal_and_attacker_port_directions_checked(tmp_path):
    # goal must be an OUTPUT port, attacker an INPUT port. Kills goal_widthchk (direction test dropped) and attin_dirchk.
    nl = load(tmp_path, net([('$_AND_', 5, [3, 4]), ('$_AND_', 6, [3, 4])]))
    with pytest.raises(g.NetlistError, match='not an output port'):
        g.build(nl, 1, goal_out='sig', goal_value=1, attack_in='sig', key=KEY)
    with pytest.raises(g.NetlistError, match='not an input port'):
        g.build(nl, 1, goal_out='boot_word', goal_value=1, attack_in='boot_word', key=KEY)
