"""Command line:  glitchsat harden <command> ...   (or: python3 -m harden <command> ...)

  design   search fixes for a design description (preset v0|v1|v2|v2e or --spec file.json) and a goal
  netlist  fix a stored Yosys JSON netlist without re-synthesis (remove single points, consumer mask) and measure
  check    only measure: minimum modelled flips of a netlist by exhaustive simulation
  moves    what each single transformation buys on a design (measured)
  resynth  (needs Yosys) synthesise before/after over the configuration grid and re-verify every netlist
"""
import argparse, json, os, sys
from . import __version__, report, resynth, search, sim, spec as S, unmerge as U
from .netlist import Netlist, NetlistError

BANNER = 'Modelled bit flips on toy designs; exhaustive within the model, not a security proof.'


def _int(x):
    return int(x, 0)


def _cycles(x):
    return None if x in ('all', '0') else int(x)


def load_spec(a):
    if a.spec:
        d = json.load(open(a.spec))
        d = d.get('after', d) if 'after' in d and a.design == 'after' else d.get('before', d)
        fields = {f.name for f in S.dataclasses.fields(S.Spec)}
        return S.Spec(**{k: (tuple(v) if k == 'owner' else v) for k, v in d.items() if k in fields})
    if a.design not in S.PRESETS:
        raise SystemExit(f'unknown design {a.design!r}: presets are {", ".join(S.PRESETS)}; or give --spec file.json')
    return S.PRESETS[a.design]


def cmd_design(a):
    sp = load_spec(a)
    allow = tuple(a.allow.split(',')) if a.allow else search.ALL_MOVES
    bad = [m for m in allow if m not in search.ALL_MOVES]
    if bad:
        raise SystemExit(f'unknown move(s) {bad}; choose from {",".join(search.ALL_MOVES)}')
    print(BANNER)
    res = search.harden(sp, a.goal, allow=allow, cycles=_cycles(a.cycles), alternatives=a.alternatives, log=print, time_budget=a.time_budget)
    files = report.write_fix_files(res, a.out, top_n=a.alternatives) if a.out else {}
    ev = report.evidence(res, files)
    print()
    print(report.TABLE_HEAD)
    print(report.table_row(ev))
    if ev['reached']:
        f = ev['fixes'][0]
        print(f'\nbest fix: {f["description"]}')
        for m in f['move_text']:
            print(f'  - {m["title"]}: {m["what"]}')
        print(f'evidence (MEASURED): {f["after"]["statement"]}; exact minimum per mapping: {f["after"]["exact_per_mapping"]}')
        print('Yosys synthesis of the hardened Verilog: UNTESTED-HERE (run cloud/run_cloud.sh)')
    else:
        print('\ngoal not reached with the allowed moves.')
    if a.out:
        with open(os.path.join(a.out, f'{sp.name}_g{a.goal}.evidence.json'), 'w') as fh:
            json.dump(ev, fh, indent=1)
        with open(os.path.join(a.out, f'{sp.name}_g{a.goal}.suggest_fix.json'), 'w') as fh:
            json.dump(report.studio_panel([ev]), fh, indent=1)
        print(f'files written under {a.out}')
    return 0 if ev['reached'] else 1


def cmd_check(a):
    nl = Netlist.load(a.netlist, a.top)
    g = sim.Goal(a.goal_out, a.goal_value, a.mask)
    r = sim.min_flips(nl, g, kmax=a.kmax, cycles=_cycles(a.cycles), key=a.key, reduce=not a.no_reduce)
    d = r.as_dict()
    d.update(netlist=a.netlist, top=nl.top, **nl.stats())
    if a.enumerate is not None:
        d['enumeration'] = sim.enumerate_sets(nl, g, a.enumerate, _cycles(a.cycles) or 6, a.key).as_dict()
    if a.json:
        json.dump(d, open(a.json, 'w'), indent=1)
    print(BANNER)
    print(f'{a.netlist} ({nl.top}): {d["gates"]} gates, {d["flops"]} flops; goal {g.describe()}; cycles {r.cycles}')
    print('minimum flips: ' + (str(r.min_flips) if r.min_flips is not None else f'none with <= {a.kmax} (exhaustive)'))
    if r.witness:
        print(f'witness: input 0x{r.witness["input"]:02X}, flips {r.witness["flips"]} (replayed)')
    print(f'right key boots: {r.honest_ok}; wrong key boots without faults: {bool(r.fault_free_wrong_accept)}; sets simulated: {r.sets_simulated}; {r.runtime_s} s')
    if a.enumerate is not None:
        e = d['enumeration']
        print(f'brute force k={e["k"]}: {e["attacking_sets"]} attacking of {e["sets"]} sets ({e["runtime_s"]} s)')
    return 0


