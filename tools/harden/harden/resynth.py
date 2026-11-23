"""Re-synthesise the before/after Verilog with Yosys over the synthesis-configuration grid of
research/c2/e2_variance (flow x order x ABC script x opt_merge x keep, 96 per design) plus the copy-separation guard
(on/off), and re-verify every netlist with harden.sim (exhaustive, every number of cycles, up to the goal).

Needs `yosys` on PATH (cloud/run_cloud.sh installs apt Yosys 0.33 on Ubuntu 24.04). With dry_run=True only the
Verilog and the scripts are written: that is all that can be checked on a machine without Yosys.

'before_repo_rtl' rows synthesise the repository RTL (rtl/<design>.v) itself when GLITCHSAT_ROOT is set; 'before' rows
synthesise the description of it written by harden.spec.verilog (same function, checked for all 256 inputs).

Optional (--z3): an independent check of the plain-flow netlists with the repository engine (scripts/glitchsat.py check,
z3, bounded to 6 cycles), compared with this simulator bounded to 6 cycles.
"""
import csv, hashlib, itertools, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from . import sim, spec as S
from .netlist import Netlist, NetlistError

FLOWS = ('plain', 'opt')
ABCS = {'default': 'abc -g AND,OR,XOR,MUX', 'fast': 'abc -fast -g AND,OR,XOR,MUX', 'noMUX': 'abc -g AND,OR,XOR', 'AND_OR': 'abc -g AND,OR',
        'dff': 'abc -dff -g AND,OR,XOR,MUX', 'noabc': ''}
ORDERS = ('abc_then_flatten', 'flatten_then_abc')
QUICK = [('plain', 'abc_then_flatten', 'default', False, True), ('plain', 'abc_then_flatten', 'default', True, True),
         ('plain', 'flatten_then_abc', 'default', False, True), ('plain', 'abc_then_flatten', 'fast', False, True),
         ('plain', 'abc_then_flatten', 'noMUX', False, True), ('opt', 'abc_then_flatten', 'default', False, True),
         ('opt', 'abc_then_flatten', 'default', True, True), ('plain', 'abc_then_flatten', 'default', False, False)]
_KEEP_RE = re.compile(r'\(\*\s*keep\s*\*\)\s*')
FIELDS = ['design', 'which', 'goal', 'config', 'flow', 'order', 'abc', 'merge', 'keep', 'guard', 'status', 'gates', 'flops', 'match_nets',
          'min_flips', 'searched_up_to', 'meets_goal', 'function_ok', 'right_key_boots', 'witness', 'z3_verdict_6cyc', 'sim_6cyc', 'z3_agrees',
          'sha256', 'note']


def grid(quick=False):
    g = QUICK if quick else list(itertools.product(FLOWS, ORDERS, ABCS, (False, True), (True, False)))
    return [dict(flow=f, order=o, abc=a, merge=m, keep=k, guard=gd) for (f, o, a, m, k) in g for gd in (False, True)]


def cfg_name(c):
    return '__'.join([c['flow'], c['order'], c['abc'], 'opt_merge' if c['merge'] else 'nomerge', 'keep_on' if c['keep'] else 'keep_off',
                      'guard' if c['guard'] else 'noguard'])


def script(sp, c, src, out, top):
    return S.yosys_script(sp, src, out, top=top, guard=c['guard'], flow=c['flow'], abc=ABCS[c['abc']], order=c['order'], merge=c['merge'])


def match_nets(nl, key=0xC3, attack_input='sig'):
    """Number of distinct nets whose fault-free value is exactly (sig == key) (the compare results). 1 = copies merged."""
    import numpy as np
    C = sim.Compiled(nl, sim.Goal(), attack_input)
    n = 1 << C.nin
    sigw = sim._pack_lanes(np.arange(n, dtype=np.uint64), C.nin)
    stw = sim._pack_lanes(np.full(n, C.init_state, np.uint64), C.nf)
    V = C.eval(sigw, stw, np.zeros((1, 0), np.int32))
    want = sim._pack_lanes(np.array([1 if s == key else 0 for s in range(n)], np.uint64), 1)[0]
    lm = sim._lane_mask(n)
    return sum(1 for y in nl.gates if np.array_equal(V[C.idx[y]][0] & lm, want & lm))


