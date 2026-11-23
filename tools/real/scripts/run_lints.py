#!/usr/bin/env python3
"""Did the redundant structures survive synthesis? Structural lints, no solver.

1. glitchsat_real.hier_lint (cell ownership by hierarchy name) on SYNFI's aes_cipher_control netlist (three FSM
   rails gen_fsm[0..2]).
2. ext/surface merge_lint.py (unchanged) on the adapted aes_cipher_control netlist, copies from the names
   gen_fsm[i], decision bits = each three-rail output port (one bit per rail).
3. Up/down round counter: are rnd_ctr and rnd_ctr_rem still separate registers?
Writes results/lint.json."""
import json, os, subprocess, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import hier_lint, nangate as ng, engine   # noqa

NETS = [("synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json", "aes_cipher_control"),
]
RAIL_PORTS = ['in_ready_o', 'out_valid_o', 'crypt_o', 'dec_key_gen_o', 'state_we_o', 'sub_bytes_en_o',
              'sub_bytes_out_ack_o', 'key_full_we_o', 'key_dec_we_o', 'key_expand_en_o', 'key_expand_out_ack_o']


def main():
    out = dict(hier_lint=[], merge_lint=[], counters=[])
    lib = ng.load_cell_lib()
    for path, top in NETS:
        doc = json.load(open(os.path.join(REAL, path)))
        r = hier_lint.lint(doc, top)
        r['netlist'] = path
        out['hier_lint'].append(r)
        print(path, r['verdict'], r['copies'], 'cross reads', r['cross_copy_reads'], 'shared nets', r['shared_driver_nets'])
        m = doc['modules'][top]
        regs = {}
        for cn, c in m['cells'].items():
            for key in ('u_rnd_ctr_regs', 'u_rnd_ctr_rem_regs', 'u_num_rounds_regs', 'u_rnd_ctr_err_reg', 'u_rnd_ctr_par_reg'):
                if key + '.' in cn and c['type'] in ng.FLOP_PINS:
                    regs.setdefault(key, []).append(cn)
        out['counters'].append(dict(netlist=path, registers={k: len(v) for k, v in sorted(regs.items())}))
    path, top = NETS[0]
    nd, meta = ng.convert(json.load(open(os.path.join(REAL, path))), top, lib=lib)
    ap = os.path.join(REAL, 'runs', 'adapted', 'aes_ctrl.json')
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    json.dump(nd, open(ap, 'w'))
    env = dict(os.environ, GLITCHSAT_ROOT=engine.ROOT)
    for port in RAIL_PORTS:
        t0 = time.time()
        p = subprocess.run([sys.executable, os.path.join(engine.EXT, 'surface', 'scripts', 'merge_lint.py'), ap,
                            '--top', top, '--goal-out', port, '--copy-regex', r'gen_fsm\[(\d)\]', '--json', '-'],
                           capture_output=True, text=True, env=env)
        if p.returncode != 0:
            out['merge_lint'].append(dict(port=port, error=p.stderr[-400:])); continue
        d = json.loads(p.stdout)
        out['merge_lint'].append(dict(port=port, mode=d['mode'], verdict=d['verdict'],
                                      copies={k: dict(cone=v['cone_size'], decision_bits=v['decision_bits']) for k, v in d['copies'].items()},
                                      shared_nets=len(d['shared_nets']), merge_points=len(d['merge_points']),
                                      single_points=len(d['single_points']), findings=d['findings'][:4],
                                      runtime_s=round(time.time() - t0, 2)))
        print(port, d['verdict'], len(d['shared_nets']), len(d['single_points']))
    os.makedirs(os.path.join(REAL, 'results'), exist_ok=True)
    json.dump(out, open(os.path.join(REAL, 'results', 'lint.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
