"""RT2 differential fuzz: --amk counter vs legacy (+ brute-force oracle + independent witness replay).
usage: python fuzz_amk.py SEED COUNT   (run with the venv python; glitchsat.py is imported from the work copy)"""
import sys, json, random, itertools, os, collections
sys.path.insert(0, '/tmp/work_rt2/p/scripts')
import glitchsat as G
from faultbound_wt import _engine as P

def gen(rng):
    wi = rng.choice([1, 2, 3]); wo = rng.choice([1, 2, 3, 4]); nff = rng.choice([0, 1, 2, 3]); ngate = rng.randint(2, 8)
    nid = [2]
    def new():
        nid[0] += 1; return nid[0] - 1
    inb = [new() for _ in range(wi)]; clk = new()
    aux = [new()] if rng.random() < .3 else []
    qs = [new() for _ in range(nff)]
    avail = inb + aux + qs + ['0', '1']
    cells = {}; gouts = []
    for g in range(ngate):
        ty = rng.choice(['$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_']); o = new()
        pick = lambda: rng.choice(avail + gouts[-3:])
        con = {'A': [pick()], 'Y': [o]}
        if ty != '$_NOT_': con['B'] = [pick()]
        if ty == '$_MUX_': con['S'] = [pick()]
        cells[f'g{g}'] = dict(type=ty, connections=con); gouts.append(o)
    pool = avail + gouts
    for i, q in enumerate(qs):
        cells[f'ff{i}'] = dict(type='$_DFF_P_', connections={'C': [clk], 'D': [rng.choice(pool)], 'Q': [q]})
    outb = [rng.choice(gouts + qs + (inb if rng.random() < .25 else []) + (['0', '1'] if rng.random() < .1 else [])) for _ in range(wo)]
    names = {}
    for i, q in enumerate(qs):
        a = {}
        if rng.random() < .5: a['init'] = rng.choice(['0', '1'])
        names[f'q{i}'] = dict(bits=[q], attributes=a)
    ports = {'clk': dict(direction='input', bits=[clk]), 'sig': dict(direction='input', bits=inb), 'boot_word': dict(direction='output', bits=outb)}
    if aux: ports['aux'] = dict(direction='input', bits=aux)
    return dict(modules={'t': dict(ports=ports, cells=cells, netnames=names)}), wi, wo

def make_sim(doc):
    m = doc['modules']['t']; drv = {}; ffs = []
    for c in m['cells'].values():
        if c['type'] == '$_DFF_P_': ffs.append((c['connections']['D'][0], c['connections']['Q'][0]))
        else: drv[c['connections']['Y'][0]] = c
    init = {}
    for n in m['netnames'].values():
        iv = n['attributes'].get('init')
        if iv: init[n['bits'][0]] = (iv[-1] == '1')
    inbits = {}
    for pn, p in m['ports'].items():
        if p['direction'] == 'input' and pn != 'clk':
            for i, b in enumerate(p['bits']): inbits[b] = (pn, i)
    outb = m['ports']['boot_word']['bits']; qs = [q for _, q in ffs]
    def run(N, faults, ins, gv, mask, init0=None):
        """returns True if goal reached at some cycle. ins: port->int. faults: set of (t,b). init0: dict q->bool or None (netlist init)."""
        st = {q: (init0[q] if init0 is not None else init.get(q, False)) for q in qs}
        for t in range(N):
            val = {}
            def get(b):
                if b == '0' or b == '1': return b == '1'
                if b in val: return val[b]
                if b in inbits: pn, i = inbits[b]; v = bool((ins[pn] >> i) & 1)
                elif b in st: v = st[b]
                else:
                    c = drv[b]; con = c['connections']; g = lambda p: get(con[p][0]); ty = c['type']
                    v = {'$_AND_': lambda: g('A') and g('B'), '$_OR_': lambda: g('A') or g('B'), '$_XOR_': lambda: g('A') != g('B'),
                         '$_NOT_': lambda: not g('A'), '$_MUX_': lambda: g('B') if g('S') else g('A')}[ty]()
                if (t, b) in faults: v = not v
                val[b] = v; return v
            nxt = {q: get(d) for d, q in ffs}
            ok = all(get(b) == bool((gv >> i) & 1) for i, b in enumerate(outb) if mask is None or (mask >> i) & 1)
            if ok: return True
            st = nxt
        return False
    sites_gate = [c['connections']['Y'][0] for c in m['cells'].values() if c['type'] != '$_DFF_P_']
    return run, sites_gate, qs, inbits, m['ports']

def input_space(ports, key, wi):
    names = [p for p, v in ports.items() if v['direction'] == 'input' and p != 'clk']
    ws = {p: len(ports[p]['bits']) for p in names}
    for combo in itertools.product(*[range(1 << ws[p]) for p in names]):
        d = dict(zip(names, combo))
        if d['sig'] != key: yield d

