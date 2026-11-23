#!/usr/bin/env python3
"""Cross-check the Liberty import against independent readers of the same cells.

For every cell of each library:
  A  exhaustive truth table: GlitchSAT's primitive network vs a direct evaluation of the parsed Liberty function
     (liberty.verify_cell; the check the importer runs on every cell a netlist uses);
  B  Yosys `read_liberty` (its own parser and its own function-to-gate conversion, no -lib): the cell module Yosys
     builds is imported and compared with GlitchSAT's mapping on every input combination and, for flip-flops, every
     stored value (outputs in the cycle and the next stored value), with the clock pin left out;
  C  sky130 only: the same cells as Liberty-in-JSON from google/skywater-pdk-libs-sky130_fd_sc_hd (pinned commit):
     every `function` / ff attribute parsed there must give the same truth table as the .lib text;
  D  Nangate45 only: the functions SYNFI documents for its cell library (lowRISC/synfi cell_lib_nangate45_autogen.py,
     the source of the repository's hand-written adapter real/glitchsat_real/nangate.py) vs the Liberty functions.

  python3 scripts/crosscheck_liberty.py [--out results/liberty_crosscheck.json]
Needs: GLITCHSAT_LIBS with the fetched libraries (scripts/fetch_libs.sh), Yosys on PATH.
"""
import argparse
import glob
import gzip
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from glitchsat_byod import liberty as LIB, netlist as NL, sim as SIM, flows as FL   # noqa: E402

LIBS = {k: os.path.join(FL.libs_dir(), v) for k, v in FL.KNOWN_LIBS.items()}


class _Ckt:
    def __init__(self):
        from glitchsat_byod.engine import gscale
        self.c = gscale().circuit.Circuit()


def table_mine(cell):
    """{(input bits..., stored): (outputs..., next)} from GlitchSAT's mapping."""
    b = LIB._TB()
    ck = cell.ff['clock_pin'] if cell.ff else None
    ins = [p for p in cell.inputs if p != ck]
    pins = {p: 'in_' + p for p in ins}
    if ck:
        pins[ck] = '0'
    outs = sorted(cell.outputs)
    res = {}
    if cell.kind == 'comb':
        o = LIB.map_comb(b, cell, pins)
        for bits in itertools.product((0, 1), repeat=len(ins)):
            env = {'in_' + p: v for p, v in zip(ins, bits)}
            res[bits] = tuple(int(b.ev(o[p], env, {})) for p in outs)
        return ins, outs, res
    d, o = LIB.ff_parts(b, cell, pins, 'q')
    for bits in itertools.product((0, 1), repeat=len(ins) + 1):
        env = {'in_' + p: v for p, v in zip(ins, bits)}; env['q'] = bits[-1]
        res[bits] = tuple(int(b.ev(o[p], env, {})) for p in outs) + (int(b.ev(d, env, {})),)
    return ins, outs, res


def table_yosys(mod, cell, ins, outs):
    R = NL.import_module(mod, cell.name, None, clock_ports=[])
    c = R.circ
    order = SIM.order(c)
    pb = {p: v['bits'][0] for p, v in mod['ports'].items()}
    res = {}
    qs = list(c.flops)
    if cell.ff and len(qs) != 1:
        return None, 'Yosys module has %d flip-flops' % len(qs)
    for bits in itertools.product((0, 1), repeat=len(ins) + (1 if cell.ff else 0)):
        inw = {pb[p]: v for p, v in zip(ins, bits)}
        st = {qs[0]: bits[-1]} if cell.ff else {}
        v, nxt = SIM.step(c, order, st, inw, 1)
        row = tuple(int(v.get(pb[p], 0)) if isinstance(pb[p], int) else int(pb[p] == '1') for p in outs)
        if cell.ff:
            row += (int(nxt[qs[0]]),)
        res[bits] = row
    return res, None


