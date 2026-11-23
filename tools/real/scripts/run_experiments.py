#!/usr/bin/env python3
"""Reproduce SYNFI's published experiments on the real OpenTitan netlists with GlitchSAT, and go beyond them.

For every experiment (SYNFI fault specification + netlist from lowRISC/synfi examples/):
  published   the number printed in the SYNFI paper (cited: table and row), from ext/datasets/published_results.json
  synfi_rerun SYNFI's own code run here on the same files (runs/synfi_ref/*.json, scripts/run_all_synfi_reference.sh)
  glitchsat   (a) SYNFI-compatible model (same region, same gate-replacement fault options): exhaustive k = 1, exact
                  k = 2 counts, per-injection agreement with every SYNFI run;
              (b) minimum number of simultaneous faults (security margin) for the gate-replacement model and for
                  GlitchSAT's bit-flip model on the same locations;
              (c) every minimum-size attack (attack surface), with the cells and nets each one uses.
Writes results/experiments.json. Usage: run_experiments.py [E1 E2 ...] [--backend auto|py|dimacs:<bin>]
"""
import argparse, collections, itertools, json, os, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import synfi_model as sm, nangate as ng, engine   # noqa: E402

PUB = os.environ.get('GLITCHSAT_PUBLISHED') or os.path.join(os.path.dirname(REAL), 'ext', 'datasets', 'published_results.json')
AES_FSM = ('synfi/examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json', 'aes_cipher_control_fsm')
AES_CTRL = ('synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json', 'aes_cipher_control')
IBEX = ('synfi/examples/ibex/netlist_ibex_if_stage.json', 'ibex_if_stage')

EXPS = [
    dict(id='E1', title='AES round counter: change it arbitrarily (FE)', net=AES_FSM,
         spec='synfi/examples/aes_cipher_control_fsm/fault_model_aes_cipher_control_fsm_rnd_cntr.json',
         published=('1', 0), ks=[1], synfi_runs={1: 'aes_fsm_fe_s1'}),
    dict(id='E2', title='AES round counter: force it to 4 (FS)', net=AES_FSM,
         spec='synfi/examples/aes_cipher_control_fsm/fault_model_aes_cipher_control_fsm_rnd_cntr_target_value.json',
         published=('1', 1), ks=[1, 2], synfi_runs={1: 'aes_fsm_fs_s1', 2: 'aes_fsm_fs_s2'}),
    dict(id='E3', title='Protected round counter (3 FSM rails, up/down counters, error register) (FD)', net=AES_CTRL,
         spec='synfi/examples/aes_cipher_control_rnd_ctr/fault_model_aes_cipher_control_rnd_cntr.json',
         published=('1', 2), ks=[1, 2], synfi_runs={1: 'aes_ctrl_fd_s1', 2: 'aes_ctrl_fd_s2_l2000'},
         synfi_explicit='aes_ctrl_fd_s2_fl'),
    dict(id='E4', title='Ibex fetch stage: change the PC arbitrarily (FE)', net=IBEX,
         spec='synfi/examples/ibex/fault_model_ibex_if_stage_pc.json',
         published=('7', 0), ks=[1], synfi_runs={1: 'ibex_pc_fe_s1'}),
    dict(id='E5', title='Ibex fetch stage: set the PC to 0x40400 (FS)', net=IBEX,
         spec='synfi/examples/ibex/fault_model_ibex_if_stage_pc_target.json',
         published=('7', 1), ks=[1, 2], synfi_runs={1: 'ibex_pc_fs_s1', 2: 'ibex_pc_fs_s2_l2000'}),
]


def published(tab, row):
    d = json.load(open(PUB))
    src = next(s for s in d['sources'] if s['id'] == 'synfi_2022')
    t = next(t for t in src['tables'] if t['table'] == tab)
    r = dict(t['rows'][row])
    r.update(citation=src['citation'], where=f"Table {tab}, row {row + 1} ({t['caption']})", flow_note=src['flow_note'])
    return r


def seq_loc(m, loc):
    """SYNFI's comb/seq split: a fault is 'sequential' when the parent node of its location is a register."""
    L = m.locs[loc]
    return m.g.kind.get(L['node']) == 'flop'