def netlist_fix(path, top, goal, groups, mask=None, goal_value=0x96, key=0xC3, cycles=None, outdir=None, tag=None):
    """Netlist-level fixes, each measured. Returns an evidence dict."""
    nl = Netlist.load(path, top)
    full = sim.Goal('boot_word', goal_value)
    g0 = sim.Goal('boot_word', goal_value, mask)
    kmax = max(goal, 1)
    before = sim.min_flips(nl, g0, kmax=kmax, cycles=cycles, key=key)
    ev = dict(schema='glitchsat-harden-netlist/1', netlist=path, top=nl.top, goal=goal, groups=groups, consumer_mask_before=mask,
              before=dict(min_flips=before.min_flips, shown=report.fmt_min(before.min_flips, kmax), witness=before.witness, label='MEASURED', **nl.stats()),
              lint=U.run_lint(path, nl.top, groups) if groups else None, steps=[], caveats=report.CAVEATS)
    cur, curgoal = nl, g0
    if mask is not None and mask != (1 << len(nl.ports['boot_word'][1])) - 1:
        r = sim.min_flips(cur, full, kmax=kmax, cycles=cycles, key=key)
        extra = bin(((1 << 8) - 1) & ~mask).count('1')
        ev['steps'].append(dict(move='consumer', title=search.MOVES['consumer'][0], what=search.MOVES['consumer'][1], min_flips=r.min_flips,
                                shown=report.fmt_min(r.min_flips, kmax), label='MEASURED', witness=r.witness,
                                cost=dict(gates_added_in_consumer_estimate=extra, note=f'{extra} more bits compared by the consumer (about one gate each; ASSUMED, the consumer is outside the netlist)')))
        curgoal = full
    if groups:
        sh = U.shared_nets(cur, groups)
        if sh:
            n2, info = U.unmerge(cur, groups)
            a, b = sim.fault_free(cur, 6, full), sim.fault_free(n2, 6, full)
            same = all((a[k] == b[k]).all() for k in a if k != 'state')
            r = sim.min_flips(n2, curgoal, kmax=kmax, cycles=cycles, key=key)
            st = n2.stats()
            step = dict(move='unmerge', title='Remove single points (separate the shared copy logic)',
                        what='Every gate that two or more copy groups share is duplicated so that each group has its own; the duplicates are marked keep.',
                        why_sound='Each duplicate computes exactly what the shared gate computed; outputs compared for all 256 inputs over 6 cycles.',
                        function_unchanged=bool(same), min_flips=r.min_flips, shown=report.fmt_min(r.min_flips, kmax), label='MEASURED', witness=r.witness,
                        cost=dict(gates_added=st['gates'] - cur.stats()['gates'], flops_added=0, depth_added=st['depth'] - cur.stats()['depth']), **info)
            if outdir:
                os.makedirs(outdir, exist_ok=True)
                tag = tag or os.path.splitext(os.path.basename(path))[0]
                n2.write(os.path.join(outdir, tag + '_unmerged.json'), creator='glitchsat harden unmerge (derived from ' + os.path.basename(path) + ')')
                with open(os.path.join(outdir, tag + '_unmerged.v'), 'w') as f:
                    f.write(n2.to_verilog(header='// Netlist after single-point removal. Toy design, modelled flips only.\n'))
                step['files'] = [tag + '_unmerged.json', tag + '_unmerged.v']
            ev['steps'].append(step)
            cur = n2
        else:
            ev['steps'].append(dict(move='unmerge', title='Remove single points', skipped='no gate is shared between the copy groups'))
    last = [s for s in ev['steps'] if 'min_flips' in s]
    am = last[-1]['min_flips'] if last else before.min_flips
    ev['after'] = dict(min_flips=am, shown=report.fmt_min(am, kmax), label='MEASURED')
    ev['reached'] = am is None or am >= goal
    return ev


