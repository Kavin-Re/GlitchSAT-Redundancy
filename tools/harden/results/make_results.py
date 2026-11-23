#!/usr/bin/env python3
"""Regenerate everything under results/ and studio/ (about 6 minutes, numpy only, no Yosys, no solver).
usage: GLITCHSAT_ROOT=<repository root> python3 results/make_results.py"""
import csv, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, TOP)
from harden import cli, report, search, sim, spec as S, unmerge as U
from harden.netlist import Netlist

ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.abspath(os.path.join(TOP, '..', '..', 'work', 'glitchsat'))
rp = lambda p: os.path.join(ROOT, p)
t00 = time.time()
out = dict(schema='glitchsat-harden-results/1', labels=report.LABELS, caveats=report.CAVEATS)
md = ['# auto-harden results', '',
      'Modelled bit flips (one-cycle flips of gate outputs and flop outputs), toy 8-bit designs, constant attacker input, known reset state.',
      'Every "min flips" below is an exhaustive simulation of the named netlist over all wrong inputs. Not a security proof.', '',
      'Labels: **MEASURED** = simulated here; **RECORDED** = value stored in the repository, shown for comparison; **UNTESTED-HERE** = needs Yosys (cloud/run_cloud.sh).', '']

# ---------------------------------------------------------------- 1. design-level search
GOALS = [('v0', 2), ('v0', 3), ('v1', 2), ('v1', 3), ('v2', 3), ('v2', 4), ('v2', 5)]
evs = []
for nm, g in GOALS:
    print('search', nm, g, flush=True)
    res = search.harden(S.PRESETS[nm], g, log=print, time_budget=600)
    files = report.write_fix_files(res, os.path.join(HERE, 'designs'), top_n=1)
    ev = report.evidence(res, files)
    evs.append(ev)
    json.dump(ev, open(os.path.join(HERE, 'designs', f'{nm}_g{g}.evidence.json'), 'w'), indent=1)
out['design_search'] = evs
md += ['## 1. Search on the design descriptions (MEASURED on reference gate mappings; Yosys netlists of the fixes UNTESTED-HERE)', '',
       '"Before" and "after" are the smallest minimum over the three unmerged reference mappings (select-shared, mux-shared, unshared), any number of cycles.',
       'The last column is the same design when identical copies are merged (the `merged` mapping, a model of opt_merge after flatten).', '', report.TABLE_HEAD]
md += [report.table_row(e) for e in evs]
md += ['', 'Per mapping (before -> after, exact where a number is shown; `> k` = none with k or fewer flips):', '',
       '| design | goal | select-shared | mux-shared | unshared | flip sets simulated in the search | search time (s) |', '|---|---|---|---|---|---|---|']
for e in evs:
    if e['reached']:
        f = e['fixes'][0]
        md.append(f"| {e['design']} | >= {e['goal']['min_flips_at_least']} | " + ' | '.join(
            f"{e['before']['per_mapping'][m]['shown']} -> {f['after']['exact_per_mapping'][m]}" for m in S.UNMERGED)
            + f" | {e['search']['sets_simulated']} | {e['search']['runtime_s']} |")
    else:
        md.append(f"| {e['design']} | >= {e['goal']['min_flips_at_least']} | " + ' | '.join(f"{e['before']['per_mapping'][m]['shown']} -> not reached" for m in S.UNMERGED)
                  + f" | {e['search']['sets_simulated']} | {e['search']['runtime_s']} |")
md.append('')

# ---------------------------------------------------------------- 2. each move alone
out['moves'] = {}
md += ['## 2. What each transformation buys when applied alone (MEASURED on reference mappings)', '']
for nm in ('v1', 'v2'):
    rows = cli.moves_table(S.PRESETS[nm], 4)
    out['moves'][nm] = rows
    md += [f'### {nm}: {S.PRESETS[nm].short()}', '', '| change (alone) | select-shared | mux-shared | unshared | copies merged | gates | flops | depth |', '|---|---|---|---|---|---|---|---|']
    md += [f"| {r['change']} | {r['min_flips']['select-shared']} | {r['min_flips']['mux-shared']} | {r['min_flips']['unshared']} | {r['merged']} | {r['gates_added']:+d} | {r['flops_added']:+d} | {r['depth_added']:+d} |" for r in rows]
    md.append('')

