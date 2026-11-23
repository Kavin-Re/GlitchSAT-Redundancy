#!/usr/bin/env python3
"""Cross-check on the OpenTitan Nangate45 netlists: the minimum from this layer against the sequential model of
the real-designs work (glitchsat_real.seq_model: its own unrolling and encoder, no site reduction, no modules).

Needs $GLITCHSAT_REAL (folder with glitchsat_real/, synfi/examples/ and runs/adapted/). Writes
results/xcheck_real.json. Same questions as the `real` set of bench_scale.py at their shortest horizon."""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.environ.get('GLITCHSAT_REAL') or os.path.normpath(os.path.join(HERE, '..', '..', '..', 'real'))
sys.path.insert(0, REAL); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
os.environ.setdefault('GLITCHSAT_ROOT', os.path.normpath(os.path.join(HERE, '..', '..', '..')))
from glitchsat_real import seq_model as sq
from gscale import spec, search
A = os.path.join(REAL, 'runs', 'adapted')
SY = os.path.join(REAL, 'synfi', 'examples')
cases = [('aes_fsm', SY + '/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json', 'aes_cipher_control_fsm', 4, 3, 'out_valid_o', 1, 'alert_o', {'in_valid_i': 0}),
         ('aes_ctrl', SY + '/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json', 'aes_cipher_control', 3, 4, 'out_valid_o', 3, 'alert_o', {'in_valid_i': 4}),
         ('ibex', SY + '/ibex/netlist_ibex_if_stage.json', 'ibex_if_stage', 3, 3, 'instr_addr_o', 0x40400, 'pc_mismatch_alert_o', {'pc_set_i': 0, 'nt_branch_mispredict_i': 0})]
out = []
for stem, orig, top, N, k, gport, gval, qport, fix in cases:
    P = spec.load_problem(A + '/%s.json' % stem, top, N, goal=['%s=%d' % (gport, gval)], quiet=['%s=0' % qport],
                          fix=['%s=%d' % kv for kv in fix.items()], inputs='cycle', no_key=True, sites_meta=A + '/%s.meta.json' % stem)
    r = search.analyse(P, k, modules='none', backend='py')
    mine = r['hi'] if r['status'] == 'EXACT' else None
    doc = json.load(open(orig))
    m0 = sq.SeqModel(doc, top, N)
    ports = m0.nl.ports
    fixed = {}
    for p, v in fix.items():
        for i, b in enumerate(ports[p]['bits']): fixed[b] = (v >> i) & 1
    m = sq.SeqModel(doc, top, N, fixed=fixed)
    gb = ports[gport]['bits']; qb = ports[qport]['bits']
    def eq(M, t, nets, value):
        ls = []
        for i, b in enumerate(nets):
            want = (value >> i) & 1
            if b in ('0', '1'): ls.append(sq.T_ if int(b) == want else sq.F_)
            else: ls.append(M.lits[t][b] if want else -M.lits[t][b])
        return M.all_of(ls)
    def goal(M):
        hits = []
        for t in range(N):
            hits.append(M.all_of([eq(M, t, gb, gval)] + [eq(M, u, qb, 0) for u in range(t + 1)]))
        return M.any_of(hits)
    m.add_goal(goal)
    m.replay = lambda w: None       # its replay needs a goal_check hook; the answer is compared, not the witness
    rr = m.min_faults(k, backend='py')
    out.append(dict(design=stem, cycles=N, k=k, gscale=mine, seq_model=rr.get('min_faults'), sites_same=len(m.sites) == len(P.sites)))
    print(out[-1], flush=True)
json.dump(out, open(os.path.join(HERE, 'results', 'xcheck_real.json'), 'w'), indent=1)
sys.exit(0 if all(o['gscale'] == o['seq_model'] for o in out) else 1)
