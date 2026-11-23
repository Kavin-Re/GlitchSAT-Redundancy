"""Evidence records, the Markdown results table and the JSON for the Studio "Suggest a fix" panel."""
import json, os
from . import spec as S, search, sim

LABELS = {
    'MEASURED': 'simulated here, exhaustively, on the netlist named in the row',
    'RECORDED': 'copied from a file already in the repository; not re-run here',
    'UNTESTED-HERE': 'needs Yosys; the generated script and cloud/run_cloud.sh produce it',
    'ASSUMED': 'a modelling choice or unit weight, stated where used',
}
CAVEATS = [
    'Modelled faults only: one-cycle bit flips of gate outputs and flop outputs. Not a physical glitch model.',
    'Toy 8-bit designs with a constant attacker input and a known reset state.',
    'A number belongs to one netlist. The reference mappings are written by this tool, they are not Yosys output; '
    're-synthesis can share or merge logic differently and change the number.',
    '"At least G" means: no set of at most G-1 modelled flips works, for every wrong input and every number of clock cycles, '
    'on the listed netlists. It is an exhaustive search of the model, not a proof about hardware.',
]


def fmt_min(m, upto):
    return str(m) if m is not None else f'> {upto}'


def changes(before, after):
    out = []
    h = lambda sp, v: f'0x{v:0{(sp.width + 3) // 4}X}'
    for k in ('idle', 'armed', 'accept', 'reject'):
        if getattr(before, k) != getattr(after, k) or before.width != after.width:
            out.append(dict(what=f'{k} code word', before=h(before, getattr(before, k)), after=h(after, getattr(after, k))))
    if before.width != after.width:
        out.append(dict(what='state width (bits)', before=before.width, after=after.width))
    if before.output != after.output:
        out.append(dict(what='boot_word source', before=before.output, after=after.output))
    if before.voter != after.voter:
        out.append(dict(what='voter placement', before=before.voter, after=after.voter))
    if before.copies != after.copies:
        out.append(dict(what='compare copies that own bits', before=before.copies, after=after.copies))
    if after.voter == 'owner' and before.owner != after.owner:
        out.append(dict(what='bit ownership (bit 7..0 -> copy)', before=''.join(map(str, reversed(before.owner))) or '-',
                        after=''.join(map(str, reversed(after.owner)))))
    if before.alarm != after.alarm:
        out.append(dict(what='alarm', before=before.alarm, after=f'{after.alarm} with {after.check_copies} check copy'))
    if before.trap_invalid != after.trap_invalid:
        out.append(dict(what='invalid state', before='held', after='goes to reject'))
    return out


