#!/usr/bin/env python3
"""For one netlist: flip each single net (gate output or flop Q) in cycle 0 (state = init,
sig = 0x00) and print the XOR it causes on the next state. Shows which single stems move several result bits at once while the
armed constant is being loaded. usage: cycle0_delta.py NETLIST TOP ARMEDHEX"""
import json, sys, collections
m = json.load(open(sys.argv[1]))['modules'][sys.argv[2]]; armed = int(sys.argv[3], 16); need = armed ^ 0x96
gates = {}; flops = []
for c in m['cells'].values():
    k = c['connections']
    if 'DFF' in c['type']: flops.append((k['D'][0], k['Q'][0]))
    else: gates[k['Y'][0]] = (c['type'], {q: v[0] for q, v in k.items() if q != 'Y'})
names = {}
for n, x in m['netnames'].items():
    for i, b in enumerate(x['bits']):
        if isinstance(b, int) and (b not in names or (names[b].startswith('$') and not n.startswith('$'))):
            names[b] = n if len(x['bits']) == 1 else '%s[%d]' % (n, i)
init = {}
for x in m['netnames'].values():
    iv = x.get('attributes', {}).get('init')
    if iv:
        for i, ch in enumerate(reversed(iv)): init[x['bits'][i]] = int(ch == '1')
st = m['netnames']['st']['bits']; sig = m['ports']['sig']['bits']
def nxt(flip):
    v = {q: init.get(q, 0) ^ (q == flip) for _, q in flops}; v.update({b: 0 for b in sig})
    def ev(b):
        if not isinstance(b, int): return int(b == '1')
        if b in v: return v[b]
        t, a = gates[b]; a = {q: ev(x) for q, x in a.items()}
        r = {'$_AND_': lambda: a['A'] & a['B'], '$_OR_': lambda: a['A'] | a['B'], '$_XOR_': lambda: a['A'] ^ a['B'],
             '$_NOT_': lambda: 1 - a['A'], '$_MUX_': lambda: a['B'] if a['S'] else a['A']}[t]() ^ (b == flip)
        v[b] = r; return r
    dq = {q: ev(d) for d, q in flops}
    return sum(dq[b] << i for i, b in enumerate(st))
base = nxt(None); grp = 'm0 m1 m2 m0 m1 m2 m0 m1'.split()
print('%s: golden next state after cycle 0 = %02X (armed %02X); bits that must change to reach 96: %02X = %s' % (
    sys.argv[1], base, armed, need, [(i, grp[i]) for i in range(8) if need >> i & 1]))
useful = collections.defaultdict(list)
for b in sorted(set(gates) | {q for _, q in flops}):
    d = nxt(b) ^ base
    if d and d & ~need == 0: useful[d].append(names.get(b, str(b)))
for d, ns in sorted(useful.items(), key=lambda kv: -bin(kv[0]).count('1')):
    print('  delta %02X (bits %s, copies %s): %d net(s): %s' % (d, [i for i in range(8) if d >> i & 1],
          sorted({grp[i] for i in range(8) if d >> i & 1}), len(ns), ', '.join(ns[:6])))
# greedy exact cover size (min number of single-net cycle-0 deltas whose XOR equals need), brute force up to 4
import itertools
ds = list(useful)
best = None
for r in range(1, 5):
    for c in itertools.combinations(ds, r):
        x = 0
        for d in c: x ^= d
        if x == need: best = (r, ['%02X' % d for d in c]); break
    if best: break
print('  fewest cycle-0 flips whose deltas XOR to %02X (deltas inside the needed bits only, <=4): %s' % (need, best))
