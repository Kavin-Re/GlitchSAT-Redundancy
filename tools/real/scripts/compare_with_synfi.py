#!/usr/bin/env python3
"""Per-injection agreement: every injection SYNFI ran (runs/synfi_ref/*.json) is re-checked by GlitchSAT's
SYNFI-compatible model (glitchsat_real.synfi_model, model='synfi'). Writes results/synfi_agreement.json."""
import json, os, sys, time, glob
REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import synfi_model as sm, nangate as ng   # noqa

RUNS = {
    'aes_fsm': ('synfi/examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json', 'aes_cipher_control_fsm'),
    'aes_ctrl': ('synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json', 'aes_cipher_control'),
    'ibex': ('synfi/examples/ibex/netlist_ibex_if_stage.json', 'ibex_if_stage'),
}


def compare(ref_path, lib, cache):
    ref = json.load(open(ref_path))
    key = os.path.basename(ref_path).split('_')[0] + '_' + os.path.basename(ref_path).split('_')[1]
    net = os.path.relpath(ref['netlist'], REAL)
    top = ref['module']
    spec = next(iter(json.load(open(ref['spec']))['fimodels'].values()))
    ck = (net, ref['spec'], ref['auto_fl'])
    t0 = time.time()
    if ck not in cache:
        doc = json.load(open(os.path.join(REAL, net)))
        cache[ck] = sm.Model(doc, top, spec, lib=lib, auto_fl=ref['auto_fl'])
    m = cache[ck]
    tb = time.time() - t0
    agree = dis = missing = 0
    bad = []
    t1 = time.time()
    for r in ref['results']:
        faults = [(f['location'], f['mapping']) for f in r['faults']]
        try:
            got = m.check(faults)
        except KeyError as e:
            missing += 1; bad.append(dict(faults=faults, error=f'location not in GlitchSAT model: {e}')); continue
        if got == r['sat']:
            agree += 1
        else:
            dis += 1; bad.append(dict(faults=faults, synfi=r['sat'], glitchsat=got))
    synfi_locs = {f['location'] for r in ref['results'] for f in r['faults']}
    return dict(reference=os.path.relpath(ref_path, REAL), injections=len(ref['results']), agree=agree, disagree=dis,
                missing=missing, examples=bad[:5], synfi_sat=ref['sat'], synfi_inject_s=ref['inject_s'],
                glitchsat_build_s=round(tb, 2), glitchsat_check_s=round(time.time() - t1, 2),
                glitchsat_locations=len(m.locs), synfi_locations_seen=len(synfi_locs),
                glitchsat_options=len(m.sel))


if __name__ == '__main__':
    lib = ng.load_cell_lib(); cache = {}
    out = []
    for p in sys.argv[1:]:
        r = compare(p, lib, cache); out.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != 'examples'}), r['examples'][:2])
