"""Gate 5: R27 speed cases + V2 spike k=3 + M1 mask samples, counter vs legacy on the patched copy
and unmodified base. usage: gate5.py speed|m1 """
import sys, json, time
sys.path.insert(0, '/tmp/work_t3/work/product/src'); sys.path.insert(0, '/tmp/work_t3/work/scripts')
from faultbound_wt import _engine as P
import glitchsat as G
NL = '/tmp/work_r27/nl/'
CASES = {'dmr': ('sbox_dmr.json', 'sbox_dmr', dict(goal_out='gout', goal_value=0x17c, attack_in='sig', key=1)),
         's2': ('s2.json', 'v2', dict())}
def one(eng, amk, name, k, T, tmo):
    f, top, kw = CASES[name]
    nl = eng.Netlist(NL + f, top); t0 = time.time()
    v, info, res = eng.solve(nl, T, k, timeout_ms=tmo, amk=amk, **kw)
    return dict(eng=eng.__name__.split('.')[-1], amk=amk, case=f'{name} k={k} T={T}', verdict=v, nfaults=len(res['faults']) if res else None,
                build_s=info['build_s'], solve_s=info['solve_s'], wall_s=round(time.time() - t0, 1))
if __name__ == '__main__':
    if sys.argv[1] == 'speed':
        for (name, k, T) in [('dmr', 1, 4), ('dmr', 1, 8), ('s2', 2, 12), ('s2', 2, 20), ('s2', 3, 6)]:
            for amk in ('counter', 'legacy'):
                tmo = 150000
                print(json.dumps(one(G, amk, name, k, T, tmo)), flush=True)
    else:
        rows = [json.loads(l) for l in open('research/c3/m1/m_v2_spike.jsonl')]; rows = rows[:5] + [r for r in rows if r['min'] in (2, 3)][:5]
        nl = P.Netlist('/tmp/work_t3/work/reference/spike_netlists/v2.json', 'v2')
        for r in rows:
            out = {}
            for amk in ('counter', 'legacy'):
                for k in range(0, 4):
                    v, i, res = P.solve(nl, 6, k, minimize=False, goal_mask=r['mask'], amk=amk, timeout_ms=120000)
                    if v == 'ATTACK_FOUND': out[amk] = k; break
                    if v != 'NO_ATTACK_UP_TO_BOUND': out[amk] = v; break
                else: out[amk] = 4
            print(json.dumps(dict(mask=r['mask'], m1_csv_min=r['min'], **out, same=out['counter'] == out['legacy'] == r['min'])), flush=True)