def crosscheck_yosys(name, lib, path, ys):
    work = tempfile.mkdtemp()
    p = path
    if p.endswith('.gz'):
        p = os.path.join(work, 'lib.lib')
        with gzip.open(path, 'rb') as fi, open(p, 'wb') as fo:
            shutil.copyfileobj(fi, fo)
    out = os.path.join(work, 'cells.json')
    r = subprocess.run([ys, '-q', '-p', 'read_liberty -ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch "%s"; write_json "%s"' % (p, out)],
                       capture_output=True, text=True)
    if r.returncode:
        return dict(error=r.stderr[-500:])
    mods = json.load(open(out))['modules']
    stats = dict(compared=0, agree=0, differ=[], not_in_yosys=[], skipped=[])
    for cn, cell in sorted(lib.cells.items()):
        if cell.kind not in ('comb', 'ff'):
            continue
        if cn not in mods or not mods[cn].get('cells') and not any(v['direction'] == 'output' for v in mods[cn]['ports'].values()):
            stats['not_in_yosys'].append(cn); continue
        try:
            ins, outs, mine = table_mine(cell)
            theirs, why = table_yosys(mods[cn], cell, ins, outs)
        except Exception as e:                 # noqa: BLE001
            stats['skipped'].append('%s: %s' % (cn, e)); continue
        if theirs is None:
            stats['skipped'].append('%s: %s' % (cn, why)); continue
        stats['compared'] += 1
        diff = [k for k in mine if mine[k] != theirs.get(k)]
        if diff:
            k = diff[0]
            stats['differ'].append(dict(cell=cn, rows_differing=len(diff), rows=len(mine), example=dict(
                inputs=dict(zip(ins + (['stored'] if cell.ff else []), k)), glitchsat=dict(zip(outs + (['next'] if cell.ff else []), mine[k])),
                yosys=dict(zip(outs + (['next'] if cell.ff else []), theirs[k])))))
        else:
            stats['agree'] += 1
    shutil.rmtree(work, ignore_errors=True)
    return stats


def crosscheck_libjson(lib):
    src = os.path.join(FL.libs_dir(), 'src', 'sky130_fd_sc_hd', 'cells')
    files = glob.glob(os.path.join(src, '*', '*__tt_025C_1v80.lib.json'))
    stats = dict(files=len(files), compared=0, agree=0, differ=[], missing_in_lib=[])
    for f in sorted(files):
        d = json.load(open(f))
        cname = os.path.basename(f).split('__tt_')[0]
        if cname not in lib.cells:
            stats['missing_in_lib'].append(cname); continue
        cell = lib.cells[cname]
        if cell.kind not in ('comb', 'ff'):
            continue
        funcs = {}
        for k, v in d.items():
            m = re.match(r'pin (\S+)', k)
            if m and isinstance(v, dict) and v.get('function'):
                funcs[m.group(1).strip('"')] = v['function']
        ok = True
        for p, f2 in funcs.items():
            if p not in cell.outputs:
                ok = False; break
            a, b = cell.outputs[p], LIB.parse_expr(f2)
            vs = sorted(LIB.expr_vars(a) | LIB.expr_vars(b))
            for bits in itertools.product((0, 1), repeat=len(vs)):
                env = dict(zip(vs, bits))
                if LIB.eval_expr(a, env) != LIB.eval_expr(b, env):
                    ok = False; break
        ffj = [v for k, v in d.items() if k.startswith('ff ')]
        if cell.ff and ffj:
            for key in ('next_state', 'clear', 'preset'):
                x, y = cell.ff.get(key), ffj[0].get(key)
                if (x is None) != (y is None):
                    ok = False
                elif x is not None:
                    yb = LIB.parse_expr(y)
                    vs = sorted(LIB.expr_vars(x) | LIB.expr_vars(yb))
                    for bits in itertools.product((0, 1), repeat=len(vs)):
                        env = dict(zip(vs, bits))
                        if LIB.eval_expr(x, env) != LIB.eval_expr(yb, env):
                            ok = False; break
        stats['compared'] += 1
        if ok:
            stats['agree'] += 1
        else:
            stats['differ'].append(cname)
    return stats


