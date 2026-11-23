#!/usr/bin/env python3
"""Benchmark of the scaling layer: CNF sizes under each reduction, runtimes per method, agreement of every answer
with the recorded results and with the other methods.

usage: bench_scale.py [--set core r20 wide proxy real repo] [--limit-s 60] [--out FILE.json]
       bench_scale.py --table results/*.json > results/BENCH.md

Sets
  core   reference/spike_netlists and one V5 netlist of the repository
  r20    the R20 designs, synthesised here with scripts/synth.sh (needs yosys on PATH or $GLITCHSAT_YOSYS_DIR)
  wide   N bytes through 2 or 3 S-box lookups (gen_wide.py), 3,068 to 32,641 gates (needs yosys)
  proxy  S-box proxy netlists of ext/fastsat (no yosys needed)
  real   OpenTitan AES cipher control / Ibex fetch stage, Nangate45 netlists adapted to primitives
         ($GLITCHSAT_REAL_ADAPTED: folder with <name>.json and <name>.meta.json)
  repo   every repository netlist with sig/boot_word ports: minimum compared with ext/fastsat

Methods (columns)
  fastsat      ext/fastsat default (single-reader collapsing), bundled Python solver          [engine questions only]
  time         this layer with cone + timing only (no site reduction), Python solver
  struct       post-dominator reduction, Python solver
  modules      struct + module summaries, Python solver
  race2        two processes: lower bound (modules, then exact) against upper bound (exact), Python solver
  cadical      struct, CaDiCaL binary through DIMACS files (not incremental)
  cadical+mod  struct + module summaries, CaDiCaL binary
  kissat       struct, Kissat binary
A cell is "<answer> <seconds>"; the answer is the minimum, "none" (no attack up to k), or an interval "[lo,hi]" /
"[lo,?]" when the time limit ended the search."""
import argparse, glob, json, os, platform, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = os.path.dirname(HERE)
EXT = os.path.dirname(SCALE)
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(EXT, '..'))
os.environ['GLITCHSAT_ROOT'] = ROOT
FASTSAT = os.environ.get('GLITCHSAT_FASTSAT') or os.path.join(EXT, 'fastsat', 'scripts')
os.environ['GLITCHSAT_FASTSAT'] = FASTSAT
for p in (os.path.join(SCALE, 'scripts'), HERE, os.path.join(os.path.dirname(FASTSAT), 'bench')):
    sys.path.insert(0, p)
import gscale                                         # noqa: E402
from gscale import circuit, search, spec, modular     # noqa: E402
import gen_wide                                       # noqa: E402

fs = gscale.fastsat()
WORK = os.path.join(HERE, 'work')
R20 = {  # stem -> (verilog parts, top, goal_out, goal_value, key)    parameters and recorded results: research/c3/r20
    'sbox_unprot': (['aes_sbox/aes_sbox.v', 'wrappers/w_sbox_unprot.v'], 'sbox_unprot', 'y', 0x7C, 1),
    'sbox_par': (['aes_sbox/aes_sbox.v', 'wrappers/w_sbox_par.v'], 'sbox_par', 'gout', 0x17C, 1),
    'sbox_par2': (['aes_sbox/aes_sbox.v', 'wrappers/w_sbox_par2.v'], 'sbox_par2', 'gout', 0x17C, 1),
    'sbox_dmr': (['aes_sbox/aes_sbox.v', 'wrappers/w_sbox_dmr.v'], 'sbox_dmr', 'gout', 0x17C, 1),
    'crc_plain': (['verilog_lfsr/lfsr.v', 'wrappers/w_crc.v'], 'bootcrc', 'ok', 1, 0xA5),
    'crc_tmr': (['verilog_lfsr/lfsr.v', 'wrappers/w_crc_tmr.v'], 'bootcrc_tmr', 'ok', 1, 0xA5),
    'uart': (['verilog_uart_tx/uart_tx.v', 'wrappers/w_uart.v'], 'uartw', 'gout', 7, 0),
}


def tool(name):
    env = os.environ.get('GLITCHSAT_' + name.upper())
    if env and os.access(env, os.X_OK): return env
    return shutil.which(name)


