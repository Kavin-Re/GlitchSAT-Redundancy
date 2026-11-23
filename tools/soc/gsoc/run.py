"""Steps of the whole-chip analysis. Every step writes one JSON file under results/runs/ and is skipped when that
file already exists (use force=True to redo), so a run can be resumed after an interruption.

Result labels
  BOUNDED   exact minimum number of faults WITHIN T CYCLES: an attack of that size was found and replayed on the
            whole chip, and the solver showed that no smaller one exists in the model within those T cycles. It is
            not an unbounded proof (nothing is said about runs longer than T), so it is never called PROVED.
  PARTIAL   only a range is known within T cycles: an interval lo..hi, or "no attack with up to k faults".
  SAMPLED   a simulation campaign: counts over the faults that were tried, no statement about the others.
All of them are statements about the modelled faults (single-cycle bit flips on cell outputs) on this netlist.
"""
import json
import os
import re
import shutil
import time

import yaml

from . import SOC, frontend, chip as chipmod, sim, slicer, gscale

G = gscale()
RUNS = os.path.join(SOC, 'results', 'runs')
WORK = os.environ.get('GSOC_WORK') or os.path.join(SOC, 'work')
SRC_DIRS = {'picosoc': 'picorv32', 'ibex_demo': 'ids'}


def load_cfg(name):
    d = os.path.join(SOC, 'chips', name)
    with open(os.path.join(d, 'chip.yaml')) as f:
        cfg = yaml.safe_load(f)
    cfg['_dir'] = d
    return cfg


def src_root(cfg):
    return os.path.join(WORK, 'src', cfg.get('source_dir') or SRC_DIRS.get(cfg['name'], cfg['name']))


def tag(cfg, variant, flow):
    return '%s.%s.%s' % (cfg['name'], variant or 'default', flow)


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    text = json.dumps(obj, indent=1, sort_keys=True, default=str)
    for prefix in (SOC + os.sep, os.path.dirname(SOC) + os.sep):      # no absolute paths of this checkout in results
        text = text.replace(prefix, '')
    text = re.sub(r'/[^"\s|]*?/share/yosys/', 'share/yosys/', text)
    with open(tmp, 'w') as f:
        f.write(text)
    os.replace(tmp, path)


def _load(path):
    with open(path) as f:
        return json.load(f)


def backend():
    b = os.environ.get('GSOC_BACKEND')
    if b:
        return b
    for name in ('cadical', 'kissat'):
        if shutil.which(name):
            return 'dimacs:' + name
    return 'py'


def _yosys_version(cfg):
    import subprocess
    try:
        out = subprocess.run([frontend.yosys_binary(cfg), '-V'], capture_output=True, text=True, timeout=20).stdout
        return ' '.join(out.split()[:2])
    except Exception:
        return 'yosys (version not read)'


class Session:
    """One chip netlist loaded once: circuit, reset state, compiled simulator."""

    def __init__(self, cfg, variant, flow, log=print):
        self.cfg, self.variant, self.flow, self.log = cfg, variant, flow, log
        pre = (cfg.get('prebuilt') or {}).get(flow)
        if pre:                       # a netlist made outside frontend.run (chips/earlgrey/frontend.sh)
            p = pre if os.path.isabs(pre) else os.path.join(WORK, pre)
            if not os.path.exists(p):
                raise FileNotFoundError('prebuilt netlist %s not found: build it first (see the chip folder)' % p)
            self.fe = dict(netlist=p, seconds=None, cached=True, script=p)
        else:
            self.fe = frontend.run(cfg, flow, os.path.join(WORK, cfg['name']), src_root(cfg), variant)
        t0 = time.time()
        self.chip = chipmod.load(self.fe['netlist'], frontend.top_of(cfg, variant), clock=cfg.get('clock'),
                                 name=tag(cfg, variant, flow))
        self.order = sim.topo_all(self.chip.circ)
        self.load_s = round(time.time() - t0, 2)
        rs = cfg.get('reset')
        self.reset = rs
        t0 = time.time()
        if rs:
            held = {}
            for b in self.chip.circ.ports[rs['port']][1]:
                held[b] = bool(int(rs.get('active', 0)))
            for p, v in (cfg.get('reset_straps') or {}).items():
                for i, b in enumerate(self.chip.circ.ports[p][1]):
                    held[b] = bool((int(v) >> i) & 1)
            self.state, self.reset_info = sim.reset_state(self.chip, held, int(rs.get('cycles', 16)), order=self.order)
        else:
            self.state = {q: bool(self.chip.init_attr.get(q, False)) for q in self.chip.circ.flops}
            self.reset_info = dict(note='no reset given: flops start at their initial value, or 0')
        self.reset_info['seconds'] = round(time.time() - t0, 2)
        self._comp = None

    @property
    def comp(self):
        if self._comp is None:
            self._comp = sim.Compiled(self.chip.circ, self.order)
        return self._comp

    def chip_record(self):
        i = dict(self.chip.info)
        i['cell_types'] = dict(i['cell_types'])
        return dict(schema='glitchsat-soc-chip/1', chip=self.cfg['name'], variant=self.variant, flow=self.flow,
                    top=i['top'], source=self.cfg.get('source'), frontend=dict(
                        tool=_yosys_version(self.cfg),
                        seconds=self.fe['seconds'], script=os.path.relpath(self.fe['script'], SOC)),
                    stats=i, reset=self.reset_info, load_seconds=self.load_s, label='MEASURED')


