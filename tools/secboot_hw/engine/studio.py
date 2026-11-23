"""JSON for a Studio panel "Secure-boot hardware". panel(None) is the skeleton stored in studio/secboot_hw.json
(every result empty, status NOT_RUN); panel(records) fills it from a cloud run (engine/run_glitchsat.py).
Run: python3 -m engine.studio        (rewrites studio/secboot_hw.json)
"""
import json, os
from model.variants import VARIANTS, CM_TEXT

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = 'glitchsat-studio-secboot-hw/1'
LABELS = dict(MEASURED='produced by the cloud run that wrote this file',
              NOT_RUN='no fault analysis has been run for this entry yet',
              FAILED='the cloud run could not synthesise or analyse this entry (see its record.json)',
              DESIGN_INTENT='what the countermeasure is meant to do; not a result')


def _k_cells(fr, kmax):
    cells = []
    for row in (fr or {}).get('k', []):
        cells.append(dict(k=row['k'], verdict=row['verdict'], min_faults=row.get('min_faults'),
                          implied=bool(row.get('implied')), solve_s=row.get('solve_s'),
                          faults=[(f['net'], f['cycle']) for f in (row.get('faults') or [])]))
    have = {c['k'] for c in cells}
    cells += [dict(k=k, verdict='NOT_RUN', min_faults=None, implied=False, solve_s=None, faults=[])
              for k in range(1, kmax + 1) if k not in have]
    return sorted(cells, key=lambda c: c['k'])


def _status(r):
    if not r:
        return 'NOT_RUN'
    ok = [f for f in r.get('flows', {}).values() if not f['synth']['exit']]
    return 'MEASURED' if ok and not r.get('error') else 'FAILED'


def panel(records=None, kmax=3, flows=('plain', 'opt')):
    by = {r['name']: r for r in (records or [])}
    cards = []
    for v in VARIANTS:
        r = by.get(v.name)
        res = {}
        for f in flows:
            fr = (r or {}).get('flows', {}).get(f)
            res[f] = dict(gates=(fr or {}).get('gates'), flops=(fr or {}).get('flops'),
                          replay_ok=((fr or {}).get('replay') or {}).get('ok'),
                          by_k=_k_cells(fr, kmax))
        cards.append(dict(
            name=v.name, family=v.family, title=v.plain,
            countermeasures=[dict(id=c, text=CM_TEXT[c]) for c in v.cms],
            design_intent=v.intent or None, slow=v.large,
            experiment=dict(top=v.top, attacker_input='sig (8 bits, held constant)', key=f'0x{v.key:02X}',
                            goal=f'{v.goal_port} == 0x{v.goal_value:X}', cycles=v.cycles,
                            register_bits=v.flop_bits(), file=f'rtl/tops/{v.top}.v'),
            status=_status(r), results=res))
    return dict(schema=SCHEMA, panel_title='Secure-boot hardware',
                banner='Our own boot-check hardware, in several protected versions. Each card asks: how many modelled '
                       'bit flips make it accept a wrong image? Results are bounded (k flips, fixed cycles) and appear '
                       'only after a cloud run; until then every result is NOT_RUN.',
                labels=LABELS, kmax=kmax, flows=list(flows), cards=cards)


def write_skeleton(root=HERE):
    p = os.path.join(root, 'studio', 'secboot_hw.json')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as fh:
        json.dump(panel(None), fh, indent=1)
        fh.write('\n')
    return p


if __name__ == '__main__':
    print(write_skeleton())
