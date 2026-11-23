#!/usr/bin/env python3
"""Correctness run: minimum flips from the SAT backend (bundled Python solver unless --backend is given) against
  (a) results recorded in the repository (results/reproduce/*.json, validation/data/*.json, research/c4/ver/heldout.csv,
      docs/NUMBERS.md row B2.v2.ok), and
  (b) the exhaustive simulator tests/bruteforce.py (every fault set of size 0..j on every site and cycle, every input).
Writes bench/results/verify_all.json and prints a summary. Exit 1 on any disagreement.

usage: verify_all.py [--backend B] [--jobs N] [--quick]
"""
import argparse, json, os, sys, time, math, glob
from multiprocessing import Pool
from common import S, ROOT, FASTSAT, repo_netlists, default_params
import bruteforce

BACKEND = 'py'
CFGS = [dict(), dict(collapse=False), dict(card='seqcounter', reduce='none'), dict(fault_enc='relax'), dict(fault_enc='relax', collapse=False, reduce='coi')]


def sat_min(nl, T, k, **kw):
    v, info, res = S.solve(nl, T, k, backend=BACKEND, **kw)
    assert v in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND'), v
    return (len(res['faults']) if res else None), res, info


def brute_job(a):
    n, T, kmax, budget = a
    t0 = time.time()
    path = os.path.join(ROOT, n['path'])
    kw, recorded = default_params(n)
    row = dict(path=n['path'], top=n['top'], T=T, **kw)
    try:
        nl = S.gs.Netlist(path, n['top'])
    except S.NetlistError as e:
        row.update(status='skipped', why='netlist rejected by the engine parser: ' + str(e)[:80]); return row
    row.update(nl.stats())
    try:
        ref = bruteforce.Ref(path, n['top'])
    except ValueError as e:
        row.update(status='skipped', why=str(e)); return row
    npairs = len(ref.sites) * T
    # exhaustive depth: largest j <= kmax with C(npairs, j) <= budget
    depth = 0
    while depth < kmax and math.comb(npairs, depth + 1) <= budget:
        depth += 1
    try:
        mins = []
        for cfg in CFGS:
            m, res, info = sat_min(nl, T, kmax, **kw, **cfg)
            mins.append(m)
            if res and not ref.witness_ok(T, res['faults'], res['inputs'], kw['goal_value'], kw['key']):
                row.update(status='MISMATCH', why=f'witness of config {cfg} does not replay on the exhaustive simulator'); return row
        if len(set(mins)) != 1:
            row.update(status='MISMATCH', why=f'configs disagree: {mins}'); return row
        m = mins[0]
        bm, tried, complete = ref.min_faults(T, depth, kw['goal_value'], kw['key'])
    except S.NetlistError as e:
        row.update(status='skipped', why='engine input error: ' + str(e)[:80]); return row
    row.update(sat_min=m, brute_min=bm, brute_depth=depth, brute_sets=tried, kmax=kmax)
    if bm is not None:
        ok = m == bm; proof = 'exhaustive minimum equal'
    elif m is None or m > depth:
        # exhaustive: no attack with <= depth flips. SAT says minimum m > depth (witness replayed above) or none <= kmax.
        ok = True
        proof = ('exhaustive none <= %d; SAT none <= %d' % (depth, kmax)) if m is None else \
                ('exhaustive none <= %d; SAT witness with %d replayed' % (depth, m))
        row['exact'] = (m is None and depth == kmax) or (m is not None and m == depth + 1)
    else:
        ok = False; proof = 'SAT found %s flips but exhaustive search found none <= %d' % (m, depth)
    row.update(status='ok' if ok else 'MISMATCH', why=proof, s=round(time.time() - t0, 1))
    return row


