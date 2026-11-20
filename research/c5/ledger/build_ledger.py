#!/usr/bin/env python3
"""Builds ledger.csv, LEDGER.md, ledger.png from the cell table below.
Every cell: (design, group, column, value, label, source). Labels: MEASURED = solver minimum on a netlist under the bit-flip
model (T=6, <=3 events); SIMULATED = modelled rail/dip/placement event on a netlist or layout-derived domain (not physical);
UNMEASURED = no number exists (reason in source)."""
import csv, json, textwrap
D = ['V0', 'V1', 'V2', 'V5']
G = [  # group, [columns]
 ('1 Synthesis flow (stem flip, full word)', ['stored spike', 'apt0.33 plain', 'apt0.33 opt', 'apt plain +opt_merge', 'conda0.38 plain', 'conda0.38 opt']),
 ('2 Consumer bits (stem)', ['full word', '4-bit 0x0F', 'accept flag boot_ok']),
 ('3 Counting rule', ['stem', 'fanout branch']),
 ('4 Fault model (word goal)', ['stem flip', 'rail 1->0', 'rail 0->1 CONTROL', 'either polarity', 'selective 1->0 subset', 'selective 0->1 subset']),
 ('4b boot_ok goal', ['rail 1->0 ', 'rail 0->1 CONTROL ']),
 ('5 Placement (V2, per-rail selective)', ['base', 'spread v8', 'rr (diff. rails)', 'any: 0->1 event']),
]
C = {}
def put(d, col, v, lab, src): C[(d, col)] = (v, lab, src)
E2 = 'research/c2/e2_variance/raw/matrix.csv (keep_on, abc_then_flatten, default ABC)'
B2 = 'research/c2/b2_scope/matrix.jsonl / B2_REPORT.md'
# ---- group 1
for d in ('V0', 'V1'):
    for col in G[0][1]: put(d, col, '1', 'MEASURED', E2 + '; ' + B2 + ('; reference/spike_netlists via B3 stem_flip row' if col == 'stored spike' else ''))
v2 = dict(zip(G[0][1], ['3', '2', '2', '1', '3', '2']))
for col, v in v2.items(): put('V2', col, v, 'MEASURED', E2 + '; B2_REPORT.md matrix; B3_REPORT.md stem row')
put('V5', 'stored spike', 'n/a', 'UNMEASURED', 'no spike netlist for V5 exists (B3_REPORT)')
for col, v, s in [('apt0.33 plain', '3', 'B3 matrix_T6.jsonl + rerun here (v5/apt_plain.rep.json)'), ('apt0.33 opt', '3', 'measured here: v5/apt_opt.json, product CLI --max-flips 3'),
                  ('apt plain +opt_merge', '1', 'measured here: v5/apt_plain_merge.json'), ('conda0.38 plain', '3', 'measured here: eda yosys 0.38, v5/conda_plain.json'),
                  ('conda0.38 opt', '3', 'measured here: v5/conda_opt.json')]: put('V5', col, v, 'MEASURED', s)
# ---- group 2
cm = 'research/c3/m1/m1_all_masks.csv (spike)'
for d, a, b, c, s in [('V0', '1', '1', '1', cm), ('V1', '1', '1', '1', cm), ('V2', '3', '2', '1', cm + '; boot_ok: B2/B3'), ('V5', '3', '2', '1', 'measured here, apt plain V5, product CLI --consumer-bits / --goal-out boot_ok')]:
    put(d, 'full word', a, 'MEASURED', s); put(d, '4-bit 0x0F', b, 'MEASURED', s); put(d, 'accept flag boot_ok', c, 'MEASURED', s)
# ---- group 3
for d, a, b, s in [('V0', '1', '1', 'B1_REPORT matrix_T6.md'), ('V1', '1', '2', 'B1_REPORT matrix_T6.md'),
                   ('V2', '3', '3', 'stem: B1/B3; branch: B1 left it unfinished at 60 s, re-run here with B1 faultpack, 100 s z3 limit: 3 (data/br.out)'),
                   ('V5', '3', '3', 'measured here, B1 faultpack branch_flip on apt plain V5 (data/br.out)')]:
    put(d, 'stem', a, 'MEASURED', s); put(d, 'fanout branch', b, 'MEASURED', s)