def goals_of(cfg, variant):
    out = []
    for g in cfg.get('goals') or []:
        if g.get('variants') and variant not in g['variants']:
            continue
        out.append(g)
    return out


def analyse_goal(sess, goal, time_s=240, workers=1, force=False, kmax=None, cycles=None, suffix=''):
    cfg = sess.cfg
    path = os.path.join(RUNS, '%s.goal.%s%s.json' % (tag(cfg, sess.variant, sess.flow), goal['id'], suffix))
    if os.path.exists(path) and not force:
        return _load(path)
    goal = dict(goal)
    if cycles: goal['cycles'] = cycles
    k = int(kmax or goal.get('kmax', 3))
    t0 = time.time()
    b = slicer.build(sess.chip, goal, sess.reset, sess.state)
    growth, depth = slicer.cone_growth(sess.chip, goal, max(12, int(goal['cycles'])))
    slice_s = round(time.time() - t0, 2)
    be = backend()
    before = _solver_files()
    try:
        o = G.search.analyse(b.P, k, time_s=time_s, workers=workers, backend=be, modules=goal.get('modules', 'auto'))
    finally:
        _reap_solvers(before)
    status = o['status']
    label = 'BOUNDED' if status == 'EXACT' else 'PARTIAL'   # never PROVED: no unbounded proof here
    rec = dict(
        schema='glitchsat-soc-goal/1', chip=cfg['name'], variant=sess.variant, flow=sess.flow, goal=goal['id'],
        title=goal.get('title'), plain=goal.get('plain'), where=goal.get('where'),
        spec=dict(hit=goal.get('hit'), hold=int(goal.get('hold', 1)), quiet=goal.get('quiet') or [],
                  attacker=goal.get('attacker'), fix=goal.get('fix') or {}, cycles=int(goal['cycles']), kmax=k),
        label=label, status=status, lo=o['lo'], hi=o['hi'],
        min_faults=o['hi'] if status == 'EXACT' else None,
        text=o['text'], lo_by=o.get('lo_by'), hi_by=o.get('hi_by'),
        slice=b.info, cone_growth=growth, cone=depth,
        search=dict(seconds=o['runtime_s'], slice_seconds=slice_s, time_limit_s=time_s, timed_out=o.get('timed_out'),
                    backend=be, workers=workers, reduction=o.get('reduction'),
                    modules=dict(count=len(o.get('modules') or []), names=[m['name'] for m in (o.get('modules') or [])][:12]),
                    parts=o.get('parts'), events=o.get('events')),
    )
    if o.get('witness'):
        w = o['witness']
        chk = slicer.replay_on_chip(sess.chip, b, sess.comp, o['_witness_raw'], sess.state)
        if not chk['ok']:
            raise RuntimeError('witness for %s does not replay on the whole chip: %s' % (goal['id'], chk))
        ins, fl = o['_witness_raw']
        free_used = sum(1 for kx, v in ins.items() if v and ((kx in b.init_in) or (isinstance(kx, tuple) and kx[1] in sess.chip.free) or kx in sess.chip.free))
        att = None
        if b.neq:
            att = sum(1 << i for i, x in enumerate(b.neq[0]) if ins.get(x, False))
        rec['witness'] = dict(
            faults=[dict(cycle=f['cycle'], net=f['name'], cell=sess.chip.circ.cell.get(f['net'], ''),
                         kind='flop' if f['net'] in sess.chip.circ.flops else 'gate') for f in w['faults']],
            hit_cycle=w['hit_cycle'], attacker_value=att,
            replayed_on_slice=True, replayed_on_whole_chip=True, whole_chip_hit_cycle=chk['hit_cycle'],
            free_values_set_to_1=free_used,
            note=('uses %d unknown start value(s) / black-box value(s) chosen by the solver' % free_used) if free_used else
                 'does not depend on any unknown start value or black-box value being 1')
    _save(path, rec)
    return rec


def _solver_files():
    import glob, tempfile
    return set(glob.glob(os.path.join(tempfile.gettempdir(), 'gscale_*.cnf')))


def _reap_solvers(before):
    """With two workers the losing worker is terminated; a solver process it started on a DIMACS file can outlive
    it. Stop every solver that runs on a file created during this search, and remove those files."""
    import signal
    new = _solver_files() - before
    if not new:
        return 0
    n = 0
    for pid in [p for p in os.listdir('/proc') if p.isdigit()] if os.path.isdir('/proc') else []:
        try:
            with open('/proc/%s/cmdline' % pid, 'rb') as f:
                cmd = f.read().decode(errors='replace').split('\0')
        except OSError:
            continue
        if any(a in new for a in cmd):
            try:
                os.kill(int(pid), signal.SIGKILL); n += 1
            except OSError:
                pass
    for f in new:
        try: os.remove(f)
        except OSError: pass
    return n


def chip_step(sess, force=False):
    path = os.path.join(RUNS, '%s.chip.json' % tag(sess.cfg, sess.variant, sess.flow))
    rec = sess.chip_record()
    _save(path, rec)
    return rec
