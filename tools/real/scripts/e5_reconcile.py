#!/usr/bin/env python3
"""E5 reconciliation: GlitchSAT's 80 of 309,580 against the paper's 62 of 309,500 (SYNFI Table 7 row 2).

Inputs: SYNFI's own fault-set list on this netlist (runs/e5_reconcile/synfi_list_seed*.json, from
synfi_e5_enumeration.py list) and SYNFI's own verdicts on chosen sets (runs/e5_reconcile/synfi_inject_*.jsonl, from
synfi_e5_enumeration.py inject). GlitchSAT's exact effective pairs are recomputed here (SYNFI-compatible model).
Writes runs/e5_reconcile/glitchsat_eff_pairs.json and results/e5_reconciliation.json.
"""
import collections, glob, itertools, json, os, sys

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [REAL, os.path.join(REAL, 'scripts')]
os.chdir(REAL)
import run_experiments as R                                        # noqa: E402
from glitchsat_real import synfi_model as sm, nangate as ng       # noqa: E402

OUT = os.path.join(REAL, 'runs', 'e5_reconcile')


def glitchsat_pairs():
    X = next(x for x in R.EXPS if x['id'] == 'E5')
    lib = ng.load_cell_lib()
    doc = json.load(open(X['net'][0]))
    spec = next(iter(json.load(open(X['spec']))['fimodels'].values()))
    mk = lambda: sm.Model(doc, X['net'][1], spec, lib=lib, model='synfi')
    m = mk(); m.backend('py')
    k1, rows = R.exhaustive_k1(m)
    k2, eff = R.exact_k2(m, {l for l, o, r in rows if r}, mk)
    assert k1['effective'] == 0 and k2['complete']
    ent = R.synfi_entries('ibex_pc_fs_s1')
    mult = collections.Counter(e[0] for e in ent)
    out = []
    for (a, oa), (b, ob) in eff:
        out.append(dict(a=a, oa=oa, what_a=R.describe_loc(m, a), nets_a=R.net_names(m, m.locs[a]['node']), mult_a=mult[a],
                        b=b, ob=ob, what_b=R.describe_loc(m, b), nets_b=R.net_names(m, m.locs[b]['node']), mult_b=mult[b]))
    d = dict(eff=out, entries=ent, k2=k2)
    json.dump(d, open(os.path.join(OUT, 'glitchsat_eff_pairs.json'), 'w'), indent=1)
    return d, m


def main():
    g, m = glitchsat_pairs()
    eff = {frozenset([(o['a'], o['oa']), (o['b'], o['ob'])]) for o in g['eff']}
    opts = {e[0]: e[1] for e in g['entries']}
    lists = {}
    for p in sorted(glob.glob(os.path.join(OUT, 'synfi_list_seed*.json'))):
        L = json.load(open(p))
        sets = [frozenset([(x, ox), (y, oy)]) for x, y in itertools.combinations(L['entry_order'], 2)
                for ox in opts[x] for oy in opts[y]]
        flags = [s in eff for s in sets]
        lists[L['seed']] = dict(entries=L['entries'], distinct_locations=L['distinct_locations'],
                                single_injections=L['single_injections'], fault_sets=L['fault_sets'],
                                synfi_log_injected_faults=L['synfi_log_injected_faults'],
                                repeated_entries_by_multiplicity=L['repeated'],
                                effective_sets_by_glitchsat_verdicts=sum(flags),
                                effective_sets_in_last_40=sum(flags[-40:]),
                                effective_sets_in_first_154750=sum(flags[:154750]),
                                order=L['entry_order'])
    seeds = sorted(lists)
    same_content = all(sorted(lists[s]['order']) == sorted(lists[seeds[0]]['order']) for s in seeds)
    same_order = all(lists[s]['order'] == lists[seeds[0]]['order'] for s in seeds)
    for s in seeds:
        del lists[s]['order']
    # SYNFI's own verdicts
    inj = {}
    for p in sorted(glob.glob(os.path.join(OUT, 'synfi_inject_*.jsonl'))):
        rows = [json.loads(l) for l in open(p)]
        agree = sum(1 for r in rows if (frozenset((f['location'], f['mapping']) for f in r['faults']) in eff
                                        if len({f['location'] for f in r['faults']}) == 2 else False) == r['sat'])
        inj[os.path.basename(p)] = dict(sets=len(rows), synfi_sat=sum(r['sat'] for r in rows), glitchsat_agrees=agree)
    # composition of the 40 effective sets
    groups = collections.Counter()
    for o in g['eff']:
        groups['both entries listed once' if o['mult_a'] == o['mult_b'] == 1 else
               f"uses an entry listed {max(o['mult_a'], o['mult_b'])} times"] += o['mult_a'] * o['mult_b']
    rep = [o for o in g['eff'] if o['mult_a'] * o['mult_b'] > 1]
    doc = dict(
        question='E5: GlitchSAT (SYNFI counting) 80 effective of 309,580 injected faults; paper 62 of 309,500',
        paper=dict(where='SYNFI paper, Table 7 row 2 and Sec. 4.3 text: "only 62 (0.02%) out of 309,500 injected faults"',
                   checked_against='arXiv:2205.04775 PDF'),
        counting_rule=('SYNFI counts faults, not fault sets: fi_injector.handle_fault_model logs len(sets)*k and '
                       'evaluate_fault_results adds 1 per fault location of every set; with k = 2 every number is '
                       'twice the number of fault sets.'),
        in_fault_sets=dict(paper=dict(sets=309500 // 2, effective=62 // 2),
                           here=dict(sets=309580 // 2, effective=80 // 2),
                           difference=dict(sets=40, effective=9)),
        synfi_enumeration=dict(
            how=('--auto_fl: every target-graph node except in/out nodes and registers; one entry per '
                 '(parent cell, graph node) as built by handle_fault_locations, so the nodes of a register that '
                 'unroll_circuit cut into c input copies are listed c times each (register node included); '
                 'itertools.combinations(entries, 2) x product of each entry\'s mapping list; no limit.'),
            per_hash_seed=lists, same_content_all_seeds=same_content, same_order_all_seeds=same_order),
        glitchsat_exact=dict(distinct_effective_sets=len(g['eff']), distinct_sets=g['k2']['injections'],
                             effective_sets_synfi_list=sum(o['mult_a'] * o['mult_b'] for o in g['eff']),
                             composition=dict(groups),
                             sets_using_repeated_entries=[dict(a=o['what_a'], nets_a=o['nets_a'], mult_a=o['mult_a'],
                                                               b=o['what_b'], nets_b=o['nets_b'], mult_b=o['mult_b'])
                                                          for o in rep],
                             all_effective=[dict(a=o['what_a'], option_a=o['oa'], nets_a=o['nets_a'], mult_a=o['mult_a'],
                                                 b=o['what_b'], option_b=o['ob'], nets_b=o['nets_b'], mult_b=o['mult_b'])
                                            for o in g['eff']]),
        synfi_own_verdicts=inj,
    )
    json.dump(doc, open(os.path.join(REAL, 'results', 'e5_reconciliation.json'), 'w'), indent=1)
    print(json.dumps(dict(lists=lists, same_content=same_content, same_order=same_order, inj=inj,
                          composition=dict(groups)), indent=1))
    for o in rep:
        print(o['mult_a'], o['mult_b'], o['what_a'], o['nets_a'], '|', o['what_b'], o['nets_b'])


if __name__ == '__main__':
    main()
