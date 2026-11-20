#!/usr/bin/env python3
# Part 2: slack-restricted fault sites.  usage: run_part2.py tag top
# Sites = cell outputs (cell-output flips) whose worst setup slack (OpenSTA, ESTIMATED) <= threshold.
import sys, re, json
sys.path.insert(0, '/home/user/project/research/c2/el2_engineering')
import mapped_adapter as A
tag, top = sys.argv[1:3]
lib = A.load_lib('/tmp/work_el2/lib/sky130_fd_sc_hd__tt_025C_1v80.lib')
vp = f'/tmp/work_el2/lay/out/{tag}_net.v'
N = A.build_netlist(vp, top, lib, {'boot_word': 0xF0} if top != 'v0' else {})
log = open(f'/tmp/work_el2/lay/out/{tag}_openroad.log').read()
cs = {}
for m in re.finditer(r'^CELLSLACK (\S+) (\S+) (\S+) (\S+) (\S+)$', log, flags=re.M):
    cs[m.group(1)] = float(m.group(4))
dsl = {}
for m in re.finditer(r'^(\S+)/D \(sky130_fd_sc_hd__dfxtp_1\)\s+\S+\s+\S+\s+(\S+) \(', log.split('EL2_ENDPOINTS_BEGIN')[1].split('EL2_ENDPOINTS_MIN')[0], flags=re.M):
    dsl[m.group(1)] = float(m.group(2))
out = {}
def sweep(name, slacks):   # slacks: cell -> slack ns ; nested sets by ascending slack
    order = sorted(slacks, key=lambda c: slacks[c])
    rows = []; prev = None
    for n in range(1, len(order) + 1):
        if n < len(order) and abs(slacks[order[n]] - slacks[order[n-1]]) < 1e-9: continue
        allowed = {N.cellinfo[c]['out'] for c in order[:n] if c in N.cellinfo}
        v, r, dt = A.solve(N, 6, 3, allowed=allowed)
        rows.append(dict(n_sites=n, slack_le_ns=round(slacks[order[n-1]], 3), verdict=v, min_k=len(r['faults']) if r else None,
                         faults=[(t, N.names.get(b, str(b))) for t, b in r['faults']] if r else [], wall=round(dt, 2)))
    return rows
out['all_cells_by_slack'] = sweep('cells', {c: s for c, s in cs.items() if c in N.cellinfo})
out['flops_only_by_Dslack'] = sweep('flops', {c: s for c, s in dsl.items() if c in N.cellinfo})
out['cell_slacks'] = {c: round(s, 3) for c, s in sorted(cs.items(), key=lambda kv: kv[1])}
out['flop_D_slacks'] = {c: round(s, 3) for c, s in sorted(dsl.items(), key=lambda kv: kv[1])}
json.dump(out, open(f'/home/user/project/research/c2/el2_engineering/data_part2_{tag}.json', 'w'), indent=1)
for k in ('all_cells_by_slack', 'flops_only_by_Dslack'):
    print(tag, k)
    for r in out[k]: print('  ', r['n_sites'], r['slack_le_ns'], r['verdict'][:9], r['min_k'], r['faults'])
