"""The cloud-side tooling without Yosys or z3: the gate-level replayer on a hand-written netlist, and the runner's
solver call, summary and Studio output with a stand-in solver script."""
import json, os, stat, sys
import os
import pytest
from engine import netsim, run_glitchsat, studio
from model.variants import BY_NAME

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tiny_netlist(tmp_path):
    """2-bit counter q (init 2'b10) that counts while sig[0] = 1; output y = q[1] AND NOT q[0], z = q via MUX."""
    m = dict(ports=dict(clk=dict(direction='input', bits=[2]), sig=dict(direction='input', bits=[3]),
                        y=dict(direction='output', bits=[10]), z=dict(direction='output', bits=[11, 12])),
             cells={
                 'ff0': dict(type='$_DFF_P_', connections=dict(C=[2], D=[20], Q=[4])),
                 'ff1': dict(type='$_DFF_P_', connections=dict(C=[2], D=[21], Q=[5])),
                 'x0': dict(type='$_XOR_', connections=dict(A=[4], B=[3], Y=[20])),
                 'a0': dict(type='$_AND_', connections=dict(A=[4], B=[3], Y=[22])),
                 'x1': dict(type='$_XOR_', connections=dict(A=[5], B=[22], Y=[21])),
                 'n0': dict(type='$_NOT_', connections=dict(A=[4], Y=[23])),
                 'a1': dict(type='$_AND_', connections=dict(A=[5], B=[23], Y=[10])),
                 'm0': dict(type='$_MUX_', connections=dict(A=['0'], B=[4], S=[3], Y=[11])),
                 'o0': dict(type='$_OR_', connections=dict(A=[5], B=['0'], Y=[12])),
             },
             netnames={'q': dict(bits=[4, 5], attributes=dict(init='10')), 'sig': dict(bits=[3], attributes={})})
    p = tmp_path / 'n.json'
    p.write_text(json.dumps(dict(modules=dict(t=m))))
    return str(p)


def test_netsim_counter(tmp_path):
    nl = netsim.GateNetlist(tiny_netlist(tmp_path), 't')
    assert nl.n_gates == 7 and len(nl.dffs) == 2 and nl.reg_bits('q') == [4, 5]
    tr = nl.run({'sig': 1}, 5)
    assert [o['y'] for o in tr] == [1, 0, 0, 0, 1]                # q = 2, 3, 0, 1, 2
    assert [o['z'] for o in tr] == [2, 3, 0, 1, 2]
    tr = nl.run({'sig': 0}, 3, flips={1: [4]})                      # q = 2, (2 ^ 1 = 3 held), 3
    assert [o['z'] for o in tr] == [2, 2, 2] and [o['y'] for o in tr] == [1, 0, 0]


def test_netsim_rejects_unsupported_cells(tmp_path):
    p = tmp_path / 'bad.json'
    p.write_text(json.dumps(dict(modules=dict(t=dict(ports={}, netnames={}, cells={
        'f': dict(type='$_DFF_PN0_', connections=dict(C=[2], D=[3], Q=[4], R=[5]))})))))
    with pytest.raises(netsim.NetsimError):
        netsim.GateNetlist(str(p), 't')


def test_read_vectors_round_trip():
    sc = netsim.read_vectors(os.path.join(HERE, 'vectors', 'd_trip.vec'))
    v = BY_NAME['d_trip']
    assert sc[0]['sig'] == 0xC3 and sc[0]['goal'][v.cfg.cycles_to_word()] == 0x96
    assert len(sc[0]['goal']) == v.cycles + 2


@pytest.fixture
def fake_root(tmp_path):
    """A stand-in repository whose glitchsat.py writes a fixed result (exercises the runner's plumbing only)."""
    (tmp_path / 'scripts').mkdir()
    g = tmp_path / 'scripts' / 'glitchsat.py'
    g.write_text('''import json, sys
a = sys.argv
k = int(a[a.index('--k') + 1]); out = a[a.index('--out') + 1]
d = dict(verdict='ATTACK_FOUND' if k >= 2 else 'NO_ATTACK_UP_TO_BOUND', runtime_s=dict(solve_and_minimize=0.1),
         honest_key_boots_fault_free=True, netlist=dict(gates=1, flops=1))
if k >= 2:
    d.update(min_faults=2, faults=[dict(net='u_core.st[0]', cycle=3), dict(net='g', cycle=4)])
json.dump(d, open(out, 'w'))
''')
    return str(tmp_path)


def test_solver_call_and_summary(fake_root, tmp_path):
    v = BY_NAME['d_trip']
    rows = [run_glitchsat.solve(fake_root, v, 'x.json', k, str(tmp_path / f'r{k}.json'), 5) for k in (1, 2)]
    assert rows[0]['verdict'] == 'NO_ATTACK_UP_TO_BOUND' and rows[1]['min_faults'] == 2
    assert '--goal-value 0x96' in rows[0]['command'] and '--key 0xc3' in rows[0]['command']
    rec = dict(name='d_trip', model_register_bits_in_goal_cone=v.flop_bits(), flows=dict(plain=dict(
        synth=dict(exit=0), gates=123, flops=v.flop_bits(), replay=dict(ok=True), k=rows + [
            dict(k=3, verdict='ATTACK_FOUND', min_faults=2, implied=True)])))
    md = run_glitchsat.summary_md([rec], ['plain'], 3)
    assert '| d_trip | plain | 123 |' in md and 'attack, min 2 (implied)' in md and 'no attack (0.1 s)' in md
    p = studio.panel([rec])
    card = next(c for c in p['cards'] if c['name'] == 'd_trip')
    assert card['status'] == 'MEASURED' and card['results']['plain']['gates'] == 123
    assert [x['verdict'] for x in card['results']['plain']['by_k']] == ['NO_ATTACK_UP_TO_BOUND', 'ATTACK_FOUND', 'ATTACK_FOUND']
    assert card['results']['opt']['by_k'][0]['verdict'] == 'NOT_RUN'


def test_solver_error_is_never_no_attack(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts' / 'glitchsat.py').write_text('import sys; sys.exit(2)\n')
    row = run_glitchsat.solve(str(tmp_path), BY_NAME['d_single'], 'x.json', 1, str(tmp_path / 'o.json'), 5)
    assert row['verdict'] == 'UNKNOWN'