def cmd_netlist(a):
    ev = netlist_fix(a.netlist, a.top, a.goal, U.parse_groups(a.groups) if a.groups else None, a.mask, a.goal_value, a.key, _cycles(a.cycles), a.out)
    print(BANNER)
    lint = ev.get('lint')
    lt = '' if not a.groups else (' (lint: not found; set GLITCHSAT_ROOT and GLITCHSAT_SURFACE; shared nets computed here instead)' if not lint else
                                  f' (lint: {lint.get("verdict")}, {lint.get("single_points")} single points)' if 'verdict' in lint else f' (lint failed: {lint.get("error")}; shared nets computed here instead)')
    print(f'{a.netlist}: before {ev["before"]["shown"]} flips' + lt)
    for s in ev['steps']:
        print(f'  {s["title"]}: ' + (s.get('skipped') or f'{s["shown"]} flips, cost {s["cost"]}'))
    print(f'after: {ev["after"]["shown"]} flips; goal >= {a.goal} ' + ('reached' if ev['reached'] else 'NOT reached'))
    if a.out:
        with open(os.path.join(a.out, 'netlist_fix.evidence.json'), 'w') as f:
            json.dump(ev, f, indent=1)
    return 0 if ev['reached'] else 1


def moves_table(sp, kmax=4):
    """Each single transformation applied alone to `sp`, measured."""
    n = sp.copies
    var = [('as is', sp)]
    if sp.output == 'state':
        if sp.voter == 'single_and':
            var += [('voter: one kept AND per state bit', sp.replace(voter='per_bit_and')),
                    ('voter: none in front of the register (bit ownership)', sp.replace(voter='owner', owner=search.round_robin(sp.width, n)))]
        else:
            var += [('voter: single AND in front of the register', sp.replace(voter='single_and', owner=())),
                    ('voter: one kept AND per state bit', sp.replace(voter='per_bit_and', owner=()))]
        ow = search.round_robin(sp.width, n + 1) if sp.voter == 'owner' else sp.owner
        var += [('one more owning copy', sp.replace(copies=n + 1, owner=ow))]
        if n + 1 >= 2:
            var += [('check copy + infection', sp.replace(alarm='infect', check_copies=1)),
                    ('check copy + sticky alarm flop', sp.replace(alarm='sticky', check_copies=1))]
        if n >= 2:
            var += [('infection without a check copy', sp.replace(alarm='infect'))]
        var += [('invalid state -> reject', sp.replace(trap_invalid=True))]
    rows = []
    base = S.build_mapping(sp, 'select-shared').stats()
    for label, v in var:
        if v.problems():
            continue
        m = search.measure(v, kmax)
        mg = search.measure(v, 1, mappings=('merged',))['merged']
        st = S.build_mapping(v, 'select-shared').stats()
        rows.append(dict(change=label, description=v.short(), min_flips={k: report.fmt_min(x['min_flips'], kmax) for k, x in m.items()},
                         worst=report.fmt_min(search.worst(m), kmax), merged=report.fmt_min(mg['min_flips'], 1),
                         gates_added=st['gates'] - base['gates'], flops_added=st['flops'] - base['flops'], depth_added=st['depth'] - base['depth']))
    return rows


def cmd_moves(a):
    rows = moves_table(load_spec(a), a.kmax)
    print(BANNER)
    print('| change (alone) | select-shared | mux-shared | unshared | copies merged | gates | flops |\n|---|---|---|---|---|---|---|')
    for r in rows:
        print(f"| {r['change']} | {r['min_flips']['select-shared']} | {r['min_flips']['mux-shared']} | {r['min_flips']['unshared']} | {r['merged']} | {r['gates_added']:+d} | {r['flops_added']:+d} |")
    if a.json:
        json.dump(rows, open(a.json, 'w'), indent=1)
    return 0


