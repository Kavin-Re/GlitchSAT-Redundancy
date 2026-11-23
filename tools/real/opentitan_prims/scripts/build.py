#!/usr/bin/env python3
"""Build every experiment netlist from the pinned OpenTitan sources.

Flow (see README, "How the netlists are made"):
  1. Yosys 0.71, built-in SystemVerilog frontend:
       read_slang --keep-hierarchy -D SYNTHESIS -I src --top TOP <files>; hierarchy -check; proc
     -> work/<id>/elab.v   (elaborated, hierarchical, word-level Verilog-2005)
  2. Yosys 0.33 (the version of the earlier GlitchSAT results) reads elab.v and runs the
     repository's plain flow (scripts/synth.sh) plus memory, async2sync and sim -w
     -> work/<id>/net.json       (the netlist every engine reads)
  3. Cross-check: Yosys 0.71 runs the same flow on its own elaboration -> work/<id>/net71.json
  4. FSM variants (fsm_* ids): the repository's opt flow (flatten + full `synth`), with and
     without FSM optimisation, see FLOWS below.

usage: build.py [ID ...]        (no id = all experiments in experiments.tsv)
Env:   Y71, Y33 (Yosys binaries), OT_SRC (sources dir).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.environ.get('OT_SRC', os.path.join(ROOT, 'src'))
WORK = os.environ.get('OT_WORK', os.path.join(ROOT, 'work'))   # OT_WORK: Labs runs build into their own folder
Y71 = os.environ.get('Y71') or os.environ.get('GLITCHSAT_YOSYS_SLANG') or shutil.which('yosys') or 'yosys'   # one with read_slang
Y33 = os.environ.get('Y33') or shutil.which('yosys') or 'yosys'
PY = sys.executable

COMMON = ['prim_generic_flop.sv', 'prim_generic_buf.sv', 'prim_generic_xor2.sv',
          'prim_generic_flop_2sync.sv', 'prim_sec_anchor_buf.sv']

# Synthesis flows after elaboration. 'plain' = repository scripts/synth.sh plain flow
# (+ memory, async2sync, sim -w). The 'opt*' flows follow scripts/synth.sh opt flow
# (`synth` then the plain mapping), with the design flattened first so that the FSM passes
# can see the state register together with its next-state logic (in OpenTitan the state
# register sits in prim_sparse_fsm_flop, a separate module).
TAIL = ['abc -g AND,OR,XOR,MUX', 'opt_clean', 'setattr -mod -unset keep_hierarchy *', 'flatten',
        'opt_clean', 'techmap', 'opt_clean']
# The target module (the wrapper's instance u_dut) is flattened into ONE module and kept apart from
# the wrapper during `synth`, so the wrapper's constant tie-offs are not folded into it (the target
# is synthesised as a stand-alone module with free inputs, as SYNFI synthesised it).
KEEPDUT = 'setattr -mod -set keep_hierarchy 1 {dut}'
# Keeps the NAME of the FSM state signal through `synth` (opt_clean would otherwise drop it), so
# the state-register fault sites can be found in the netlist. It does not stop the FSM passes
# (fsm_detect/fsm_extract do not look at `keep`); used identically in all opt* flows.
NAMEKEEP = 'setattr -set keep 1 w:aes_cipher_ctrl_cs'
FLOWS = {
    'plain': ['proc', 'memory', 'async2sync', 'dffunmap', 'opt_clean', 'techmap', 'opt_clean'] + TAIL,
    # full synth incl. fsm (fsm_detect/extract/opt/recode/map)
    'opt_fsm': ['proc', KEEPDUT, 'flatten', NAMEKEEP, 'synth -top {top}', 'async2sync', 'dffunmap'] + TAIL,
    # same, FSM optimisation switched off (the option the SYNFI paper names)
    'opt_nofsm': ['proc', KEEPDUT, 'flatten', NAMEKEEP, 'synth -nofsm -top {top}', 'async2sync', 'dffunmap'] + TAIL,
    # same as opt_fsm, but the state register carries fsm_encoding="none" (a keep constraint:
    # fsm_detect skips it); everything else is optimised as in opt_fsm
    'opt_fsm_keep': ['proc', KEEPDUT, 'flatten', NAMEKEEP,
                     'setattr -set fsm_encoding "none" w:*aes_cipher_ctrl_cs* w:*state_raw* w:*u_state_flop*',
                     'synth -top {top}', 'async2sync', 'dffunmap'] + TAIL,
}


def read_tsv():
    rows = []
    with open(os.path.join(ROOT, 'experiments.tsv')) as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            p = line.rstrip('\n').split('\t')
            rows.append(dict(id=p[0], top=p[1], wrapper=p[2], packages=p[3], modules=p[4],
                             goal_value=p[5], key=p[6], cycles=int(p[7]), kmax=int(p[8]),
                             flow=p[9], sites=p[10], prediction=p[11] if len(p) > 11 else ''))
    return rows


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def yosys(binary, script, log, timeout=580):
    with open(script + '.ys', 'w') as f:
        f.write(script_text(script))
    r = subprocess.run([binary, '-q', '-l', log, '-s', script + '.ys'], capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode != 0:
        tail = open(log).read().splitlines()[-25:] if os.path.exists(log) else []
        raise RuntimeError('yosys failed (%s):\n%s\n%s' % (binary, r.stderr[-2000:], '\n'.join(tail)))


_SCRIPTS = {}


def script_text(key):
    return _SCRIPTS[key]


def files_for(e):
    fs = [os.path.join(SRC, x) for x in e['packages'].split(',') if x]
    fs += [os.path.join(SRC, x) for x in COMMON]
    fs += [os.path.join(SRC, x) for x in e['modules'].split(',') if x]
    fs += sorted(os.path.join(ROOT, 'shims', x) for x in os.listdir(os.path.join(ROOT, 'shims')))
    fs.append(os.path.join(ROOT, 'wrappers', e['wrapper']))
    for x in fs:
        if not os.path.isfile(x):
            raise FileNotFoundError(x)
    return fs


def stat_counts(netjson, top):
    m = json.load(open(netjson))['modules'][top]
    gates = flops = 0
    types = {}
    for c in m['cells'].values():
        t = c['type']
        types[t] = types.get(t, 0) + 1
        if t == '$_DFF_P_':
            flops += 1
        elif t != '$scopeinfo':
            gates += 1
    return gates, flops, types


def build(e):
    d = os.path.join(WORK, e['id'])
    os.makedirs(d, exist_ok=True)
    top = e['top']
    fs = files_for(e)
    flow = e['flow']
    meta = {'id': e['id'], 'top': top, 'flow': flow, 'inputs': {os.path.relpath(x, ROOT): sha(x) for x in fs}}

    # 1. elaboration with Yosys 0.71 / slang
    k = os.path.join(d, 'elab')
    for x in fs + [SRC, d]:  # paths go into a Yosys script unquoted (read_slang keeps quotes)
        if any(ch in x for ch in ' \t"\';#\\`'):
            raise ValueError('path not accepted: %r' % x)
    _SCRIPTS[k] = ('read_slang --keep-hierarchy -D SYNTHESIS -I %s --top %s %s\n'
                   'hierarchy -check -top %s\nproc\n'
                   'tee -q -o %s/elab_stat.txt stat\n'
                   'bwmuxmap\n'
                   'write_verilog -noattr %s/elab.v\n'
                   'write_rtlil %s/elab.il\n') % (SRC, top, ' '.join(fs), top, d, d, d)
    yosys(Y71, k, os.path.join(d, 'elab.log'))

    dut = None
    cur = None
    for line in open(os.path.join(d, 'elab.v')):
        t = line.split()
        if t[:1] == ['module']:
            cur = t[1].split('(')[0]
        elif cur == top and len(t) >= 3 and t[1] == 'u_dut' and t[2].startswith('('):
            dut = t[0].lstrip('\\')
    if dut is None and '{dut}' in ' '.join(FLOWS[flow]):   # only the opt* flows need the u_dut instance
        raise RuntimeError('instance u_dut not found in %s' % top)
    meta['dut_module'] = dut
    steps = [s.format(top=top, dut=dut) for s in FLOWS[flow]]
    simw = ['sim -clock clk -n 1 -w %s' % top, 'opt_clean']

    def finish(binary, src_cmds, out):
        kk = os.path.join(d, out)
        _SCRIPTS[kk] = '\n'.join(src_cmds + ['hierarchy -check -top %s' % top] + steps + simw +
                                 ['tee -q -o %s/%s_stat.txt stat' % (d, out),
                                  'write_json %s/%s.json' % (d, out)]) + '\n'
        yosys(binary, kk, os.path.join(d, out + '.log'))
        chk = subprocess.run([PY, '-I', os.path.join(ROOT, 'check_netlist.py'), os.path.join(d, out + '.json'),
                              top, 'sim'], capture_output=True, text=True)
        if chk.returncode != 0:
            raise RuntimeError('netlist check failed for %s: %s' % (out, chk.stdout + chk.stderr))
        return chk.stdout.strip()

    # 2. main netlist: Yosys 0.33 finishes from the elaborated Verilog
    meta['check'] = finish(Y33, ['read_verilog -sv %s/elab.v' % d], 'net')
    # 3. cross-check netlist: Yosys 0.71 runs the same flow on its own elaboration
    meta['check71'] = finish(Y71, ['read_rtlil %s/elab.il' % d], 'net71')
    g, f, t = stat_counts(os.path.join(d, 'net.json'), top)
    g71, f71, _ = stat_counts(os.path.join(d, 'net71.json'), top)
    meta.update(gates=g, flops=f, cell_types=t, gates71=g71, flops71=f71,
                net_sha256=sha(os.path.join(d, 'net.json')),
                yosys_elab=subprocess.run([Y71, '-V'], capture_output=True, text=True).stdout.strip(),
                yosys_synth=subprocess.run([Y33, '-V'], capture_output=True, text=True).stdout.strip())
    json.dump(meta, open(os.path.join(d, 'build.json'), 'w'), indent=1)
    return meta


def main(argv):
    want = set(argv[1:])
    status = 0
    for e in read_tsv():
        if want and e['id'] not in want:
            continue
        try:
            m = build(e)
            print('[%s] built: %d gates, %d flops (0.71 cross-check: %d gates, %d flops)  %s'
                  % (e['id'], m['gates'], m['flops'], m['gates71'], m['flops71'], m['check']))
        except Exception as ex:  # report and continue with the next experiment
            status = 3
            print('[%s] NOT BUILT: %s' % (e['id'], ex))
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv))
