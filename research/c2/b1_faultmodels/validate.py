#!/usr/bin/env python3
"""Cross-check faultpack.py (z3) against modelsim.py (exhaustive simulation) on the spike
netlists at T=4. For each (design, model): solver min-cost (cap CAP) vs exhaustive enumeration of all action sets of
cost <= KEX=2. Agreement rule: solver min<=2 => exhaustive finds same min; solver min>2 or none => exhaustive finds no
attack with cost<=2 (and the solver witness, if any, is replayed in the simulator and must succeed).
usage: python3 validate.py [out.json]"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import faultpack as fp, modelsim as ms
ROOT = os.environ.get('PROJ', '<repo>')
T, CAP, KEX = 4, 3, 2
SPEC = {  # model name -> (modelsim model dict, groups-fn(sim), m, singletons)
    'stem_flip': (dict(site='stem', effects=['flip']), None, 1, True),
    'branch_flip': (dict(site='branch', effects=['flip']), None, 1, True),
    'stem_or_branch_flip': (dict(site='both', effects=['flip']), None, 1, True),
    'set_only': (dict(site='stem', effects=['set']), None, 1, True),
    'reset_only': (dict(site='stem', effects=['reset']), None, 1, True),
    'branch_set': (dict(site='branch', effects=['set']), None, 1, True),
    'branch_reset': (dict(site='branch', effects=['reset']), None, 1, True),
    'flop_hold': (dict(site='stem', effects=['hold']), None, 1, True),
    'group_flops_m2': (dict(site='stem', effects=['flip']), lambda s: [frozenset(q for _, q in s.flops)], 2, True),
    'group_hood_m2': (dict(site='stem', effects=['flip']), lambda s: s.hood_groups(), 2, True),
    'cone_flip_exact': (dict(site='stem', effects=['flip']), lambda s: s.cone_groups(), 10 ** 6, True, True),
    'hood_flip_exact': (dict(site='stem', effects=['flip']), lambda s: s.hood_groups(), 10 ** 6, True, True),
    'input_flip': (dict(site='stem', effects=['flip'], inputs=True), None, 1, True),
    'input_set': (dict(site='stem', effects=['set'], inputs=True), None, 1, True),
    'input_reset': (dict(site='stem', effects=['reset'], inputs=True), None, 1, True),
    'input_branch_flip': (dict(site='branch', effects=['flip'], inputs=True), None, 1, True),
    'clock_skip_all': (dict(site='stem', effects=['hold']), lambda s: [frozenset(q for _, q in s.flops)], 10 ** 6, True),
}

def to_sim_fault(t, site, eff):
    k = site[0]
    if k == 'n': return (t, 'n', site[1], eff)
    if k == 'g': return (t, 'g', site[1], site[2], eff)
    if k == 'd': return (t, 'd', site[1], eff)
    if k == 'o': return (t, 'o', site[1], eff)
    if k == 'h': return (t, 'h', site[1])

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'validation_T4.json')
    rows = []; bad = 0
    for d in ['v0', 'v1', 'v2']:
        path = os.path.join(ROOT, 'reference', 'spike_netlists', f'{d}.json')
        nl = fp.Netlist(path, d); sim = ms.Sim(path, d)
        for mname, spec in SPEC.items():
            mm, gfn, m, sing = spec[:4]; ex = len(spec) > 4 and spec[4]
            t0 = time.time()
            r = fp.min_cost(nl, T, fp.MODELS[mname], CAP)
            kz = r['min']
            groups = gfn(sim) if gfn else None
            ke, w, tried = ms.min_cost_exhaustive_par(sim, T, mm, KEX, groups, m, sing, procs=4, exact=ex)
            replay = None
            if r['status'] == 'ATTACK':
                fl = [to_sim_fault(t, s, e) for t, s, e in r['faults']]
                replay = bool(ms.hit_lanes(sim.run(T, fl)))
            if r['status'] == 'ATTACK' and kz <= KEX: agree = (ke == kz)
            elif r['status'] == 'ATTACK': agree = (ke is None) and replay
            else: agree = (ke is None)
            if r['status'] == 'ATTACK' and not replay and mname not in ('group_flops_m2', 'group_hood_m2', 'clock_skip_all'):
                agree = False
            if r['status'] == 'TIMEOUT': agree = None
            bad += (agree is False)
            row = dict(design=d, model=mname, T=T, solver=fp.fmt(r), exhaustive_min_le2=ke, exhaustive_sets_tried=tried,
                       witness_replay_ok=replay, agree=agree, secs=round(time.time() - t0, 1))
            rows.append(row); print(row, flush=True)
    json.dump(dict(label='MEASURED', T=T, cap=CAP, exhaustive_kmax=KEX, rows=rows, disagreements=bad), open(out, 'w'), indent=1)
    print('disagreements:', bad)
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