def cmd_resynth(a):
    resynth.main(a.specs, a.out, quick=a.quick, dry_run=a.dry_run, yosys=a.yosys, root=a.root, z3=a.z3, workers=a.workers, time_limit=a.time_limit, use_cache=not a.no_cache)
    print(open(os.path.join(a.out, 'resynth_summary.md')).read())
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog='glitchsat harden', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--version', action='version', version=__version__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('design', help='search fixes for a design description')
    p.add_argument('design', nargs='?', default='v2')
    p.add_argument('--spec', help='JSON file with the description fields (see README)')
    p.add_argument('--goal', type=int, required=True, help='G: at least G modelled flips must be needed')
    p.add_argument('--cycles', default='all', help='"all" (default: every number of cycles) or N')
    p.add_argument('--allow', help='comma list of moves: ' + ','.join(search.ALL_MOVES))
    p.add_argument('--alternatives', type=int, default=3)
    p.add_argument('--time-budget', type=float, default=900)
    p.add_argument('--out', help='directory for hardened Verilog, Yosys script, netlists, evidence JSON')
    p.set_defaults(fn=cmd_design)
    p = sub.add_parser('netlist', help='fix a stored netlist without re-synthesis')
    p.add_argument('netlist'); p.add_argument('--top')
    p.add_argument('--goal', type=int, required=True)
    p.add_argument('--groups', help='bit ownership of the goal word, e.g. "0,3,6;1,4,7;2,5"')
    p.add_argument('--mask', type=_int, help='bits the consumer checks today (e.g. 0x0F)')
    p.add_argument('--goal-value', type=_int, default=0x96); p.add_argument('--key', type=_int, default=0xC3)
    p.add_argument('--cycles', default='all'); p.add_argument('--out')
    p.set_defaults(fn=cmd_netlist)
    p = sub.add_parser('check', help='minimum modelled flips of a netlist (exhaustive simulation)')
    p.add_argument('netlist'); p.add_argument('--top')
    p.add_argument('--kmax', type=int, default=3); p.add_argument('--cycles', default='6')
    p.add_argument('--goal-out', default='boot_word'); p.add_argument('--goal-value', type=_int, default=0x96)
    p.add_argument('--mask', type=_int); p.add_argument('--key', type=_int, default=0xC3)
    p.add_argument('--no-reduce', action='store_true', help='keep dominated fault sites (slower, same minimum)')
    p.add_argument('--enumerate', type=int, metavar='K', help='also brute-force every set of exactly K (cycle, site) pairs')
    p.add_argument('--json')
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser('moves', help='what each single transformation buys (measured)')
    p.add_argument('design', nargs='?', default='v2'); p.add_argument('--spec'); p.add_argument('--kmax', type=int, default=4); p.add_argument('--json')
    p.set_defaults(fn=cmd_moves)
    p = sub.add_parser('resynth', help='(needs Yosys) synthesise before/after over the configuration grid and re-verify')
    p.add_argument('--specs', required=True, help='directory with *.spec.json written by `design --out`')
    p.add_argument('--out', required=True); p.add_argument('--quick', action='store_true'); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--yosys', default='yosys')
    p.add_argument('--root', help='repository root (for the optional z3 cross-check); default $GLITCHSAT_ROOT')
    p.add_argument('--z3', action='store_true', help='also run scripts/glitchsat.py check (z3, 6 cycles) on the plain-flow netlists')
    p.add_argument('--workers', type=int, help='parallel jobs (default: number of CPUs)')
    p.add_argument('--time-limit', type=float, default=600, help='seconds per netlist verification')
    p.add_argument('--no-cache', action='store_true', help='re-run every configuration (default: reuse rows whose script, Verilog and Yosys version are unchanged)')
    p.set_defaults(fn=cmd_resynth)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except (NetlistError, ValueError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
