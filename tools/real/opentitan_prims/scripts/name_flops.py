#!/usr/bin/env python3
"""Give the flip-flops of an async2sync netlist the register names again (a view for the survival checker).

`async2sync` turns each asynchronous-reset flop into a plain flop whose Q net gets a new internal name
($auto$async2sync...); the register's own name moves to the reset gate after it (q AND rst_ni, or
q OR NOT rst_ni after mapping). The survival checker finds registers by the names of flop Q nets, so it
would not find them. This script copies every public name of such a reset gate onto the Q net of its
flop. Only net names change; cells and connections are not touched (tests/test_pipeline.py checks
that the cell lists of input and output are identical).

A net counts as the reset-gated copy of flop F when its cone (at most 6 gates deep) reads nothing but
F's Q and the wrapper reset register `rst_q`, and it equals Q whenever rst_q is 1 (checked on the
cone's truth table).

usage: name_flops.py IN.json TOP OUT.json
"""
import json
import sys


def reset_aliases(m):
    """{net bit: flop Q bit} for every net that is the reset-gated copy of one flop (see module doc)."""
    driver = {}
    for name, c in m['cells'].items():
        for p, bits in c['connections'].items():
            if c['port_directions'][p] == 'output':
                for b in bits:
                    driver[b] = c
    rst = m['netnames']['rst_q']['bits'][0]

    flop_q = {c['connections']['Q'][0] for c in m['cells'].values() if c['type'] == '$_DFF_P_'}
    ops = {'$_AND_': lambda a, b: a & b, '$_OR_': lambda a, b: a | b, '$_XOR_': lambda a, b: a ^ b}

    def leaves(b, depth=0):
        if b in flop_q or b == rst:
            return {b}
        c = driver.get(b)
        if c is None or depth > 6 or not isinstance(b, int):
            return None
        out = set()
        for p in sorted(c['connections']):
            if c['port_directions'][p] != 'input':
                continue
            for x in c['connections'][p]:
                if not isinstance(x, int):
                    continue
                sub = leaves(x, depth + 1)
                if sub is None:
                    return None
                out |= sub
        return out

    def ev(b, val):
        if b in val:
            return val[b]
        if isinstance(b, str):
            return int(b == '1')
        c = driver[b]
        con = c['connections']
        t = c['type']
        if t == '$_NOT_':
            return 1 - ev(con['A'][0], val)
        if t == '$_MUX_':
            return ev(con['B'][0], val) if ev(con['S'][0], val) else ev(con['A'][0], val)
        return ops[t](ev(con['A'][0], val), ev(con['B'][0], val))

    alias = {}   # net bit -> flop Q bit
    for b in list(driver):
        if b in flop_q or not isinstance(b, int):
            continue
        lv = leaves(b)
        if not lv:
            continue
        qs = lv - {rst}
        if len(qs) != 1:
            continue
        q = next(iter(qs))
        if ev(b, {q: 0, rst: 1}) == 0 and ev(b, {q: 1, rst: 1}) == 1:
            alias[b] = q
    return alias


def register_flops(m, name):
    """Q bits of the flops behind the register net `name` (LSB first), or None."""
    alias = reset_aliases(m)
    bits = m['netnames'][name]['bits']
    if not all(isinstance(b, int) and b in alias for b in bits):
        return None
    return [alias[b] for b in bits]


def main(argv):
    src, top, dst = argv[1], argv[2], argv[3]
    doc = json.load(open(src))
    m = doc['modules'][top]
    alias = reset_aliases(m)
    added = 0
    new = {}
    for name, n in m['netnames'].items():
        if name.startswith('$') or not any(isinstance(b, int) and b in alias for b in n['bits']):
            continue
        if not all(isinstance(b, int) and b in alias for b in n['bits']):
            continue
        new['%s' % name] = dict(n, bits=[alias[b] for b in n['bits']], hide_name=0)
        added += 1
    # the gate outputs keep their names under a suffix, so each name stays unique
    for name, n in new.items():
        m['netnames'][name + '__rst_gated'] = m['netnames'][name]
        m['netnames'][name] = n
    json.dump(doc, open(dst, 'w'))
    print('%s: %d register names moved onto flop Q nets (%d reset-gated nets found)' % (dst, added, len(alias)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
