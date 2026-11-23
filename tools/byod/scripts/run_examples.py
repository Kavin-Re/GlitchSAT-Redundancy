#!/usr/bin/env python3
"""Run every gallery example (each variant) and write examples/<name>/expected_results.json.

  python3 scripts/run_examples.py [--only NAME] [--check] [--quick] [--examples DIR]
  --check: compare with the stored file instead of writing it; exits 1 on any difference, error or missing run.
The stored values are what `glitchsat run` gives here (MEASURED); tests/test_examples.py re-runs the fast parts.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from glitchsat_byod.run import run_project          # noqa: E402
from glitchsat_byod.errors import GSError           # noqa: E402

EX = os.path.join(os.path.dirname(HERE), 'examples')


def summary(rep):
    out = dict(top=rep['top'], frontend=rep['frontend'], checks={})
    for c in rep['checks']:
        A = c.get('analyses', {})
        mf = A.get('min_faults', {})
        d = dict(verdict=mf.get('verdict'), min_faults=mf.get('min_faults'), max_faults=c.get('max_faults'), horizon=c.get('horizon'),
                 witness=[(f['cycle'], f['site'], f['type']) for f in (mf.get('witness') or {}).get('faults', [])],
                 validation={fl: (x.get('validation') or {}).get('mismatch', 'not run') is None for fl, x in c.get('flows', {}).items()})
        if A.get('survival'):
            d['survival'] = {r['flow']: r.get('min_faults') if r.get('min_faults') is not None else r['verdict'] for r in A['survival']['rows']}
        if A.get('attack_surface', {}).get('count') is not None:
            d['attack_surface'] = dict(count=A['attack_surface']['count'], complete=A['attack_surface']['complete'])
        if A.get('unbounded', {}).get('verdict'):
            d['unbounded'] = dict(verdict=A['unbounded']['verdict'], k=A['unbounded'].get('k'))
        if A.get('merge_lint', {}).get('countermeasures') is not None:
            d['merge_lint'] = {cm['title']: {s['stage']: s['verdict'] for s in cm['stages']} for cm in A['merge_lint']['countermeasures']}
        out['checks'][c['id']] = d
    return out


def variants(name):
    les = json.load(open(os.path.join(EX, name, 'lesson.json')))
    return [(r.get('file', 'glitchsat.yaml'), r.get('task') or None, r.get('expect')) for r in les['runs']]


def portable(text):
    """No absolute paths of this computer in a shipped file: folders become $GLITCHSAT_LIBS, <repository>, <byod>, ~."""
    from glitchsat_byod.engine import repo_root
    from glitchsat_byod.flows import libs_dir
    import shutil
    pairs = [(os.path.realpath(libs_dir()), '$GLITCHSAT_LIBS'), (libs_dir(), '$GLITCHSAT_LIBS'),
             (os.path.dirname(HERE), '<byod>'), (os.path.realpath(os.path.dirname(HERE)), '<byod>')]
    if repo_root():
        pairs.append((repo_root(), '<repository>'))
    for tool in ('cadical', 'kissat', 'yosys'):
        w = shutil.which(tool)
        if w:
            pairs.append((os.path.dirname(w), '<bin>'))
    for k in ('GLITCHSAT_YOSYS', 'GLITCHSAT_YOSYS_SLANG'):
        if os.environ.get(k):
            pairs.append((os.path.dirname(os.environ[k]), '<bin>'))
    pairs.append((os.path.expanduser('~'), '~'))
    import tempfile
    pairs.append((tempfile.gettempdir(), '<tmp>'))
    for a, b in sorted(pairs, key=lambda x: -len(x[0])):
        if a and a != os.sep:
            text = text.replace(a, b)
    return text


def _n(k, one, many):
    return '%d %s' % (k, one if k == 1 else many)


def readme(name):
    """Rewrite the results table and the lesson text of examples/<name>/README.md from the stored results."""
    p = os.path.join(EX, name, 'README.md')
    er = json.load(open(os.path.join(EX, name, 'expected_results.json')))
    les = json.load(open(os.path.join(EX, name, 'lesson.json')))
    rows = ['| command | smallest attack (within the horizon) | any number of cycles | other builds | analysed netlist = RTL in simulation |',
            '|---|---|---|---|---|']
    for f, task, expect in variants(name):
        key = '%s%s' % (f, (' --task ' + task) if task else '')
        r = er.get(key) or {}
        cmd = 'glitchsat run' + ('' if f == 'glitchsat.yaml' else ' ' + f) + (' --task ' + task if task else '')
        for cid, c in (r.get('checks') or {}).items():
            m = c.get('min_faults')
            sm = _n(m, 'fault', 'faults') if m is not None else 'no attack with up to %s' % _n(c['max_faults'], 'fault', 'faults')
            u = c.get('unbounded') or {}
            ub = ('proved for any number of cycles with %s' % _n(u['k'], 'fault', 'faults') if u.get('verdict') == 'PROVED_UNBOUNDED'
                  else 'not decided in the time limit' if u.get('verdict') else '-')
            sv = c.get('survival')
            other = ', '.join('%s: %s' % (k, v if isinstance(v, int) else 'no attack up to %d' % c['max_faults'] if v == 'NO_ATTACK_UP_TO_BOUND' else v)
                              for k, v in sv.items()) if sv else '-'
            ok = 'yes' if c.get('validation') and all(c['validation'].values()) else 'no'
            rows.append('| `%s` | %s | %s | %s | %s |' % (cmd, sm, ub, other, ok))
    text = open(p).read()
    a = text.index('## Expected results')
    head = text[:a]
    body = ('## Expected results (MEASURED by `python3 scripts/run_examples.py`, stored in expected_results.json)\n\n' + '\n'.join(rows) +
            '\n\nThe fault model is the same in every build: each build is normalised to plain D flip-flops plus gates, and a '
            'flip-flop\'s fault site is its stored value. Without Yosys, the Studio shows the saved full reports in `saved/` '
            '(labelled RECORDED).\n\n' + les.get('lesson_after', '') + '\n')
    open(p, 'w').write(head + body)


def saved_name(key):
    """File name of the saved full report of one gallery run (used by the Studio when Yosys is not installed)."""
    return key.replace('.yaml', '').replace(' --task ', '.') + '.report.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only'); ap.add_argument('--check', action='store_true'); ap.add_argument('--quick', action='store_true')
    ap.add_argument('--examples', help='gallery folder (default: examples/ next to this script)')
    ap.add_argument('--readme', action='store_true', help='only rewrite the example READMEs from the stored results')
    a = ap.parse_args()
    global EX
    if a.examples:
        EX = os.path.abspath(a.examples)
    if a.readme:
        for name in sorted(os.listdir(EX)):
            if os.path.isfile(os.path.join(EX, name, 'lesson.json')) and (not a.only or name == a.only):
                readme(name)
        return 0
    bad = 0
    for name in sorted(os.listdir(EX)):
        if a.only and name != a.only or not os.path.isfile(os.path.join(EX, name, 'lesson.json')):
            continue
        res = {}
        reports = {}
        for f, task, expect in variants(name):
            key = '%s%s' % (f, (' --task ' + task) if task else '')
            t0 = time.time()
            try:
                rep, spec = run_project(os.path.join(EX, name, f), task, quick=a.quick)
                res[key] = dict(summary(rep), expect_in_words=expect, runtime_s=round(time.time() - t0, 1), label='MEASURED')
                reports[key] = rep
            except GSError as e:
                res[key] = dict(error=e.to_json())
            print('%-16s %-32s %s %ss%s' % (name, key, json.dumps({k: (v['verdict'], v['min_faults']) for k, v in res[key].get('checks', {}).items()}),
                                           res[key].get('runtime_s'), ('  ERROR ' + res[key]['error']['code'] + ': ' + res[key]['error']['message'])
                                           if res[key].get('error') else ''), flush=True)
        p = os.path.join(EX, name, 'expected_results.json')
        if a.check:
            old = json.load(open(p)) if os.path.isfile(p) else {}
            for k in sorted(set(old) | set(res)):
                v, o = res.get(k), old.get(k)
                if v is None or o is None:
                    print('  DIFFERS %s %s: %s' % (name, k, 'not stored' if o is None else 'not run now'))
                    bad += 1
                    continue
                if v.get('error') or o.get('error'):
                    if (v.get('error') or {}).get('code') != (o.get('error') or {}).get('code') or v.get('error'):
                        print('  DIFFERS %s %s: %s' % (name, k, 'error now: %s' % v['error']['message'] if v.get('error')
                                                       else 'stored result is an error'))
                        bad += 1
                    continue
                if set(v.get('checks', {})) != set(o.get('checks', {})):
                    print('  DIFFERS %s %s: checks %s, stored %s' % (name, k, sorted(v.get('checks', {})), sorted(o.get('checks', {}))))
                    bad += 1
                for cid, c in v.get('checks', {}).items():
                    oc = o.get('checks', {}).get(cid)
                    if oc is None:
                        continue
                    for fld in ('verdict', 'min_faults', 'survival', 'unbounded'):
                        if fld in oc and oc.get(fld) != c.get(fld) and not (a.quick and fld == 'unbounded'):
                            print('  DIFFERS %s %s %s %s: stored %s, now %s' % (name, k, cid, fld, oc.get(fld), c.get(fld)))
                            bad += 1
        else:
            with open(p, 'w') as fo:
                json.dump(res, fo, indent=1)
            sd = os.path.join(EX, name, 'saved')
            os.makedirs(sd, exist_ok=True)
            for key, rep in reports.items():
                rep = dict(rep, label='RECORDED', recorded_note='saved by scripts/run_examples.py; shown when Yosys is not installed')
                rep.pop('progress', None)
                with open(os.path.join(sd, saved_name(key)), 'w') as fo:
                    fo.write(portable(json.dumps(rep, indent=None, separators=(',', ':'), default=str)))
    if a.check:
        print('run_examples --check: %s' % ('all results reproduce the stored ones' if not bad else '%d difference(s)' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