def yosys_env():
    env = dict(os.environ)
    d = os.environ.get('GLITCHSAT_YOSYS_DIR')
    if d: env['PATH'] = d + os.pathsep + env['PATH']
    return env if shutil.which('yosys', path=env['PATH']) else None


def synth(parts, top, out, text=None):
    """scripts/synth.sh (plain flow) on the concatenated sources. Returns the JSON path or None without yosys."""
    if os.path.isfile(out): return out
    env = yosys_env()
    if env is None: return None
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(WORK, top + '.v')
    with open(src, 'w') as f:
        for p in parts: f.write(open(os.path.join(ROOT, 'research', 'c3', 'r20', 'designs', p)).read() + '\n')
        if text: f.write(text)
    r = subprocess.run(['sh', os.path.join(ROOT, 'scripts', 'synth.sh'), src, top, out], env=env, capture_output=True, text=True)
    return out if r.returncode == 0 and os.path.isfile(out) else None


def designs(sets):
    ds = []

    def eng(name, path, top, T, k, rec=None, src='', **kw):
        ds.append(dict(name=name, path=path, top=top, T=T, k=k, rec=rec, src=src, engine=True, kw=kw))
    if 'core' in sets:
        sp = os.path.join(ROOT, 'reference', 'spike_netlists')
        eng('v2 spike', os.path.join(sp, 'v2.json'), 'v2', 6, 3, 3, 'results/reproduce')
        eng('v2 spike T=20', os.path.join(sp, 'v2.json'), 'v2', 20, 3, 3, 'ext/fastsat README 7.1')
        v5 = os.path.join(ROOT, 'research', 'c4', 'b3', 'nl', 'v5_apt033.json')
        if os.path.isfile(v5): eng('v5 (apt 0.33)', v5, 'v5', 6, 3, 3, 'ext/fastsat README 7.1')
    if 'r20' in sets:
        for stem, (parts, top, go, gv, key) in R20.items():
            p = synth(parts, top, os.path.join(WORK, stem + '.json'))
            if not p: continue
            rec = {'sbox_dmr': 2}.get(stem, 1)
            for T, k in ([(6, 3), (30, 2), (60, 3)] if stem == 'uart' else [(4, 3)]):
                eng('R20 %s%s' % (stem, ' T=%d' % T if stem == 'uart' else ''), p, top, T, k, rec,
                    'R20_REPORT.md' + ('' if (stem, T) != ('uart', 60) else ' (z3 run did not finish; min 1 follows from T=6)'),
                    goal_out=go, goal_value=gv, key=key)
    if 'wide' in sets:
        import gen_sbox_proxy
        box = gen_sbox_proxy.aes_sbox()
        for kind, n in (('tmr2', 1), ('dmr', 4), ('tmr2', 4), ('dmr', 10), ('dmr', 16)):
            top = 'sbox_%s_w%d' % (kind, n)
            p = synth(['aes_sbox/aes_sbox.v'], top, os.path.join(WORK, top + '.json'), gen_wide.verilog(kind, n))
            if not p: continue
            pr = gen_wide.params(kind, n, box)
            eng('%s x%d bytes' % (kind, n), p, top, 4, 3, None, 'by construction: %d' % (2 if kind == 'dmr' else 3),
                goal_out=pr['goal_out'], goal_value=pr['goal_value'], key=pr['key'])
            ds[-1]['expect'] = 2 if kind == 'dmr' else 3
    if 'proxy' in sets:
        import gen_sbox_proxy as g
        box = g.aes_sbox(); os.makedirs(WORK, exist_ok=True)
        for kind, shared, rec in (('dmr', False, 2), ('dmr', True, 2), ('tmr2', False, 3), ('tmr2', True, 3)):
            b = g.build(kind, box, shared)
            p = os.path.join(WORK, b.top + '.json')
            json.dump(b.doc(), open(p, 'w'))
            pr = g.PARAMS[kind]
            eng('proxy %s%s' % (kind, ' shared' if shared else ' trees'), p, b.top, pr['cycles'], 3, rec, 'ext/fastsat README 7.1',
                goal_out=pr['goal_out'], goal_value=pr['goal_value'], key=pr['key'])
    if 'real' in sets:
        ad = os.environ.get('GLITCHSAT_REAL_ADAPTED') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'real', 'runs', 'adapted'))
        real = [('OT AES cipher control FSM: out_valid without in_valid, alert silent', 'aes_fsm', 'aes_cipher_control_fsm', 4, 3,
                 dict(goal=['out_valid_o=1'], quiet=['alert_o=0'], fix=['in_valid_i=0'])),
                ('OT AES cipher control (3 rails): out_valid=011 with in_valid=100, alert silent', 'aes_ctrl', 'aes_cipher_control', 3, 4,
                 dict(goal=['out_valid_o=3'], quiet=['alert_o=0'], fix=['in_valid_i=4'])),
                ('same, 8 cycles', 'aes_ctrl', 'aes_cipher_control', 8, 4,
                 dict(goal=['out_valid_o=3'], quiet=['alert_o=0'], fix=['in_valid_i=4'])),
                ('Ibex fetch stage: fetch address 0x40400 with no PC set and no mispredict, mismatch alert silent', 'ibex', 'ibex_if_stage', 3, 3,
                 dict(goal=['instr_addr_o=0x40400'], quiet=['pc_mismatch_alert_o=0'], fix=['pc_set_i=0', 'nt_branch_mispredict_i=0'])),
                ('same, 8 cycles', 'ibex', 'ibex_if_stage', 8, 3,
                 dict(goal=['instr_addr_o=0x40400'], quiet=['pc_mismatch_alert_o=0'], fix=['pc_set_i=0', 'nt_branch_mispredict_i=0']))]
        for name, stem, top, T, k, kw in real:
            p = os.path.join(ad, stem + '.json')
            if os.path.isfile(p):
                ds.append(dict(name=name, path=p, top=top, T=T, k=k, rec=None, src='', engine=False,
                               kw=dict(kw, inputs='cycle', no_key=True, sites_meta=os.path.join(ad, stem + '.meta.json'))))
    return ds


