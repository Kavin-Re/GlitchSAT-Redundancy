"""Whole-chip front end: RTL of a complete SoC -> one flattened gate-level Yosys JSON netlist per flow.

Flows (all end in the gate library the loader reads; none uses a cell library or timing):
  written   elaborate, flatten, map to gates. No sharing, no logic optimisation beyond constant folding. This is
            the chip "as written": redundant copies are still separate.
  keep      the standard `synth` flow; modules marked (* keep_hierarchy *) are synthesised on their own and
            flattened afterwards. Logic optimisation is `abc -g AND,OR,XOR,MUX` (the gate set of the engine).
  flat      as keep, but keep_hierarchy is removed first, so the optimiser sees redundant copies together.

Memories: arrays up to `memory_map_max_words` words become flops and multiplexers (modelled exactly). Larger ones
stay as one $mem_v2 cell that the loader treats as a black box (read data = free values).
"""
import os
import shutil
import subprocess
import time

from . import SOC


class FrontendError(Exception):
    pass


def yosys_binary(cfg):
    need_slang = cfg.get('frontend') == 'slang'
    cands = [os.environ.get('GSOC_YOSYS')]
    if need_slang:
        cands = [os.environ.get('GSOC_YOSYS_SLANG')] + cands
    cands += [shutil.which('yosys')]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise FrontendError('yosys not found (set GSOC_YOSYS%s)' % (' / GSOC_YOSYS_SLANG to a Yosys with read_slang' if need_slang else ''))


def _rel(p):
    """Paths in the Yosys script are relative to ext/soc (Yosys runs there), so that the cell names Yosys derives
    from source locations do not contain the absolute path of the checkout."""
    r = os.path.relpath(os.path.abspath(p), SOC)
    return p if r.startswith('..' + os.sep + '..' + os.sep + '..') else r


def top_of(cfg, variant=None):
    if variant and (cfg.get('variants') or {}).get(variant, {}).get('top'):
        return cfg['variants'][variant]['top']
    return cfg['top']


def script(cfg, flow, out_json, src_root, variant=None):
    top = top_of(cfg, variant)
    defs = dict(cfg.get('defines') or {})
    extra = []
    if variant:
        vv = (cfg.get('variants') or {})[variant]
        defs.update(vv.get('defines') or {})
        extra = vv.get('files') or []
    files = []
    for f in list(cfg['files']) + list(extra):
        p = f if os.path.isabs(f) else os.path.join(src_root if not os.path.exists(os.path.join(cfg['_dir'], f)) else cfg['_dir'], f)
        if not os.path.exists(p):
            raise FrontendError('source file not found: %s (run the chip\'s fetch.sh first)' % p)
        files.append(_rel(p))
    incs = [_rel(d if os.path.isabs(d) else os.path.join(src_root, d)) for d in cfg.get('include_dirs') or []]
    out_json = _rel(out_json)
    L = []
    if cfg.get('frontend') == 'slang':
        if os.environ.get('GSOC_SLANG_PLUGIN'):      # Yosys builds where read_slang is a plugin (OSS CAD Suite)
            L.append('plugin -i slang')
        cmd = ['read_slang', '--top', top] + cfg.get('slang_args', [])
        for k, v in defs.items(): cmd.append('-D%s=%s' % (k, v) if v not in (None, '') else '-D%s' % k)
        for d in incs: cmd += ['-I', d]
        for d in cfg.get('library_dirs') or []: cmd += ['-y', _rel(d if os.path.isabs(d) else os.path.join(src_root, d))]
        if cfg.get('library_dirs'): cmd += ['--libext', 'sv']
        for k, v in (cfg.get('parameters') or {}).items(): cmd += ['-G', '%s=%s' % (k, v)]
        L.append(' '.join(cmd + files))
    else:
        dd = ' '.join('-D%s=%s' % (k, v) if v not in (None, '') else '-D%s' % k for k, v in defs.items())
        ii = ' '.join('-I%s' % d for d in incs)
        for f in files:
            L.append('read_verilog -defer %s %s %s %s' % ('-sv' if f.endswith('.sv') else '', dd, ii, f))
        for k, v in (cfg.get('parameters') or {}).items():
            L.append('chparam -set %s %s %s' % (k, v, top))
    for bb in cfg.get('blackbox_modules') or []:
        L.append('blackbox %s' % bb)
    L.append('hierarchy -check -top %s' % top)
    mm = int(cfg.get('memory_map_max_words', 4096))
    memmap = 'memory_map t:$mem_v2 r:SIZE<=%d %%i' % mm
    if flow == 'written':
        L += ['proc', 'setattr -mod -unset keep_hierarchy', 'flatten', 'opt_expr', 'opt_clean', 'memory -nomap', memmap,
              'techmap', 'opt_expr', 'opt_clean']
    elif flow in ('keep', 'flat'):
        if flow == 'flat':
            L.append('setattr -mod -unset keep_hierarchy')
        L += ['synth -top %s -flatten -run begin:fine' % top,
              'opt -fast -full', memmap, 'opt -full', 'techmap', 'opt -fast',
              'abc -g AND,OR,XOR,MUX', 'opt -fast', 'opt_clean']
        if flow == 'keep':
            L += ['setattr -mod -unset keep_hierarchy', 'flatten', 'opt_clean']
    else:
        raise FrontendError('unknown flow %r' % flow)
    L += ['check', 'tee -o %s.stat stat' % out_json, 'write_json %s' % out_json]
    return '\n'.join(L) + '\n'


def run(cfg, flow, work, src_root, variant=None, timeout=570, force=False):
    """Returns dict(netlist, seconds, cached, log). Resumable: an existing netlist newer than the script is reused."""
    os.makedirs(work, exist_ok=True)
    tag = '%s%s_%s' % (cfg['name'], '_' + variant if variant else '', flow)
    out = os.path.join(work, tag + '.json')
    ys = os.path.join(work, tag + '.ys')
    text = script(cfg, flow, out, src_root, variant)
    if not force and os.path.exists(out) and os.path.exists(ys) and open(ys).read() == text and os.path.getsize(out) > 0:
        secs = None
        if os.path.exists(out + '.time'):
            secs = float(open(out + '.time').read())
        return dict(netlist=out, seconds=secs, cached=True, log=os.path.join(work, tag + '.log'), script=ys)
    with open(ys, 'w') as f:
        f.write(text)
    if os.path.exists(out):
        os.remove(out)
    t0 = time.time()
    log = os.path.join(work, tag + '.log')
    try:
        r = subprocess.run([yosys_binary(cfg), '-q', '-l', _rel(log), _rel(ys)], capture_output=True, text=True, timeout=timeout,
                           cwd=SOC)
    except subprocess.TimeoutExpired:
        raise FrontendError('yosys did not finish within %d s (flow %s); see %s' % (timeout, flow, log))
    secs = round(time.time() - t0, 1)
    if r.returncode != 0 or not os.path.exists(out):
        raise FrontendError('yosys failed (flow %s): %s' % (flow, (r.stderr or r.stdout)[-1500:]))
    with open(out + '.time', 'w') as f:
        f.write(str(secs))
    return dict(netlist=out, seconds=secs, cached=False, log=log, script=ys)
