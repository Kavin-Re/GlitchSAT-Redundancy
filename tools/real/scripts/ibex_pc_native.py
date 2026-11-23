#!/usr/bin/env python3
"""Ibex fetch stage, whole netlist, sequential: GlitchSAT's own version of SYNFI Table 7 row 2 ("set the PC to
0x40400").

SYNFI analyses one combinational slice between branch_target_ex_i and pc_if_o, with every signal entering the slice
from elsewhere left free (its "side inputs"). Here the whole ibex_if_stage netlist (SYNFI's examples/ibex file,
adapted to GlitchSAT primitives) is unrolled for N cycles from reset, so every signal is computed by the real logic:
  * flops start at their reset value; rst_ni = 1 (reset released);
  * every PC source is pinned to 0: boot_addr_i, branch_target_ex_i, nt_branch_addr_i, csr_mepc_i, csr_depc_i,
    csr_mtvec_i (so the only legal PCs are small: 0x80 after boot, vector-table entries, the debug-module addresses
    of the netlist parameters, and +2/+4 increments within N cycles);
  * every other input (memory handshake and data, pc_set_i, pc_mux_i, exception selects, ...) is free in every cycle.
Goal: pc_if_o == 0x40400 in some cycle t < N. k = 0 must be impossible (checked). Fault model: single-cycle bit
flips of Nangate cell outputs and flop outputs, at most k in total. Bounded (N cycles). Writes results/ibex_pc_native.json.
"""
import json, os, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import seq_model as sq, nangate as ng   # noqa

NETLIST = 'synfi/examples/ibex/netlist_ibex_if_stage.json'
TOP = 'ibex_if_stage'
TARGET = 0x40400
PINNED = ['boot_addr_i', 'branch_target_ex_i', 'nt_branch_addr_i', 'csr_mepc_i', 'csr_depc_i', 'csr_mtvec_i']


def run(N, kmax, backend='auto', cap=200):
    lib = ng.load_cell_lib()
    doc = json.load(open(os.path.join(REAL, NETLIST)))
    ports = doc['modules'][TOP]['ports']
    fixed = {}
    for p in PINNED:
        for b in ports[p]['bits']:
            if isinstance(b, int):
                fixed[b] = 0
    pc = ports['pc_if_o']['bits']
    t0 = time.time()
    m = sq.SeqModel(doc, TOP, N, lib=lib, fixed=fixed)

    def lit_pc(mm, t):
        ls = []
        for i, b in enumerate(pc):
            want = (TARGET >> i) & 1
            if b in ('0', '1'):
                if int(b) != want:
                    return sq.F_
                continue
            ls.append(mm.lits[t][b] if want else -mm.lits[t][b])
        return mm.all_of(ls)
    m.add_goal(lambda mm: mm.any_of([lit_pc(mm, t) for t in range(N)]))

    def check(tr):
        for t in range(N):
            v = sum((int(b) if b in ('0', '1') else tr[t][b]) << i for i, b in enumerate(pc))
            if v == TARGET:
                return True
        return False
    m.goal_check = check
    r = m.min_faults(kmax, backend=backend)
    out = dict(cycles=N, kmax=kmax, sites=len(m.sites), cnf=m.e.stats(), build_s=round(m.build_s, 2),
               verdict=r['verdict'], min_faults=r['min_faults'], sweep=r['sweep'])
    if r.get('witness'):
        out['witness'] = [dict(cycle=f['cycle'], cell=f['cell'], type=f['cell_type'], pin=f['pin'], net=f['name'])
                          for f in r['witness']['flips']]
        out['replayed_on_reference'] = r['witness'].get('replayed', False)
        m2 = sq.SeqModel(doc, TOP, N, lib=lib, fixed=fixed)
        m2.add_goal(lambda mm: mm.any_of([lit_pc(mm, t) for t in range(N)]))
        m2.goal_check = check
        atts, stop = m2.all_min_attacks(r['min_faults'], backend=backend, cap=cap, timeout_s=5400)
        import collections
        cnt = collections.Counter((f['cell'], f['pin'], f['name']) for w in atts for f in w['flips'])
        cyc = collections.Counter(f['cycle'] for w in atts for f in w['flips'])
        out['surface'] = dict(attacks=len(atts), complete=stop == 'exhausted', stop=stop,
                              cycles=dict(sorted(cyc.items())),
                              hot_spots=[dict(cell=c, pin=p, net=n, attacks=k) for (c, p, n), k in cnt.most_common(15)],
                              first_attacks=[[dict(cycle=f['cycle'], net=f['name'], type=f['cell_type']) for f in w['flips']]
                                             for w in atts[:10]])
    out['runtime_s'] = round(time.time() - t0, 1)
    return out


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    kmax = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    backend = sys.argv[3] if len(sys.argv) > 3 else 'auto'
    cap = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    res = dict(experiment='ibex_pc_native', netlist=NETLIST, top=TOP, target=hex(TARGET), pinned_inputs=PINNED,
               model='GlitchSAT bit flips (single cycle) on Nangate cell outputs / flop Q; whole netlist; inputs free each cycle except the pinned PC sources; reset released',
               backend=backend, runs=[run(N, kmax, backend=backend, cap=cap)])
    os.makedirs(os.path.join(REAL, 'results'), exist_ok=True)
    json.dump(res, open(os.path.join(REAL, 'results', 'ibex_pc_native.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in res['runs'][0].items() if k not in ('surface',)}, indent=0)[:1500])
    if 'surface' in res['runs'][0]:
        print(json.dumps(res['runs'][0]['surface'])[:1500])