def answer(r):
    if r['status'] == 'EXACT': return r['hi']
    if r['status'] == 'NO_ATTACK_UP_TO_BOUND': return 'none'
    return '[%d,%s]' % (r['lo'], '?' if r['hi'] is None else r['hi'])


def run_design(d, limit, big_limit):
    kw = d['kw']
    P = spec.load_problem(d['path'], d['top'], d['T'], **kw)
    c = P.circ
    row = dict(name=d['name'], top=d['top'], gates=len(c.gates), flops=len(c.flops), T=d['T'], k=d['k'], recorded=d['rec'],
               source=d['src'], expect=d.get('expect'), netlist=os.path.relpath(d['path'], ROOT) if d['path'].startswith(ROOT) else os.path.basename(d['path']))
    big = len(c.gates) > 5000
    t0 = time.time()
    row['sizes'] = search.sizes(P, d['k'], modules='auto', levels=('time', 'struct', 'full'), reduce_time_s=15 if not big else 30)
    row['sizes_s'] = round(time.time() - t0, 2)
    mods = modular.find_modules(P, 'auto')
    row['modules'] = [m[0] for m in mods]
    cells = {}

    def cell(name, **a):
        t0 = time.time()
        try:
            r = search.analyse(P, d['k'], time_s=limit, **a)
            cells[name] = dict(answer=answer(r), s=round(time.time() - t0, 2), status=r['status'], lo=r['lo'], hi=r['hi'],
                               lo_by=r['lo_by'], hi_by=r['hi_by'], events=r['events'], parts=r['parts'])
        except Exception as ex:
            cells[name] = dict(answer='error', s=round(time.time() - t0, 2), error=repr(ex))
        print('   %-12s %-8s %7.2f s' % (name, cells[name]['answer'], cells[name]['s']), flush=True)
    if d['engine']:
        nl = fs.gs.Netlist(d['path'], d['top'])
        ekw = {k: v for k, v in kw.items() if k in ('goal_out', 'goal_value', 'key')}
        t0 = time.time()
        e = fs.encode(nl, d['T'], **ekw); fs.add_cardinality(e, min(d['k'], len(e.fault_order)))
        row['sizes']['fastsat'] = dict(fault_vars=e.info['fault_vars'], **e.stats())
        try:
            v, info, res = fs.solve(nl, d['T'], d['k'], timeout_ms=int(limit * 1000), backend='py', **ekw)
            a = len(res['faults']) if res else ('none' if v == 'NO_ATTACK_UP_TO_BOUND' else '[?,?]')
            if res and not info.get('minimum_proved', True): a = '[?,%d]' % len(res['faults'])
        except Exception as ex:
            a = 'error'
        cells['fastsat'] = dict(answer=a, s=round(time.time() - t0, 2))
        print('   %-12s %-8s %7.2f s' % ('fastsat', a, cells['fastsat']['s']), flush=True)
    cell('time', reduce='time', modules='none', backend='py')
    cell('struct', reduce='struct', modules='none', backend='py')
    if mods: cell('modules', reduce='struct', modules=mods, backend='py')
    if not big: cell('race2', reduce='struct', modules=mods or 'none', backend='py', workers=2)
    cad, kis = tool('cadical'), tool('kissat')
    if cad:
        cell('cadical', reduce='struct', modules='none', backend='dimacs:' + cad)
        if mods: cell('cadical+mod', reduce='struct', modules=mods, backend='dimacs:' + cad)
    if kis: cell('kissat', reduce='struct', modules='none', backend='dimacs:' + kis)
    row['cells'] = cells
    exact = {c_['answer'] for c_ in cells.values() if isinstance(c_['answer'], int) or c_['answer'] == 'none'}
    row['agree'] = len(exact) <= 1 and not any(c_['answer'] == 'error' for c_ in cells.values())
    want = d['rec'] if d['rec'] is not None else d.get('expect')
    row['matches_recorded'] = None if want is None or not exact else (exact == {want})
    for nm, c_ in cells.items():                      # an interval must contain the exact answer
        if 'lo' in c_ and exact and len(exact) == 1:
            x = next(iter(exact)); xv = d['k'] + 1 if x == 'none' else x
            if c_['lo'] > xv or (c_['hi'] is not None and c_['hi'] < xv): row['agree'] = False
    return row