def brute(run, sites_gate, qs, inbits, ports, N, k, key, gv, mask, input_sites, init_mode, wi, nff):
    sites = list(qs) + sites_gate + (list(inbits) if input_sites else [])
    allf = [(t, b) for t in range(N) for b in sites]
    inits = [None] if init_mode == 'known' else [dict(zip(qs, bits)) for bits in itertools.product([False, True], repeat=nff)]
    for r in range(k + 1):
        for fl in itertools.combinations(allf, r):
            fs = set(fl)
            for ins in input_space(ports, key, wi):
                for i0 in inits:
                    if init_mode == 'free_nongoal' and run(N, set(), ins, gv, mask, i0): continue
                    if run(N, fs, ins, gv, mask, i0): return r
    return None

def cost(sites, N, k):
    from math import comb
    return sum(comb(sites * N, r) for r in range(k + 1))

def main(seed, cnt):
    rng = random.Random(seed); bad = 0; st = collections.Counter(); wit_bad = 0
    for i in range(cnt):
        doc, wi, wo = gen(rng)
        N = rng.randint(1, 5); k = rng.choice([0, 1, 2, 3, 3]); key = rng.randrange(1 << wi); gv = rng.randrange(1 << wo)
        mask = rng.choice([None, None, rng.randrange(1, 1 << wo)])
        input_sites = rng.random() < .35; init_mode = rng.choice(['known', 'known', 'known', 'arbitrary', 'free_nongoal'])
        p = f'/tmp/work_rt2/fz/n{seed}_{i}.json'; json.dump(doc, open(p, 'w'))
        run, sg, qs, inbits, ports = make_sim(doc)
        nsites = len(sg) + len(qs) + (len(inbits) if input_sites else 0)
        tractable = cost(nsites, N, k) * (1 << sum(len(v['bits']) for pn, v in ports.items() if v['direction'] == 'input' and pn != 'clk')) * (1 << len(qs) if init_mode != 'known' else 1) <= 120000
        exp = None
        if tractable:
            b = brute(run, sg, qs, inbits, ports, N, k, key, gv, mask, input_sites, init_mode, wi, len(qs))
            exp = ('ATTACK_FOUND', b) if b is not None else ('NO_ATTACK_UP_TO_BOUND', None)
            st['oracle'] += 1
        results = {}
        for eng_name, mod in (('P', P), ('G', G)):
            if eng_name == 'G' and (mask is not None or input_sites or init_mode != 'known'): continue
            nl = mod.Netlist(p, 't')
            for amk in ('counter', 'legacy'):
                for red in ('none', 'coi', 'full'):
                    kw = dict(key=key, goal_value=gv, reduce=red, amk=amk)
                    if eng_name == 'P': kw.update(goal_mask=mask, input_sites=input_sites, init_mode=init_mode)
                    try:
                        v, info, res = mod.solve(nl, N, k, **kw)
                        mn = len(res['faults']) if res else None
                        got = (v, mn)
                        if res:   # independent witness replay
                            ins = {pn: res['inputs'].get(pn, 0) for pn in ports if ports[pn]['direction'] == 'input' and pn != 'clk'}
                            i0 = None
                            if eng_name == 'P' and init_mode != 'known':
                                ones = set(res.get('init_ones', [])); i0 = {q: (q in ones) for q in qs}
                            fs = set(res['faults'])
                            problems = []
                            if len(fs) != len(res['faults']) or len(fs) > k: problems.append('count')
                            if ins['sig'] == key: problems.append('sig==key')
                            if not run(N, fs, ins, gv, mask if eng_name == 'P' else None, i0): problems.append('goal-not-reached')
                            if init_mode == 'free_nongoal' and eng_name == 'P' and run(N, set(), ins, gv, mask, i0): problems.append('faultfree-accepts')
                            if problems:
                                wit_bad += 1; print('WITNESS', i, eng_name, amk, red, problems, p, flush=True)
                    except Exception as e:
                        got = ('EXC', repr(e)[:100])
                    results[(eng_name, amk, red)] = got
                    if exp and got != exp:
                        bad += 1; print('ORACLE-DISAGREE', i, eng_name, amk, red, 'N', N, 'k', k, 'mask', mask, 'is', input_sites, init_mode, 'exp', exp, 'got', got, p, flush=True)
        # counter vs legacy
        for (e, a, r), g in results.items():
            if a == 'counter':
                o = results[(e, 'legacy', r)]
                st['cl_pairs'] += 1
                if o != g: bad += 1; print('CTR-LEG-DISAGREE', i, e, r, g, o, p, flush=True)
        vs = {g[0] for g in results.values()}
        st['att' if 'ATTACK_FOUND' in vs else 'none'] += 1
        st['runs'] += len(results)
    print('seed', seed, 'netlists', cnt, 'bad', bad, 'witness_bad', wit_bad, dict(st))

if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]))
