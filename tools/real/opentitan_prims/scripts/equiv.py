#!/usr/bin/env python3
"""Sequential equivalence of each experiment netlist with its elaborated RTL (Yosys 0.71 `sat -tempinduct`).

gold : work/<id>/elab.il (read_slang + proc, Yosys 0.71), then proc; flatten; async2sync; dffunmap; and the
       same one-cycle reset simulation (sim -w) as the synthesis flow -> same power-up state convention
gate : work/<id>/net.json (Yosys 0.33 finish, the netlist the engines read) and net71.json (Yosys 0.71 finish)
check: miter -equiv on all outputs; sat -tempinduct -prove trigger 0 (power-up values from the init attributes;
       -set-init-undef only for registers without one).
       'proved' = every output equal at every cycle from the power-up state (induction succeeded);
       'bounded N' = no difference within N cycles, induction did not close; 'DIFFERENT' = counterexample.
A negative control (--control) inverts one gate of the gate netlist and must give DIFFERENT.

usage: equiv.py [--control] [ID ...]
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402

MAXSTEPS = 25


def check(e, gate_file, d, tag):
    top = e['top']
    ys = os.path.join(d, 'equiv_%s.ys' % tag)
    log = os.path.join(d, 'equiv_%s.log' % tag)
    open(ys, 'w').write('\n'.join([
        'read_rtlil %s/elab.il' % d, 'hierarchy -top %s' % top, 'proc', 'flatten', 'async2sync', 'dffunmap',
        'opt_clean', 'sim -clock clk -n 1 -w %s' % top, 'rename %s gold' % top, 'design -stash g',
        'read_json %s' % gate_file, 'rename %s gate' % top, 'design -copy-from g -as gold gold',
        'miter -equiv -flatten -make_assert -ignore_gold_x gold gate miter', 'hierarchy -top miter',
        'sat -tempinduct -enable_undef -prove trigger 0 -set-init-undef -maxsteps %d -show-ports miter' % MAXSTEPS]) + '\n')
    r = subprocess.run([build.Y71, '-q', '-l', log, '-s', ys], capture_output=True, text=True, timeout=580)
    txt = open(log).read() if os.path.exists(log) else ''
    if 'Induction step proven: SUCCESS' in txt:
        m = re.findall(r'Trying induction with length (\d+)', txt)
        return dict(verdict='proved', induction_length=int(m[-1]) if m else None)
    if 'model found for base case: FAIL' in txt or 'model found: FAIL' in txt:
        return dict(verdict='DIFFERENT', log=os.path.relpath(log, build.ROOT))
    if r.returncode != 0:
        return dict(verdict='error', rc=r.returncode, tail=txt.splitlines()[-6:])
    return dict(verdict='bounded %d' % MAXSTEPS)


def broken_copy(src, dst, top):
    """Copy of the netlist with one gate in the output cone changed (AND<->OR, XOR->OR): a known difference."""
    doc = json.load(open(src))
    m = doc['modules'][top]
    drv = {}
    for name, c in m['cells'].items():
        for p, bits in c['connections'].items():
            if c['port_directions'][p] == 'output':
                for b in bits:
                    drv[b] = name
    todo = [b for b in m['ports']['gout']['bits'] if isinstance(b, int)]
    seen = set()
    while todo:
        b = todo.pop(0)
        if b in seen or b not in drv:
            continue
        seen.add(b)
        c = m['cells'][drv[b]]
        if c['type'] in ('$_AND_', '$_OR_', '$_XOR_'):
            c['type'] = {'$_AND_': '$_OR_', '$_OR_': '$_AND_', '$_XOR_': '$_OR_'}[c['type']]
            json.dump(doc, open(dst, 'w'))
            return drv[b]
        for p, bits in c['connections'].items():
            if c['port_directions'][p] == 'input':
                todo += [x for x in bits if isinstance(x, int)]
    raise RuntimeError('no gate found in the output cone')


def main(argv):
    control = '--control' in argv
    ids = [a for a in argv[1:] if not a.startswith('--')]
    out = {}
    path = os.path.join(build.ROOT, 'results', 'equivalence.json')
    if os.path.exists(path):
        out = json.load(open(path))
    for e in build.read_tsv():
        if ids and e['id'] not in ids:
            continue
        d = os.path.join(build.WORK, e['id'])
        if not os.path.exists(os.path.join(d, 'net.json')):
            continue
        rec = {'net (Yosys 0.33)': check(e, os.path.join(d, 'net.json'), d, 'net33'),
               'net71 (Yosys 0.71)': check(e, os.path.join(d, 'net71.json'), d, 'net71')}
        if control:
            cell = broken_copy(os.path.join(d, 'net.json'), os.path.join(d, 'net_broken.json'), e['top'])
            rec['negative control (one AND made OR: %s)' % cell[:60]] = check(
                e, os.path.join(d, 'net_broken.json'), d, 'broken')
        out[e['id']] = rec
        print('[%s] %s' % (e['id'], '  '.join('%s: %s' % (k.split()[0], v['verdict']) for k, v in rec.items())),
              flush=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
