#!/usr/bin/env python3
"""E5 (Ibex PC set to a value, 2 faults): SYNFI's own exhaustive fault-set list and SYNFI's own verdicts.

Uses SYNFI's unmodified functions (pinned clone, with shims/) step by step, exactly as fi_injector.handle_fault_model
does: extract_graph -> handle_fault_locations(--auto_fl) -> fault_combinations(no limit). Then FiInjector (SYNFI's
injector, unmodified) is run on chosen fault sets, in resumable chunks (results appended to a JSONL file).

  synfi_e5_enumeration.py list   [--seed S]         build the list; write runs/e5_reconcile/synfi_list_seed<S>.json
  synfi_e5_enumeration.py inject --which glitchsat_effective|cluster|sample:N|range:A:B  [--seed S] [--max-s 540]

The list order depends on Python's string hashing (networkx subgraph views iterate over a Python set), so the
order is recorded per PYTHONHASHSEED; the content (multiset of fault sets) is what the counts depend on.
"""
import argparse, collections, json, os, pickle, random, subprocess, sys, time

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNFI = os.path.join(REAL, 'synfi')
OUT = os.path.join(REAL, 'runs', 'e5_reconcile')
SPEC = os.path.join(SYNFI, 'examples', 'ibex', 'fault_model_ibex_if_stage_pc_target.json')
PICKLE = os.path.join(REAL, 'runs', 'synfi_ref', 'ibex', 'netlist.pickle')


def synfi_modules():
    sys.path[:0] = [os.path.join(REAL, 'shims'), SYNFI]
    import fi_injector, injector_class          # SYNFI, unmodified
    return fi_injector, injector_class


def build(seed):
    fi, _ = synfi_modules()
    cell_lib = fi.load_cell_lib_module(type('A', (), {'cell_lib_path': os.path.join(SYNFI, 'cell_lib_nangate45_autogen.py')}))
    name, fm = next(iter(json.load(open(SPEC))['fimodels'].items()))
    fm['simultaneous_faults'] = 2
    graph = fi.read_circuit(PICKLE)
    t0 = time.time()
    tg = fi.extract_graph(graph, fm, cell_lib, 1, False)
    t1 = time.time()
    locs = fi.handle_fault_locations(True, fm, tg, cell_lib)
    comb = fi.fault_combinations(tg, locs, fm, None)
    return dict(fi=fi, cell_lib=cell_lib, name=name, fm=fm, graph=graph, tg=tg, locs=locs, comb=comb,
                extract_s=round(t1 - t0, 1))


def cmd_list(a):
    b = build(a.seed)
    locs, comb, tg = b['locs'], b['comb'], b['tg']
    parent = {l.location: tg.nodes[l.location]['node'].parent_name for l in locs}
    per_parent_nodes = collections.Counter(tg.nodes[n]['node'].parent_name for n in tg.nodes
                                           if tg.nodes[n]['node'].type not in ('in_node', 'out_node'))
    mult = collections.Counter(l.location for l in locs)
    # where the 'name' used by _inject_faults differs from the graph key (would make a fault a no-op)
    name_mismatch = [n for n in mult if tg.nodes[n]['node'].name != n]
    doc = dict(seed=a.seed, extract_s=b['extract_s'], entries=len(locs), distinct_locations=len(mult),
               single_injections=sum(len(b['fm']['node_fault_mapping'][tg.nodes[l.location]['node'].type]) for l in locs),
               fault_sets=len(comb), synfi_log_injected_faults=2 * len(comb),
               repeated=dict(collections.Counter(mult.values())), name_mismatch=name_mismatch,
               entry_order=[l.location for l in locs], parent=parent)
    p = os.path.join(OUT, f'synfi_list_seed{a.seed}.json')
    json.dump(doc, open(p, 'w'), indent=1)
    print(json.dumps({k: v for k, v in doc.items() if k not in ('entry_order', 'parent')}))


def key(fs):
    return tuple(sorted((f.location, f.mapping) for f in fs))


def cmd_inject(a):
    b = build(a.seed)
    _, ic = synfi_modules()
    import ray                                   # the shim (sequential), as used by fi_injector
    comb = b['comb']
    if a.which == 'glitchsat_effective':
        g = json.load(open(os.path.join(OUT, 'glitchsat_eff_pairs.json')))
        eff = {tuple(sorted([(o['a'], o['oa']), (o['b'], o['ob'])])) for o in g['eff']}
        idx = [i for i, fs in enumerate(comb) if key(fs) in eff]
    elif a.which == 'cluster':      # every set whose two locations both occur in some GlitchSAT-effective set
        g = json.load(open(os.path.join(OUT, 'glitchsat_eff_pairs.json')))
        L = {o['a'] for o in g['eff']} | {o['b'] for o in g['eff']}
        idx = [i for i, fs in enumerate(comb) if all(x.location in L for x in fs)]
    elif a.which.startswith('sample:'):
        n = int(a.which.split(':')[1])
        idx = sorted(random.Random(12345).sample(range(len(comb)), n))
    else:
        _, lo, hi = a.which.split(':'); idx = list(range(int(lo), min(int(hi), len(comb))))
    res_p = os.path.join(OUT, f'synfi_inject_{a.which.replace(":", "_")}_seed{a.seed}.jsonl')
    done = set()
    if os.path.exists(res_p):
        done = {json.loads(l)['key_str'] for l in open(res_p)}
    todo = [i for i in idx if json.dumps(key(comb[i])) not in done]
    print(f'{len(idx)} sets selected, {len(todo)} to do', flush=True)
    t0 = time.time()
    with open(res_p, 'a') as f:
        for i in todo:
            if time.time() - t0 > a.max_s:
                print('time budget reached; rerun to resume', flush=True); break
            inj = ic.FiInjector.remote(b['name'], b['tg'], b['graph'], [comb[i]], b['fm'], b['cell_lib'])
            (r,) = ray.get(inj.perform_attack.remote())
            f.write(json.dumps(dict(index=i, key_str=json.dumps(key(comb[i])), sat=bool(r.sat_result),
                                    faults=[dict(location=x.location, mapping=x.mapping) for x in comb[i]])) + '\n')
            f.flush()
    rows = [json.loads(l) for l in open(res_p)]
    print(f'{len(rows)} done, {sum(r["sat"] for r in rows)} SAT, {round(time.time() - t0, 1)} s')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'inject'])
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--which', default='glitchsat_effective')
    ap.add_argument('--max-s', type=float, default=540)
    a = ap.parse_args()
    if os.environ.get('PYTHONHASHSEED') != str(a.seed):     # make the list order reproducible
        env = dict(os.environ, PYTHONHASHSEED=str(a.seed))
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))
    os.makedirs(OUT, exist_ok=True)
    (cmd_list if a.cmd == 'list' else cmd_inject)(a)


if __name__ == '__main__':
    main()
