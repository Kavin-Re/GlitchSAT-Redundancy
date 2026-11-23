#!/usr/bin/env python3
"""GlitchSAT Labs, OpenTitan hardening primitives: build 3 real OpenTitan primitives from the pinned sources with
Yosys 0.71 (read_slang) + Yosys 0.33, find the smallest number of bit flips that breaks each one, and check that
its countermeasure survived synthesis.

Example (smallest meaningful set, under a minute):
  mubi_flag   prim_mubi4_sender -> sync -> dec: a 4-bit "multi-bit boolean" decoded to one flag
  mubi_word   prim_mubi4_sender -> sync: the 4-bit word itself
  count_regs  prim_count: primary up counter + secondary down counter, a fault makes them disagree

Everything is built into labs/work/ (OT_WORK), never over the recorded results in work/.
usage: run_labs.py [--ids mubi_flag,mubi_word,count_regs] [--out results/labs_result.json]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXT = os.environ.get('GLITCHSAT_EXT') or (lambda _d: _d if os.path.isdir(os.path.join(_d, 'fastsat')) else os.path.join(_d, 'ext'))(os.path.dirname(os.path.dirname(ROOT)))
sys.path.insert(0, os.path.join(EXT, 'labs'))
import labs_result as LR  # noqa: E402

WORK = os.path.join(HERE, 'work')
PY = sys.executable
SURVIVAL = {'mubi_word': 'mubi.yaml', 'count_regs': 'count.yaml'}
IDS = ['mubi_flag', 'mubi_word', 'count_regs']
WHAT = {'mubi_flag': 'OpenTitan multi-bit boolean (prim_mubi4 sender, sync, decoder) ending in one flag',
        'mubi_word': 'OpenTitan multi-bit boolean word (prim_mubi4 sender and sync)',
        'count_regs': 'OpenTitan prim_count redundant counter pair (up and down copies)'}


def sh(cmd, env, timeout=540):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def survival_cfg(i):
    """Copy of survival/<cfg>.yaml with paths pointing at this Labs build."""
    src = os.path.join(ROOT, 'survival', SURVIVAL[i])
    txt = open(src).read().replace('../work/%s/' % i, os.path.join(WORK, i) + '/').replace('../src/', os.path.join(ROOT, 'src') + '/')
    p = os.path.join(WORK, i, 'survival.yaml')
    open(p, 'w').write(txt)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default=','.join(IDS))
    ap.add_argument('--out', default=os.path.join(HERE, 'results', 'labs_result.json'))
    a = ap.parse_args(argv)
    t0, started, errors, rows = time.time(), LR.now(), [], {}
    env = dict(os.environ, OT_WORK=WORK, TIMEOUT_S=os.environ.get('TIMEOUT_S', '240'))
    os.makedirs(WORK, exist_ok=True)
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import build  # noqa: E402
    tsv = {e['id']: e for e in build.read_tsv()}
    ids = a.ids.split(',')
    rc, out = sh([PY, os.path.join(ROOT, 'scripts', 'build.py')] + ids, env)
    for i in ids:
        row = dict(prediction=tsv[i]['prediction'], kmax=tsv[i]['kmax'], cycles=tsv[i]['cycles'])
        bj = os.path.join(WORK, i, 'build.json')
        if not os.path.exists(bj) or ('[%s] built' % i) not in out:
            errors.append('%s: build failed: %s' % (i, out[-600:]))
            rows[i] = row
            continue
        b = json.load(open(bj))
        row['build'] = {k: b[k] for k in ('gates', 'flops', 'gates71', 'flops71', 'yosys_elab', 'yosys_synth', 'net_sha256')}
        rc2, out2 = sh([PY, os.path.join(ROOT, 'scripts', 'run.py'), '--force', '--only', 'scale,legit', i], env)
        for name in ('scale', 'legit'):
            p = os.path.join(WORK, i, 'runs', name + '.json')
            r = (json.load(open(p))['result'] or {}) if os.path.exists(p) else {}
            row[name] = {k: r.get(k) for k in ('status', 'lo', 'hi', 'text', 'note', 'runtime_s')}
            if not r:
                errors.append('%s: %s run gave no result: %s' % (i, name, out2[-400:]))
        rec = os.path.join(ROOT, 'work', i, 'runs', 'scale.json')
        if os.path.exists(rec):
            rr = json.load(open(rec))['result'] or {}
            row['recorded'] = {k: rr.get(k) for k in ('status', 'lo', 'hi')}
        if i in SURVIVAL:
            net = os.path.join(WORK, i, 'net.json')
            sh([PY, os.path.join(ROOT, 'scripts', 'name_flops.py'), net, tsv[i]['top'], os.path.join(WORK, i, 'net_named.json')], env)
            sj = os.path.join(WORK, i, 'survival.json')
            rc3, out3 = sh([PY, os.path.join(EXT, 'checker', 'glitchsat'), 'check-survival', survival_cfg(i), '--json', sj,
                            '--quiet'], env)
            if os.path.exists(sj):
                s = json.load(open(sj))
                row['survival'] = [dict(id=c['id'], verdict=c['verdict']) for c in s['countermeasures']]
            else:
                errors.append('%s: survival check gave no result (exit %s): %s' % (i, rc3, out3[-400:]))
        rows[i] = row

    findings = []
    for i in ids:
        r = rows.get(i, {})
        if 'build' not in r:
            continue
        bd = r['build']
        findings.append(LR.finding('%s.build' % i, '%s: built from the pinned OpenTitan sources with %s (read_slang) and %s: '
                                   '%d gates, %d flip-flops (Yosys 0.71 alone: %d gates, %d flip-flops).' % (
                                       WHAT[i], bd['yosys_elab'].split(' (')[0], bd['yosys_synth'].split(' (')[0],
                                       bd['gates'], bd['flops'], bd['gates71'], bd['flops71']), 'MEASURED', **bd))
        sc = r.get('scale') or {}
        if sc.get('status'):
            if sc.get('lo') is not None and sc.get('lo') == sc.get('hi'):
                ans = 'the smallest attack needs %d bit flip(s)' % sc['lo']
            elif sc.get('status') == 'EXACT' or sc.get('lo') is None:
                ans = 'result %s' % sc['status']
            else:
                ans = 'between %s and %s bit flips (not narrowed down)' % (sc.get('lo'), sc.get('hi'))
            if sc.get('hi') is None and sc.get('lo') is not None and sc['lo'] > r['kmax']:
                ans = 'no attack with up to %d bit flips within %d cycles' % (r['kmax'], r['cycles'])
            rec = r.get('recorded') or {}
            same = rec and rec.get('lo') == sc.get('lo') and rec.get('hi') == sc.get('hi')
            findings.append(LR.finding('%s.min_flips' % i, '%s: %s (model: single-cycle bit flips on gate and flip-flop '
                                       'outputs, up to %d flips, %d cycles). Prediction written before the run: %s. %s' % (
                                           WHAT[i], ans, r['kmax'], r['cycles'], r['prediction'],
                                           'Same answer as the recorded run in work/.' if same else
                                           'Recorded run in work/: %s.' % (rec or 'none')),
                                       'SIMULATED', status=sc.get('status'), lo=sc.get('lo'), hi=sc.get('hi'),
                                       legit=(r.get('legit') or {}).get('status'), recorded=rec, kmax=r['kmax'], cycles=r['cycles']))
        for s in r.get('survival', []):
            if s['verdict'] == 'UNTRACKED':
                findings.append(LR.finding('%s.survival.%s' % (i, s['id']), '%s: %s was found in the RTL but could not be '
                                           'tracked into the netlist, so whether it survived is not known.' % (WHAT[i], s['id']),
                                           'UNTESTED', verdict=s['verdict']))
                continue
            findings.append(LR.finding('%s.survival.%s' % (i, s['id']), '%s: countermeasure %s %s synthesis (structural check '
                                       'of the netlist).' % (WHAT[i], s['id'], {'SURVIVED': 'survived', 'WEAKENED': 'was WEAKENED by',
                                                                                'REMOVED': 'was REMOVED by'}.get(s['verdict'], s['verdict'] + ' after')),
                                       'MEASURED', verdict=s['verdict']))
    findings.append(LR.finding('other_prims', 'The other experiments of experiments.tsv (prim_double_lfsr, AES counter and cipher '
                               'FSMs, FSM-optimisation flows) are not part of this Labs example.', 'UNTESTED'))
    findings.append(LR.finding('real_flow', 'OpenTitan\'s own synthesis flow and standard-cell libraries were not used; results '
                               'can change with them.', 'UNTESTED'))
    d = LR.make('opentitan_prims', 'OpenTitan hardening primitives',
                "Do OpenTitan's built-in fault countermeasures (multi-bit booleans, redundant counters) still need several "
                'bit flips to break after an open-source synthesis tool has built them, and are the redundant parts still there?',
                dict(name='3 primitives: mubi_flag, mubi_word, count_regs', description=__doc__.split('\n\n')[1].strip(),
                     command='python3 real/opentitan_prims/labs/run_labs.py'),
                findings,
                ['Built with open-source Yosys (0.71 read_slang to elaborate, 0.33 to map to generic gates), not with '
                 "OpenTitan's flow or a real cell library.",
                 'Fault model: single-cycle bit flips on gate and flip-flop outputs, bounded number of flips and cycles; '
                 'a bounded result says nothing beyond those bounds.',
                 'Each primitive is analysed alone, in a small wrapper; in a chip, the surrounding logic can help or hurt.',
                 'The survival check is structural (are redundant copies still separate nets/registers?), not a proof.',
                 'The OpenTitan SystemVerilog is used through small shims for primgen primitives (shims/).'],
                dict(started=started, seconds=round(time.time() - t0, 2), ok=not errors, errors=errors,
                     tools=dict(build='scripts/build.py', run='scripts/run.py', survival='ext/checker'), rows=rows))
    LR.write(a.out, d)
    print('wrote %s (%d findings, %d errors, %.1f s)' % (a.out, len(findings), len(errors), time.time() - t0))
    for f in findings:
        print(' [%s] %s' % (f['label'], f['text']))
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
