#!/usr/bin/env python3
"""Prove the Nangate45 -> GlitchSAT adapter correct on the real SYNFI netlists.

1. Exhaustive truth-table check of every Nangate45 (cell, output pin) in SYNFI's cell library: primitive tree ==
   docstring function == SYNFI's CNF clauses (nangate.verify_cells).
2. Sequential random co-simulation, per netlist: the original netlist evaluated with SYNFI's clause semantics and
   Nangate flop behaviour (refsim.RefSim) against the adapted primitive netlist parsed by the GlitchSAT engine
   (refsim.PrimSim over glitchsat.Netlist). Every net of the original netlist (cell outputs, flop Q/QN, output
   ports) is compared in every cycle and every lane.
     mode 'deasserted': reset input held inactive (1) in every cycle, flops start at their reset value.
     mode 'sync': reset input random in every cycle; adapter built with reset_mode='sync'; reference applies the
                  reset at the clock edge.
3. The GlitchSAT engine's own scalar simulator (fastsat glitchsat_sat.simulate, constant inputs) on a sample of
   vectors, against the reference, for every output port.
Writes results/adapter_validation.json.
"""
import json, os, random, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REAL)
from glitchsat_real import nangate as ng, refsim, engine   # noqa: E402

NETLISTS = [
    ('aes_cipher_control_fsm', 'synfi/examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json'),
    ('aes_cipher_control', 'synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json'),
    ('ibex_if_stage', 'synfi/examples/ibex/netlist_ibex_if_stage.json'),
    ('aes_cipher_control', 'synfi/examples/circuit.json'),
]


def cosim(path, top, mode, W, T, seed, lib):
    doc = json.load(open(os.path.join(REAL, path)))
    nd, meta = ng.convert(doc, top, lib=lib, reset_mode=mode)
    nl = engine.netlist_from_doc(nd, top)
    ref = refsim.RefSim(doc, top, lib)
    prim = refsim.PrimSim(nl)
    rng = random.Random(seed)
    rst = {r['net']: 1 - r['active'] for r in meta['resets']}
    ins = refsim.random_inputs(doc['modules'][top]['ports'], T, W, rng, hold=rst if mode == 'deasserted' else None)
    init = {cn: f['init'] for cn, f in meta['flops'].items()}
    t0 = time.time()
    a = ref.run(T, ins, W, init)
    b = prim.run(T, ins, W)
    nets = sorted(set(ref.drv) | {x for p in doc['modules'][top]['ports'].values() if p['direction'] == 'output'
                                  for x in p['bits'] if isinstance(x, int)})
    mism = []
    for t in range(T):
        for n in nets:
            if a[t].get(n) is None:
                continue
            if a[t][n] != b[t][n]:
                mism.append(dict(cycle=t, net=n, lanes=bin(a[t][n] ^ b[t][n]).count('1')))
    return dict(netlist=path, top=top, reset_mode=mode, lanes=W, cycles=T, seed=seed,
                cells=meta['cell_count'], primitives=meta['prim_count'], flops=len(meta['flops']),
                nets_compared=len(nets), comparisons=len(nets) * T * W, mismatches=len(mism),
                first_mismatches=mism[:5], runtime_s=round(time.time() - t0, 2)), doc, nd, meta, nl, ref


def engine_check(doc, top, nd, meta, nl, ref, n_vec, N, seed):
    """fastsat's scalar simulate() (the engine-side simulator, constant inputs) vs RefSim with constant inputs."""
    fs = engine.fastsat()
    rng = random.Random(seed)
    ports = doc['modules'][top]['ports']
    rst = {r['net']: 1 - r['active'] for r in meta['resets']}
    outs = [p for p, x in ports.items() if x['direction'] == 'output' and all(isinstance(b, int) for b in x['bits'])]
    bad = 0; checks = 0
    init = {cn: f['init'] for cn, f in meta['flops'].items()}
    for _ in range(n_vec):
        vals = {}
        for p, x in ports.items():
            if x['direction'] != 'input' or p == 'clk_i':
                continue
            v = rng.getrandbits(len(x['bits']))
            for i, b in enumerate(x['bits']):
                if b in rst:
                    v = (v & ~(1 << i)) | (rst[b] << i)
            vals[p] = v
        ins = [{b: (vals[p] >> i) & 1 for p in vals for i, b in enumerate(ports[p]['bits'])} for _ in range(N)]
        tr = ref.run(N, ins, 1, init)
        engine_inputs = dict(vals); engine_inputs.setdefault('clk_i', 0)
        for o in outs:
            got = fs.simulate(nl, N, engine_inputs, [], o)
            want = [sum(tr[t][b] << i for i, b in enumerate(ports[o]['bits'])) for t in range(N)]
            checks += 1
            if got != want:
                bad += 1
    return dict(vectors=n_vec, cycles=N, output_ports=len(outs), port_traces_compared=checks, mismatches=bad)


def main():
    t0 = time.time()
    lib = ng.load_cell_lib()
    cells = ng.verify_cells(lib)
    out = dict(cell_check=dict(cell_pins=len(cells), rows=sum(r['rows_checked'] for r in cells.values()),
                               mismatches=0, cells=cells), cosim=[], engine_sim=[])
    seen = set()
    for top, path in NETLISTS:
        for mode in ('deasserted', 'sync'):
            r, doc, nd, meta, nl, ref = cosim(path, top, mode, W=512, T=12, seed=1, lib=lib)
            out['cosim'].append(r)
            print(f"{path} [{mode}]: {r['comparisons']} net-lane-cycle comparisons, {r['mismatches']} mismatches")
            if mode == 'deasserted' and path not in seen:
                seen.add(path)
                e = engine_check(doc, top, nd, meta, nl, ref, n_vec=8, N=4, seed=2)
                e['netlist'] = path
                out['engine_sim'].append(e)
                print(f"  engine simulate(): {e['port_traces_compared']} port traces, {e['mismatches']} mismatches")
    out['runtime_s'] = round(time.time() - t0, 1)
    out['all_ok'] = all(r['mismatches'] == 0 for r in out['cosim']) and all(e['mismatches'] == 0 for e in out['engine_sim'])
    os.makedirs(os.path.join(REAL, 'results'), exist_ok=True)
    json.dump(out, open(os.path.join(REAL, 'results', 'adapter_validation.json'), 'w'), indent=1)
    print('ALL OK' if out['all_ok'] else 'MISMATCH', f"({out['runtime_s']} s)")
    return 0 if out['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
