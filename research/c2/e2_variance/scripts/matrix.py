#!/usr/bin/env python3
"""Synthesis-variance matrix driver.
Synthesises {v0,v1,v2} x {yosys build} x factor grid, hashes netlists, solves each UNIQUE netlist (canonical sha) with the
copied glitchsat engine (z3, goal boot_word==0x96, attacker input sig held constant, 6 cycles, k<=3, minimising).
Usage: matrix.py <outdir> ; writes outdir/matrix.json"""
import sys, os, json, hashlib, itertools, subprocess, collections, re
from multiprocessing import Pool
W = '/tmp/work_e2'
YOSYS = {'apt0.33': '/usr/bin/yosys', 'conda-formal0.38': '/tmp/mm_root/envs/formal/bin/yosys', 'conda-eda0.38': '/tmp/mm_root/envs/eda/bin/yosys'}
ABCS = {'default': 'abc -g AND,OR,XOR,MUX', 'fast': 'abc -fast -g AND,OR,XOR,MUX', 'noMUX': 'abc -g AND,OR,XOR',
        'AND_OR': 'abc -g AND,OR', 'dff': 'abc -dff -g AND,OR,XOR,MUX', 'noabc': ''}
FLOWS = ['plain', 'opt']; ORDERS = ['abc_then_flatten', 'flatten_then_abc']; MERGES = ['nomerge', 'opt_merge']; KEEPS = ['keep_on', 'keep_off']
UNSET = 'setattr -mod -unset keep_hierarchy *'

def script(top, vfile, out, flow, order, abc, merge):
    pre = f'synth -top {top}; dffunmap' if flow == 'opt' else 'proc; opt_clean; techmap; opt_clean'
    m = 'opt_merge; ' if merge == 'opt_merge' else ''
    A = ABCS[abc]
    if order == 'abc_then_flatten':   # as scripts/synth.sh: map per module, then flatten (merge, if any, after flatten)
        s = [f'read_verilog {vfile}', f'hierarchy -top {top}'] + pre.split('; ') + ([A] if A else []) + ['opt_clean', UNSET, 'flatten', 'opt_clean', 'techmap', 'opt_clean'] + (['opt_merge', 'opt_clean'] if m else [])
    else:                              # flatten before abc (merge, if any, after flatten, before abc)
        s = [f'read_verilog {vfile}', f'hierarchy -top {top}', 'proc', UNSET, 'flatten'] + (pre.split('; ')[0:0]) 
        s += (['synth -top %s' % top, 'dffunmap'] if flow == 'opt' else ['opt_clean', 'techmap', 'opt_clean'])
        s += (['opt_merge', 'opt_clean'] if m else []) + ([A] if A else []) + ['opt_clean']
    s += [f'write_json {out}']
    return s

def synth(job):
    build, design, flow, order, abc, merge, keep, rep = job
    tag = f'{build}__{design}__{flow}__{order}__{abc}__{merge}__{keep}'
    d = f'{W}/nl/{tag}'; os.makedirs(d, exist_ok=True)
    v = f'{W}/rtl_{keep}/{design}.v'
    out = f'{d}/r{rep}.json'
    open(f'{d}/r{rep}.ys', 'w').write('\n'.join(script(design, v, out, flow, order, abc, merge)) + '\n')
    p = subprocess.run([YOSYS[build], '-q', '-s', f'{d}/r{rep}.ys'], capture_output=True, text=True, timeout=120)
    if p.returncode != 0 or not os.path.exists(out):
        return dict(tag=tag, rep=rep, ok=False, err=(p.stderr or p.stdout)[-300:])
    raw = open(out, 'rb').read()
    j = json.loads(raw); j.pop('creator', None)
    canon = hashlib.sha256(json.dumps(j, sort_keys=True).encode()).hexdigest()
    return dict(tag=tag, rep=rep, ok=True, path=out, sha256=hashlib.sha256(raw).hexdigest(), canon_sha256=canon)

def solve(args):
    path, design = args
    p = subprocess.run(['python3', '-I', f'{W}/scripts/analyze.py', path, design, '--k', '3', '--cycles', '6'], capture_output=True, text=True, timeout=900)
    try: return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: return dict(error=(p.stderr or p.stdout)[-300:])

if __name__ == '__main__':
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    for keep in KEEPS:
        os.makedirs(f'{W}/rtl_{keep}', exist_ok=True)
        for dsg in ('v0', 'v1', 'v2'):
            t = open(f'{W}/{dsg}.v').read()
            if keep == 'keep_off': t = t.replace('(* keep *) ', '')
            open(f'{W}/rtl_{keep}/{dsg}.v', 'w').write(t)
    jobs = [(b, d, f, o, a, m, k, r) for b in YOSYS for d in ('v0', 'v1', 'v2') for f in FLOWS for o in ORDERS for a in ABCS for m in MERGES for k in KEEPS for r in (1, 2, 3)]
    with Pool(4) as P: S = P.map(synth, jobs, chunksize=8)
    json.dump(S, open(f'{outdir}/synth_all.json', 'w'), indent=0)
    uniq = {}
    for s in S:
        if s['ok'] and s['rep'] == 1:
            design = s['tag'].split('__')[1]
            uniq.setdefault((s['canon_sha256'], design), s['path'])
    print('synth jobs', len(S), 'failed', sum(not s['ok'] for s in S), 'unique netlists to solve', len(uniq), flush=True)
    keys = list(uniq)
    with Pool(4) as P: R = P.map(solve, [(uniq[k], k[1]) for k in keys], chunksize=1)
    sol = {f'{k[0]}|{k[1]}': r for k, r in zip(keys, R)}
    json.dump(sol, open(f'{outdir}/solve_by_canon_sha.json', 'w'), indent=1)
    print('done')