# ---------------------------------------------------------------- 3. armed sweep
print('armed sweep', flush=True)
v2 = S.PRESETS['v2']
sweep = []
for a in range(256):
    if a in (v2.idle, v2.accept, v2.reject):
        continue
    c = v2.replace(armed=a)
    m = search.measure(c, 2)
    sweep.append(dict(armed=f'{a:02X}', copies_touched=len({c.owner[i] for i in range(8) if ((a ^ c.accept) >> i) & 1}),
                      **{k: report.fmt_min(v['min_flips'], 2) for k, v in m.items()}, passes_goal_3=search.passes(m, 3)))
with open(os.path.join(HERE, 'armed_sweep_v2.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(sweep[0].keys())); w.writeheader(); w.writerows(sweep)
n_pass = sum(r['passes_goal_3'] for r in sweep)
per = {mp: sum(r[mp] == '> 2' for r in sweep) for mp in S.UNMERGED}
out['armed_sweep_v2'] = dict(constants=len(sweep), reach_3_on_all_unmerged_mappings=n_pass, reach_3_per_mapping=per,
                             passing=[r['armed'] for r in sweep if r['passes_goal_3']], file='results/armed_sweep_v2.csv')
md += ['## 3. Every armed constant of V2 (MEASURED on reference mappings)', '',
       f'{len(sweep)} possible armed code words (all 8-bit values except idle 0xF0, accept 0x96, reject 0x69), other parameters as rtl/v2.v.',
       f'No attack with 2 or fewer flips: select-shared {per["select-shared"]}, mux-shared {per["mux-shared"]}, unshared {per["unshared"]}; on all three: **{n_pass}**.',
       'Rows: `results/armed_sweep_v2.csv`. 0xA5 (rtl/v2e.v) reaches 3 on mux-shared and unshared and 2 on select-shared; 0x5A and the pick 0xC8 reach 3 on all three.', '']

# ---------------------------------------------------------------- 4. stored Yosys netlists
print('stored netlists', flush=True)
rec = {}
with open(rp('research/c6/p01/sweep_rows.csv')) as f:
    for r in csv.DictReader(f):
        if r['variant'] == 'plain':
            rec[('apt' if '0.33' in r['yosys'] else 'conda', r['armed_const'])] = r['min_flips']
stored = []
for armed, top in (('CC', 'v2'), ('04', 'v2c04'), ('4D', 'v2c4d'), ('5A', 'v2c5a'), ('A5', 'v2e')):
    c = v2.replace(armed=int(armed, 16))
    refm = search.measure(c, 3)
    for build in ('apt', 'conda'):
        p = f'research/c6/p01/netlists/nl_{build}_{top}.json'
        nl = Netlist.load(rp(p), top)
        r6 = sim.min_flips(nl, kmax=3, cycles=6)
        ra = sim.min_flips(nl, kmax=3, cycles=None)
        e2 = sim.enumerate_sets(nl, k=2, cycles=6)
        stored.append(dict(armed=armed, netlist=p, yosys='0.33 (apt)' if build == 'apt' else '0.38+92 (conda)', gates=nl.stats()['gates'],
                           min_flips_6_cycles=report.fmt_min(r6.min_flips, 3), min_flips_all_cycles=report.fmt_min(ra.min_flips, 3),
                           recorded=rec.get((build, armed), ''), pairs_simulated=e2.sets, attacking_pairs=e2.attacking_sets,
                           reference={k: report.fmt_min(v['min_flips'], 3) for k, v in refm.items()}))
out['stored_yosys_netlists'] = stored
md += ['## 4. The encoding fix on Yosys netlists already in the repository (MEASURED here on stored netlists; plain flow)', '',
       'Same design, only the armed constant differs. These are real Yosys outputs (`research/c6/p01/netlists/`). "Recorded" is the solver value in `research/c6/p01/sweep_rows.csv`.',
       'Brute force = every pair of (cycle, site) flips over 6 cycles.', '',
       '| armed | Yosys | gates | min flips, 6 cycles | min flips, all cycles | recorded (solver) | brute force pairs: attacking / all | reference mappings sel / mux / unshared |', '|---|---|---|---|---|---|---|---|']
md += [f"| {s['armed']} | {s['yosys']} | {s['gates']} | {s['min_flips_6_cycles']} | {s['min_flips_all_cycles']} | {s['recorded']} | {s['attacking_pairs']} / {s['pairs_simulated']} | "
       f"{s['reference']['select-shared']} / {s['reference']['mux-shared']} / {s['reference']['unshared']} |" for s in stored]
agree = sum(1 for s in stored if s['min_flips_6_cycles'] == s['recorded'])
low = sum(1 for s in stored if int(s['reference']['select-shared'].strip('> ')) + (1 if s['reference']['select-shared'].startswith('>') else 0) <= int(s['min_flips_6_cycles'].strip('> ')) + (1 if s['min_flips_6_cycles'].startswith('>') else 0))
out['stored_yosys_agreement'] = dict(netlists=len(stored), simulator_equals_recorded_solver=agree, select_shared_not_above_yosys=low)
md += ['', f'Simulator equals the recorded solver value on {agree} of {len(stored)} netlists. The select-shared mapping is not above the Yosys netlist on {low} of {len(stored)}.',
       'So the manual fix 0xCC -> 0xA5 is confirmed here on the stored apt 0.33 netlist: **2 -> 3**; 0xCC -> 0x5A likewise 2 -> 3. The search pick 0xC8 has no stored Yosys netlist: UNTESTED-HERE.', '']

# ---------------------------------------------------------------- 5. netlist-level fixes
print('netlist fixes', flush=True)
G = [[0, 3, 6], [1, 4, 7], [2, 5]]
nf = []
for p, top, goal, mask, note in (
        ('validation/nl/v2.json', 'v2', 2, None, 'V2 synthesised flatten-first (copies merged by abc)'),
        ('research/c2/reviews/ct/tests/v2_inbuf.json', 'v2', 3, None, 'V2 with a shared input buffer stage'),
        ('reference/spike_netlists/v2.json', 'v2', 3, 0x8D, 'stored V2, consumer checks only bits 0x8D'),
        ('reference/spike_netlists/v2.json', 'v2', 3, 0x0F, 'stored V2, consumer checks only the low nibble'),
        ('research/c2/e2_variance/baseline_netlists/apt0.33_v2.json', 'v2', 3, None, 'apt 0.33 V2: no shared copy logic, nothing to remove')):
    tag = os.path.splitext(os.path.basename(p))[0] + ('' if mask is None else f'_mask{mask:02X}')
    ev = cli.netlist_fix(rp(p), top, goal, G, mask, outdir=os.path.join(HERE, 'netlists'), tag=tag)
    ev['netlist'] = p
    ev['note'] = note
    nf.append(ev)
out['netlist_fixes'] = nf
md += ['## 5. Fixes applied directly to stored netlists (MEASURED here, no re-synthesis)', '',
       '| netlist | what it is | goal | lint | fix | min flips before | min flips after | cost | goal reached |', '|---|---|---|---|---|---|---|---|---|']
for ev in nf:
    lint = ev['lint'] or {}
    steps = [s for s in ev['steps'] if 'min_flips' in s]
    fix = ' + '.join(s['title'] for s in steps) or 'none applicable'
    cst = '; '.join((f"+{s['cost']['gates_added']} gates, depth {s['cost']['depth_added']:+d}" if 'gates_added' in s['cost'] else f"+{s['cost']['gates_added_in_consumer_estimate']} compared bits in the consumer (ASSUMED)") for s in steps) or '-'
    md.append(f"| `{ev['netlist']}` | {ev['note']} | >= {ev['goal']} | {lint.get('verdict', 'n/a')}, {lint.get('single_points', 0)} single points | {fix} | {ev['before']['shown']} | {ev['after']['shown']} | {cst} | {'yes' if ev['reached'] else 'no'} |")
md += ['', 'The lint is `merge_lint.py` from the attack-surface work, called with the V2 bit ownership 0,3,6 / 1,4,7 / 2,5. The un-merged netlists are in `results/netlists/` (JSON readable by scripts/glitchsat.py, and structural Verilog).', '']

# ---------------------------------------------------------------- 6. recorded synthesis study
rows = [r for r in csv.DictReader(open(rp('research/c2/e2_variance/raw/matrix.csv'))) if r['design'] == 'v2' and r['status'] == 'SOLVED']
def cnt(pred):
    xs = [int(r['min_flips']) for r in rows if pred(r)]
    return {k: xs.count(k) for k in (1, 2, 3)}, len(xs)
sep = lambda r: r['order'] == 'abc_then_flatten' and r['merge'] == 'nomerge'
e2 = dict(solved=len(rows), all=cnt(lambda r: True)[0], opt_merge=cnt(lambda r: r['merge'] == 'opt_merge')[0],
          flatten_then_abc=cnt(lambda r: r['order'] == 'flatten_then_abc')[0], separate_flows=cnt(sep)[0],
          one_match_net_when_min1=sum(1 for r in rows if r['min_flips'] == '1' and r['distinct_match_nets'] in ('1', '2')),
          min1=sum(1 for r in rows if r['min_flips'] == '1'),
          three_match_nets_min_ge2=sum(1 for r in rows if r['distinct_match_nets'] == '3' and int(r['min_flips']) >= 2),
          three_match_nets=sum(1 for r in rows if r['distinct_match_nets'] == '3'))
out['recorded_synthesis_study'] = dict(source='research/c2/e2_variance/raw/matrix.csv', label='RECORDED', **e2)
f3 = lambda d: f"{d[1]} / {d[2]} / {d[3]}"
md += ['## 6. Why the separation constraints (RECORDED: the 264 solved V2 configurations of research/c2/e2_variance)', '',
       '| subset of the 264 solved V2 configurations | min 1 / min 2 / min 3 |', '|---|---|',
       f"| all | {f3(e2['all'])} |", f"| opt_merge after flatten | {f3(e2['opt_merge'])} |", f"| flatten before abc | {f3(e2['flatten_then_abc'])} |",
       f"| abc per module then flatten, no opt_merge (the flow the guard script enforces) | {f3(e2['separate_flows'])} |", '',
       f"{e2['three_match_nets_min_ge2']} of the {e2['three_match_nets']} configurations that still have three distinct match nets need 2 or more flips; "
       f"{e2['one_match_net_when_min1']} of the {e2['min1']} one-flip configurations have fewer than three.",
       'The guard added by harden (keep on every cell of a kept module before flatten) is meant to make the opt_merge rows behave like the last row. '
       'That is read from the Yosys 0.33 source of opt_merge (two cells that both carry keep are not merged); it is UNTESTED-HERE and is the first thing cloud/run_cloud.sh measures. '
       'It cannot help the flatten-before-abc rows: abc rebuilds the logic.', '']

out['runtime_s'] = round(time.time() - t00, 1)
json.dump(out, open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
md += ['## Reproduce', '', '```', 'GLITCHSAT_ROOT=<repository root> python3 results/make_results.py     # this file, results.json, studio/suggest_fix.json',
       'sh cloud/run_cloud.sh                                                # Ubuntu 24.04: Yosys 0.33 re-synthesis check', '```', '',
       f'Run time of this file: {out["runtime_s"]} s (numpy only).', '']
open(os.path.join(HERE, 'RESULTS.md'), 'w').write('\n'.join(md))
os.makedirs(os.path.join(TOP, 'studio'), exist_ok=True)
panel = report.studio_panel(evs, extra=dict(
    netlist_fixes=[dict(netlist=e['netlist'], note=e['note'], goal_min_flips=e['goal'], before_min_flips=e['before']['shown'], after_min_flips=e['after']['shown'],
                        reached=e['reached'], lint=e['lint'], steps=[{k: s[k] for k in ('title', 'what', 'shown', 'cost', 'label', 'skipped') if k in s} for s in e['steps']],
                        evidence_label='MEASURED') for e in nf],
    confirmed_on_stored_yosys_netlists=[dict(change=f'armed 0xCC -> 0x{a}', yosys=s['yosys'], before=next(x['min_flips_6_cycles'] for x in stored if x['armed'] == 'CC' and x['yosys'] == s['yosys']),
                                             after=s['min_flips_6_cycles'], netlist=s['netlist'], evidence_label='MEASURED') for a in ('A5', '5A') for s in stored if s['armed'] == a],
    separation_evidence=out['recorded_synthesis_study'], armed_sweep=out['armed_sweep_v2'],
    moves={k: v for k, v in out['moves'].items()}))
json.dump(panel, open(os.path.join(TOP, 'studio', 'suggest_fix.json'), 'w'), indent=1)
print('done', out['runtime_s'], 's')
