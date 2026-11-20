"""Replays the z3/CLI witnesses in the z3-free simulator (anchor_sim.Net). Names are resolved through netnames."""
import json, sys
from anchor_sim import Net, ALL
def resolve(N, name):
    for b, n in N.names.items():
        if n == name: return b
    # fall back: cell-name search for abc-named gates is not available through netnames; search all netnames
    raise KeyError(name)
def replay(path, top, T, flips, sig):
    N = Net(path, top); st = N.init; by = {}
    for t, nm in flips: by.setdefault(t, set()).add(resolve(N, nm))
    hit_sig = False; res = []
    for t in range(T):
        h, ok, st = N.cycle(st, by.get(t, ()))
        res.append((t, bool((h >> sig) & 1)))
    return res
print('spike V2 CLI T=3 witness c2.m,c0.m,c1.m @1 sig=0x00:', replay('v2_spike.json', 'v2', 3, [(1, 'c2.m'), (1, 'c0.m'), (1, 'c1.m')], 0x00))
print('  same, only 2 of the 3 flips (c2.m,c0.m):', replay('v2_spike.json', 'v2', 3, [(1, 'c2.m'), (1, 'c0.m')], 0x00))
print('spike V2 CLI T=4 witness c2.m,c0.m,$flatten\\c1.$abc$251$new_n16_ @1 sig=0x03:', replay('v2_spike.json', 'v2', 4, [(1, 'c2.m'), (1, 'c0.m'), (1, '$flatten\\c1.$abc$251$new_n16_')], 0x03))
print('apt0.33 V2 z3 (b3pack) witness new_n58_,new_n74_ both @0, any sig (sig=0x00):', replay('v2_apt033.json', 'v2', 4, [(0, '$abc$275$new_n58_'), (0, '$abc$275$new_n74_')], 0x00))
