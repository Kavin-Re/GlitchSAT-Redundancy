#!/usr/bin/env python3
# Count distinct nets in a synthesised netlist whose function of one 8-bit source (sig, or flops s1 / s2)
# equals (src == 0xC3): "compare copies surviving synthesis". Also counts flops/gates. Exhaustive over 256 values.
import json, sys, glob
def analyse(path, top):
    m = json.load(open(path))['modules'][top]
    gates = {}; dffs = []
    for cn, c in m['cells'].items():
        t, con = c['type'], c['connections']
        if t == '$_DFF_P_': dffs.append(con['Q'][0])
        else: gates[con['Y'][0]] = (t, con)
    srcs = {}
    for n, x in m['netnames'].items():
        if n in ('sig', 's1', 's2') and len(x['bits']) == 8: srcs[n] = x['bits']
    res = {}
    for sn, bits in srcs.items():
        memo = {}
        def ev(b, vals):
            if b == '0': return 0
            if b == '1': return 1
            if b in vals: return vals[b]
            if b in cache: return cache[b]
            if b not in gates: return None   # other flop / input
            t, con = gates[b]; g = lambda p: ev(con[p][0], vals)
            a = [g(p) for p in (('A','B','S') if t=='$_MUX_' else ('A','B') if t!='$_NOT_' else ('A',))]
            if None in a: r = None
            elif t == '$_AND_': r = a[0] & a[1]
            elif t == '$_OR_': r = a[0] | a[1]
            elif t == '$_XOR_': r = a[0] ^ a[1]
            elif t == '$_NOT_': r = 1 - a[0]
            else: r = a[1] if a[2] else a[0]
            cache[b] = r; return r
        tts = {b: [] for b in gates}
        for v in range(256):
            vals = {bits[i]: (v >> i) & 1 for i in range(8)}
            cache = {}
            for b in gates: ev(b, vals)
            for b in gates:
                tts[b].append(cache.get(b))
        want = [1 if v == 0xC3 else 0 for v in range(256)]
        ismatch = {b for b in gates if tts[b] == want}
        roots = [b for b in ismatch if not any(x[0] in ismatch for x in gates[b][1].values() if isinstance(x, list) and False) and not any(f in ismatch for k2, v2 in gates[b][1].items() if k2 != 'Y' for f in v2)]
        res[sn] = (len(roots), len(ismatch))
    return dict(gates=len(gates), flops=len(dffs), compare_nets=res)
if __name__ == '__main__':
    for p in sorted(glob.glob('/tmp/work_v456/nl/*.json')):
        n = p.split('/')[-1][:-5]; top = n.split('_')[0]
        print(n, analyse(p, top))