def repo_agreement(limit):
    import common
    rows = []; skipped = 0
    for n in common.repo_netlists():
        if n['ports'].get('sig', ('', 0))[0] != 'input' or n['ports'].get('boot_word', ('', 0))[0] != 'output': continue
        par, rec = common.default_params(n)
        path = os.path.join(ROOT, n['path'])
        try: nl = fs.gs.Netlist(path, n['top'])
        except fs.NetlistError:
            skipped += 1; continue
        v, info, res = fs.solve(nl, 6, 3, backend='py', **par)
        want = len(res['faults']) if res else 'none'
        got = {}
        for nm, a in (('struct', dict(reduce='struct', modules='none')), ('full', dict(reduce='full', modules='none', reduce_time_s=5)),
                      ('modules', dict(reduce='struct', modules='islands', min_module_sites=4)), ('time', dict(reduce='time', modules='none'))):
            P = circuit.engine_problem(nl, 6, goal_value=par['goal_value'], key=par['key'])
            got[nm] = answer(search.analyse(P, 3, backend='py', **a))
        rows.append(dict(path=n['path'], fastsat=want, recorded=rec, **got))
    bad = [r for r in rows if any(r[k] != r['fastsat'] for k in ('struct', 'full', 'modules', 'time'))]
    hist = {}
    for r in rows: hist[str(r['fastsat'])] = hist.get(str(r['fastsat']), 0) + 1
    return dict(netlists=len(rows), skipped_by_parser=skipped, disagreements=len(bad), minimum_histogram=hist, bad=bad, rows=rows)