def evidence(res, files=None):
    """Plain dict (JSON-safe) for one harden() result."""
    base, goal, best = res['design'], res['goal'], res['best']
    mp = lambda meas, upto: {k: dict(min_flips=v['min_flips'], shown=fmt_min(v['min_flips'], upto), gates=v['gates'], flops=v['flops'],
                                     sets_simulated=v['sets_simulated'], fault_sites_per_cycle=v['sites'], witness=v['witness'],
                                     right_key_boots=v['honest_ok'], wrong_key_boots_without_faults=bool(v['wrong_accept']),
                                     matches_description=v['matches_description']) for k, v in meas.items()}
    e = dict(schema='glitchsat-harden/1', design=base.name, design_description=base.short(), spec=base.as_dict(),
             goal=dict(min_flips_at_least=goal, meaning=f'no attack with {goal - 1} or fewer modelled flips'),
             goal_output=f'boot_word == 0x{base.goal_value():02X} while sig != 0x{base.key:02X}',
             cycles=res['cycles'], moves_allowed=res['allow'],
             before=dict(min_flips=res['before_min'], shown=fmt_min(res['before_min'], max(goal, 1)), label='MEASURED',
                         per_mapping=mp(res['before'], max(goal, 1)),
                         if_copies_merged=fmt_min(res['before_merged']['min_flips'], 1)),
             search=dict(res['stats'], runtime_s=res['runtime_s']),
             reached=best is not None, fixes=[], caveats=CAVEATS, labels=LABELS)
    for i, f in enumerate(res['found']):
        sp = f['spec']
        am = f.get('after_min')
        e['fixes'].append(dict(
            rank=i + 1, description=sp.short(), spec=sp.as_dict(), moves=f['moves'],
            move_text=[dict(move=m, title=search.MOVES[m][0], what=search.MOVES[m][1], why_sound=search.MOVES[m][2]) for m in f['moves'] + ['separation']],
            changes=changes(base, sp),
            after=dict(min_flips=am, shown=(str(am) if am is not None else f'> {goal}'), label='MEASURED',
                       statement=f'no attack with <= {goal - 1} flips on all {len(f["measured"])} unmerged reference mappings, all wrong inputs, any number of cycles',
                       per_mapping=mp(f['measured'], goal - 1), exact_per_mapping={k: fmt_min(v[0], v[1] if v[1] is not None else goal) for k, v in f.get('exact', {}).items()},
                       witness_at_minimum=f.get('exact_witness'), bounded_6_cycles={k: fmt_min(v, goal - 1) for k, v in f.get('bounded6', {}).items()},
                       if_copies_merged=fmt_min(f['merged']['min_flips'], 1)),
            cost=f['cost'],
            yosys=dict(label='UNTESTED-HERE', note='hardened Verilog and Yosys script are generated; cloud/run_cloud.sh synthesises them with apt Yosys 0.33 '
                                                   'over the synthesis configurations and re-runs this verification on every netlist'),
            files=(files or {}).get(i, {})))
    if best is None and res['best_fail']:
        w, c, mv = res['best_fail']
        e['closest'] = dict(min_flips=w, description=c.short(), moves=mv, note='best candidate simulated that did not reach the goal')
    return e


def write_fix_files(res, outdir, top_n=1):
    """Write Verilog, Yosys scripts and reference netlists for the best fixes. Returns {rank index: {name: path}}."""
    os.makedirs(outdir, exist_ok=True)
    base = res['design']
    files = {}
    with open(os.path.join(outdir, f'{base.name}_before.v'), 'w') as f:
        f.write(S.verilog(base, note='Design as analysed (before).'))
    for i, fx in enumerate(res['found'][:top_n]):
        sp = fx['spec']
        tag = f'{base.name}_g{res["goal"]}' + ('' if i == 0 else f'_alt{i}')
        top = f'{base.name}h'
        d = {}
        d['verilog'] = os.path.join(outdir, tag + '.v')
        with open(d['verilog'], 'w') as f:
            f.write(S.verilog(sp, module=top, note=f'Hardened for: at least {res["goal"]} modelled flips. Verified by exhaustive simulation on reference '
                                                    'gate mappings only; Yosys synthesis of this file is UNTESTED here (see cloud/run_cloud.sh).\n'
                                                    'Synthesis must keep the cmp8 copies separate: use the .ys script next to this file.'))
        d['yosys_script'] = os.path.join(outdir, tag + '.ys')
        with open(d['yosys_script'], 'w') as f:
            f.write('# project plain flow + copy-separation guard (cells of every kept module get keep=1 before flatten)\n')
            f.write(YS_GUARD_NOTE)
            f.write(S.yosys_script(sp, os.path.basename(d['verilog']), tag + '_yosys.json', top=top))
        for mpn in S.UNMERGED:
            nl = S.build_mapping(sp.replace(name=top), mpn)
            p = os.path.join(outdir, f'{tag}_{mpn}.json')
            nl.write(p)
            d['netlist_' + mpn] = p
        nl = S.build_mapping(sp.replace(name=top), 'select-shared')
        d['netlist_verilog'] = os.path.join(outdir, tag + '_netlist.v')
        with open(d['netlist_verilog'], 'w') as f:
            f.write(nl.to_verilog(header='// Gate-level netlist of the select-shared reference mapping that was verified (one assign per gate).\n'
                                         '// Toy design, modelled bit flips only.\n'))
        d['spec'] = os.path.join(outdir, tag + '.spec.json')
        with open(d['spec'], 'w') as f:
            json.dump(dict(before=base.as_dict(), after=sp.as_dict(), goal=res['goal'], top=top), f, indent=1)
        files[i] = {k: os.path.relpath(v, os.path.dirname(outdir.rstrip('/'))) for k, v in d.items()}
    return files


