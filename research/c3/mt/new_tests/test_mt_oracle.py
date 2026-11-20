"""Differential test of the solver against an independent brute-force simulator on small
hand-generated Yosys-JSON netlists, plus targeted netlists whose answer is known by construction.
Works for BOTH engines: scripts/glitchsat.py (suite 'root') and faultbound_wt._engine (suite 'product').
Select with env MT_ENGINE=root|product (default root). Root: run from the repo root, `pytest research/c3/mt/new_tests` or copy this file into tests/.
"""
import itertools, json, os, random, sys
import pytest

ENGINE = os.environ.get('MT_ENGINE', 'root')
if ENGINE == 'root':
    ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import glitchsat as g
else:
    from faultbound_wt import _engine as g

# ------------------------------------------------------------------ netlist builder (nets are ints; sig=[3,4], clk=[2], out=[5,6])
SIG, OUT, KEY, GOAL = [3, 4], [5, 6], 3, 1

def make(gates, flops, init=None, outbits=OUT):
    """gates: list of (type, out_net, [in nets in pin order A,B(,S)]); flops: list of (d, q)."""
    cells, n = {}, 0
    pins = {'$_AND_': 'AB', '$_OR_': 'AB', '$_XOR_': 'AB', '$_NOT_': 'A', '$_MUX_': 'ABS'}
    for ty, o, ins in gates:
        c = {p: [i] for p, i in zip(pins[ty], ins)}; c['Y'] = [o]
        cells[f'g{n}'] = dict(type=ty, connections=c); n += 1
    for d, q in flops:
        cells[f'f{n}'] = dict(type='$_DFF_P_', connections=dict(C=[2], D=[d], Q=[q])); n += 1
    netnames = {}
    for q, v in (init or {}).items():
        netnames[f'q{q}'] = dict(bits=[q], attributes=dict(init='1' if v else '0'))
    for q in [q for _, q in flops]:
        netnames.setdefault(f'q{q}', dict(bits=[q], attributes={}))
    ports = dict(clk=dict(direction='input', bits=[2]), sig=dict(direction='input', bits=SIG),
                 boot_word=dict(direction='output', bits=outbits))
    return dict(modules=dict(t=dict(ports=ports, cells=cells, netnames=netnames)))

def load(tmp, doc, name='n.json'):
    p = os.path.join(str(tmp), name)
    json.dump(doc, open(p, 'w'))
    return g.Netlist(p, 't')

# ------------------------------------------------------------------ independent brute-force oracle
def simulate(doc, N, sig, faults, goal=GOAL):
    m = doc['modules']['t']; cells = m['cells']
    gates = [(c['type'], c['connections']) for c in cells.values() if c['type'] != '$_DFF_P_']
    flops = [(c['connections']['D'][0], c['connections']['Q'][0]) for c in cells.values() if c['type'] == '$_DFF_P_']
    init = {}
    for x in m['netnames'].values():
        if x['attributes'].get('init') == '1': init[x['bits'][0]] = True
    state = {q: init.get(q, False) for _, q in flops}
    for t in range(N):
        val = {SIG[0]: bool(sig & 1), SIG[1]: bool(sig & 2)}
        val.update(state)
        for q in state:
            if (t, q) in faults: val[q] = not val[q]
        pending = list(gates)
        while pending:
            rest = []
            for ty, con in pending:
                ins = [con[p][0] for p in 'ABS' if p in con]
                if all(i in val or i in ('0', '1') for i in ins):
                    a = [val[i] if i in val else (i == '1') for i in ins]
                    y = {'$_AND_': lambda: a[0] and a[1], '$_OR_': lambda: a[0] or a[1], '$_XOR_': lambda: a[0] != a[1],
                         '$_NOT_': lambda: not a[0], '$_MUX_': lambda: a[1] if a[2] else a[0]}[ty]()
                    o = con['Y'][0]
                    val[o] = (y != ((t, o) in faults))
                else: rest.append((ty, con))
            assert len(rest) < len(pending), 'oracle: loop'
            pending = rest
        word = sum(int(val[b]) << i for i, b in enumerate(OUT))
        if word == goal: return True
        state = {q: val[d] if d in val else (d == '1') for d, q in flops}
    return False

