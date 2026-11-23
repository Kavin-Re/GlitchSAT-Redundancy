#!/usr/bin/env python3
"""glitchsat_scale: the GlitchSAT bounded fault-injection question on designs of thousands of gates.

Same fault model as scripts/glitchsat.py (single-cycle bit flips of gate outputs and flop Q, at most K in N cycles).
What is added is how the question is answered: fault-site reduction, module summaries, one incremental formula for
all budgets and horizons, two-core search, and an answer that is an interval when the time limit is reached.
See ../README.md.

  check    smallest number of flips (exact, or an interval under --time-s)
  deepen   the minimum for every horizon 1..N from one formula
  sizes    CNF sizes under each reduction level (no solving)
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gscale                                   # noqa: E402
from gscale import circuit, search, modular, spec     # noqa: E402

NOTE = ("BOUNDED: the statement holds for at most {k} single-cycle bit flips (gate outputs and flop Q) within {n} "
        "cycles on this netlist. It says nothing about more flips, longer runs, other fault types or physical "
        "feasibility. Modelled faults.")


def _int(s):
    return int(str(s), 0)


def build_problem(a):
    return spec.load_problem(a.netlist, a.top, a.cycles, goal_out=a.goal_out, goal_value=a.goal_value,
                             attack_input=a.attack_input, key=a.key, goal=a.goal, quiet=a.quiet, fix=a.fix,
                             inputs=a.inputs, no_key=a.no_key, sites_meta=a.sites_meta, clock=a.clock)


def _common(p):
    p.add_argument('netlist'); p.add_argument('--top', required=True)
    p.add_argument('--k', type=int, default=3); p.add_argument('--cycles', type=int, default=6)
    p.add_argument('--goal-out', default='boot_word'); p.add_argument('--goal-value', type=_int, default=0x96)
    p.add_argument('--attack-input', default='sig'); p.add_argument('--key', type=_int, default=0xC3)
    p.add_argument('--goal', action='append', metavar='PORT=VALUE', help='output port value at the hit cycle (repeatable)')
    p.add_argument('--quiet', action='append', metavar='PORT=VALUE', help='output port value that must hold up to the hit cycle')
    p.add_argument('--fix', action='append', metavar='PORT=VALUE', help='tie an input port')
    p.add_argument('--inputs', choices=['const', 'cycle'], default='const', help='free inputs: one value per run, or a new value every cycle')
    p.add_argument('--no-key', action='store_true', help='no "attacker input differs from key" condition')
    p.add_argument('--sites-meta', help='JSON with "sites" (nets that may be flipped) and "resets" (tied inactive)')
    p.add_argument('--clock', action='append', help='clock port name (default clk, clk_i)')
    p.add_argument('--reduce', choices=['time', 'struct', 'full'], default='struct')
    p.add_argument('--modules', default='auto', help='auto | prefix | islands | none | FILE.json ({"name": [net, ...]})')
    p.add_argument('--backend', default='auto'); p.add_argument('--out')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='glitchsat_scale.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--version', action='version', version=gscale.__version__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check'); _common(c)
    c.add_argument('--time-s', type=float, help='time limit; the answer is then an interval if the search is not finished')
    c.add_argument('--workers', type=int, default=1, choices=[1, 2]); c.add_argument('--mode', choices=['race', 'cubes'], default='race')
    c.add_argument('--symmetry', action='store_true')
    d = sub.add_parser('deepen'); _common(d); d.add_argument('--time-s', type=float)
    s = sub.add_parser('sizes'); _common(s)
    a = ap.parse_args(argv)
    fs = gscale.fastsat()
    try:
        P = build_problem(a)
        mods = a.modules
        if mods not in ('auto', 'prefix', 'islands', 'none'):
            mods = [(k, set(v)) for k, v in json.load(open(mods)).items()]
        if a.cmd == 'check':
            r = search.analyse(P, a.k, time_s=a.time_s, reduce=a.reduce, modules=mods, workers=a.workers, mode=a.mode,
                               backend=a.backend, use_symmetry=a.symmetry)
            r.pop('_witness_raw', None)
            r['note'] = NOTE.format(k=a.k, n=a.cycles)
            print(r['text']); print(r['note'])
            code = 0 if r['status'] in ('EXACT', 'NO_ATTACK_UP_TO_BOUND') else 2
        elif a.cmd == 'deepen':
            r = search.deepen(P, a.k, reduce=a.reduce, backend=a.backend, time_s=a.time_s)
            for row in r['rows']:
                print('cycles %3d: %s%s' % (row['cycles'], 'no attack with up to %d flips' % a.k if row['min_faults'] is None
                                            else 'minimum %d flip(s)' % row['min_faults'], '' if row['proved'] else '  (not proved: time limit)'))
            code = 0 if all(x['proved'] for x in r['rows']) and len(r['rows']) == P.N else 2
        else:
            r = search.sizes(P, a.k, modules=mods)
            print(json.dumps(r, indent=1)); code = 0
        if a.out:
            with open(a.out, 'w') as f: json.dump(r, f, indent=1, default=str)
        return code
    except (fs.NetlistError, circuit.CircuitError, OSError, ValueError) as ex:
        print('error: %s' % ex, file=sys.stderr); return 3
    except (AssertionError, RuntimeError) as ex:
        print('internal error: %s' % ex, file=sys.stderr); return 4


if __name__ == '__main__':
    sys.exit(main())