def table_row(e):
    if e['reached']:
        f = e['fixes'][0]
        c = f['cost']
        ch = '; '.join(f"{x['what']} {x['before']} -> {x['after']}" for x in f['changes']) or 'none needed'
        return (f"| {e['design']} | >= {e['goal']['min_flips_at_least']} | {ch} | {e['before']['shown']} | {f['after']['shown']} | "
                f"{c['gates_added']:+d} gates, {c['flops_added']:+d} flops, depth {c['depth_added']:+d}, latency +0 cycles | {f['after']['if_copies_merged']} |")
    cl = e.get('closest')
    return (f"| {e['design']} | >= {e['goal']['min_flips_at_least']} | not reached" + (f" (closest: {cl['description']}, {cl['min_flips']})" if cl else '')
            + f" | {e['before']['shown']} | - | - | - |")


TABLE_HEAD = ('| design | goal (min flips) | best fix found | min flips before | min flips after | cost | after, if copies get merged |\n'
              '|---|---|---|---|---|---|---|')


YS_GUARD_NOTE = ('# the guard matters when a later flow adds opt/opt_merge: after flatten this script itself runs only opt_clean and\n'
                 '# techmap, which do not merge the copies\n')


def boot_word_note(changes):
    """Plain note when a fix changes what boot_word shows before the decision (decoded output -> state word), else None."""
    ch = {c['what']: c for c in changes}
    src = ch.get('boot_word source')
    if not src or src['before'] != 'decoded' or src['after'] != 'state':
        return None
    idle, armed = ch.get('idle code word', {}).get('after'), ch.get('armed code word', {}).get('after')
    rej = ch.get('reject code word', {}).get('after')
    if not (idle and armed and rej):
        return None
    h = lambda x: x[2:].upper() if x.lower().startswith('0x') else x
    return (f'The fix changes what boot_word shows before the decision ({h(idle)}/{h(armed)} instead of {h(rej)}); '
            f'a consumer that tests == 0x96 is unaffected.')


def studio_panel(evs, extra=None):
    """Compact JSON for the Studio "Suggest a fix" panel."""
    cards = []
    for e in evs:
        card = dict(design=e['design'], goal_min_flips=e['goal']['min_flips_at_least'], before_min_flips=e['before']['shown'],
                    before_witness=next((v['witness'] for v in e['before']['per_mapping'].values() if v['witness']), None),
                    reached=e['reached'], suggestions=[])
        for f in e['fixes']:
            card['suggestions'].append(dict(
                title=' + '.join(search.MOVES[m][0] for m in f['moves']) or 'No change needed',
                plain=[search.MOVES[m][1] for m in f['moves']],
                changes=f['changes'], after_min_flips=f['after']['shown'], evidence_label='MEASURED',
                evidence=f['after']['statement'], per_mapping={k: v['shown'] for k, v in f['after']['per_mapping'].items()},
                if_copies_merged=f['after']['if_copies_merged'],
                cost=dict(gates=f['cost']['gates_added'], flops=f['cost']['flops_added'], depth=f['cost']['depth_added'], latency_cycles=0),
                needs='copies kept separate through synthesis (script provided)', yosys='UNTESTED-HERE', files=f['files']))
            note = boot_word_note(f['changes'])
            if note:
                card['suggestions'][-1]['note'] = note
        if not e['reached'] and e.get('closest'):
            card['closest'] = e['closest']
        cards.append(card)
    return dict(schema='glitchsat-studio-suggest-fix/1', panel_title='Suggest a fix',
                banner='Modelled bit flips on toy designs. "After" numbers are exhaustive simulations of reference gate mappings written by the tool, '
                       'not of a Yosys netlist, unless a row says so. Not a security proof.',
                labels=LABELS, cards=cards, **(extra or {}))