def oracle_min(doc, N, kmax):
    m = doc['modules']['t']
    nets = [c['connections']['Y'][0] for c in m['cells'].values() if c['type'] != '$_DFF_P_'] + \
           [c['connections']['Q'][0] for c in m['cells'].values() if c['type'] == '$_DFF_P_']
    sites = [(t, b) for t in range(N) for b in nets]
    for k in range(kmax + 1):
        for fs in itertools.combinations(sites, k):
            fs = set(fs)
            if any(simulate(doc, N, s, fs) for s in range(4) if s != KEY): return k
    return None

def rand_net(seed):
    r = random.Random(seed)
    nflop, ngate = r.randint(0, 3), r.randint(3, 7)
    qs = list(range(10, 10 + nflop)); gs = list(range(20, 20 + ngate))
    avail = SIG + qs[:]; gates = []
    for o in gs:
        ty = r.choice(['$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'])
        ni = {'$_NOT_': 1, '$_MUX_': 3}.get(ty, 2)
        gates.append((ty, o, [r.choice(avail) for _ in range(ni)])); avail.append(o)
    # outputs driven through buffers-as-gates so ports are nets: out bits = last two gates (make them distinct nets)
    outs = gs[-2:] if len(gs) >= 2 else gs
    flops = [(r.choice(avail), q) for q in qs]
    init = {q: True for q in qs if r.random() < .5}   # others have NO init attribute (default 0)
    return make(gates, flops, init, outbits=outs if len(outs) == 2 else [outs[0], outs[0]])

# ------------------------------------------------------------------ tests
SEEDS = [3, 13, 15, 16, 22, 23, 25, 26, 27, 30, 34, 35, 36, 40, 41, 44, 48, 51, 53, 54, 58, 59, 62, 64, 65, 75, 77, 82, 87, 88]  # all have >=1 flop and oracle min 1 or 2 (chosen offline)

@pytest.mark.parametrize('seed', SEEDS)
@pytest.mark.parametrize('reduce', ['none', 'full'])
def test_matches_bruteforce(seed, reduce, tmp_path):
    doc = rand_net(seed); N, kmax = 3, 2
    global OUT
    outs = doc['modules']['t']['ports']['boot_word']['bits']
    old = OUT; OUT = outs
    try:
        nl = load(tmp_path, doc)
        want = oracle_min(doc, N, kmax)
        v, _, res = g.solve(nl, N, kmax, reduce=reduce, key=KEY, goal_value=GOAL)
        if want is None:
            assert v == 'NO_ATTACK_UP_TO_BOUND'
        else:
            assert v == 'ATTACK_FOUND'
            assert len(res['faults']) == want                    # minimisation loop and k bound
            # witness replays: the reported fault set + input really reach the goal and the input is not the key
            assert res['inputs']['sig'] != KEY
            assert simulate(doc, N, res['inputs']['sig'], set(res['faults']))
            # and k = want - 1 must be unsat (bound not off by one)
            if want >= 1:
                assert g.solve(nl, N, want - 1, reduce=reduce, key=KEY, goal_value=GOAL)[0] == 'NO_ATTACK_UP_TO_BOUND'
    finally:
        OUT = old


# ------------------------------------------------------------------ targeted: a design where ONLY a flop flip can reach the goal
def test_flop_only_attack_found(tmp_path):
    """No gates at all: boot_word bits are two flop Q nets (init 0). Goal 0b01 is reachable with exactly 1 flip of flop q10 at cycle 0.
    Kills mutants that drop flop fault sites (no_flop_sites), or that make flop flips inert."""
    doc = make([], [(10, 10), (11, 11)], init={10: False, 11: False}, outbits=[10, 11])
    nl = load(tmp_path, doc)
    assert g.solve(nl, 2, 0, key=KEY, goal_value=GOAL)[0] == 'NO_ATTACK_UP_TO_BOUND'
    v, _, res = g.solve(nl, 2, 1, key=KEY, goal_value=GOAL)
    assert v == 'ATTACK_FOUND' and res['faults'] == [(0, 10)] or res['faults'] == [(1, 10)]
    assert len(res['faults']) == 1