# ---- group 4 (pol.jsonl, B3)
rows = [json.loads(l) for l in open('data/pol.jsonl')]
nm = {'V0': 'v0', 'V1': 'v1', 'V2': 'v2', 'V5': 'v5_apt033'}
def val(d, models, goal):
    xs = [r['min'] for r in rows if r['design'] == nm[d] and r['model'] in models and r['goal'] == goal]
    ints = [int(x) for x in xs if x.isdigit()]
    return str(min(ints)) if ints else '>3'
RISE = ('rise_all', 'rise_half', 'rise_unions', 'rise_cone')
RAIL = ('rail_any',)
for d in D:
    src = 'data/pol.jsonl (b3pol.py = B3 engine copy + 0->1 events), T=6 cap 3 z3 60 s; ' + ('spike netlist' if d != 'V5' else 'apt0.33 plain netlist')
    put(d, 'stem flip', {'V0': '1', 'V1': '1', 'V2': '3', 'V5': '3'}[d], 'MEASURED', 'B3 stem_flip row, reproduced in data/ctrl.jsonl')
    put(d, 'rail 1->0', val(d, RAIL, 'word'), 'SIMULATED', src + '; B3 rail_any (all/half/unions/cone)')
    put(d, 'rail 0->1 CONTROL', val(d, RISE, 'word'), 'SIMULATED', src + '; rise_all/half/unions/cone, min')
    put(d, 'either polarity', val(d, ('both_any',), 'word'), 'SIMULATED', src + '; both_any = union of both event families, one polarity per event')
    put(d, 'selective 1->0 subset', val(d, ('dip_subset',), 'word'), 'SIMULATED', src + '; B3 dip_subset bound')
    put(d, 'selective 0->1 subset', val(d, ('rise_subset',), 'word'), 'SIMULATED', src)
    put(d, 'rail 1->0 ', val(d, RAIL, 'ok'), 'SIMULATED', src)
    put(d, 'rail 0->1 CONTROL ', val(d, RISE, 'ok'), 'SIMULATED', src)
# ---- group 5
L2 = 'research/c4/l2/L2_REPORT.md rail-level paragraph (SUB cost word/ok), research/c4/layout/LAYOUT_REPORT.md'
put('V2', 'base', '1', 'SIMULATED', L2 + ': VPWR rail family base 1/1'); put('V2', 'spread v8', '2', 'SIMULATED', L2 + ': v8 2/2'); put('V2', 'rr (diff. rails)', '3', 'SIMULATED', L2 + ': rr 3/2')
put('V1', 'base', '1', 'SIMULATED', 'LAYOUT_REPORT sec.4: V1 rows/rails/straps SUB 1/1')
for d in ('V1',):
    for col in ('spread v8', 'rr (diff. rails)'): put(d, col, 'n/a', 'UNMEASURED', 'no spread layout for V1')
for d in ('V0', 'V5'):
    for col in ('base', 'spread v8', 'rr (diff. rails)'): put(d, col, 'n/a', 'UNMEASURED', 'no placed layout for ' + d)