def crosscheck_synfi(lib):
    path = os.environ.get('SYNFI_CELL_LIB', '')
    if not os.path.isfile(path):
        return dict(error='SYNFI cell library not found (set SYNFI_CELL_LIB)')
    txt = open(path).read()
    stats = dict(compared=0, agree=0, differ=[], not_parsed=0)
    for m in re.finditer(r"def (\w+)\(inputs: dict, graph: nx.DiGraph, solver\):\s*'''(.*?)'''", txt, re.S):
        fname, doc = m.group(1), m.group(2)
        cell, _, pin = fname.rpartition('_')
        fm = re.search(r'Returns:\s*\n\s*(\w+)\s*=\s*(.+)', doc)
        if cell not in lib.cells or not fm or lib.cells[cell].kind not in ('comb', 'ff'):
            stats['not_parsed'] += 1; continue
        outp, expr = fm.group(1), fm.group(2).strip()
        if outp not in lib.cells[cell].outputs:
            stats['not_parsed'] += 1; continue
        try:
            b = LIB.parse_expr(expr)
        except LIB.ExprError:
            stats['not_parsed'] += 1; continue
        a = lib.cells[cell].outputs[outp]
        if lib.cells[cell].kind == 'ff':
            stats['not_parsed'] += 1; continue     # SYNFI models registers as Q = D (no reset); not comparable
        vs = sorted(LIB.expr_vars(a) | LIB.expr_vars(b))
        same = all(LIB.eval_expr(a, dict(zip(vs, bits))) == LIB.eval_expr(b, dict(zip(vs, bits)))
                   for bits in itertools.product((0, 1), repeat=len(vs)))
        stats['compared'] += 1
        if same:
            stats['agree'] += 1
        else:
            stats['differ'].append('%s.%s: liberty %s / synfi %s' % (cell, outp, LIB.expr_str(a), expr))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), 'results', 'liberty_crosscheck.json'))
    a = ap.parse_args()
    ys = FL.find_yosys()
    out = dict(label='MEASURED', yosys=ys.short(), libraries={})
    for name, path in LIBS.items():
        if not os.path.isfile(path):
            out['libraries'][name] = dict(error='not fetched: %s' % path); continue
        t0 = time.time()
        lib = LIB.load(path)
        v = LIB.verify_library(lib)
        r = dict(path_in_libs_dir=os.path.relpath(os.path.realpath(path), FL.libs_dir()), summary=lib.summary(),
                 A_truth_table=dict(passed=sum(1 for x in v.values() if x['ok']), failed=[k for k, x in v.items() if x['ok'] is False],
                                    not_modelled=sorted('%s: %s' % (k, x['detail']) for k, x in v.items() if x['ok'] is None)),
                 B_yosys_read_liberty=crosscheck_yosys(name, lib, path, ys.path))
        if name == 'sky130hd':
            r['C_skywater_lib_json'] = crosscheck_libjson(lib)
        if name == 'nangate45':
            r['D_synfi_functions'] = crosscheck_synfi(lib)
        r['seconds'] = round(time.time() - t0, 1)
        out['libraries'][name] = r
        B = r['B_yosys_read_liberty']
        print('%-11s cells %3d | A %d passed, %d failed | B Yosys: %s agree of %s, %d differ%s%s' % (
            name, len(lib.cells), r['A_truth_table']['passed'], len(r['A_truth_table']['failed']), B.get('agree'), B.get('compared'),
            len(B.get('differ', [])),
            (' | C lib.json: %d/%d' % (r['C_skywater_lib_json']['agree'], r['C_skywater_lib_json']['compared'])) if 'C_skywater_lib_json' in r else '',
            (' | D SYNFI: %d/%d' % (r['D_synfi_functions']['agree'], r['D_synfi_functions']['compared'])) if 'D_synfi_functions' in r else ''))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1)
    bad = any(r.get('A_truth_table', {}).get('failed') for r in out['libraries'].values())
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
