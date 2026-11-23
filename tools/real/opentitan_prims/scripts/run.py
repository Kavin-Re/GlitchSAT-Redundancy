#!/usr/bin/env python3
"""Run the analysis engines on every built experiment and write work/<id>/runs/*.json.

Per experiment (experiments.tsv; sites 'none' = build only, skipped here):
  scale     ext/scale glitchsat_scale.py check, CaDiCaL (DIMACS)       -> minimum flips (main answer)
  legit     the same engine with 0 flips and the attacker input fixed to the key (sanity check of the
            reset model: True means the goal is reached legitimately)
  fastsat   ext/fastsat glitchsat_sat.py check, Kissat (DIMACS)         -> second solver (sites 'all' only)
  z3        scripts/glitchsat.py check (the original z3 engine)         -> third solver (sites 'all' only)
  unbounded ext/unbounded check at k = minimum-1 (or k = kmax when no attack was found): is there an
            attack with fewer flips at ANY time? (sites 'all' only; reported as proved / not proved)
  surface   ext/surface merge_lint.py (structural: do redundant copies share logic?) on 'all' netlists

usage: run.py [--force] [--only ENGINE,...] [ID ...]
Every command is limited to TIMEOUT_S (default 540 s); a timeout is reported as UNKNOWN, never as
"no attack". Results already present are reused unless --force (the run can be resumed).
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build  # noqa: E402

def _find_repo(start):
    """The GlitchSAT repository: $GLITCHSAT_ROOT, else the first folder above `start` that holds scripts/glitchsat.py
    (directly, or as work/glitchsat/ in a development work tree). Never a fixed machine path."""
    if os.environ.get('GLITCHSAT_ROOT'):
        return os.environ['GLITCHSAT_ROOT']
    d = os.path.abspath(start)
    while True:
        for c in (d, os.path.join(d, 'work', 'glitchsat')):
            if os.path.isfile(os.path.join(c, 'scripts', 'glitchsat.py')):
                return c
        up = os.path.dirname(d)
        if up == d:
            return os.path.join(os.path.dirname(os.path.abspath(start)), 'glitchsat')
        d = up


REAL_DIR = os.path.dirname(ROOT)                        # real/ (this file: real/opentitan_prims/scripts/run.py)


def _find_ext(real_dir):
    """The folder that holds the modules (scale, fastsat, ...): ext/ beside real/ (development tree), or the folder that
    holds real/ itself (repository: tools/real beside tools/scale)."""
    for c in (os.path.join(os.path.dirname(real_dir), 'ext'), os.path.dirname(real_dir)):
        if os.path.isdir(os.path.join(c, 'scale')):
            return c
    return os.path.join(os.path.dirname(real_dir), 'ext')


EXT = os.environ.get('GLITCHSAT_EXT') or _find_ext(REAL_DIR)
REPO = _find_repo(REAL_DIR)
CADICAL = os.environ.get('CADICAL') or shutil.which('cadical') or 'cadical'
KISSAT = os.environ.get('KISSAT') or shutil.which('kissat') or 'kissat'
TIMEOUT_S = int(os.environ.get('TIMEOUT_S', '540'))
PY = sys.executable


def env():
    e = dict(os.environ)
    e['GLITCHSAT_ROOT'] = REPO
    e['GLITCHSAT_FASTSAT'] = os.path.join(EXT, 'fastsat')
    e['GLITCHSAT_REAL'] = os.environ.get('GLITCHSAT_REAL') or REAL_DIR
    return e


def run_cmd(cmd, out_json, timeout=TIMEOUT_S):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30, env=env())
        rc, so, se = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        rc, so, se = 'timeout', '', ''
    wall = round(time.time() - t0, 3)
    res = None
    if out_json and os.path.exists(out_json):
        try:
            res = json.load(open(out_json))
        except ValueError:
            res = None
    return dict(cmd=cmd, rc=rc, wall_s=wall, stdout=so[-4000:], stderr=se[-2000:], result=res)


def state_sites(netjson, top):
    """Q nets of the 6 flops of the FSM state register (found behind the net u_dut.aes_cipher_ctrl_cs)."""
    import name_flops
    m = json.load(open(netjson))['modules'][top]
    bits = name_flops.register_flops(m, 'u_dut.aes_cipher_ctrl_cs')
    if bits is None or len(bits) != 6 or len(set(bits)) != 6:
        raise RuntimeError('state register flops not found in %s' % netjson)
    return bits


def goal_args(e):
    return ['--goal-out', 'gout', '--goal-value', e['goal_value'], '--attack-input', 'sig', '--key', e['key']]


def run_one(e, force, only):
    d = os.path.join(build.WORK, e['id'])
    net = os.path.join(d, 'net.json')
    rd = os.path.join(d, 'runs')
    os.makedirs(rd, exist_ok=True)
    top, k, T = e['top'], e['kmax'], e['cycles']
    out = {}

    def want(name):
        return (not only or name in only) and (force or not os.path.exists(os.path.join(rd, name + '.json')))

    def save(name, rec):
        json.dump(rec, open(os.path.join(rd, name + '.json'), 'w'), indent=1)
        out[name] = rec

    meta = None
    if e['sites'] == 'state':
        meta = os.path.join(d, 'sites_state.json')
        json.dump({'sites': state_sites(net, top), 'resets': [],
                   'note': 'fault sites = Q nets of the 6 state register flops (behind u_dut.aes_cipher_ctrl_cs)'},
                  open(meta, 'w'), indent=1)
    scale = [PY, os.path.join(EXT, 'scale', 'scripts', 'glitchsat_scale.py'), 'check', net, '--top', top,
             '--k', str(k), '--cycles', str(T)] + goal_args(e) + ['--backend', 'dimacs:' + CADICAL,
                                                                  '--time-s', str(TIMEOUT_S)]
    if meta:
        scale += ['--sites-meta', meta]
    if want('scale'):
        oj = os.path.join(rd, 'scale_out.json')
        if os.path.exists(oj):
            os.remove(oj)
        save('scale', run_cmd(scale + ['--out', oj], oj))
    if want('legit'):
        oj = os.path.join(rd, 'legit_out.json')
        if os.path.exists(oj):
            os.remove(oj)
        cmd = [PY, os.path.join(EXT, 'scale', 'scripts', 'glitchsat_scale.py'), 'check', net, '--top', top,
               '--k', '0', '--cycles', str(T), '--goal', 'gout=%s' % e['goal_value'], '--fix', 'sig=%s' % e['key'],
               '--no-key', '--backend', 'dimacs:' + CADICAL, '--out', oj]
        save('legit', run_cmd(cmd, oj))
    if e['sites'] != 'all':
        return out
    if want('fastsat'):
        oj = os.path.join(rd, 'fastsat_out.json')
        if os.path.exists(oj):
            os.remove(oj)
        cmd = [PY, os.path.join(EXT, 'fastsat', 'scripts', 'glitchsat_sat.py'), 'check', net, '--top', top,
               '--k', str(k), '--cycles', str(T)] + goal_args(e) + [
               '--backend', 'dimacs:' + KISSAT, '--timeout-ms', str(TIMEOUT_S * 1000), '--out', oj]
        save('fastsat', run_cmd(cmd, oj))
    if want('z3'):
        oj = os.path.join(rd, 'z3_out.json')
        if os.path.exists(oj):
            os.remove(oj)
        cmd = [PY, os.path.join(REPO, 'scripts', 'glitchsat.py'), 'check', net, '--top', top, '--k', str(k),
               '--cycles', str(T)] + goal_args(e) + ['--timeout-ms', str(TIMEOUT_S * 1000), '--out', oj]
        save('z3', run_cmd(cmd, oj))
    if want('unbounded'):
        sc = json.load(open(os.path.join(rd, 'scale.json')))['result'] or {}
        if sc.get('status') == 'EXACT' and sc.get('lo') == sc.get('hi'):
            ku = sc['lo'] - 1
        elif sc.get('status') == 'NO_ATTACK_UP_TO_BOUND':
            ku = k
        else:
            ku = None
        if ku is not None and ku >= 0:
            oj = os.path.join(rd, 'unbounded_out.json')
            if os.path.exists(oj):
                os.remove(oj)
            nflops = build.stat_counts(net, top)[1]
            if nflops <= 20:   # ext/unbounded CLI: explicit oracle + k-induction + IC3, must agree
                cmd = [PY, os.path.join(EXT, 'unbounded', 'src', 'unbounded.py'), 'check', net, '--top', top,
                       '--k', str(ku), '--goal-out', 'gout', '--goal-value', e['goal_value'], '--attack-in', 'sig',
                       '--key', e['key'], '--timeout', str(TIMEOUT_S // 3), '--out', oj]
            else:              # oracle limited to 20 flops: SAT methods only, through the library
                cmd = [PY, os.path.join(HERE, 'unbounded_sat.py'), net, top, str(ku), e['goal_value'], e['key'], oj,
                       str(TIMEOUT_S - 40)]
            rec = run_cmd(cmd, oj)
            rec['k_checked'] = ku
            save('unbounded', rec)
    if want('surface'):
        oj = os.path.join(rd, 'surface_out.json')
        if os.path.exists(oj):
            os.remove(oj)
        cmd = [PY, os.path.join(EXT, 'surface', 'scripts', 'merge_lint.py'), net, '--top', top,
               '--goal-out', 'gout', '--json', oj]
        save('surface', run_cmd(cmd, oj, timeout=300))
    return out


def main(argv):
    args = argv[1:]
    force = '--force' in args
    only = set()
    if '--only' in args:
        i = args.index('--only')
        only = set(args[i + 1].split(','))
        del args[i:i + 2]
    ids = [a for a in args if not a.startswith('--')]
    for e in build.read_tsv():
        if e['sites'] == 'none' or (ids and e['id'] not in ids):
            continue
        if not os.path.exists(os.path.join(build.WORK, e['id'], 'net.json')):
            print('[%s] not built; skipped' % e['id'])
            continue
        t0 = time.time()
        out = run_one(e, force, only)
        summ = []
        for name, rec in out.items():
            r = rec.get('result') or {}
            summ.append('%s:%s/%s/%ss' % (name, r.get('status') or r.get('verdict') or rec['rc'],
                                          r.get('lo', r.get('min_faults', '')), rec['wall_s']))
        print('[%s] %.1fs  %s' % (e['id'], time.time() - t0, '  '.join(summ)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