for d in D: put(d, 'any: 0->1 event', 'n/a', 'UNMEASURED', 'the 0->1 control was run on netlist hierarchy domains only; not on layout-derived domains (needs b3cell + L2 DEFs)')
# ---- write csv / md
with open('ledger.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['design', 'stage', 'column', 'min_events', 'label', 'source'])
    for d in D:
        for g, cols in G:
            for c in cols:
                v, lab, src = C[(d, c)]; w.writerow([d, g, c.strip(), v, lab, src])
tag = {'MEASURED': 'M', 'SIMULATED': 'S', 'UNMEASURED': 'U'}
md = ['Cell = minimum number of modelled events (single-cycle bit flips / rail events), T=6 cycles, at most 3 events, goal boot_word==0x96 unless stated; `>3` = no attack found up to 3 (a bound, not "secure"). Label: M = MEASURED, S = SIMULATED (modelled rail/dip/placement event, not physical), U = UNMEASURED (n/a).', '']
for g, cols in G:
    md += [f'**{g}**', '', '| design | ' + ' | '.join(c.strip() for c in cols) + ' |', '|---|' + '---|' * len(cols)]
    for d in D: md.append(f'| {d} | ' + ' | '.join(f'{C[(d,c)][0]} ({tag[C[(d,c)][1]]})' for c in cols) + ' |')
    md.append('')
open('LEDGER_table.md', 'w').write('\n'.join(md))
# ---- PNG
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
cols = [(gi, c) for gi, (g, cs) in enumerate(G) for c in cs]
fig, ax = plt.subplots(figsize=(24, 6.2))
fill = {'MEASURED': '#cfe3f5', 'SIMULATED': '#fde3b8', 'UNMEASURED': '#e6e6e6'}
cw, rh, gap = 1.0, 1.0, 0.5
x = 0; xs = []
for i, (gi, c) in enumerate(cols):
    if i and cols[i - 1][0] != gi: x += gap
    xs.append(x); x += cw
for ri, d in enumerate(D):
    y = len(D) - 1 - ri
    ax.text(-0.15, y + 0.5, d, ha='right', va='center', fontsize=13, fontweight='bold')
    for (gi, c), x0 in zip(cols, xs):
        v, lab, _ = C[(d, c)]
        ax.add_patch(Rectangle((x0, y), cw, rh, facecolor=fill[lab], edgecolor='white', lw=2))
        crit = v == '1'
        ax.text(x0 + cw / 2, y + 0.5, v if v != 'n/a' else '–', ha='center', va='center', fontsize=15 if v != 'n/a' else 12,
                fontweight='bold' if crit else 'normal', color='#b00020' if crit else ('#555' if v == 'n/a' else '#111'))
        if lab == 'SIMULATED': ax.text(x0 + cw - 0.06, y + 0.06, 'S', ha='right', va='bottom', fontsize=7, color='#8a5a00')
        if lab == 'UNMEASURED': ax.text(x0 + cw - 0.06, y + 0.06, 'U', ha='right', va='bottom', fontsize=7, color='#555')
for gi, (g, cs) in enumerate(G):
    idx = [i for i, (gj, _) in enumerate(cols) if gj == gi]
    x0, x1 = xs[idx[0]], xs[idx[-1]] + cw
    ax.text((x0 + x1) / 2, len(D) + 1.6, g, ha='center', va='bottom', fontsize=9, fontweight='bold')
for (gi, c), x0 in zip(cols, xs):
    ax.text(x0 + cw / 2, len(D) + 0.05, '\n'.join(textwrap.wrap(c.strip(), 11)), ha='center', va='bottom', fontsize=7.5)
ax.set_xlim(-0.9, x); ax.set_ylim(-1.1, len(D) + 2.3); ax.axis('off')
ax.legend(handles=[Patch(fc=fill['MEASURED'], label='MEASURED (solver minimum on a netlist)'), Patch(fc=fill['SIMULATED'], label='SIMULATED (modelled rail/dip/placement event)'),
                   Patch(fc=fill['UNMEASURED'], label='UNMEASURED (no number)')], loc='lower left', ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0, -0.02))
fig.suptitle('Redundancy survival ledger: minimum modelled events to reach the accept word (T=6, <=3 events; red 1 = one event suffices; >3 = none found up to 3)', fontsize=12.5, y=0.99)
fig.text(0.01, 0.01, 'Toy designs, modelled bit flips and rail events, no physical-glitch or hardware claim. Source per cell: research/c5/ledger/ledger.csv', fontsize=8, color='#444')
fig.savefig('ledger.png', dpi=130, bbox_inches='tight'); print('ok')
