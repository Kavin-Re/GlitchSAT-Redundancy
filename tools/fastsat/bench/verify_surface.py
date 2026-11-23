#!/usr/bin/env python3
"""Cross-check against the independent exhaustive oracle of ext/surface (scripts/attack_surface.py, `exhaustive`):
a bit-parallel numpy simulator written separately from this backend and from tests/bruteforce.py.

For every repository netlist with `sig` input and `boot_word` output ports (at most 16 free input bits), at each
horizon T in --cycles, budget k <= --k, goal/key as in verify_all.py (common.default_params):
  * SAT minimum (this backend, --backend, default the bundled Python solver),
  * oracle: every fault set of size 0, 1, 2, ... on the engine's `full` site set, stopping at the first size with an
    attack; complete when it finishes within --timeout-s per cell,
  * when the oracle is complete and finds attacks: the SAT witness must be one of the oracle's minimum attacks
    (fault set compared as a set of (net, cycle)).
Also re-reads ext/surface/results/surface_*.json (the minimums recorded there) and checks the SAT minimum for each.

Status per cell: ok (equal), consistent (oracle stopped early at size s with no attack below s; SAT minimum >= s),
MISMATCH. Exit 1 on any mismatch. Writes --out (JSON).

usage: verify_surface.py [--surface DIR] [--cycles 6 3] [--k 3] [--timeout-s 120] [--jobs N] [--backend py]
"""
import argparse, glob, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from common import S, ROOT, FASTSAT, repo_netlists, default_params

SURFACE = os.environ.get('GLITCHSAT_SURFACE') or os.path.normpath(os.path.join(FASTSAT, '..', 'surface'))
A = dict(backend='py', timeout=120, k=3, batch=50000)


def oracle():
    sys.path.insert(0, os.path.join(SURFACE, 'scripts'))
    import attack_surface
    return attack_surface


def cell(job):
    n, T = job
    AS = oracle()
    kw, _ = default_params(n)
    row = dict(path=n['path'], top=n['top'], T=T, k=A['k'], goal_value=kw['goal_value'], key=kw['key'])
    try:
        nl = S.gs.Netlist(os.path.join(ROOT, n['path']), n['top'])
    except S.NetlistError as e:
        row.update(status='skipped', why='rejected by the engine parser: ' + str(e)[:80]); return row
    row.update(nl.stats())
    t0 = time.time()
    try:
        v, info, res = S.solve(nl, T, A['k'], backend=A['backend'], **kw)
    except S.NetlistError as e:
        row.update(status='skipped', why='engine input error: ' + str(e)[:80]); return row
    row['sat_s'] = round(time.time() - t0, 3)
    if v not in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND'):
        row.update(status='skipped', why='SAT verdict ' + v); return row
    m = len(res['faults']) if res else None
    wit = {(nl.names.get(b, str(b)), t) for t, b in res['faults']} if res else None
    t0 = time.time()
    try:
        o = AS.exhaustive(nl, T, A['k'], goal_value=kw['goal_value'], key=kw['key'], timeout_s=A['timeout'], batch=A['batch'])
    except ValueError as e:
        row.update(status='skipped', why='oracle: ' + str(e)[:80], sat_min=m); return row
    except S.NetlistError as e:
        row.update(status='skipped', why='oracle input error: ' + str(e)[:80], sat_min=m); return row
    row['oracle_s'] = round(time.time() - t0, 2)
    row.update(sat_min=m, oracle_verdict=o['verdict'], oracle_min=o['min_faults'], oracle_sets=o['sets_simulated'],
               oracle_complete=o['complete'], oracle_attacks=len(o['attacks']))
    if o['verdict'] == 'INCOMPLETE':
        s = o.get('searched_below', 0)       # no attack with fewer than s flips; size s not finished
        ok = m is None or m >= s
        row.update(status='consistent' if ok else 'MISMATCH', why=f'oracle: no attack with < {s} flips (stopped at size {s})')
        return row
    if o['verdict'] == 'NO_ATTACK_UP_TO_BOUND':
        row.update(status='ok' if m is None else 'MISMATCH', why='oracle: none <= %d' % A['k']); return row
    if m != o['min_faults']:
        row.update(status='MISMATCH', why=f"oracle min {o['min_faults']}, SAT min {m}"); return row
    if o['complete']:
        sets = {frozenset((nl.names.get(b, str(b)), t) for t, b in a) for a, _ in o['attacks']}
        row['witness_in_oracle_set'] = frozenset(wit) in sets
        if not row['witness_in_oracle_set']:
            row.update(status='MISMATCH', why='SAT witness is not among the oracle minimum attacks'); return row
    row.update(status='ok', why='minimum equal' + (', witness in the oracle set' if o['complete'] else ''))
    return row