def synfi_rerun(name, m):
    p = os.path.join(REAL, 'runs', 'synfi_ref', name + '.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    tuples = [tuple((f['location'], f['mapping']) for f in r['faults']) for r in d['results']]
    uniq = {}
    for t, r in zip(tuples, d['results']):
        uniq[t] = r['sat']
    agree = sum(1 for t, r in zip(tuples, d['results']) if m.check(list(t)) == r['sat'])
    k = d['simultaneous_faults']
    return dict(run=os.path.relpath(p, REAL), simultaneous_faults=k, limit=d.get('limit'),
                injections=len(tuples), injected_faults=len(tuples) * k, effective_injections=d['sat'],
                effective_percent=round(100.0 * d['sat'] / len(tuples), 2) if tuples else None,
                distinct_injections=len(uniq), distinct_effective=sum(uniq.values()),
                distinct_effective_percent=round(100.0 * sum(uniq.values()) / len(uniq), 2) if uniq else None,
                synfi_log=d['synfi_log_summary'], runtime_s=d['inject_s'] + d['parse_s'],
                solver='SYNFI code unmodified; Minisat22 replaced by the pure-Python CDCL (shims/), sequential',
                glitchsat_agrees_on=f'{agree}/{len(tuples)}')


def exhaustive_k1(m):
    t0 = time.time()
    eff = comb = seq = 0
    rows = []
    for (loc, opt) in m.sel:
        r = m.check([(loc, opt)])
        rows.append((loc, opt, r))
        if r:
            eff += 1
            if seq_loc(m, loc): seq += 1
            else: comb += 1
    n = len(m.sel)
    return dict(injections=n, effective=eff, effective_comb=comb, effective_seq=seq,
                effective_percent=round(100.0 * eff / n, 2) if n else None,
                comb_percent=round(100.0 * comb / n, 2) if n else None, seq_percent=round(100.0 * seq / n, 2) if n else None,
                runtime_s=round(time.time() - t0, 2)), rows


def exact_k2(m, k1_effective_locs, make_model, direct_limit=60000, cap=200000):
    """Exact count of effective 2-fault injections over all location pairs x option pairs (SYNFI's -s 2 space,
    distinct injections). Direct enumeration when small; otherwise (requires that no single fault is effective):
    enumerate effective location pairs with blocking clauses, then test every option pair of those."""
    t0 = time.time()
    locs = list(m.locs)
    nopt = {l: len(m.locs[l]['options']) for l in locs}
    total = 0
    s1 = sum(nopt.values()); s2 = sum(v * v for v in nopt.values())
    total = (s1 * s1 - s2) // 2
    if total <= direct_limit:
        eff = []
        for a, b in itertools.combinations(locs, 2):
            for oa in m.locs[a]['options']:
                for ob in m.locs[b]['options']:
                    if m.check([(a, oa), (b, ob)]):
                        eff.append(((a, oa), (b, ob)))
        return dict(method='direct', injections=total, effective=len(eff),
                    effective_percent=round(100.0 * len(eff) / total, 4), runtime_s=round(time.time() - t0, 2)), eff
    if k1_effective_locs:
        return dict(method='skipped', injections=total, note='single faults are effective; exact pair count needs '
                    'direct enumeration of all pairs, above the limit here'), None
    attacks, stop = make_model().all_min_attacks(2, cap=cap)    # separate instance: blocking clauses stay there
    pairs = sorted({tuple(sorted({x['location'] for x in w})) for w in attacks})
    eff = []
    for a, b in pairs:
        for oa in m.locs[a]['options']:
            for ob in m.locs[b]['options']:
                if m.check([(a, oa), (b, ob)]):
                    eff.append(((a, oa), (b, ob)))
    return dict(method='blocking', injections=total, effective=len(eff), effective_location_pairs=len(pairs),
                complete=(stop == 'exhausted'), stop=stop,
                effective_percent=round(100.0 * len(eff) / total, 4), runtime_s=round(time.time() - t0, 2)), eff


def synfi_entries(run):
    """SYNFI's fault-location list (with its repeated entries), rebuilt from its own k = 1 run: consecutive rows
    of one location form one entry; a location that comes back later is a repeated entry."""
    d = json.load(open(os.path.join(REAL, 'runs', 'synfi_ref', run + '.json')))
    out = []
    for r in d['results']:
        (f,) = r['faults']
        if out and out[-1][0] == f['location'] and f['mapping'] not in out[-1][1]:
            out[-1][1].append(f['mapping'])
        else:
            out.append([f['location'], [f['mapping']]])
    return out


def synfi_list_k2(run_k1, eff_pairs, k1_rows):
    """What an exhaustive SYNFI run with -s 2 reports on this netlist: SYNFI combines its location LIST (repeats
    included) two at a time. Same-node pairs act as one fault (SYNFI applies the second mapping to the node).
    Computed from GlitchSAT's exact distinct-pair verdicts; no solver call."""
    ent = synfi_entries(run_k1)
    n = [len(e[1]) for e in ent]
    tuples = (sum(n) ** 2 - sum(x * x for x in n)) // 2
    mult = collections.Counter(e[0] for e in ent)
    nopt = {e[0]: len(e[1]) for e in ent}
    eff1 = collections.Counter(l for l, o, r in k1_rows if r)
    eff = sum(mult[a] * mult[b] for (a, oa), (b, ob) in eff_pairs)
    eff += sum((mult[l] * (mult[l] - 1) // 2) * nopt[l] * eff1[l] for l in mult)
    return dict(entries=len(ent), repeated_entries=len(ent) - len(mult), injected_faults=2 * tuples,
                effective_faults=2 * eff, effective_percent=round(100.0 * eff / tuples, 4) if tuples else None)


def synfi_list_k1(run_k1, k1_rows):
    ent = synfi_entries(run_k1)
    eff = {(l, o) for l, o, r in k1_rows if r}
    tot = sum(len(e[1]) for e in ent)
    e = sum(1 for l, os_ in ent for o in os_ if (l, o) in eff)
    return dict(injected_faults=tot, effective_faults=e, effective_percent=round(100.0 * e / tot, 2) if tot else None)


def describe_loc(m, loc):
    L = m.locs[loc]
    node = L['node']
    if L['kind'] == 'cell':
        what = f"cell {node} ({L['type']})"
    elif L['kind'] == 'flop':
        what = f"register {node}"
    elif L['kind'] == 'side':
        what = f"side input from {node}" + (f" ({m.m['cells'][node]['type']})" if node in m.m['cells'] else '')
    elif L['kind'] == 'input_end':
        what = f"stage input {node}"
    else:
        what = f"stage output {node}"
    return what


def net_names(m, node):
    """Readable net names driven by a node (hierarchical names first)."""
    if node not in m.m['cells']:
        return [node]
    c = m.m['cells'][node]
    out = []
    for p, d in c['port_directions'].items():
        if d == 'output':
            for b in c['connections'].get(p, []):
                ns = [n for n, x in m.m['netnames'].items() if b in x['bits']]
                ns.sort(key=lambda n: (n.startswith('$'), len(n)))
                out += ns[:1]
    return out


def surface(m, k, cap, check_model=None):
    """m gets blocking clauses; every attack is re-confirmed on check_model (a clean instance)."""
    attacks, stop = m.all_min_attacks(k, cap=cap, timeout_s=1800)
    if check_model is not None:
        for w in attacks:
            if not check_model.check([(x['location'], x['option']) for x in w]):
                raise RuntimeError('attack not confirmed on a clean model instance')
    cnt = collections.Counter()
    kinds = collections.Counter()
    types = collections.Counter()
    sets = []
    for w in attacks:
        locs = sorted({x['location'] for x in w})
        sets.append([dict(location=x['location'], option=x['option'], what=describe_loc(m, x['location'])) for x in w])
        for l in locs:
            cnt[l] += 1
            kinds[m.locs[l]['kind']] += 1
            types[m.locs[l]['type']] += 1
    hot = [dict(location=l, what=describe_loc(m, l), nets=net_names(m, m.locs[l]['node']), attacks=c,
                share=round(c / len(attacks), 3)) for l, c in cnt.most_common(15)]
    return dict(min_faults=k, attacks=len(attacks), complete=(stop == 'exhausted'), stop=stop,
                locations_used=len(cnt), by_kind=dict(kinds), by_type=dict(types.most_common(12)),
                hot_spots=hot, first_attacks=sets[:20])


def run_exp(X, lib, backend, kmax=4, cap=5000):
    t0 = time.time()
    doc = json.load(open(os.path.join(REAL, X['net'][0])))
    spec = next(iter(json.load(open(os.path.join(REAL, X['spec'])))['fimodels'].values()))
    out = dict(id=X['id'], title=X['title'], netlist=X['net'][0], top=X['net'][1], spec=X['spec'],
               published=published(*X['published']))
    # (a) SYNFI-compatible model
    m = sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi')
    m.backend(backend)
    out['solver'] = m.be.name if hasattr(m.be, 'name') else str(type(m.be))
    out['model_stats'] = m.stats()
    out['target_ge'] = m.region_ge()
    out['goal'] = m.goal_info
    out['synfi_rerun'] = {}
    for k, name in X['synfi_runs'].items():
        out['synfi_rerun'][f's{k}'] = synfi_rerun(name, m)
    if X.get('synfi_explicit'):
        me = sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi', auto_fl=False)
        out['synfi_rerun']['s2_explicit_locations'] = synfi_rerun(X['synfi_explicit'], me)
    k1, rows = exhaustive_k1(m)
    out['glitchsat_k1'] = k1
    eff_locs = {l for l, o, r in rows if r}
    if 2 in X['ks']:
        k2, effp = exact_k2(m, eff_locs, lambda: sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi'))
        out['glitchsat_k2'] = k2
        if effp is not None:
            out['glitchsat_k2_synfi_list_basis'] = synfi_list_k2(X['synfi_runs'][1], effp, rows)
    k1['synfi_list_basis'] = synfi_list_k1(X['synfi_runs'][1], rows)
    # (b) security margin, gate-replacement model (fresh instance: cardinality constraint added)
    m2 = sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi')
    mf = m2.min_faults(kmax, backend=backend)
    if mf.get('witness'):
        mf['witness'] = [dict(w, what=describe_loc(m2, w['location'])) for w in mf['witness']]
        assert m.check([(w['location'], w['option']) for w in mf['witness']]), 'witness not confirmed by check()'
    out['margin_synfi_model'] = mf
    if mf['min_faults']:
        m3 = sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi')
        out['surface_synfi_model'] = surface(m3, mf['min_faults'], cap, check_model=m)
    # (b') bit-flip model on the same locations
    mfl = sm.Model(doc, X['net'][1], spec, lib=lib, model='flip')
    rf = mfl.min_faults(kmax, backend=backend)
    if rf.get('witness'):
        rf['witness'] = [dict(w, what=describe_loc(mfl, w['location'])) for w in rf['witness']]
    out['margin_flip_model'] = rf
    if rf['min_faults']:
        mfl2 = sm.Model(doc, X['net'][1], spec, lib=lib, model='flip')
        out['surface_flip_model'] = surface(mfl2, rf['min_faults'], cap, check_model=mfl)
    out['runtime_s'] = round(time.time() - t0, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--backend', default='auto')
    ap.add_argument('--out', default=os.path.join(REAL, 'results', 'experiments.json'))
    a = ap.parse_args()
    lib = ng.load_cell_lib()
    res = {}
    if os.path.exists(a.out):
        res = {r['id']: r for r in json.load(open(a.out))['experiments']}
    for X in EXPS:
        if a.ids and X['id'] not in a.ids:
            continue
        print('running', X['id'], X['title'], flush=True)
        r = run_exp(X, lib, a.backend)
        res[X['id']] = r
        print(json.dumps(dict(id=r['id'], k1=r['glitchsat_k1'], k2=r.get('glitchsat_k2'),
                              margin=r['margin_synfi_model']['min_faults'], flip=r['margin_flip_model']['min_faults'],
                              rerun={k: (v or {}).get('glitchsat_agrees_on') for k, v in r['synfi_rerun'].items()},
                              t=r['runtime_s'])), flush=True)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump(dict(schema='glitchsat-real-experiments/1', experiments=[res[k] for k in sorted(res)]),
                  open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
