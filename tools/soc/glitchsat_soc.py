#!/usr/bin/env python3
"""GlitchSAT on whole chips. See README.md.

  glitchsat_soc.py list
  glitchsat_soc.py build     CHIP [--variant V] [--flow F]          RTL -> gate-level netlist (resumable)
  glitchsat_soc.py analyse   CHIP [--variant V] [--flow F] [--goal ID] [--time-s S] [--workers N]
  glitchsat_soc.py inventory CHIP [--variant V]                     countermeasures, survival, merge lint
  glitchsat_soc.py campaign  CHIP [--variant V] [--flow F] [--goal ID] [--lanes N] [--seed S]
  glitchsat_soc.py report                                           results/RESULTS.md, results/soc_results.json,
                                                                    studio/explore_chip.json
Exit codes: 0 done, 2 a result is PARTIAL only (interval / time limit), 3 input error, 4 internal error.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='glitchsat_soc.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['list', 'build', 'analyse', 'inventory', 'campaign', 'report'])
    ap.add_argument('chip', nargs='?')
    ap.add_argument('--variant'); ap.add_argument('--flow'); ap.add_argument('--goal')
    ap.add_argument('--time-s', type=float, default=240.0); ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--kmax', type=int); ap.add_argument('--cycles', type=int)
    ap.add_argument('--lanes', type=int, default=4096); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    from gsoc import run, frontend, chip as chipmod
    G = run.G
    try:
        if a.cmd == 'list':
            for n in sorted(os.listdir(os.path.join(HERE, 'chips'))):
                p = os.path.join(HERE, 'chips', n, 'chip.yaml')
                if os.path.exists(p):
                    c = run.load_cfg(n)
                    print('%-18s %s  variants: %s  flows: %s  goals: %s' % (n, c.get('title', ''), ','.join(c.get('variants') or ['-']),
                          ','.join(c.get('flows') or []), ','.join(g['id'] for g in c.get('goals') or [])))
            return 0
        if a.cmd == 'report':
            from gsoc import report
            report.write_all()
            return 0
        if not a.chip:
            ap.error('give a chip (see `list`)')
        cfg = run.load_cfg(a.chip)
        variants = [a.variant] if a.variant else (list(cfg.get('variants') or [None]))
        flows = [a.flow] if a.flow else list(cfg.get('flows') or ['flat'])
        rc = 0
        if a.cmd == 'inventory':
            from gsoc import inventory
            for v in variants:
                r = inventory.run_inventory(cfg, v, force=a.force)
                print(inventory.format_text(r))
            return 0
        for v in variants:
            for fl in flows:
                if a.cmd == 'build':
                    r = frontend.run(cfg, fl, os.path.join(run.WORK, cfg['name']), run.src_root(cfg), v, force=a.force)
                    print('%s: %s (%s)' % (run.tag(cfg, v, fl), r['netlist'], 'cached' if r['cached'] else '%.1f s' % r['seconds']))
                    continue
                s = run.Session(cfg, v, fl)
                rec = run.chip_step(s)
                st = rec['stats']
                print('%s: %d cells (%d gates, %d flops), %d clock domain(s), %d black box(es); reset: %d flops known, %d unknown'
                      % (run.tag(cfg, v, fl), st['cells'], st['gates'], st['flops'], len(st['clock_domains']), len(st['blackboxes']),
                         rec['reset'].get('flops_known', 0), rec['reset'].get('flops_unknown', 0)))
                for g in run.goals_of(cfg, v):
                    if a.goal and g['id'] != a.goal:
                        continue
                    if a.cmd == 'analyse':
                        r = run.analyse_goal(s, g, a.time_s, a.workers, a.force, a.kmax, a.cycles)
                        print('  %-16s %-8s %s  [slice %d of %d cells = %.2f%%, %.1f s]' % (
                            g['id'], r['label'], r['text'], r['slice']['slice_cells'], r['slice']['chip_cells'],
                            100 * r['slice']['slice_share'], r['search']['seconds']))
                        if r.get('witness'):
                            print('    faults: ' + ', '.join('%s@%d' % (f['net'], f['cycle']) for f in r['witness']['faults'])
                                  + '; replayed on the whole chip, goal at cycle %s' % r['witness']['whole_chip_hit_cycle'])
                        if r['label'] != 'BOUNDED':
                            rc = 2
                    elif a.cmd == 'campaign':
                        from gsoc import campaign
                        r = campaign.run_campaign(s, g, lanes=a.lanes, seed=a.seed, force=a.force)
                        print('  ' + campaign.format_text(r))
        return rc
    except (frontend.FrontendError, chipmod.ChipError, G.circuit.CircuitError, FileNotFoundError, KeyError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 3
    except RuntimeError as e:
        print('internal error: %s' % e, file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())
