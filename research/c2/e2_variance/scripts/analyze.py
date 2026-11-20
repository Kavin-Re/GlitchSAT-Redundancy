#!/usr/bin/env python3
"""Usage: analyze.py <netlist.json> <top> [--k 3 --cycles 6 --seeds N]
Prints one JSON line: gate histogram, structural 'match-net' check, min-k via glitchsat (z3). Never writes results/."""
import sys, json, collections, itertools, time, argparse
sys.path.insert(0, '/tmp/work_e2/scripts')
import glitchsat as G
from z3 import set_param

def structural(nl):
    """Evaluate every net whose support is only `sig` over all 256 inputs; find nets computing (sig==0xC3)."""
    sig = nl.ports['sig']['bits']
    full = (1 << 256) - 1
    tt = {}
    for i, b in enumerate(sig):
        v = 0
        for x in range(256):
            if (x >> i) & 1: v |= 1 << x
        tt[b] = v
    tt['0'] = 0; tt['1'] = full
    memo = {}; ok = {}
    def ev(b):
        if b in memo: return memo[b]
        if b in tt: memo[b] = tt[b]; return tt[b]
        if b not in nl.drivers: memo[b] = None; return None
        _, ty, con = nl.drivers[b]
        g = lambda p: ev(con[p][0])
        a = {p: g(p) for p in con if p != 'Y'}
        if any(v is None for v in a.values()): r = None
        elif ty == '$_AND_': r = a['A'] & a['B']
        elif ty == '$_OR_': r = a['A'] | a['B']
        elif ty == '$_XOR_': r = a['A'] ^ a['B']
        elif ty == '$_XNOR_': r = full ^ a['A'] ^ a['B']
        elif ty == '$_NAND_': r = full ^ (a['A'] & a['B'])
        elif ty == '$_NOR_': r = full ^ (a['A'] | a['B'])
        elif ty == '$_ANDNOT_': r = a['A'] & (full ^ a['B'])
        elif ty == '$_ORNOT_': r = a['A'] | (full ^ a['B'])
        elif ty == '$_NOT_': r = full ^ a['A']
        elif ty == '$_MUX_': r = (a['A'] & (full ^ a['S'])) | (a['B'] & a['S'])
        else: r = None
        memo[b] = r; return r
    match_tt = 1 << 0xC3
    matches = [b for b in nl.drivers if ev(b) == match_tt]
    nmatches = [b for b in nl.drivers if ev(b) == full ^ match_tt]   # inverted match nets
    def cone(b, acc):
        if b in nl.drivers and b not in acc:
            acc.add(b)
            for f in nl.fanins(b):
                if isinstance(f, int): cone(f, acc)
        return acc
    cones = {b: cone(b, set()) for b in matches}
    shared = 0
    for a, b in itertools.combinations(matches, 2):
        shared += len(cones[a] & cones[b])
    # hierarchical names that survived (c0.m etc.)
    named = {n: x['bits'] for n, x in nl.m['netnames'].items() if n in ('m0','m1','m2')}
    nb = {n: v[0] for n, v in named.items()}
    ncone = {n: cone(b, set()) for n, b in nb.items() if isinstance(b, int)}
    nshared = {f'{a}&{b}': len(ncone[a] & ncone[b]) for a, b in itertools.combinations(sorted(ncone), 2)}
    named_distinct = len({tuple(v) for v in named.values()}) if named else None
    # how many distinct nets feed the 8 word-bit decision: sel-nets reaching state-flop D inputs
    return dict(distinct_match_nets=len(matches), distinct_inverted_match_nets=len(nmatches),
                gates_shared_between_match_cones=shared, named_copy_nets=len(named),
                named_copy_nets_distinct=named_distinct, named_copy_cone_sizes={n: len(c) for n, c in ncone.items()}, named_copy_shared_gates=nshared)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('json'); ap.add_argument('top')
    ap.add_argument('--k', type=int, default=3); ap.add_argument('--cycles', type=int, default=6)
    ap.add_argument('--seeds', type=int, default=0); ap.add_argument('--nosolve', action='store_true')
    a = ap.parse_args()
    d0 = json.load(open(a.json)); stripped = 0
    for mod in d0['modules'].values():
        for cn in [c for c, v in mod['cells'].items() if v['type'] == '$scopeinfo']:
            del mod['cells'][cn]; stripped += 1
    if stripped:   # Yosys >=0.4x flatten emits $scopeinfo (non-logic); glitchsat.py rejects it, so strip on OUR copy only
        a.json = a.json + '.noscope.json'; json.dump(d0, open(a.json, 'w'))
    cells = collections.Counter(c['type'] for c in json.load(open(a.json))['modules'][a.top]['cells'].values())
    bad = [t for t in cells if t not in ('$_AND_','$_OR_','$_XOR_','$_NOT_','$_MUX_','$_DFF_P_')]
    if bad:
        print(json.dumps(dict(netlist=a.json, cells=dict(cells), solver='ENGINE_UNSUPPORTED_CELLS ' + ','.join(bad), gates_total_cells=sum(cells.values())))); return
    nl = G.Netlist(a.json, a.top)
    hist = collections.Counter(t for _, t, _ in nl.drivers.values())
    out = dict(scopeinfo_stripped=stripped, netlist=a.json, top=a.top, gates=len(nl.drivers), flops=len(nl.dffs), hist=dict(hist))
    out['struct'] = structural(nl)
    unsupported = [t for t in hist if t not in ('$_AND_','$_OR_','$_XOR_','$_NOT_','$_MUX_')]
    if unsupported: out['solver'] = 'UNSUPPORTED_CELLS ' + ','.join(unsupported)
    elif not a.nosolve:
        t0 = time.time()
        v, info, res = G.solve(nl, a.cycles, a.k)
        out['verdict_k%d' % a.k] = v
        out['min_k'] = len(res['faults']) if res else None
        out['faults'] = [(t, nl.names.get(b, str(b))) for t, b in res['faults']] if res else None
        out['honest_boots'] = G.honest_boots(nl, a.cycles)
        out['solve_s'] = round(time.time() - t0, 2)
        out['by_k'] = {}
        if a.seeds:
            mins = []
            for sd in range(a.seeds):
                set_param('smt.random_seed', sd); set_param('sat.random_seed', sd)
                v2, _, r2 = G.solve(nl, a.cycles, a.k)
                mins.append(len(r2['faults']) if r2 else None)
            out['seed_min_k'] = mins
    print(json.dumps(out))
main()
