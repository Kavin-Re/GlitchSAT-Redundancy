#!/usr/bin/env python3
"""Netlist inspector: init state, golden state sequence, gate counts, fan-out of a net
to flop D pins (structural cone). usage: nl_info.py NETLIST TOP [net-substring ...]"""
import json, sys, collections
p, top = sys.argv[1], sys.argv[2]
d = json.load(open(p)); m = d['modules'][top]
gates = {}; flops = []
for cn, c in m['cells'].items():
    k = c['connections']
    if 'DFF' in c['type']: flops.append((k['D'][0], k['Q'][0]))
    else: gates[k['Y'][0]] = (c['type'], {q: v[0] for q, v in k.items() if q != 'Y'}, cn)
names = {}
for n, x in m['netnames'].items():
    for i, b in enumerate(x['bits']):
        if isinstance(b, int):
            s = n if len(x['bits']) == 1 else '%s[%d]' % (n, i)
            if b not in names or (names[b].startswith('$') and not n.startswith('$')) : names[b] = s
init = {}
for n, x in m['netnames'].items():
    iv = x.get('attributes', {}).get('init')
    if iv:
        for i, ch in enumerate(reversed(iv)): init[x['bits'][i]] = int(ch == '1')
st = m['netnames']['st']['bits']; sig = m['ports']['sig']['bits']
print('creator:', d.get('creator')); print('comb gates:', len(gates), dict(collections.Counter(g[0] for g in gates.values())), 'flops:', len(flops))
def ev(b, v):
    if not isinstance(b, int): return int(b == '1')
    if b in v: return v[b]
    t, i, _ = gates[b]
    a = {q: ev(x, v) for q, x in i.items()}
    r = {'$_AND_': lambda: a['A'] & a['B'], '$_OR_': lambda: a['A'] | a['B'], '$_XOR_': lambda: a['A'] ^ a['B'],
         '$_NOT_': lambda: 1 - a['A'], '$_MUX_': lambda: a['B'] if a['S'] else a['A']}[t]()
    v[b] = r; return r
def run(s, T=5):
    cur = {q: init.get(q, 0) for _, q in flops}; seq = []
    for t in range(T):
        v = dict(cur); v.update({b: (s >> i) & 1 for i, b in enumerate(sig)})
        seq.append('%02X' % sum(v[b] << i for i, b in enumerate(st)))
        cur = {q: ev(dd, v) for dd, q in flops}
    return seq
print('init attr st = %02X' % sum(init.get(b, 0) << i for i, b in enumerate(st)))
print('state seq wrong key 0x00:', run(0), ' honest 0xC3:', run(0xC3))
dq = {dd: q for dd, q in flops}
fan = collections.defaultdict(set)
for y, (_, i, _) in gates.items():
    for x in i.values():
        if isinstance(x, int): fan[x].add(y)
grp = {0: 'm0', 1: 'm1', 2: 'm2', 3: 'm0', 4: 'm1', 5: 'm2', 6: 'm0', 7: 'm1'}
def reach(b):
    seen = set(); stk = [b]; out = set()
    while stk:
        x = stk.pop()
        if x in seen: continue
        seen.add(x)
        if x in dq: out.add(st.index(dq[x]))
        stk.extend(fan[x])
    return sorted(out)
for sub in sys.argv[3:]:
    for b, n in sorted(names.items()):
        if sub in n:
            g = gates.get(b)
            print('NET %s (bit %s) driver=%s inputs=%s direct_fanout=%d -> %s ; reaches D of st bits %s copies %s' % (
                n, b, g[0] if g else 'flop/input', {q: names.get(x, x) for q, x in g[1].items()} if g else '-', len(fan[b]),
                [names.get(y, y) + ':' + gates[y][0] for y in sorted(fan[b])], reach(b), [grp[i] for i in reach(b)]))
