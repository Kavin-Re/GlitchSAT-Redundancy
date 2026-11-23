#!/usr/bin/env python3
"""Cross-check the z3 enumeration of minimum attacks against the exhaustive simulator (needs z3).

For each case, both methods must agree on the minimum size and on the exact SET of minimum attacks.
Exit 0 when all cases agree, 1 on any disagreement, 3 when z3 is missing.
Usage: python3 compare_methods.py [--slow]   (--slow adds V2 stored at 6 cycles: about a minute for the exhaustive side)
"""
import argparse, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import merge_lint, attack_surface   # noqa: E402

CASES = [('reference/spike_netlists/v0.json', 'v0', 4), ('reference/spike_netlists/v0.json', 'v0', 6),
         ('reference/spike_netlists/v1.json', 'v1', 6), ('reference/spike_netlists/v2.json', 'v2', 4),
         ('research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 4), ('research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 6),
         ('validation/nl/v2.json', 'v2', 6)]
SLOW = [('reference/spike_netlists/v2.json', 'v2', 6)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--slow', action='store_true')
    ap.add_argument('--k', type=int, default=3)
    a = ap.parse_args(argv)
    GS = merge_lint.engine()
    if GS._Z3_IMPORT_ERROR is not None:
        print('z3 is not installed: pip install z3-solver'); return 3
    root = merge_lint._repo_root()
    bad = 0
    for path, top, N in CASES + (SLOW if a.slow else []):
        nl = GS.Netlist(os.path.join(root, path), top)
        t0 = time.time(); ex = attack_surface.exhaustive(nl, N, a.k); te = time.time() - t0
        t0 = time.time(); st = attack_surface.enumerate_sat(nl, N, a.k, cap=1000000); ts = time.time() - t0
        se = {frozenset(x) for x, _ in ex['attacks']}
        ss = {frozenset(x) for x, _ in st['attacks']}
        ok = (ex['min_faults'] == st['min_faults'] and se == ss and ex['complete'] and st['complete']
              and st.get('confirmed_by_simulation') == len(ss))
        bad += not ok
        print(f"{'OK  ' if ok else 'DIFF'} {path} top={top} T={N}: exhaustive m={ex['min_faults']} n={len(se)} ({te:.1f} s) | "
              f"sat m={st['min_faults']} n={len(ss)} complete={st['complete']} confirmed={st.get('confirmed_by_simulation')} "
              f"calls={st['solver_calls']} ({ts:.1f} s)")
        if not ok:
            print('   only exhaustive:', sorted(map(sorted, se - ss))[:5])
            print('   only sat       :', sorted(map(sorted, ss - se))[:5])
    print('ALL AGREE' if not bad else f'{bad} case(s) DISAGREE')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
