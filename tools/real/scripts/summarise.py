#!/usr/bin/env python3
"""Collect every result file into results/results.json and print the comparison tables used in README.md."""
import json, os, platform, sys

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(REAL, 'results')


def load(name):
    p = os.path.join(R, name)
    return json.load(open(p)) if os.path.exists(p) else None


def pct(x):
    return '-' if x is None else f'{x:g}%'


def main():
    ex = load('experiments.json')
    exc = load('experiments_cadical.json')
    val = load('adapter_validation.json')
    out = dict(schema='glitchsat-real-results/1',
               about='GlitchSAT on SYNFI\'s real OpenTitan netlists (lowRISC/synfi @ 2d08c4c, Yosys + Nangate45). '
                     'All verdicts are for modelled faults; sequential results are bounded (N cycles).',
               python=platform.python_version(),
               adapter_validation=None, experiments=[], beyond={})
    if val:
        out['adapter_validation'] = dict(
            cell_pins=val['cell_check']['cell_pins'], truth_table_rows=val['cell_check']['rows'],
            cosim_comparisons=sum(r['comparisons'] for r in val['cosim']),
            cosim_mismatches=sum(r['mismatches'] for r in val['cosim']),
            engine_sim_traces=sum(e['port_traces_compared'] for e in val['engine_sim']),
            engine_sim_mismatches=sum(e['mismatches'] for e in val['engine_sim']), all_ok=val['all_ok'])
    cad = {e['id']: e for e in (exc or {}).get('experiments', [])}
    rows = []
    for e in ex['experiments']:
        p = e['published']
        s1 = e['synfi_rerun'].get('s1') or {}
        s2 = e['synfi_rerun'].get('s2') or {}
        k1, k2 = e['glitchsat_k1'], e.get('glitchsat_k2')
        k2l = e.get('glitchsat_k2_synfi_list_basis')
        c = cad.get(e['id'])
        agree_all = [v['glitchsat_agrees_on'] for v in e['synfi_rerun'].values() if v]
        n_ag = sum(int(a.split('/')[0]) for a in agree_all); n_tot = sum(int(a.split('/')[1]) for a in agree_all)
        same_solver = None
        if c:
            same_solver = (c['margin_synfi_model']['min_faults'] == e['margin_synfi_model']['min_faults'] and
                           c['margin_flip_model']['min_faults'] == e['margin_flip_model']['min_faults'] and
                           c['glitchsat_k1']['effective'] == k1['effective'] and
                           (c.get('glitchsat_k2') or {}).get('effective') == (k2 or {}).get('effective') and
                           (c.get('surface_synfi_model') or {}).get('attacks') == (e.get('surface_synfi_model') or {}).get('attacks'))
        r = dict(
            id=e['id'], title=e['title'], netlist=e['netlist'], spec=e['spec'],
            published=dict(where=p['where'], citation=p['citation'], setting=p['setting'],
                           simultaneous_faults=p['simultaneous_faults'], effective_percent=p['effective_percent'],
                           total_injected=p['total_injected'], execution=p['execution'], circuit_GE=p['circuit_GE'],
                           flow='Yosys + Nangate45 (same netlist family as here)' if p['where'].startswith('Table 7')
                           else 'Synopsys DC + proprietary library (different netlist from the one here)'),
            synfi_rerun_here=dict(
                s1=dict(injected=s1.get('injected_faults'), effective_percent=s1.get('effective_percent'),
                        runtime_s=s1.get('runtime_s'), log=s1.get('synfi_log')) if s1 else None,
                s2=dict(injected=s2.get('injected_faults'), limit=s2.get('limit'), effective=s2.get('effective_injections'),
                        runtime_s=s2.get('runtime_s')) if s2 else None,
                solver=s1.get('solver')),
            glitchsat=dict(
                target_GE=e['target_ge'], locations=e['model_stats']['locations'], fault_options=e['model_stats']['options'],
                k1_distinct=dict(injections=k1['injections'], effective=k1['effective'], percent=k1['effective_percent'],
                                 comb_percent=k1['comb_percent'], seq_percent=k1['seq_percent'], runtime_s=k1['runtime_s']),
                k1_synfi_list_basis=k1.get('synfi_list_basis'),
                k2_distinct=k2, k2_synfi_list_basis=k2l,
                min_faults_gate_replacement=e['margin_synfi_model']['min_faults'],
                min_faults_bit_flip=e['margin_flip_model']['min_faults'],
                witness_gate_replacement=e['margin_synfi_model'].get('witness'),
                witness_bit_flip=e['margin_flip_model'].get('witness'),
                min_search_runtime_s=e['margin_synfi_model'].get('runtime_s'),
                minimum_attacks_gate_replacement=(e.get('surface_synfi_model') or {}).get('attacks'),
                minimum_attacks_bit_flip=(e.get('surface_flip_model') or {}).get('attacks'),
                surface_gate_replacement=e.get('surface_synfi_model'), surface_bit_flip=e.get('surface_flip_model'),
                solver=e.get('solver'), total_runtime_s=e['runtime_s'],
                cadical_cross_check=dict(solver=c.get('solver'), identical=same_solver, runtime_s=c['runtime_s']) if c else None),
            agreement=dict(per_injection=f'{n_ag}/{n_tot}', runs=agree_all))
        out['experiments'].append(r)
        rows.append(r)
    for name in ('fsm_state_single.json', 'fsm_state_single_cadical.json', 'fsm_state_multirail_from_reset.json',
                 'ibex_pc_native.json', 'lint.json', 'synfi_targeted_check.json',
                 'e5_reconciliation.json'):
        d = load(name)
        if d is None:
            continue
        if name.startswith('fsm'):
            out['beyond'][name[:-5]] = dict(summary=d['summary'], cycles=d['cycles'], model=d['model'],
                                            alert_quiet=d.get('alert_quiet'), hit_cycles=d.get('hit_cycles'),
                                            backend=d.get('backend', 'auto (minicdcl)'),
                                            rows=[dict(start=x['start'], target=x['target'], hamming=x['hamming'],
                                                       state_flops=x['state_flops']['min_faults'] if x['state_flops']['verdict'] != 'legal' else 'legal',
                                                       all_sites=x['all']['min_faults'] if x['all']['verdict'] != 'legal' else 'legal',
                                                       witness_all=x['all'].get('witness'))
                                                  for x in d['rows']])
        elif name == 'ibex_pc_native.json':
            out['beyond']['ibex_pc_native'] = d
        elif name == 'lint.json':
            out['beyond']['lint'] = d
        elif name == 'e5_reconciliation.json':
            out['e5_reconciliation'] = d
        else:
            out['beyond']['synfi_targeted_check'] = d
    json.dump(out, open(os.path.join(R, 'results.json'), 'w'), indent=1)
    # markdown
    print('| Exp | SYNFI paper (cited) | SYNFI re-run here | GlitchSAT (same model) | agree | GlitchSAT min faults: gate repl. / bit flip |')
    print('|---|---|---|---|---|---|')
    for r in rows:
        p, s, g = r['published'], r['synfi_rerun_here'], r['glitchsat']
        k = p['simultaneous_faults']
        if k == 1:
            here = f"{s['s1']['effective_percent']}% of {s['s1']['injected']}"
            gl = f"{g['k1_synfi_list_basis']['effective_percent']}% of {g['k1_synfi_list_basis']['injected_faults']}"
        else:
            l = g['k2_synfi_list_basis']
            if not s['s2']:
                here = '-'
            elif s['s2']['limit']:
                here = f"first {s['s2']['limit']} faults of SYNFI's order: {s['s2']['effective']} effective"
            else:
                here = f"{round(100.0 * s['s2']['effective'] * 2 / s['s2']['injected'], 2)}% of {s['s2']['injected']}"
            gl = f"{l['effective_percent']:g}% of {l['injected_faults']:,}" if l else '-'
        print(f"| {r['id']} | {k} fault(s), {p['effective_percent']}% of {p['total_injected']}, {p['execution']} | {here} | {gl} | "
              f"{r['agreement']['per_injection']} | {g['min_faults_gate_replacement']} / {g['min_faults_bit_flip']} |")


if __name__ == '__main__':
    main()
