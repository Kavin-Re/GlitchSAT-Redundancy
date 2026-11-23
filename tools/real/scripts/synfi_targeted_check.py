#!/usr/bin/env python3
"""Cross-check GlitchSAT's 2-fault attacks with SYNFI itself.

The prefix of SYNFI's own 2-fault enumeration that is affordable here (-l 2000) contains no effective pair for the
Ibex and protected-counter experiments, so it only tests negatives. This script takes minimum attacks that GlitchSAT
found (results/experiments.json, surface_synfi_model.first_attacks), writes a SYNFI fault specification whose
explicit fault_locations are exactly the parents of those locations, runs SYNFI unmodified with -s 2 (no --auto_fl),
and compares every injection SYNFI makes with GlitchSAT's check(). Writes results/synfi_targeted_check.json.
"""
import json, os, subprocess, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import synfi_model as sm, nangate as ng   # noqa

WORK = {'E3': 'aes_ctrl', 'E5': 'ibex'}


def main(ids=('E5', 'E3'), per_exp=4):
    lib = ng.load_cell_lib()
    exps = {e['id']: e for e in json.load(open(os.path.join(REAL, 'results', 'experiments.json')))['experiments']}
    out = []
    for i in ids:
        e = exps[i]
        doc = json.load(open(os.path.join(REAL, e['netlist'])))
        base = json.load(open(os.path.join(REAL, e['spec'])))
        name, fm = next(iter(base['fimodels'].items()))
        m = sm.Model(doc, e['top'], fm, lib=lib)
        attacks = e['surface_synfi_model']['first_attacks'][:per_exp]
        for j, att in enumerate(attacks):
            fl = {}
            for x in att:
                L = m.locs[x['location']]
                fl.setdefault(m._parent(L['node']), []).append(L['stage'])
            spec = json.loads(json.dumps(base))
            spec['fimodels'][name]['fault_locations'] = fl
            spec['fimodels'][name]['simultaneous_faults'] = 2
            sp = os.path.join(REAL, 'runs', 'targeted', f'{i}_{j}_spec.json')
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            json.dump(spec, open(sp, 'w'), indent=1)
            res = os.path.join(REAL, 'runs', 'targeted', f'{i}_{j}_synfi.json')
            if not os.path.exists(res):
                subprocess.run([sys.executable, os.path.join(REAL, 'scripts', 'run_synfi_reference.py'), '--netlist',
                                os.path.join(REAL, e['netlist']), '--module', e['top'], '--spec', sp, '-s', '2',
                                '--work', os.path.join(REAL, 'runs', 'synfi_ref', WORK[i]), '--out', res],
                               check=True, capture_output=True)
            ref = json.load(open(res))
            me = sm.Model(doc, e['top'], spec['fimodels'][name], lib=lib, auto_fl=False)
            agree = sum(1 for r in ref['results'] if me.check([(f['location'], f['mapping']) for f in r['faults']]) == r['sat'])
            target = tuple(sorted((x['location'], x['option']) for x in att))
            hit = [r['sat'] for r in ref['results'] if tuple(sorted((f['location'], f['mapping']) for f in r['faults'])) == target]
            row = dict(experiment=i, attack=[dict(location=x['location'], option=x['option']) for x in att],
                       fault_locations=fl, synfi_injections=len(ref['results']), synfi_effective=ref['sat'],
                       agree=agree, synfi_verdict_on_this_attack=hit, synfi_runtime_s=ref['inject_s'])
            out.append(row)
            print(i, j, 'SYNFI injections', len(ref['results']), 'effective', ref['sat'], 'agree', agree,
                  'SYNFI says this attack is', hit, flush=True)
    json.dump(out, open(os.path.join(REAL, 'results', 'synfi_targeted_check.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
