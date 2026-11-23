#!/usr/bin/env python3
"""AES cipher control FSM, sparse state encoding (the question of SYNFI Table 4, asked with GlitchSAT's own model).

Netlist: SYNFI's examples/aes_cipher_control_fsm (Yosys + Nangate45, OpenTitan 0975212). State encodings are read
from that OpenTitan commit (ot_097521/hw/ip/aes/rtl/aes_cipher_control_fsm.sv; minimum Hamming distance 3).

For every ordered pair (S, Y) of valid states (ERROR excluded as a target): the FSM starts in S (state flops set
to S, the other flop at its reset value), reset inactive, every other input free in every cycle. Goal: within
N = 2 cycles the state register shows Y in some cycle t while alert_o stayed 0 in cycles 0..t. Fault budget k.
  k = 0 satisfiable  -> Y is a legal successor of S (or S itself): not an attack, reported as 'legal'.
  otherwise          -> minimum number of single-cycle bit flips, for two site sets:
       'state_flops' : flips of the 6 state-register outputs only (what SYNFI Table 4 injects into),
       'all'         : any Nangate cell output or flop output of the module.
Options: --cycles N (default 2), --quiet end (alert must stay 0 in every cycle of the run, not only up to t).
Bounded (N cycles, k <= kmax) and modelled. Writes results/fsm_state_<cfg><tag>.json."""
import json, os, re, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import seq_model as sq, nangate as ng   # noqa

NETLIST = 'synfi/examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json'
TOP = 'aes_cipher_control_fsm'
RTL = 'ot_097521/hw/ip/aes/rtl/aes_cipher_control_fsm.sv'


def encodings():
    txt = open(os.path.join(REAL, RTL)).read()
    enc = {}
    for name, bits in re.findall(r"^\s*(IDLE|INIT|ROUND|FINISH|PRNG_RESEED|CLEAR_S|CLEAR_KD|ERROR)\s*=\s*6'b([01]{6})", txt, re.M):
        enc[name] = int(bits, 2)
    assert len(enc) == 8, enc
    return enc


CONFIGS = {
    # single FSM instance (SYNFI examples/aes_cipher_control_fsm)
    'single': dict(netlist=NETLIST, top=TOP, state_nets=['u_state_regs.state_o'], kmax=4, pairs=None),
    # three-rail FSM (SYNFI examples/aes_cipher_control_rnd_ctr: three aes_cipher_control_fsm instances)
    'multirail': dict(netlist='synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json',
                      top='aes_cipher_control',
                      state_nets=[f'gen_fsm[{i}].gen_fsm_{pn}.u_aes_cipher_control_fsm_i.u_aes_cipher_control_fsm.aes_cipher_ctrl_cs'
                                  for i, pn in ((0, 'p'), (1, 'p'), (2, 'n'))], kmax=5, pairs=None),
}


def state_flops(doc, top, nets):
    m = doc['modules'][top]
    q2cell = {}
    for cn, c in m['cells'].items():
        if c['type'] in ng.FLOP_PINS:
            q2cell[c['connections']['Q'][0]] = cn
    groups = [m['netnames'][n]['bits'] for n in nets]
    return [[q2cell[b] for b in bits] for bits in groups], groups


