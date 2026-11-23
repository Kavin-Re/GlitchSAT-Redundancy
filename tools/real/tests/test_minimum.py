"""Minimum-fault search == brute force over check(); witnesses confirmed; sequential model == reference replay."""
import itertools, json, os
import pytest
from conftest import load, spec
from glitchsat_real import synfi_model as sm, seq_model as sq, nangate as ng


@pytest.mark.parametrize('eid', ['E1', 'E2'])
@pytest.mark.parametrize('model', ['synfi', 'flip'])
def test_min_equals_bruteforce(eid, model, lib):
    net, fm = spec(eid)
    doc, top = load(net)
    m = sm.Model(doc, top, fm, lib=lib, model=model)
    opts = list(m.sel)
    brute = None
    for k in (0, 1, 2):
        for combo in itertools.combinations(opts, k):
            if len({l for l, _ in combo}) < k:
                continue
            if m.check(list(combo)):
                brute = k; break
        if brute is not None:
            break
    m2 = sm.Model(doc, top, fm, lib=lib, model=model)
    r = m2.min_faults(3)
    assert r['min_faults'] == brute
    assert m.check([(w['location'], w['option']) for w in r['witness']])


def test_all_min_attacks_complete_E2(lib):
    net, fm = spec('E2')
    doc, top = load(net)
    m = sm.Model(doc, top, fm, lib=lib)
    single = {l for (l, o) in m.sel if m.check([(l, o)])}
    m2 = sm.Model(doc, top, fm, lib=lib)
    att, stop = m2.all_min_attacks(1)
    assert stop == 'exhausted'
    assert {w[0]['location'] for w in att} == single


def test_seq_state_flops_equals_bruteforce(lib):
    """FSM IDLE -> FINISH with state-register flips only: SAT minimum == exhaustive search on the reference
    simulator (2 cycles, 12 candidate flip sites, all subsets of size <= 3, inputs from the SAT witness are not
    reused: the brute force fixes all free inputs to 0, so it gives an upper bound that must match here)."""
    doc, top = load('aes_fsm')
    m0 = doc['modules'][top]
    q2c = {c['connections']['Q'][0]: cn for cn, c in m0['cells'].items() if c['type'] in ng.FLOP_PINS}
    qbits = m0['netnames']['u_state_regs.state_o']['bits']
    cells = [q2c[b] for b in qbits]
    IDLE, FINISH = 0b001001, 0b010000
    alert = m0['ports']['alert_o']['bits'][0]
    init = {c: (IDLE >> i) & 1 for i, c in enumerate(cells)}
    m = sq.SeqModel(doc, top, 2, lib=lib, init=init, site_filter=lambda n, s: s['cell'] in cells and s['pin'] == 'Q')
    def goal(mm):
        return mm.any_of([mm.e.g_and(mm.eq_const(t, qbits, FINISH), mm.all_of([-mm.lits[u][alert] for u in range(t + 1)])) for t in range(2)])
    m.add_goal(goal)
    r = m.min_faults(4)
    assert r['min_faults'] == 3                      # Hamming distance IDLE/FINISH
    from glitchsat_real import refsim
    ref = refsim.RefSim(doc, top, lib)
    sites = [(t, b) for t in range(2) for b in qbits]
    ins = [{b: 0 for p, x in m0['ports'].items() if x['direction'] == 'input' for b in x['bits'] if isinstance(b, int)} for _ in range(2)]
    for i in ins:
        i[m0['ports']['rst_ni']['bits'][0]] = 1
    best = None
    for k in range(0, 4):
        for combo in itertools.combinations(sites, k):
            tr = sq.ref_run_with_flips(ref, 2, ins, dict(init), {x: 1 for x in combo})
            if any(sum(tr[t][b] << i for i, b in enumerate(qbits)) == FINISH and all(tr[u][alert] == 0 for u in range(t + 1)) for t in range(2)):
                best = k; break
        if best is not None:
            break
    assert best == 3