def recorded_surface():
    """Minimums recorded in ext/surface/results/surface_*.json."""
    out = []
    for f in sorted(glob.glob(os.path.join(SURFACE, 'results', 'surface_*.json'))):
        d = json.load(open(f))
        p = d['netlist']
        if not os.path.isabs(p):
            p = os.path.join(ROOT, p)
        if not os.path.isfile(p):                  # recorded on another checkout: find the same relative path here
            parts = p.split(os.sep)
            for i in range(len(parts)):
                cand = os.path.join(ROOT, *parts[i:])
                if os.path.isfile(cand):
                    p = cand; break
        b = d['bound']
        row = dict(source='ext/surface/results/' + os.path.basename(f), netlist=os.path.relpath(p, ROOT), T=b['cycles'],
                   k=b['max_faults'], recorded=[d['verdict'], d['min_faults'], d.get('count'), d.get('complete')])
        try:
            nl = S.gs.Netlist(p, d['top'])
            v, info, res = S.solve(nl, b['cycles'], b['max_faults'], backend=A['backend'], key=b['key'],
                                   goal_value=int(b['goal'].split('==')[1].split()[0], 0))
        except Exception as e:          # noqa: BLE001 - reported, not hidden
            row.update(status='skipped', why=str(e)[:100]); out.append(row); continue
        m = len(res['faults']) if res else None
        row['sat'] = [v, m]
        if d['verdict'] in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND'):
            ok = v == d['verdict'] and m == d['min_faults']
        else:
            ok = True
        row['status'] = 'ok' if ok else 'MISMATCH'
        if res and d.get('complete') and d['verdict'] == 'ATTACK_FOUND' and d.get('count', 0) <= len(d.get('attacks', [])):
            sets = {frozenset((x[0], x[1]) for x in a['faults']) for a in d['attacks']}
            row['witness_in_recorded_set'] = frozenset((nl.names.get(bb, str(bb)), t) for t, bb in res['faults']) in sets
            if not row['witness_in_recorded_set']:
                row['status'] = 'MISMATCH'
        out.append(row)
    return out


def _init(a):
    A.update(a)


def run_cells(jobs, n):
    """Run cell() in worker processes. A worker that dies (e.g. killed for memory) marks its cell 'skipped' instead of
    hanging the run (multiprocessing.Pool waits forever for a task lost with a dead worker)."""
    rows = [None] * len(jobs); todo = list(range(len(jobs)))
    while todo:
        with ProcessPoolExecutor(n, initializer=_init, initargs=(dict(A),)) as ex:
            futs = {i: ex.submit(cell, jobs[i]) for i in todo}
            broken = []
            for i, f in futs.items():
                try:
                    rows[i] = f.result()
                except BrokenProcessPool:
                    broken.append(i)
        if len(broken) == len(todo):                 # nothing finished: give up on these cells, one at a time
            i = broken.pop(0)
            rows[i] = dict(path=jobs[i][0]['path'], top=jobs[i][0]['top'], T=jobs[i][1], status='skipped',
                           why='worker process died (out of memory?)')
            print('    skipped (worker died):', jobs[i][0]['path'], 'T=%d' % jobs[i][1], flush=True)
        todo = broken
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='py'); ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--cycles', type=int, nargs='+', default=[6, 3]); ap.add_argument('--timeout-s', type=float, default=120)
    ap.add_argument('--batch', type=int, default=50000, help='fault sets per oracle batch (memory)')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    ap.add_argument('--out', default=os.path.join(FASTSAT, 'bench', 'results', 'verify_surface.json'))
    a = ap.parse_args()
    A.update(backend=a.backend, timeout=a.timeout_s, k=a.k, batch=a.batch)
    if not os.path.isfile(os.path.join(SURFACE, 'scripts', 'attack_surface.py')):
        sys.exit(f'ext/surface not found at {SURFACE}; set GLITCHSAT_SURFACE')
    t0 = time.time()
    rec = recorded_surface()
    print(f'(a) ext/surface recorded minimums: {sum(r["status"] == "ok" for r in rec)}/{len(rec)} equal '
          f'({sum(1 for r in rec if r.get("witness_in_recorded_set"))} SAT witnesses found in a complete recorded attack list), '
          f'{sum(r["status"] == "skipped" for r in rec)} skipped', flush=True)
    for r in rec:
        print(f"    {r['source']:<45} T={r['T']} recorded {r['recorded'][:2]} SAT {r.get('sat')} {r['status']}")
    nls = [n for n in repo_netlists() if n['ports'].get('sig', (None,))[0] == 'input' and n['ports'].get('boot_word', (None,))[0] == 'output']
    jobs = [(n, T) for n in nls for T in a.cycles]
    rows = run_cells(jobs, a.jobs)
    st = {}
    for r in rows:
        st[r['status']] = st.get(r['status'], 0) + 1
    print(f'(b) exhaustive oracle (ext/surface) on {len(nls)} netlists x T in {a.cycles}, k <= {a.k}: {st}  [{time.time() - t0:.0f}s]')
    print(f"    witness inside the complete oracle attack set: {sum(1 for r in rows if r.get('witness_in_oracle_set'))} cells")
    for r in rows:
        if r['status'] == 'MISMATCH':
            print('   MISMATCH', r)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(dict(label='MEASURED', backend=a.backend, oracle='ext/surface scripts/attack_surface.py exhaustive',
                   wall_s=round(time.time() - t0, 1), recorded=rec, cells=rows), open(a.out, 'w'), indent=1)
    bad = any(r['status'] == 'MISMATCH' for r in rows + rec)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