def recorded_checks():
    rows = []; skipped = []

    def add(src, path, top, T, k, exp_verdict, exp_min, **kw):
        try:
            nl = S.gs.Netlist(os.path.join(ROOT, path), top)
            m, res, info = sat_min(nl, T, k, **kw)
        except S.NetlistError as e:
            skipped.append(dict(source=src, netlist=path, why='rejected by the current engine parser/model: ' + str(e)[:90])); return
        v = 'ATTACK_FOUND' if m is not None else 'NO_ATTACK_UP_TO_BOUND'
        ok = v == exp_verdict and (exp_min is None or m == exp_min)
        rows.append(dict(source=src, netlist=path, T=T, k=k, expected=[exp_verdict, exp_min], got=[v, m], status='ok' if ok else 'MISMATCH'))
    # results/reproduce: given-netlist rows directly; rtl/plain rows on the stored plain-flow netlists when their
    # gate/flop counts equal the recorded ones (the recorded hash is of the Verilog file, so the match is by counts)
    for f in sorted(glob.glob(os.path.join(ROOT, 'results', 'reproduce', '*.json'))):
        d = json.load(open(f))
        src = 'results/reproduce/' + os.path.basename(f)
        if d['synth_flow'] == 'given-netlist':
            path = d['netlist_json']
        else:
            path = f"results/deep/work/nl/{d['top']}_rtl.json"
            ok = d['synth_flow'] == 'plain' and os.path.isfile(os.path.join(ROOT, path))
            if ok:
                ok = S.gs.Netlist(os.path.join(ROOT, path), d['top']).stats() == d['netlist']
            if not ok:
                skipped.append(dict(source=src, why=f"no stored netlist for synth flow {d['synth_flow']!r} with matching gate/flop count (needs yosys)")); continue
        add(src, path, d['top'], d['bound']['cycles'], d['bound']['max_faults'], d['verdict'], d.get('min_faults'))
    for d in ('v0', 'v1', 'v2'):
        f = os.path.join(ROOT, 'validation', 'data', f'spike_{d}_results.json')
        if os.path.isfile(f):
            for top, T, k, r, _, _ in json.load(open(f)):
                add(f'validation/data/spike_{d}_results.json', f'reference/spike_netlists/{d}.json', top, T, k,
                    'ATTACK_FOUND' if r == 'sat' else 'NO_ATTACK_UP_TO_BOUND', None)
    from common import heldout_params
    for b, h in sorted(heldout_params().items()):
        if h['recorded'] is None: continue
        p = f'research/c4/ver/gen/{b}'
        if not os.path.isfile(os.path.join(ROOT, p)): continue
        add('research/c4/ver/heldout.csv (full mask)', p, h['top'], 6, 3,
            'NO_ATTACK_UP_TO_BOUND' if h['recorded'] == '>3' else 'ATTACK_FOUND', None if h['recorded'] == '>3' else h['recorded'],
            goal_value=h['acc'], key=h['key'])
    add('docs/NUMBERS.md B2.v2.ok', 'reference/spike_netlists/v2.json', 'v2', 6, 1, 'ATTACK_FOUND', 1, goal_out='boot_ok', goal_value=1)
    return rows, skipped


def main():
    global BACKEND
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='py'); ap.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    ap.add_argument('--quick', action='store_true', help='smaller exhaustive budget (about a minute)')
    ap.add_argument('--out', default=os.path.join(FASTSAT, 'bench', 'results', 'verify_all.json'))
    a = ap.parse_args()
    BACKEND = a.backend
    t0 = time.time()
    rec, rec_skipped = recorded_checks()
    print(f'(a) recorded results: {sum(r["status"] == "ok" for r in rec)}/{len(rec)} equal, {len(rec_skipped)} skipped  [{time.time() - t0:.0f}s]', flush=True)
    for r in rec:
        if r['status'] != 'ok': print('   MISMATCH', r)
    nls = [n for n in repo_netlists() if n['ports'].get('sig', (None,))[0] == 'input' and n['ports'].get('boot_word', (None,))[0] == 'output']
    others = [n['path'] for n in repo_netlists() if n not in nls]
    budget = 3000 if a.quick else 160000
    jobs = []
    for n in nls:
        jobs.append((n, 6, 3, budget))
        jobs.append((n, 3, 3, budget))            # shorter horizon: deeper exhaustive depth on the same netlist
    with Pool(a.jobs) as pl:
        rows = pl.map(brute_job, jobs, chunksize=1)
    ok = [r for r in rows if r['status'] == 'ok']; bad = [r for r in rows if r['status'] == 'MISMATCH']; sk = [r for r in rows if r['status'] == 'skipped']
    print(f'(b) exhaustive simulator: {len(ok)} cells equal/consistent, {len(bad)} mismatches, {len(sk)} skipped, on {len(nls)} distinct netlists  [{time.time() - t0:.0f}s]')
    exact = [r for r in ok if r['brute_min'] is not None or r.get('exact')]
    print(f'    exact minimum established by exhaustion (+ replayed witness) in {len(exact)} cells; lower bound only in {len(ok) - len(exact)}')
    hist = {}
    for r in ok: hist[str(r['sat_min'])] = hist.get(str(r['sat_min']), 0) + 1
    print('    SAT minimum histogram over cells:', dict(sorted(hist.items())))
    for r in bad: print('   MISMATCH', r)
    print('    netlists without sig/boot_word ports (not covered here):', others)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(dict(label='MEASURED', backend=a.backend, quick=a.quick, wall_s=round(time.time() - t0, 1), recorded=rec, recorded_skipped=rec_skipped,
                   exhaustive=rows, not_covered=others), open(a.out, 'w'), indent=1)
    sys.exit(1 if bad or any(r['status'] != 'ok' for r in rec) else 0)


if __name__ == '__main__':
    main()
