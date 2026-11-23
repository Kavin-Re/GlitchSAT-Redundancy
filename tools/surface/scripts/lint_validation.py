#!/usr/bin/env python3
"""Compare the redundancy-merge lint verdict with the minimum number of flips, on every stored V2-family netlist.

For each distinct (by SHA-256) Yosys JSON netlist in the repository whose top module is v2, v2e, v2c04, v2c4d, v2c5a or
v2_wi (plus v1 netlists as a control), it records:
  * the lint verdict (auto mode: hierarchy names when present, else structural grouping with --copies 3, or 2 for v1),
  * the minimum flips MEASURED here with the exhaustive simulator (attack_surface.exhaustive, T cycles, sizes <= k,
    stopping at the first attack of the minimum size), and
  * the minimum recorded in the repository where a file states it for that exact netlist (RECORDED below).
Then a confusion table: lint "merged" vs measured minimum == 1.

Usage: python3 lint_validation.py [--cycles 6] [--k 3] [--timeout-s 600] [--json out.json] [--md out.md]
"""
import argparse, collections, hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import merge_lint, attack_surface   # noqa: E402

TOPS = {'v2': 3, 'v2e': 3, 'v2c04': 3, 'v2c4d': 3, 'v2c5a': 3, 'v2_wi': 3, 'v1': 2}

# sha256 prefix (16) -> (recorded minimum flips at T=6 unless noted, source file)
RECORDED = {
    '289355dc483b9e6a': (3, 'results/reproduce/v2_spike_given-netlist_k3.json'),
    '4c6cea5e7392a51f': (1, 'validation/VALIDATION.md (flow B: 4 of 378 single flips succeed)'),
    'f954078f944ab7a2': (2, 'research/c6/p12/enum.json (V2-apt, T=4)'),
    '0454bf4a8b04d33c': (2, 'research/c2/e2_variance/raw/matrix.csv (apt0.33 plain baseline)'),
    '72fd54da6554fb06': (3, 'research/c2/e2_variance/raw/matrix.csv (conda-eda0.38 plain baseline)'),
    '4ca175d0a3fb5355': (3, 'research/c2/e2_variance/raw/matrix.csv (conda-formal0.38 plain baseline)'),
    '239ea9b919b64806': (3, 'research/c3/rep/rep_results.csv (orig_unit)'),
    '005b02a5d7a79f30': (3, 'research/c6/p01/glitchsat_cross.txt (apt v2e); research/c6/p12/enum.json (T=4)'),
    '84730fa7b5e3dbef': (1, 'results/reproduce (V1 spike, k=1)'),
    '214a2987170feb50': (2, 'research/c6/p01/glitchsat_cross.txt (apt v2)'),
    '152aad31162f5775': (3, 'research/c6/p01/glitchsat_cross.txt (conda v2)'),
    'a2aa7119f3e45462': (3, 'research/c6/p01/glitchsat_cross.txt (conda v2e)'),
}
PREFER = ('reference/', 'validation/', 'research/', 'results/')


