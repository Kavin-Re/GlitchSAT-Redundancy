#!/usr/bin/env python3
"""Run SYNFI's own, unmodified pipeline (parse.py + fi_injector.py from the pinned clone) and store every
injection result as JSON. Used as the reference ("SYNFI's own netlist semantics") for GlitchSAT's adapter.

ray / python-sat / sympy are replaced by the stand-ins in ../shims (sequential execution, pure-Python CDCL);
see shims/README.md. Usage:
  run_synfi_reference.py --example aes_cipher_control_fsm --netlist N.json --module M --spec S.json -s 1 [--auto_fl]
                         [--limit L] --out result.json
"""
import argparse, json, os, sys, time, io, logging, contextlib

REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNFI = os.path.join(REAL, 'synfi')
sys.path[:0] = [os.path.join(REAL, 'shims'), SYNFI]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--netlist', required=True)
    ap.add_argument('--module', required=True)
    ap.add_argument('--spec', required=True)
    ap.add_argument('-s', type=int, required=True)
    ap.add_argument('--auto_fl', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    for k in ('netlist','spec','work','out'): setattr(a, k, os.path.abspath(getattr(a, k)))
    os.makedirs(a.work, exist_ok=True)
    import parse, fi_injector                      # SYNFI modules, unmodified
    pk = os.path.join(a.work, 'netlist.pickle')
    t0 = time.time()
    log = io.StringIO()
    h = logging.StreamHandler(log)
    logging.getLogger().addHandler(h)
    if not os.path.exists(pk):
        parse.main(['-j', a.netlist, '-m', a.module, '-o', pk])
    t1 = time.time()
    args = ['-p', pk, '-f', a.spec, '-n', '1', '-c', os.path.join(SYNFI, 'cell_lib_nangate45_autogen.py'),
            '-s', str(a.s)]
    if a.auto_fl: args.append('--auto_fl')
    if a.limit: args += ['-l', str(a.limit)]
    cwd = os.getcwd(); os.chdir(a.work)
    try:
        res = fi_injector.main(args)
    finally:
        os.chdir(cwd)
    t2 = time.time()
    rows = []
    for per_model in res:
        for r in per_model:
            rows.append(dict(sat=bool(r.sat_result),
                             faults=[dict(location=fl.location, stage=fl.stage, mapping=fl.mapping)
                                     for fl in r.fault_location]))
    summary = [l for l in log.getvalue().splitlines() if 'Found' in l or 'Circuit size' in l or 'Injecting' in l]
    doc = dict(tool='SYNFI (lowRISC/synfi @ pinned commit, run unmodified with shims/)', netlist=a.netlist,
               module=a.module, spec=a.spec, simultaneous_faults=a.s, auto_fl=a.auto_fl, limit=a.limit,
               parse_s=round(t1 - t0, 2), inject_s=round(t2 - t1, 2), solver='minicdcl (via shims/pysat)',
               synfi_log_summary=summary, injections=len(rows), sat=sum(r['sat'] for r in rows), results=rows)
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
    print('\n'.join(summary))
    print(f"wrote {a.out}: {len(rows)} injections, {doc['sat']} SAT, {doc['inject_s']} s")


if __name__ == '__main__':
    main()
