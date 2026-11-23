#!/usr/bin/env python3
"""GlitchSAT ext/opentitan: one table from the solver JSON files of one run.py/run.sh pass.
Own code, Apache-2.0.

usage: summarise.py RESULTS_DIR experiments.tsv BUILD_DIR
Prints a text table and writes RESULTS_DIR/summary.csv. Rows come only from files that exist;
a run without a JSON file (timeout, error) shows as UNKNOWN or ERROR from its log.
"""
import csv
import json
import os
import sys


def rows(tsv):
    with open(tsv) as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            p = line.rstrip('\n').split('\t')
            yield dict(id=p[0], top=p[1], goal=p[5], key=p[6], cycles=p[7], kmax=int(p[8]), prediction=p[9])


def first_line(path):
    try:
        with open(path) as f:
            return f.readline().strip()
    except OSError:
        return ''


def main(argv):
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(3)
    res, tsv, build = argv[1], argv[2], argv[3]
    out = []
    for e in rows(tsv):
        for k in range(1, 10):
            pre = os.path.join(res, f"{e['id']}_k{k}")
            if not os.path.exists(pre + '.log'):
                continue
            r = dict(experiment=e['id'], k=k, verdict='', min_faults='', faults='', gates='', flops='',
                     cycles='', legit_reaches_goal='', solve_s='', netlist_sha256='', fastsat='',
                     prediction=e['prediction'])
            try:
                with open(pre + '.json') as f:
                    d = json.load(f)
                r.update(verdict=d['verdict'], gates=d['netlist']['gates'], flops=d['netlist']['flops'],
                         cycles=d['bound']['cycles'], legit_reaches_goal=d['honest_key_boots_fault_free'],
                         solve_s=d['runtime_s']['solve_and_minimize'])
                if 'min_faults' in d:
                    r['min_faults'] = d['min_faults']
                    r['faults'] = '; '.join(f"{x['net']}@{x['cycle']}({x['kind']})" for x in d['faults'])
            except (OSError, ValueError, KeyError):
                line = first_line(pre + '.log')
                r['verdict'] = 'UNKNOWN/ERROR' + (f' ({line[:80]})' if line else '')
            meta = os.path.join(build, e['id'], 'meta.txt')
            try:
                with open(meta) as f:
                    for line in f:
                        if line.startswith('netlist_sha256:'):
                            r['netlist_sha256'] = line.split(':', 1)[1].strip()[:16]
            except OSError:
                pass
            fs = pre + '.fastsat.json'
            if os.path.exists(fs):
                try:
                    with open(fs) as f:
                        fd = json.load(f)
                    agree = (fd.get('verdict') == r['verdict'] and fd.get('min_faults', '') == r['min_faults'])
                    r['fastsat'] = f"{fd.get('verdict')} {fd.get('min_faults', '')}" + ('' if agree else '  DISAGREES')
                except (OSError, ValueError):
                    r['fastsat'] = 'unreadable'
            out.append(r)
    cols = ['experiment', 'k', 'cycles', 'gates', 'flops', 'verdict', 'min_faults', 'solve_s',
            'legit_reaches_goal', 'netlist_sha256', 'fastsat', 'faults', 'prediction']
    with open(os.path.join(res, 'summary.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print('Summary of this run (produced by the commands above on this machine). Bounded verdicts only.')
    print('The prediction column is what was expected from reading the code before any run; it is not a result.')
    short = cols[:10]
    widths = {c: max(len(c), *(len(str(r[c])) for r in out)) if out else len(c) for c in short}
    print('  '.join(c.ljust(widths[c]) for c in short))
    for r in out:
        print('  '.join(str(r[c]).ljust(widths[c]) for c in short))
    print()
    for r in out:
        if r['faults'] or r['fastsat']:
            print(f"{r['experiment']} k={r['k']}: faults {r['faults'] or '-'}" + (f" | fastsat {r['fastsat']}" if r['fastsat'] else ''))
    print()
    seen = set()
    for r in out:
        if r['experiment'] not in seen:
            seen.add(r['experiment'])
            print(f"{r['experiment']}: prediction was: {r['prediction']}")


if __name__ == '__main__':
    main(sys.argv)