def find_netlists(root):
    seen = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ('.git', 'node_modules')]
        for f in sorted(fn):
            if not f.endswith('.json'):
                continue
            p = os.path.join(dp, f)
            if os.path.getsize(p) > 5_000_000:
                continue
            try:
                with open(p) as fh:
                    d = json.load(fh)
            except (ValueError, OSError):
                continue
            if not (isinstance(d, dict) and isinstance(d.get('modules'), dict)):
                continue
            for top in d['modules']:
                if top in TOPS:
                    with open(p, 'rb') as fh:
                        h = hashlib.sha256(fh.read()).hexdigest()
                    seen.setdefault(h, [None, top, []])[2].append(os.path.relpath(p, root))
    for h, v in seen.items():   # show the copy under reference/ or validation/ first when the same file is stored twice
        v[0] = sorted(v[2], key=lambda q: (next((i for i, pre in enumerate(PREFER) if q.startswith(pre)), 9), q))[0]
    return seen


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cycles', type=int, default=6)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--timeout-s', type=float, default=600)
    ap.add_argument('--json')
    ap.add_argument('--md')
    a = ap.parse_args(argv)
    root = merge_lint._repo_root()
    GS = merge_lint.engine()
    rows = []
    for h, (path, top, copies) in sorted(find_netlists(root).items(), key=lambda kv: (kv[1][1], kv[1][0])):
        full = os.path.join(root, path)
        row = dict(netlist=path, identical_copies=sorted(set(copies) - {path}), top=top, sha16=h[:16])
        try:
            nl = GS.Netlist(full, top)
        except GS.NetlistError as e:
            row.update(error=str(e)); rows.append(row); continue
        row.update(gates=len(nl.drivers), flops=len(nl.dffs))
        r = merge_lint.lint(nl, expected_copies=TOPS[top])
        row.update(lint_mode=r['mode'], lint_verdict=r['verdict'], single_points=len(r['single_points']),
                   structural_groups=len(r['structural_groups']),
                   first_points=[s['net'] for s in r['single_points'] if s['kind'] == 'shared' or s.get('first')][:3])
        t0 = time.time()
        try:
            ex = attack_surface.exhaustive(nl, a.cycles, a.k, cap=1, timeout_s=a.timeout_s)
            row.update(measured_min=ex['min_faults'], measured_verdict=ex['verdict'], measured_s=round(time.time() - t0, 1),
                       measured_complete_minimum=ex['verdict'] != 'INCOMPLETE')
        except (ValueError, GS.NetlistError) as e:
            row.update(measured_min=None, measured_verdict='ERROR: ' + str(e))
        rec = RECORDED.get(h[:16])
        row.update(recorded_min=rec[0] if rec else None, recorded_source=rec[1] if rec else None)
        rows.append(row)
        print(f"{path:60s} {top:6s} lint={row['lint_verdict']:16s} measured_min={row['measured_min']} recorded={row['recorded_min']} ({row.get('measured_s')} s)", flush=True)
    def confusion(rows):
        conf = collections.Counter()
        for r in rows:
            if 'lint_verdict' not in r:
                continue
            if r.get('measured_min') is None and r.get('measured_verdict') != 'NO_ATTACK_UP_TO_BOUND':
                continue
            conf[(r['lint_verdict'] == 'merged', r.get('measured_min') == 1)] += 1
        return {'lint merged, min 1': conf[(True, True)], 'lint merged, min > 1': conf[(True, False)],
                'lint not merged, min 1': conf[(False, True)], 'lint not merged, min > 1': conf[(False, False)]}
    by_family = {'v1 (control)': confusion([r for r in rows if r['top'] == 'v1']),
                 'v2 family': confusion([r for r in rows if r['top'] != 'v1'])}
    conf = collections.Counter()
    for r in rows:
        if 'lint_verdict' not in r:
            continue
        if r.get('measured_min') is None and r.get('measured_verdict') != 'NO_ATTACK_UP_TO_BOUND':
            continue   # incomplete or error: not counted
        conf[(r['lint_verdict'] == 'merged', r.get('measured_min') == 1)] += 1
    table = {'lint merged, min 1': conf[(True, True)], 'lint merged, min > 1': conf[(True, False)],
             'lint not merged, min 1': conf[(False, True)], 'lint not merged, min > 1': conf[(False, False)]}
    out = dict(cycles=a.cycles, k=a.k, rows=rows, confusion=table, confusion_by_family=by_family,
               note='MEASURED here: lint verdict and exhaustive minimum (same modelled fault model as scripts/glitchsat.py, '
                    f'T={a.cycles}, sizes <= {a.k}). Recorded minima are copied from the named files, not re-run.')
    print(json.dumps(table)); print(json.dumps(by_family))
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(out, f, indent=2)
    if a.md:
        L = ['| netlist | top | gates | lint (mode) | single points | measured min | recorded min (source) |', '|---|---|---|---|---|---|---|']
        for r in rows:
            L.append(f"| `{r['netlist']}` | {r['top']} | {r.get('gates')} | {r.get('lint_verdict')} ({r.get('lint_mode')}) | "
                     f"{r.get('single_points')} | {r.get('measured_min') if r.get('measured_min') is not None else r.get('measured_verdict')} | "
                     f"{r['recorded_min'] if r.get('recorded_min') is not None else '-'}{' (' + r['recorded_source'] + ')' if r.get('recorded_source') else ''} |")
        for name, t in [('all', table)] + list(by_family.items()):
            L += ['', f'{name}:', '', '| | measured min 1 | measured min > 1 |', '|---|---|---|',
                  f"| lint merged | {t['lint merged, min 1']} | {t['lint merged, min > 1']} |",
                  f"| lint not merged | {t['lint not merged, min 1']} | {t['lint not merged, min > 1']} |"]
        with open(a.md, 'w') as f:
            f.write('\n'.join(L) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