def verify(path, top, sp, goal, time_limit=600):
    """Exhaustive re-verification of one synthesised netlist. Returns a dict of row fields."""
    import numpy as np
    nl = Netlist.load(path, top)
    g = sim.Goal('boot_word', sp.goal_value())
    ff = sim.fault_free(nl, 6, g)
    fok = bool((ff['boot_word'] == np.array(S.reference_trace(sp, 6)).T).all())
    r = sim.min_flips(nl, g, kmax=goal, cycles=None, key=sp.key, time_limit=time_limit)
    st = nl.stats()
    done = r.exhaustive_up_to is not None
    mf = r.min_flips if r.min_flips is not None else (f'>{goal}' if done else '')
    meets = bool(fok and r.honest_ok and not r.fault_free_wrong_accept and done and (r.min_flips is None or r.min_flips >= goal))
    if not done and r.min_flips is not None and r.min_flips < goal:
        meets = False
    return dict(status='MEASURED', gates=st['gates'], flops=st['flops'], match_nets=match_nets(nl, sp.key), function_ok=fok,
                right_key_boots=r.honest_ok, min_flips=mf, searched_up_to=goal if done else 'time limit', meets_goal=meets,
                witness=json.dumps(r.witness['flips']) if r.witness else '', note='' if done else 'time limit reached: no verdict')


