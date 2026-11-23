#!/usr/bin/env python3
"""GlitchSAT Labs, masking: build the example gadgets and run the first-order probing check.

Example (smallest meaningful set, about 10 s):
  naive_and2      own textbook gadget, known INSECURE (no randomness)
  isw_and2        own textbook ISW AND: known secure without glitches, known insecure with glitches
  dom_indep_and2  own textbook DOM-indep AND: known secure in both models
  ot_dom_and      OpenTitan prim_dom_and_2share (DW=1), elaborated with Yosys 0.71 read_slang
  ot_gf2p2_mul    OpenTitan aes_dom_indep_mul_gf2pn (NPower=2), the DOM multiplier inside the masked S-box
  ot_sbox_dom     OpenTitan aes_sbox_dom: build only (too many random bits for exhaustive counting)

Own gadgets are built twice: `plain` (structure kept: proc, flatten, techmap) and `synth` (Yosys `synth`
with abc), to see whether synthesis keeps the masking ("does it survive?").

usage: run_labs.py [--out results/labs_result.json] [--quick]   (--quick: own gadgets only)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), 'labs'))
import labs_result as LR  # noqa: E402
from masking import probe  # noqa: E402

Y33 = os.environ.get('Y33') or shutil.which('yosys') or 'yosys'                                    # any Yosys >= 0.33
Y71 = os.environ.get('Y71') or os.environ.get('GLITCHSAT_YOSYS_SLANG') or shutil.which('yosys') or 'yosys'   # one with read_slang
OT = os.environ.get('OT_SRC', os.path.join(ROOT, 'work', 'ot'))
WORK = os.path.join(ROOT, 'work', 'labs')
SH = os.path.join(ROOT, 'shims')
PRIM = os.path.join(OT, 'hw', 'ip', 'prim', 'rtl')
PRIMG = os.path.join(OT, 'hw', 'ip', 'prim_generic', 'rtl')
AES = os.path.join(OT, 'hw', 'ip', 'aes', 'rtl')
TAIL = 'async2sync; dffunmap; techmap; opt_clean'
FLOWS = {'plain': 'proc; flatten; ' + TAIL,
         'synth': 'proc; flatten; synth -flatten -top {top}; abc -g AND,OR,XOR,MUX; ' + TAIL}
OT_COMMON = [os.path.join(PRIM, 'prim_assert.sv'), os.path.join(PRIMG, 'prim_generic_xor2.sv'),
             os.path.join(PRIMG, 'prim_generic_flop_en.sv'), os.path.join(PRIMG, 'prim_generic_flop.sv'),
             os.path.join(PRIMG, 'prim_generic_buf.sv'), os.path.join(PRIM, 'prim_sec_anchor_buf.sv'),
             os.path.join(SH, 'prim_xor2.sv'), os.path.join(SH, 'prim_flop_en.sv'), os.path.join(SH, 'prim_buf.sv')]

SHARES2 = {'a0': 'secret 0', 'a1': 'secret 0', 'b0': 'secret 1', 'b1': 'secret 1', 'r': 'volatile_random', 'clk': 'unimportant'}
OWN = [
    dict(id='naive_and2', top='naive_and2', expect={'standard': False, 'glitch': False}, labels=SHARES2,
         pairs=[('q0', 'q1')], what='textbook masked AND without fresh randomness (known insecure)'),
    dict(id='isw_and2', top='isw_and2', expect={'standard': True, 'glitch': False}, labels=SHARES2,
         pairs=[('q0', 'q1')], what='textbook ISW masked AND, no registers (known: secure without glitches, insecure with glitches)'),
    dict(id='dom_indep_and2', top='dom_indep_and2', expect={'standard': True, 'glitch': True}, labels=SHARES2,
         pairs=[('q0', 'q1')], what='textbook DOM-indep masked AND with registered cross terms (known secure in both models)'),
]
OT_EX = [
    dict(id='ot_dom_and', top='prim_dom_and_2share', params=['-G', 'DW=1'],
         files=[os.path.join(PRIM, 'prim_dom_and_2share.sv')],
         labels={'a0_i': 'secret 0', 'a1_i': 'secret 0', 'b0_i': 'secret 1', 'b1_i': 'secret 1', 'z_i': 'volatile_random',
                 'z_valid_i': 'fixed 1', 'rst_ni': 'fixed 1', 'clk_i': 'unimportant'},
         pairs=[('q0_o', 'q1_o')], what='OpenTitan prim_dom_and_2share, 1 bit wide, Pipeline=0'),
    dict(id='ot_gf2p2_mul', top='aes_dom_indep_mul_gf2pn', params=['-G', 'NPower=2'],
         files=None,
         labels={'a_x[0]': 'secret 0', 'b_x[0]': 'secret 0', 'a_x[1]': 'secret 1', 'b_x[1]': 'secret 1',
                 'a_y[0]': 'secret 2', 'b_y[0]': 'secret 2', 'a_y[1]': 'secret 3', 'b_y[1]': 'secret 3',
                 'z_0': 'volatile_random', 'we_i': 'fixed 1', 'rst_ni': 'fixed 1', 'clk_i': 'unimportant'},
         pairs=[('a_q', 'b_q')], what='OpenTitan aes_dom_indep_mul_gf2pn, NPower=2 (a GF(2^2) DOM multiplier of the masked S-box)'),
]
SBOX = dict(id='ot_sbox_dom', top='aes_sbox_dom',
            files=[os.path.join(OT, 'hw', 'ip', 'prim', 'rtl', 'prim_util_pkg.sv'), os.path.join(AES, 'aes_reg_pkg.sv'),
                   os.path.join(AES, 'aes_pkg.sv'), os.path.join(AES, 'aes_sbox_canright_pkg.sv'), os.path.join(AES, 'aes_sbox_dom.sv')])


def yosys(binary, script, log):
    r = subprocess.run([binary, '-q', '-l', log, '-p', script], capture_output=True, text=True, timeout=540)
    if r.returncode != 0:
        raise RuntimeError('yosys failed (%s): %s' % (log, (r.stdout + r.stderr)[-800:]))


def build_own(g, flow):
    d = os.path.join(WORK, '%s_%s' % (g['id'], flow))
    os.makedirs(d, exist_ok=True)
    net = os.path.join(d, 'net.json')
    yosys(Y33, 'read_verilog %s; hierarchy -top %s; %s; stat; write_json %s' % (
        os.path.join(ROOT, 'gadgets', g['id'] + '.v'), g['top'], FLOWS[flow].format(top=g['top']), net), os.path.join(d, 'yosys.log'))
    return net


def build_ot(e, flow='plain'):
    e = dict(e, files=e['files'] or SBOX['files'])
    d = os.path.join(WORK, e['id'])
    os.makedirs(d, exist_ok=True)
    net = os.path.join(d, 'net.json')
    files = ' '.join(OT_COMMON + e['files'])
    yosys(Y71, 'read_slang -D SYNTHESIS -I %s --top %s %s %s; hierarchy -check; %s; stat; write_json %s' % (
        PRIM, e['top'], ' '.join(e.get('params', [])), files, FLOWS[flow].format(top=e['top']), net), os.path.join(d, 'yosys.log'))
    return net


def analyse(net, top, labels, pairs):
    c = probe.Circuit(probe.load(net, top), labels)
    out = dict(stats=c.stats(), unmasked_output_ok=c.output_ok(pairs))
    for model in ('standard', 'glitch'):
        out[model] = c.check(model, 1)
    return out


def word(secure):
    return 'no leak found' if secure else 'LEAKS'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'results', 'labs_result.json'))
    ap.add_argument('--quick', action='store_true', help='own textbook gadgets only (no OpenTitan sources needed)')
    a = ap.parse_args(argv)
    t0, started, errors, findings, rows = time.time(), LR.now(), [], [], {}
    for g in OWN:
        for flow in FLOWS:
            key = '%s/%s' % (g['id'], flow)
            try:
                r = analyse(build_own(g, flow), g['top'], g['labels'], g['pairs'])
                r['expected'] = g['expect']
                r['matches_textbook'] = all(r[m]['secure'] == g['expect'][m] for m in ('standard', 'glitch'))
                rows[key] = r
            except Exception as ex:            # noqa: BLE001 - a Labs run reports, it does not crash
                errors.append('%s: %s' % (key, ex))
    if not a.quick:
        for e in OT_EX:
            try:
                rows[e['id'] + '/plain'] = analyse(build_ot(e), e['top'], e['labels'], e['pairs'])
            except Exception as ex:            # noqa: BLE001
                errors.append('%s: %s' % (e['id'], ex))
        try:
            net = build_ot(SBOX)
            m = probe.load(net, SBOX['top'])
            rows['ot_sbox_dom/plain'] = dict(built=True, cells=len(m['cells']),
                                             input_bits=sum(len(p['bits']) for p in m['ports'].values() if p['direction'] == 'input'))
        except Exception as ex:                # noqa: BLE001
            errors.append('ot_sbox_dom: %s' % ex)

    for g in OWN:
        for flow in FLOWS:
            r = rows.get('%s/%s' % (g['id'], flow))
            if not r:
                continue
            ex = r['glitch']['examples'][:1] or r['standard']['examples'][:1]
            plain = rows.get('%s/plain' % g['id'])
            why = ''
            if flow == 'synth' and not r['matches_textbook'] and plain and plain['matches_textbook']:
                why = (' Yosys `synth` regrouped the AND/XOR terms (%d cells instead of %d) and the regrouped circuit leaks:'
                       ' the masking did not survive synthesis.' % (r['stats']['cells'], plain['stats']['cells']))
            findings.append(LR.finding(
                '%s.%s' % (g['id'], flow),
                '%s, built with the %s flow: standard probing model %s, glitch model %s (%s the textbook expectation).%s' % (
                    g['what'], flow, word(r['standard']['secure']), word(r['glitch']['secure']),
                    'matches' if r['matches_textbook'] else 'DOES NOT match', why),
                'SIMULATED', standard=r['standard']['leaking_sets'], glitch=r['glitch']['leaking_sets'],
                probe_sets=r['standard']['probe_sets'], expected=g['expect'], matches_textbook=r['matches_textbook'],
                unmasked_output_ok=r['unmasked_output_ok'], cells=r['stats']['cells'], example_leak=ex))
    for e in OT_EX:
        r = rows.get(e['id'] + '/plain')
        if not r:
            continue
        findings.append(LR.finding(
            e['id'], '%s: standard probing model %s, glitch model %s, first order, in the "inputs held stable, enable on" setting.' % (
                e['what'], word(r['standard']['secure']), word(r['glitch']['secure'])),
            'SIMULATED', standard=r['standard']['leaking_sets'], glitch=r['glitch']['leaking_sets'],
            probe_sets=r['standard']['probe_sets'], unmasked_output_ok=r['unmasked_output_ok'], cells=r['stats']['cells'],
            share_and_random_bits=r['stats']['share_and_random_bits']))
    s = rows.get('ot_sbox_dom/plain')
    if s:
        findings.append(LR.finding('ot_sbox_dom.build', 'OpenTitan aes_sbox_dom (the full masked S-box) elaborates with Yosys 0.71 '
                                   'read_slang and maps to %d single-bit cells.' % s['cells'], 'MEASURED', cells=s['cells'],
                                   input_bits=s['input_bits']))
    findings.append(LR.finding('ot_sbox_dom.probing', 'Whether the full masked S-box is first-order secure under glitches: not checked. '
                               'It has too many share and random bits for exhaustive counting; a smarter engine is needed.', 'UNTESTED'))
    findings.append(LR.finding('transitions', 'Leakage from value changes between cycles (transition leakage) and higher orders: not checked.',
                               'UNTESTED'))
    d = LR.make('masking', 'Side-channel masking survival',
                'Does a masked circuit still hide its secret from someone who measures one wire, with and without glitches, '
                'and does that stay true after synthesis?',
                dict(name='3 textbook gadgets x 2 build flows + 2 OpenTitan gadgets', description=__doc__.split('\n\n')[1].strip(),
                     command='python3 ext/masking/scripts/run_labs.py' + (' --quick' if a.quick else '')),
                findings,
                ['Exact counting on a model: first-order probes only, inputs held stable, flip-flops settled, enable active.',
                 'Glitch model is the usual "a probe sees its whole combinational cone up to registers"; real glitches can be '
                 'weaker or stronger (routing, couplings).',
                 'Transition leakage, multi-cycle effects and order 2 or more are not checked.',
                 'Exhaustive: limited to 20 share and random bits; the full OpenTitan S-box is out of reach.',
                 'No power traces were recorded; nothing here is measured on a chip.'],
                dict(started=started, seconds=round(time.time() - t0, 2), ok=not errors, errors=errors,
                     tools=dict(yosys33=Y33, yosys71=Y71), rows=rows))
    LR.write(a.out, d)
    print('wrote %s (%d findings, %d errors, %.1f s)' % (a.out, len(findings), len(errors), time.time() - t0))
    for f in findings:
        print(' [%s] %s' % (f['label'], f['text']))
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
