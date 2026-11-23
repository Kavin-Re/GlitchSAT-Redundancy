#!/usr/bin/env python3
"""Generate S-box benchmark netlists (Yosys JSON form) WITHOUT Yosys.

These are PROXIES for the R20 designs (research/c3/r20/designs/wrappers/w_sbox_*.v): the same wrapper structure
(input registers, one or two S-box lookups, output register, parity or full compare, goal port `gout`/`y`), but the
S-box logic is produced here as one multiplexer tree per output bit (no sharing between output bits or copies), not by
Yosys+ABC from secworks aes_sbox.v. Gate counts are close to R20's (1012 gates per lookup there) but the netlists are
NOT the R20 netlists, so results on them are results on the proxies only.

usage: gen_sbox_proxy.py OUTDIR      writes sbox_{unprot,par,par2,dmr,tmr,tmr2}_proxy.json (mux trees) and
                                     sbox_{unprot,par,par2,dmr,tmr,tmr2}s_proxy.json (shared muxes, fan-out > 1)
"""
import json, os, sys


def aes_sbox():
    """AES S-box from its definition (inverse in GF(2^8) mod x^8+x^4+x^3+x+1, then the affine map)."""
    def mul(a, b):
        r = 0
        while b:
            if b & 1: r ^= a
            a <<= 1
            if a & 0x100: a ^= 0x11B
            b >>= 1
        return r
    inv = [0] * 256
    for a in range(1, 256):
        for b in range(1, 256):
            if mul(a, b) == 1:
                inv[a] = b; break
    box = []
    for a in range(256):
        x = inv[a]; y = 0
        for i in range(8):
            bit = ((x >> i) ^ (x >> ((i + 4) % 8)) ^ (x >> ((i + 5) % 8)) ^ (x >> ((i + 6) % 8)) ^ (x >> ((i + 7) % 8)) ^ (0x63 >> i)) & 1
            y |= bit << i
        box.append(y)
    assert box[0] == 0x63 and box[1] == 0x7C and box[0x53] == 0xED
    return box


class B:
    def __init__(self, top):
        self.top = top; self.n = 1; self.cells = {}; self.names = {}; self.ports = {}; self.k = 0

    def net(self):
        self.n += 1
        return self.n

    def gate(self, ty, tag, **pins):
        y = self.net(); self.k += 1
        con = {p: [v] for p, v in pins.items()}; con['Y'] = [y]
        self.cells[f'{tag}${self.k}'] = {'type': ty, 'connections': con}
        self.names[f'{tag}.n{y}'] = {'bits': [y], 'attributes': {}}
        return y

    def reg(self, name, width):
        q = [self.net() for _ in range(width)]
        self.names[name] = {'bits': q, 'attributes': {}}
        return q

    def connect(self, name, q, d):
        for i, (qq, dd) in enumerate(zip(q, d)):
            self.cells[f'{name}_ff{i}'] = {'type': '$_DFF_P_', 'connections': {'D': [dd], 'Q': [qq]}}

    def port(self, name, direction, bits):
        self.ports[name] = {'direction': direction, 'bits': bits}
        self.names.setdefault(name, {'bits': bits, 'attributes': {}})

    def sbox(self, tag, x, box, shared=False):
        """8 output nets; a mux tree per output bit over x[0] (leaves) .. x[7] (root). Constant-fed muxes are kept as
        MUX cells with '0'/'1' pins (the engine supports constant pins).
        shared=False: every mux is its own cell (pure trees, fan-out 1 inside the S-box).
        shared=True: identical muxes (same A, B, S) inside this copy are one cell (a shared decision diagram; many nets
        have fan-out > 1, as in an optimised netlist). Copies never share cells with each other."""
        nx0 = self.gate('$_NOT_', tag, A=x[0])
        memo = {}

        def mux(a, b_, s):
            if not shared:
                return self.gate('$_MUX_', tag, A=a, B=b_, S=s)
            if (a, b_, s) not in memo:
                memo[(a, b_, s)] = self.gate('$_MUX_', tag, A=a, B=b_, S=s)
            return memo[(a, b_, s)]
        out = []
        for j in range(8):
            lvl = []
            for i in range(0, 256, 2):
                a, b = (box[i] >> j) & 1, (box[i + 1] >> j) & 1
                lvl.append('0' if (a, b) == (0, 0) else '1' if (a, b) == (1, 1) else x[0] if (a, b) == (0, 1) else nx0)
            for d in range(1, 8):
                lvl = [lvl[i] if lvl[i] == lvl[i + 1] else mux(lvl[i], lvl[i + 1], x[d])
                       for i in range(0, len(lvl), 2)]
            out.append(lvl[0])
        return out

    def neq(self, tag, a, b):
        xs = [self.gate('$_XOR_', tag, A=p, B=q) for p, q in zip(a, b)]
        r = xs[0]
        for x in xs[1:]:
            r = self.gate('$_OR_', tag, A=r, B=x)
        return r

    def xor_reduce(self, tag, a):
        r = a[0]
        for x in a[1:]:
            r = self.gate('$_XOR_', tag, A=r, B=x)
        return r

    def doc(self):
        return {'creator': 'gen_sbox_proxy.py (proxy netlist, not Yosys output)',
                'modules': {self.top: {'ports': self.ports, 'cells': self.cells, 'netnames': self.names}}}