def z3_check(path, top, k, root, timeout_s=900):
    """Repository engine, bounded: 'NO_ATTACK_UP_TO_BOUND' / 'ATTACK_FOUND' / error text."""
    eng = os.path.join(root, 'scripts', 'glitchsat.py')
    if not os.path.isfile(eng):
        return 'engine not found'
    if k < 1:
        return 'k<1'
    out = path + f'.z3k{k}.json'
    try:
        p = subprocess.run([sys.executable, eng, 'check', path, '--top', top, '--k', str(k), '--cycles', '6', '--out', out],
                           capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return 'timeout'
    if os.path.isfile(out):
        try:
            return json.load(open(out)).get('verdict', 'no verdict')
        except ValueError:
            pass
    return f'exit {p.returncode}'


def cache_key(ys, src, yosys_version, goal, z3, time_limit):
    """Hash of everything a row depends on: script, Verilog, Yosys version, this package, goal, options."""
    from . import __version__
    h = hashlib.sha256()
    for part in (open(ys, 'rb').read(), open(src, 'rb').read(), yosys_version.encode(), __version__.encode(),
                 f'{goal}|{bool(z3)}|{time_limit}'.encode()):
        h.update(hashlib.sha256(part).digest())
    return h.hexdigest()


def _job(args):
    sp_d, top, goal, which, tag, c, workdir, yosys, root, z3, time_limit, yv, use_cache = args
    name = cfg_name(c)
    src = os.path.join(workdir, f'{top}_{"keep_on" if c["keep"] else "keep_off"}.v')
    ys = os.path.join(workdir, name + '.ys')
    row = dict.fromkeys(FIELDS, '')
    row.update(design=tag, which=which, goal=goal, config=name, **c, status='SCRIPT_ONLY')
    if yosys is None:
        return row
    key = cache_key(ys, src, yv, goal, z3, time_limit)
    cf = os.path.join(workdir, name + '.row.json')
    if use_cache and os.path.isfile(cf):
        try:
            cached = json.load(open(cf))
            if cached.get('cache_key') == key:
                r = cached['row']
                r['note'] = (r.get('note') or '') + (' ' if r.get('note') else '') + '(cached)'
                return r
        except (ValueError, KeyError):
            pass
    row = _run(sp_d, top, goal, row, c, workdir, name, ys, yosys, root, z3, time_limit)
    if row['status'] in ('MEASURED', 'ENGINE_UNSUPPORTED', 'SYNTH_FAILED') and 'timeout' not in row['note']:
        with open(cf, 'w') as f:
            json.dump(dict(cache_key=key, row=row), f)
    return row


def _run(sp_d, top, goal, row, c, workdir, name, ys, yosys, root, z3, time_limit):
    sp = _mk(sp_d)
    out = os.path.join(workdir, name + '.json')
    if os.path.isfile(out):
        os.remove(out)
    try:
        p = subprocess.run([yosys, '-q', '-s', ys], capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        row.update(status='SYNTH_FAILED', note='yosys timeout')
        return row
    if p.returncode != 0 or not os.path.isfile(out):
        msg = (p.stderr or p.stdout).strip().splitlines()
        row.update(status='SYNTH_FAILED', note=msg[-1][:200] if msg else f'exit {p.returncode}')
        return row
    row['sha256'] = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    try:
        row.update(verify(out, top, sp, goal, time_limit))
    except (NetlistError, ValueError) as e:
        row.update(status='ENGINE_UNSUPPORTED', note=str(e)[:200])
        return row
    if z3 and c['flow'] == 'plain' and c['abc'] == 'default' and c['keep']:
        k = goal - 1
        v = z3_check(out, top, k, root)
        b = sim.min_flips(Netlist.load(out, top), sim.Goal('boot_word', sp.goal_value()), kmax=k, cycles=6, key=sp.key)
        s6 = 'ATTACK_FOUND' if b.min_flips is not None else 'NO_ATTACK_UP_TO_BOUND'
        row.update(z3_verdict_6cyc=v, sim_6cyc=s6, z3_agrees=(v == s6) if v in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND') else '')
    return row


def _mk(d):
    fields = {f.name for f in S.dataclasses.fields(S.Spec)}
    return S.Spec(**{k: (tuple(v) if k == 'owner' else v) for k, v in d.items() if k in fields})


def jobs_for(spec_file, outdir, quick, yosys, root, z3, time_limit, yv='', use_cache=True):
    j = json.load(open(spec_file))
    tag = os.path.basename(spec_file)[:-len('.spec.json')]
    jobs = []
    variants = [('before', j['before']['name'], 'before', None), ('after', j['top'], 'after', None)]
    rtl = S.PRESET_RTL.get(j['before']['name'])
    if root and rtl and os.path.isfile(os.path.join(root, rtl)):
        variants.insert(1, ('before_repo_rtl', j['before']['name'], 'before', open(os.path.join(root, rtl)).read()))
    for which, top, spk, text in variants:
        sp = _mk(j[spk])
        wd = os.path.join(outdir, 'work', tag, which)
        os.makedirs(wd, exist_ok=True)
        for keep in (True, False):
            v = text if text is not None else S.verilog(sp, module=top)
            if not keep:
                v = _KEEP_RE.sub('', v)
            with open(os.path.join(wd, f'{top}_{"keep_on" if keep else "keep_off"}.v'), 'w') as f:
                f.write(v)
        for c in grid(quick):
            name = cfg_name(c)
            with open(os.path.join(wd, name + '.ys'), 'w') as f:
                f.write(script(sp, c, os.path.join(wd, f'{top}_{"keep_on" if c["keep"] else "keep_off"}.v'), os.path.join(wd, name + '.json'), top))
            jobs.append((j[spk], top, j['goal'], which, tag, c, wd, yosys, root, z3, time_limit, yv, use_cache))
    return jobs


def summarise(rows):
    rate = lambda xs: f"{sum(1 for r in xs if r['meets_goal'] is True)} / {len(xs)}" if xs else '-'
    L = ['| design | which | goal | netlists verified | meet goal: all | guard off | guard on | opt_merge rows, guard off | opt_merge rows, guard on '
         '| per-module flows (abc_then_flatten, no opt_merge) | min flips seen | unsupported / failed / time limit |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|']
    keys = []
    for r in rows:
        k = (r['design'], r['which'])
        if k not in keys:
            keys.append(k)
    for k in keys:
        rs = [r for r in rows if (r['design'], r['which']) == k]
        m = [r for r in rs if r['status'] == 'MEASURED' and r['searched_up_to'] != 'time limit']
        mins = sorted({str(r['min_flips']) for r in m})
        sep = [r for r in m if r['order'] == 'abc_then_flatten' and not r['merge']]
        L.append(f"| {k[0]} | {k[1]} | >= {rs[0]['goal']} | {len(m)} | {rate(m)} | {rate([r for r in m if not r['guard']])} | {rate([r for r in m if r['guard']])} "
                 f"| {rate([r for r in m if r['merge'] and not r['guard']])} | {rate([r for r in m if r['merge'] and r['guard']])} | {rate(sep)} "
                 f"| {', '.join(mins)} | {len(rs) - len(m)} |")
    z = [r for r in rows if r.get('z3_agrees') != '']
    if z:
        L += ['', f"z3 engine (scripts/glitchsat.py, 6 cycles, k = goal-1) agrees with the simulator (6 cycles) on {sum(1 for r in z if r['z3_agrees'] is True)} of {len(z)} netlists."]
    return '\n'.join(L) + '\n'


def write_csv(rows, path):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def yosys_version(yosys):
    try:
        return subprocess.run([yosys, '-V'], capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ''


def main(specs_dir, outdir, quick=False, dry_run=False, yosys='yosys', root=None, z3=False, workers=None, time_limit=600, log=print, use_cache=True):
    if not dry_run and not shutil.which(yosys):
        raise SystemExit(f'{yosys} not found: install Yosys (cloud/run_cloud.sh) or use --dry-run')
    yv = '' if dry_run else yosys_version(yosys)
    os.makedirs(outdir, exist_ok=True)
    root = root or os.environ.get('GLITCHSAT_ROOT', '')
    jobs = []
    for fn in sorted(os.listdir(specs_dir)):
        if fn.endswith('.spec.json'):
            jobs += jobs_for(os.path.join(specs_dir, fn), outdir, quick, None if dry_run else yosys, root, z3, time_limit, yv, use_cache)
    if not jobs:
        raise SystemExit(f'no *.spec.json in {specs_dir}')
    t0 = time.time()
    rows = []
    workers = workers or max(1, os.cpu_count() or 1)
    with ProcessPoolExecutor(workers) as ex:
        for i, row in enumerate(ex.map(_job, jobs, chunksize=1)):
            rows.append(row)
            if not dry_run:
                log(f"[{i + 1}/{len(jobs)}] {row['design']}:{row['which']} {row['config']}: {row['status']} min={row['min_flips']} "
                    f"meets={row['meets_goal']} ({time.time() - t0:.0f}s)")
    write_csv(rows, os.path.join(outdir, 'resynth_rows.csv'))
    head = ('# Re-synthesis check\n\nEvery row of resynth_rows.csv: one Yosys configuration of the before or after Verilog, re-verified by exhaustive '
            'simulation (all wrong inputs, every number of cycles, up to the goal). Modelled flips, toy designs.\n'
            '"meet goal" = function equals the description for all 256 inputs, right key boots, no wrong key boots, and no attack with '
            'fewer than goal flips. Configurations: research/c2/e2_variance (96) x copy-separation guard off/on.\n\n')
    body = summarise(rows) if not dry_run else f'dry run: {len(rows)} scripts written, nothing synthesised\n'
    if yv:
        head += f'Yosys: {yv}\n\n'
    with open(os.path.join(outdir, 'resynth_summary.md'), 'w') as f:
        f.write(head + body)
    return rows
