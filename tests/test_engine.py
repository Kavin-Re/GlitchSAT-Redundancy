import json, os, sys, subprocess
import pytest
pytest.importorskip('z3', reason='z3-solver is not installed: pip install z3-solver')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g, replay

def check(d, k, N=6, tmp=None):
    out = os.path.join(str(tmp), f'{d}_k{k}.json')
    return g.run_check(os.path.join(ROOT, f'rtl/{d}.v'), d, k, N, out, workdir=os.path.join(str(tmp), 'w')), out

@pytest.mark.parametrize('d', ['v0', 'v1', 'v2'])
def test_k0_unsat_and_known_key_boots(d, tmp_path):
    r, _ = check(d, 0, tmp=tmp_path)
    assert r['verdict'] == 'NO_ATTACK_UP_TO_BOUND'          # no fault, wrong key never boots
    assert r['honest_key_boots_fault_free'] is True          # legitimate key 0xC3 reaches boot word 0x96
    assert 'BOUNDED, NOT UNBOUNDED' in r['note']

def test_v0_v1_one_fault_breaks(tmp_path):
    for d in ('v0', 'v1'):
        r, _ = check(d, 1, tmp=tmp_path)
        assert r['verdict'] == 'ATTACK_FOUND' and r['min_faults'] == 1

def test_v1_weak_point_is_ok_net(tmp_path):
    r, _ = check('v1', 1, tmp=tmp_path)
    assert r['faults'][0]['net'] == 'ok'
    assert 'SINGLE POINT OF FAILURE' in r['explanation']['summary'] and '`ok`' in r['explanation']['summary']

@pytest.mark.parametrize('d', ['v0', 'v1'])
def test_replay_agrees_with_solver(d, tmp_path):
    r, out = check(d, 1, tmp=tmp_path)
    res = replay.replay(out, str(tmp_path / 'tb'))
    assert res['agrees_with_solver'] and res['faulted']['goal_hit_cycle'] >= 0 and res['faultfree']['goal_hit_cycle'] == -1

def test_spike_v2_netlist_unsat_le2_sat_3():
    nl = g.Netlist(os.path.join(ROOT, 'reference/spike_netlists/v2.json'), 'v2')
    assert g.solve(nl, 6, 2)[0] == 'NO_ATTACK_UP_TO_BOUND'
    v, _, res = g.solve(nl, 6, 3)
    assert v == 'ATTACK_FOUND' and len(res['faults']) == 3

def test_reduction_preserves_verdict():
    nl = g.Netlist(os.path.join(ROOT, 'reference/spike_netlists/v1.json'), 'v1')
    assert {g.solve(nl, 5, 1, reduce=r)[0] for r in ('none', 'coi', 'full')} == {'ATTACK_FOUND'}
    nl2 = g.Netlist(os.path.join(ROOT, 'reference/spike_netlists/v2.json'), 'v2')
    assert {g.solve(nl2, 4, 2, reduce=r)[0] for r in ('none', 'coi', 'full')} == {'NO_ATTACK_UP_TO_BOUND'}

def test_mutation_detected():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/mutate.py'), '--all'], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    s = json.load(open(os.path.join(ROOT, 'results/mutation_summary.json')))
    assert all(r['caught'] for r in s['netlist_level_on_spike_netlist']['rows'])
    assert any(r['caught'] for r in s['rtl_level']['rows'])