def build(kind, box, shared=False):
    b = B(f'sbox_{kind}{"s" if shared else ""}_proxy')
    _sb = b.sbox
    b.sbox = lambda tag, x, bx: _sb(tag, x, bx, shared)
    clk = b.net(); b.port('clk', 'input', [clk])
    sig = [b.net() for _ in range(8)]; b.port('sig', 'input', sig)
    x = b.reg('x', 8); b.connect('x', x, sig)
    yr = b.reg('yr', 8)
    a = b.sbox('A', x, box); b.connect('yr', yr, a)
    if kind == 'unprot':
        b.port('y', 'output', yr)
    elif kind in ('par', 'par2'):
        x2 = x if kind == 'par' else b.reg('x2', 8)
        if kind == 'par2': b.connect('x2', x2, sig)
        bb = b.sbox('B', x2, box)
        p = b.reg('p', 1); b.connect('p', p, [b.xor_reduce('pb', bb)])
        alarm = b.gate('$_XOR_', 'chk', A=b.xor_reduce('py', yr), B=p[0])
        b.port('gout', 'output', yr + [b.gate('$_NOT_', 'chk', A=alarm)])
    elif kind == 'dmr':
        x2 = b.reg('x2', 8); b.connect('x2', x2, sig)
        y2 = b.reg('y2', 8); b.connect('y2', y2, b.sbox('B', x2, box))
        alarm = b.neq('chk', yr, y2)
        b.port('gout', 'output', yr + [b.gate('$_NOT_', 'chk', A=alarm)])
    elif kind in ('tmr', 'tmr2'):            # three lookups; tmr: ONE alarm bit (any pair differs); tmr2: TWO alarm bits
        x2 = b.reg('x2', 8); b.connect('x2', x2, sig)
        x3 = b.reg('x3', 8); b.connect('x3', x3, sig)
        y2 = b.reg('y2', 8); b.connect('y2', y2, b.sbox('B', x2, box))
        y3 = b.reg('y3', 8); b.connect('y3', y3, b.sbox('C', x3, box))
        if kind == 'tmr':
            alarm = b.gate('$_OR_', 'chk', A=b.neq('chk12', yr, y2), B=b.neq('chk13', yr, y3))
            b.port('gout', 'output', yr + [b.gate('$_NOT_', 'chk', A=alarm)])
        else:                                # gout = {~alarm13, ~alarm12, y}: the two compares stay separate output bits
            b.port('gout', 'output', yr + [b.gate('$_NOT_', 'chk12', A=b.neq('chk12', yr, y2)),
                                           b.gate('$_NOT_', 'chk13', A=b.neq('chk13', yr, y3))])
    return b


# goal / key as in R20: key 0x01, S(1) = 0x7C; `gout` = {~alarm, y} so the accept word is 0x17C
PARAMS = {'unprot': dict(goal_out='y', goal_value=0x7C, key=1, cycles=4),
          'par': dict(goal_out='gout', goal_value=0x17C, key=1, cycles=4),
          'par2': dict(goal_out='gout', goal_value=0x17C, key=1, cycles=4),
          'dmr': dict(goal_out='gout', goal_value=0x17C, key=1, cycles=4),
          'tmr': dict(goal_out='gout', goal_value=0x17C, key=1, cycles=4),
          'tmr2': dict(goal_out='gout', goal_value=0x37C, key=1, cycles=4)}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    box = aes_sbox()
    for shared in (False, True):
        for kind in PARAMS:
            b = build(kind, box, shared)
            p = os.path.join(out, f'{b.top}.json')
            with open(p, 'w') as f:
                json.dump(b.doc(), f)
            ng = sum(1 for c in b.cells.values() if c['type'] != '$_DFF_P_')
            print(f'{p}: {ng} gates, {len(b.cells) - ng} flops')


if __name__ == '__main__':
    main()