def table(files):
    rows = []; repo = None; envs = []
    for f in files:
        d = json.load(open(f))
        rows += d.get('rows', []); repo = d.get('repo') or repo; envs.append(d.get('env'))
    out = []
    lv = ['time', 'fastsat', 'struct', 'full', 'modules']
    out.append('### Sizes (fault variables / CNF variables / CNF clauses)\n')
    out.append('| design | gates / flops | T | sites x cycles | cone+timing | fastsat collapsing | post-dominators | + functional | module formula |')
    out.append('|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        z = r['sizes']
        cs = ['%d / %d / %d' % (z[l]['fault_vars'] + z[l].get('cost_vars', 0), z[l]['vars'], z[l]['clauses']) if l in z else '-' for l in lv]
        out.append('| %s | %d / %d | %d | %d | %s |' % (r['name'], r['gates'], r['flops'], r['T'], z['sites_total'], ' | '.join(cs)))
    ms = ['fastsat', 'time', 'struct', 'modules', 'race2', 'cadical', 'cadical+mod', 'kissat']
    out.append('\n### Answers and runtimes (answer, seconds)\n')
    out.append('| design | k | recorded | ' + ' | '.join(ms) + ' | all equal |')
    out.append('|---|---|---|' + '---|' * (len(ms) + 1))
    for r in rows:
        cs = ['%s, %.1f' % (r['cells'][m]['answer'], r['cells'][m]['s']) if m in r['cells'] else '-' for m in ms]
        rec = r['recorded'] if r['recorded'] is not None else ('(%s)' % r['expect'] if r.get('expect') else '-')
        ok = 'yes' if r['agree'] and r['matches_recorded'] in (None, True) else 'NO'
        out.append('| %s | %d | %s | %s | %s |' % (r['name'], r['k'], rec, ' | '.join(cs), ok))
    if repo:
        out.append('\n### Repository netlists (T=6, k<=3)\n')
        out.append('%d netlists with sig/boot_word ports (%d more rejected by the engine parser): minimum from ext/fastsat compared with '
                   'this layer at levels time, struct, full and with island modules: **%d disagreements**. Minimum histogram: %s.'
                   % (repo['netlists'], repo['skipped_by_parser'], repo['disagreements'], repo['minimum_histogram']))
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--set', nargs='+', default=['core'], choices=['core', 'r20', 'wide', 'proxy', 'real', 'repo'])
    ap.add_argument('--limit-s', type=float, default=60.0); ap.add_argument('--out')
    ap.add_argument('--only', help='substring of the design name')
    ap.add_argument('--table', nargs='+', metavar='JSON')
    a = ap.parse_args()
    if a.table:
        sys.stdout.write(table(a.table)); return 0
    env = dict(python=platform.python_version(), machine=platform.machine(), cpus=os.cpu_count(), load=os.getloadavg(),
               cadical=tool('cadical'), kissat=tool('kissat'), yosys=bool(yosys_env()), limit_s=a.limit_s,
               date=time.strftime('%Y-%m-%d %H:%M'))
    for nm in ('cadical', 'kissat'):
        if env[nm]:
            env[nm + '_version'] = subprocess.run([env[nm], '--version'], capture_output=True, text=True).stdout.strip().splitlines()[0]
            env[nm] = os.path.basename(env[nm])
    out = dict(env=env, rows=[])
    for d in designs([s for s in a.set if s != 'repo']):
        if a.only and a.only not in d['name']: continue
        print(d['name'], flush=True)
        out['rows'].append(run_design(d, a.limit_s, a.limit_s))
        if a.out: json.dump(out, open(a.out, 'w'), indent=1, default=str)
    if 'repo' in a.set:
        out['repo'] = repo_agreement(a.limit_s)
        print('repo: %d netlists, %d disagreements' % (out['repo']['netlists'], out['repo']['disagreements']))
    if a.out: json.dump(out, open(a.out, 'w'), indent=1, default=str)
    bad = [r['name'] for r in out['rows'] if not r['agree'] or r['matches_recorded'] is False]
    if bad: print('DISAGREEMENT:', bad)
    return 1 if bad or (out.get('repo') or {}).get('disagreements') else 0


if __name__ == '__main__':
    sys.exit(main())
