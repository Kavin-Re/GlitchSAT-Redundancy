#!/usr/bin/env python3
"""Mutation check: break the V2 countermeasure (share a net between redundant copies) and show glitchsat notices:
a mutant is CAUGHT if its minimum attack cost drops below the unmutated design's (same synthesis flow, same bound)."""
import json, os, random, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
import glitchsat as g
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUT = {
 'share_c1_with_c0': ("cmp8 c1(.a(sig), .m(m1));", "assign m1 = m0; /* MUTANT: copy 1 shares copy 0's result net */"),
 'share_c2_with_c1': ("cmp8 c2(.a(sig), .m(m2));", "assign m2 = m1; /* MUTANT: copy 2 shares copy 1's result net */"),
 'single_decision_net': ("wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0};", "wire [7:0] sel = {8{m0 & m1 & m2}}; /* MUTANT: one AND decides all bits */"),
}
ap = argparse.ArgumentParser(); ap.add_argument('--seed', type=int, default=1); ap.add_argument('--all', action='store_true')
ap.add_argument('--k', type=int, default=3); ap.add_argument('--cycles', type=int, default=6); a = ap.parse_args()
src = open(os.path.join(ROOT, 'rtl/v2.v')).read()
os.makedirs(os.path.join(ROOT, 'results/mutants'), exist_ok=True)
base = g.run_check(os.path.join(ROOT, 'rtl/v2.v'), 'v2', a.k, a.cycles, os.path.join(ROOT, 'results/mutants/baseline_v2.json'))
bmin = base.get('min_faults', None)
names = sorted(MUT) if a.all else [random.Random(a.seed).choice(sorted(MUT))]
rows = []
for n in names:
    old, new = MUT[n]; assert old in src, n
    p = os.path.join(ROOT, f'results/mutants/v2_{n}.v'); open(p, 'w').write(src.replace(old, new))
    r = g.run_check(p, 'v2', a.k, a.cycles, os.path.join(ROOT, f'results/mutants/v2_{n}.json'), workdir=os.path.join(ROOT, 'results/mutants/work'))
    mm = r.get('min_faults', None)
    rows.append(dict(mutant=n, baseline_min_faults=bmin, mutant_min_faults=mm, verdict=r['verdict'], caught=(mm is not None and (bmin is None or mm < bmin)),
                     explanation=r.get('explanation', {}).get('summary'), label='MEASURED', bound=dict(k=a.k, cycles=a.cycles)))
    print({k: v for k, v in rows[-1].items() if k != 'explanation'})
json.dump(dict(seed=a.seed, all=a.all, baseline_min_faults=bmin, rows=rows), open(os.path.join(ROOT, 'results/mutation_summary.json'), 'w'), indent=2)

# ---- netlist-level mutants on the spike V2 netlist (baseline min cost 3): rewire consumers of one copy's result to another copy's net
import copy
sp = json.load(open(os.path.join(ROOT, 'reference/spike_netlists/v2.json')))
bits = {n: x['bits'][0] for n, x in sp['modules']['v2']['netlists' if False else 'netnames'].items() if n in ('c0.m', 'c1.m', 'c2.m')}
NM = {'netlist_share_c1_with_c0': ('c1.m', 'c0.m'), 'netlist_share_c2_with_c1': ('c2.m', 'c1.m')}
nrows = []
bn = g.Netlist(os.path.join(ROOT, 'reference/spike_netlists/v2.json'), 'v2')
vb, ib, rb = g.solve(bn, a.cycles, a.k)
bmin2 = len(rb['faults']) if rb else None
for n, (dead, live) in NM.items():
    j = copy.deepcopy(sp)
    for c in j['modules']['v2']['cells'].values():
        c['connections'] = {pn: [bits[live] if x == bits[dead] else x for x in v] if c['port_directions'].get(pn) == 'input' else v
                            for pn, v in c['connections'].items()}
    pj = os.path.join(ROOT, f'results/mutants/v2_{n}.json'); json.dump(j, open(pj, 'w'))
    r = g.run_check(pj, 'v2', a.k, a.cycles, os.path.join(ROOT, f'results/mutants/v2_{n}_result.json'))
    mm = r.get('min_faults')
    nrows.append(dict(mutant=n, baseline_min_faults=bmin2, mutant_min_faults=mm, verdict=r['verdict'], caught=(mm is not None and (bmin2 is None or mm < bmin2)),
                      explanation=r.get('explanation', {}).get('summary'), label='MEASURED', bound=dict(k=a.k, cycles=a.cycles)))
    print({k: v for k, v in nrows[-1].items() if k != 'explanation'})
json.dump(dict(seed=a.seed, rtl_level=dict(baseline_min_faults=bmin, rows=rows), netlist_level_on_spike_netlist=dict(baseline_min_faults=bmin2, rows=nrows)),
          open(os.path.join(ROOT, 'results/mutation_summary.json'), 'w'), indent=2)
