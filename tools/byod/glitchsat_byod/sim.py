"""Bit-parallel cycle simulation of a primitive Circuit (W independent runs packed into Python integers), and a
three-valued (0/1/X) variant used to compute the state after reset when the power-up state is unknown.
Written independently of the solver encodings; used to validate generated wrappers and mapped netlists."""
import random


def order(c):
    return c.topo(list(c.gates))


def step(c, ordr, state, inw, mask, faults=None):
    """One cycle: state {q: word}, inw {input net: word}. Returns (values, next_state). faults: {net: word} XORed."""
    v = {}
    faults = faults or {}

    def g(b):
        if b == '0': return 0
        if b == '1': return mask
        r = v.get(b)
        if r is None:
            r = inw.get(b, 0)
        return r
    for q in c.flops:
        v[q] = state[q] ^ faults.get(q, 0)
    for b in ordr:
        op, fi = c.gates[b]
        if op == 'AND': r = g(fi[0]) & g(fi[1])
        elif op == 'OR': r = g(fi[0]) | g(fi[1])
        elif op == 'XOR': r = g(fi[0]) ^ g(fi[1])
        elif op == 'NOT': r = g(fi[0]) ^ mask
        else:
            s = g(fi[0]); r = (s & g(fi[1])) | ((s ^ mask) & g(fi[2]))
        f = faults.get(b)
        v[b] = r ^ f if f else r
    for b, w in inw.items():
        v.setdefault(b, w)
    nxt = {q: g(d) for q, (d, _) in c.flops.items()}
    return v, nxt


def run(c, N, W, inputs_at, init=None, watch=None, ordr=None):
    """inputs_at(t) -> {input net: word}. init: {q: word} (default: the circuit's init bits). Returns [ {net: word} ]."""
    mask = (1 << W) - 1
    ordr = ordr or order(c)
    state = {q: (mask if i else 0) for q, (d, i) in c.flops.items()}
    if init:
        state.update(init)
    out = []
    for t in range(N):
        v, state = step(c, ordr, state, inputs_at(t), mask)
        out.append({b: v.get(b, 0) if b not in ('0', '1') else (mask if b == '1' else 0) for b in (watch or v)})
    return out


def rand_word(rng, W):
    return rng.getrandbits(W)


# ------------------------------------------------------------------ three-valued (scalar) simulation

def step3(c, ordr, state, inv):
    """0/1/None(X) values. state {q: v}, inv {input net: v}."""
    v = {}

    def g(b):
        if b == '0': return 0
        if b == '1': return 1
        if b in v: return v[b]
        return inv.get(b)
    for q in c.flops:
        v[q] = state[q]
    for b in ordr:
        op, fi = c.gates[b]
        x = [g(f) for f in fi]
        if op == 'AND':
            r = 0 if 0 in x else (None if None in x else 1)
        elif op == 'OR':
            r = 1 if 1 in x else (None if None in x else 0)
        elif op == 'XOR':
            r = None if None in x else x[0] ^ x[1]
        elif op == 'NOT':
            r = None if x[0] is None else 1 - x[0]
        else:
            s, t, e = x
            r = t if s == 1 else e if s == 0 else (t if t == e and t is not None else None)
        v[b] = r
    nxt = {q: g(d) for q, (d, _) in c.flops.items()}
    return v, nxt


# ------------------------------------------------------------------ three-valued, bit-parallel (dual rail)
# A value is (v, k): k = known mask, v = value bits (meaningful where k is 1).

def step3w(c, ordr, state, inw, mask):
    v = {}
    Z = (0, mask)
    O = (mask, mask)

    def g(b):
        if b == '0': return Z
        if b == '1': return O
        r = v.get(b)
        if r is None:
            r = inw.get(b, (0, 0))
        return r
    for q in c.flops:
        v[q] = state[q]
    for b in ordr:
        op, fi = c.gates[b]
        if op == 'AND':
            (av, ak), (bv, bk) = g(fi[0]), g(fi[1])
            z = (ak & ~av) | (bk & ~bv)
            k = ((ak & bk) | z) & mask
            r = (av & bv & k & ~z, k)
        elif op == 'OR':
            (av, ak), (bv, bk) = g(fi[0]), g(fi[1])
            o = (ak & av) | (bk & bv)
            k = ((ak & bk) | o) & mask
            r = ((o | (av | bv)) & k, k)
        elif op == 'XOR':
            (av, ak), (bv, bk) = g(fi[0]), g(fi[1])
            k = ak & bk
            r = ((av ^ bv) & k, k)
        elif op == 'NOT':
            av, ak = g(fi[0])
            r = ((~av) & ak & mask, ak)
        else:
            (sv, sk), (tv, tk), (ev, ek) = g(fi[0]), g(fi[1]), g(fi[2])
            s1 = sk & sv; s0 = sk & ~sv & mask
            same = tk & ek & ~(tv ^ ev)
            k = (s1 & tk) | (s0 & ek) | (~sk & same & mask)
            val = (s1 & tv) | (s0 & ev) | (~sk & same & tv)
            r = (val & k & mask, k & mask)
        v[b] = r
    for b, w in inw.items():
        v.setdefault(b, w)
    nxt = {q: g(d) for q, (d, _) in c.flops.items()}
    return v, nxt