def run(cfg='single', N=2, backend='auto', only_pairs=None, quiet='t', starts=None, settle=0):
    C = CONFIGS[cfg]
    kmax = C['kmax']
    lib = ng.load_cell_lib()
    doc = json.load(open(os.path.join(REAL, C['netlist'])))
    top = C['top']
    enc = encodings()
    cellg, qg = state_flops(doc, top, C['state_nets'])
    allcells = {c for g in cellg for c in g}
    alert = doc['modules'][top]['ports']['alert_o']['bits'][0]
    rows = []
    t0 = time.time()
    for S, sv in enc.items():
        if S == 'ERROR' or (starts and S not in starts):
            continue
        for Y, yv in enc.items():
            if Y in ('ERROR', S):
                continue
            if only_pairs and (S, Y) not in only_pairs:
                continue
            row = dict(start=S, target=Y, hamming=bin(sv ^ yv).count('1'))
            for label, filt in (('state_flops', lambda n, s: s['cell'] in allcells and s['pin'] == 'Q'), ('all', None)):
                init = {c: (sv >> i) & 1 for cells in cellg for i, c in enumerate(cells)}
                m = sq.SeqModel(doc, top, N, lib=lib, init=init, site_filter=filt)

                def goal(mm, yv=yv):
                    hits = []
                    for t in range(N - settle):
                        ok = mm.all_of([mm.eq_const(t, qbits, yv) for qbits in qg])
                        silent = mm.all_of([-mm.lits[u][alert] for u in range(t + 1 if quiet == 't' else N)])
                        hits.append(mm.e.g_and(ok, silent))
                    return mm.any_of(hits)

                def check(tr, yv=yv):
                    for t in range(N - settle):
                        if all(sum(tr[t][b] << i for i, b in enumerate(qbits)) == yv for qbits in qg) and \
                                all(tr[u][alert] == 0 for u in range(t + 1 if quiet == 't' else N)):
                            return True
                    return False
                m.add_goal(goal)
                m.goal_check = check
                r = m.min_faults(kmax, backend=backend)
                ent = dict(min_faults=r['min_faults'], verdict=r['verdict'], sweep=r['sweep'], sites=len(m.sites),
                           cnf=m.e.stats(), build_s=round(m.build_s, 3))
                if r['min_faults'] == 0:
                    ent['verdict'] = 'legal'
                if r.get('witness'):
                    ent['witness'] = [dict(cycle=f['cycle'], cell=f['cell'], type=f['cell_type'], pin=f['pin'], net=f['name'])
                                      for f in r['witness']['flips']]
                    ent['replayed_on_reference'] = r['witness'].get('replayed', False)
                row[label] = ent
            rows.append(row)
            print(S, '->', Y, 'HD', row['hamming'], 'state-flops:', row['state_flops']['min_faults'],
                  'all:', row['all']['min_faults'], flush=True)
    attacks = [r for r in rows if r['state_flops']['verdict'] != 'legal']
    summ = dict(
        pairs=len(rows), legal_pairs=sum(1 for r in rows if r['state_flops']['verdict'] == 'legal'),
        min_state_flops=min((r['state_flops']['min_faults'] for r in attacks if r['state_flops']['min_faults'] is not None), default=None),
        min_all=min((r['all']['min_faults'] for r in attacks if r['all']['min_faults'] is not None), default=None),
        state_flops_le_hamming=all(r['state_flops']['min_faults'] <= r['hamming'] for r in attacks
                                   if r['state_flops']['min_faults'] is not None),
        runtime_s=round(time.time() - t0, 1))
    return dict(experiment='aes_fsm_sparse_state_' + cfg, netlist=C['netlist'], top=top, state_nets=C['state_nets'], rtl_encodings=RTL, encodings={k: format(v, '06b') for k, v in enc.items()},
                cycles=N, kmax=kmax, alert_quiet=('cycles 0..t' if quiet == 't' else f'all cycles 0..{N - 1}'), backend=backend,
                hit_cycles=f'0..{N - 1 - settle}', model='GlitchSAT bit flips (single cycle) on Nangate cell outputs / flop Q; inputs free each cycle; reset inactive',
                summary=summ, rows=rows)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cfg', choices=sorted(CONFIGS))
    ap.add_argument('--pairs', help='e.g. ROUND>FINISH,IDLE>FINISH')
    ap.add_argument('--cycles', type=int, default=2)
    ap.add_argument('--quiet', choices=['t', 'end'], default='t', help="alert must stay 0 up to the hit cycle, or to the end")
    ap.add_argument('--backend', default='auto')
    ap.add_argument('--tag', default='')
    ap.add_argument('--starts', help='comma list of start states (default all)')
    ap.add_argument('--settle', type=int, default=0, help='goal must be hit at least this many cycles before the end')
    a = ap.parse_args()
    pairs = {tuple(p.split('>')) for p in a.pairs.split(',')} if a.pairs else None
    out = run(a.cfg, N=a.cycles, backend=a.backend, only_pairs=pairs, quiet=a.quiet,
              starts=set(a.starts.split(',')) if a.starts else None, settle=a.settle)
    os.makedirs(os.path.join(REAL, 'results'), exist_ok=True)
    json.dump(out, open(os.path.join(REAL, 'results', f'fsm_state_{a.cfg}{a.tag}.json'), 'w'), indent=1)
    print(json.dumps(out['summary']))
