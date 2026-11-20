#!/usr/bin/env python3
"""N5: reconcile the DA/REP 32 V2 netlists (research/c3/rep/rep_results.csv) with E2's 864-config grid
(research/c2/e2_variance/raw/matrix.csv). Mapping (checked against gen_rep.sh and matrix.py): REP flow plain/opt = E2 flow; REP ABC s0 = E2 default,
s1 = noMUX, s2 = fast, s4 = AND_OR; s3, s5, s6, s7 have no E2 level. REP build 033 = E2 apt0.33; 038 = E2 conda-formal0.38 (and conda-eda0.38, same git sha).
REP recipe = E2 order abc_then_flatten, merge nomerge, keep_on (RTL as written). usage: python3 grid_reconcile.py   (run from anywhere)"""
import csv, collections, os
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
E2 = list(csv.DictReader(open(f'{R}/c2/e2_variance/raw/matrix.csv'))); REP = list(csv.DictReader(open(f'{R}/c3/rep/rep_results.csv')))
v2 = [r for r in E2 if r['design'] == 'v2']; solved = [r for r in v2 if r['status'] == 'SOLVED']
print('E2 V2 configs', len(v2), 'solved', len(solved), 'min counts', dict(collections.Counter(r['min_flips'] for r in solved)), 'ENGINE_UNSUPPORTED', len(v2) - len(solved))
abcmap = {'s0': 'default', 's1': 'noMUX', 's2': 'fast', 's4': 'AND_OR'}; bmap = {'033': ['apt0.33'], '038': ['conda-formal0.38', 'conda-eda0.38']}
rep2 = [r for r in REP if r['netlist'].startswith('v2_')]
print('REP V2 netlists', len(rep2), 'unit min counts', dict(collections.Counter(r['rep_unit_cli'] for r in rep2)))
pairs = []; inside = set()
for r in rep2:
    _, fl, ver, s = r['netlist'].split('_')
    if s not in abcmap: continue
    inside.add(r['netlist'])
    for b in bmap[ver]:
        m = [x for x in v2 if x['build'] == b and x['flow'] == fl and x['order'] == 'abc_then_flatten' and x['abc'] == abcmap[s] and x['merge'] == 'nomerge' and x['keep'] == 'keep_on']
        assert len(m) == 1; pairs.append((r['netlist'], b, r['rep_unit_cli'], m[0]['min_flips'], r['gates'], m[0]['gates']))
print('REP V2 netlists with an E2 counterpart', len(inside), 'of', len(rep2), '; (REP netlist, E2 config) pairs', len(pairs),
      '; min flips agree', sum(p[2] == p[3] for p in pairs), '; gate count agree', sum(p[4] == p[5] for p in pairs))
print('REP min=3 netlists inside E2 grid:', sorted(r['netlist'] for r in rep2 if r['rep_unit_cli'] == '3' and r['netlist'] in inside),
      '; outside:', sorted(r['netlist'] for r in rep2 if r['rep_unit_cli'] == '3' and r['netlist'] not in inside))
print('REP min=2 inside/outside:', sum(1 for r in rep2 if r['rep_unit_cli'] == '2' and r['netlist'] in inside), '/', sum(1 for r in rep2 if r['rep_unit_cli'] == '2' and r['netlist'] not in inside))
sub = [x for x in v2 if x['order'] == 'abc_then_flatten' and x['merge'] == 'nomerge' and x['keep'] == 'keep_on' and x['abc'] in abcmap.values()]
print('E2 sub-grid with the REP recipe (4 shared ABC, 2 flows, 3 builds):', len(sub), dict(collections.Counter(x['min_flips'] for x in sub)))
rest = [x for x in solved if x not in sub]
print('E2 V2 solved configs NOT reachable by the REP recipe:', len(rest), dict(collections.Counter(x['min_flips'] for x in rest)))
print('E2 min=1 configs reachable by REP recipe family (order abc_then_flatten, nomerge, keep_on):',
      sum(1 for x in v2 if x['order'] == 'abc_then_flatten' and x['merge'] == 'nomerge' and x['keep'] == 'keep_on' and x['min_flips'] == '1'), '(all are abc -dff, a level REP does not have)')
