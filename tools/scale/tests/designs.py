"""Small hand-built designs for the tests (gscale Circuit objects, no netlist file needed)."""
from gscale.circuit import Circuit, Problem, AND, OR, XOR, NOT, MUX


class B:
    def __init__(self):
        self.c = Circuit(); self.n = 1

    def net(self, name=None):
        self.n += 1
        if name: self.c.names[self.n] = name
        return self.n

    def inp(self, port, w):
        bits = [self.net('%s[%d]' % (port, i)) for i in range(w)]
        for i, b in enumerate(bits): self.c.inputs[b] = (port, i)
        self.c.ports[port] = ('input', bits)
        return bits

    def g(self, op, *fi, name=None):
        y = self.net(name); self.c.gates[y] = (op, tuple(fi)); self.c.cell[y] = name or 'g%d' % y
        return y

    def ff(self, d, init=False, name=None):
        q = self.net(name); self.c.flops[q] = (d, init); self.c.cell[q] = name or 'ff%d' % q
        return q


def tmr(w=3, voter_sites=False, key=None):
    """Three copies of "x == all ones" behind input and output registers, majority voter
    OR(OR(AND(a,b), AND(a,c)), AND(b,c)). Swapping copies b and c maps the design onto itself.
    Goal: voter output 1 with input != all ones. Without voter fault sites the minimum is 2."""
    b = B(); sig = b.inp('sig', w)
    ys = []; mods = []
    for cp in 'abc':
        nets = set()
        x = [b.ff(s, name='%s.x%d' % (cp, i)) for i, s in enumerate(sig)]
        r = x[0]
        for i in range(1, w):
            r = b.g(AND, r, x[i], name='%s.and%d' % (cp, i)); nets.add(r)
        if w == 1:
            r = b.g(AND, r, '1', name='%s.and0' % cp); nets.add(r)
        ys.append(b.ff(r, name='%s.y' % cp)); mods.append((cp, nets))
    a, bb, cc = ys
    v1 = b.g(AND, a, bb, name='v.ab'); v2 = b.g(AND, a, cc, name='v.ac'); v3 = b.g(AND, bb, cc, name='v.bc')
    o = b.g(OR, b.g(OR, v1, v2, name='v.o1'), v3, name='v.out')
    b.c.ports['ok'] = ('output', [o])
    sites = set(b.c.gates) | set(b.c.flops)
    if not voter_sites:
        sites -= {v1, v2, v3, o, b.c.gates[o][1][0]}
    P = Problem(b.c, 4, [(o, True)], neq=(sig, (1 << w) - 1 if key is None else key), sites=sites, label='tmr')
    return P, mods


def xor_cancel():
    """a feeds x1 = a^p and x2 = a^q, y = x1^x2 = p^q. Only a, p, q are fault sites (x1, x2, y are not), so no site
    post-dominates a; flipping a never changes y. Goal y == 1 with p, q registered from equal inputs."""
    b = B(); s = b.inp('sig', 2)
    p = b.ff(s[0], name='p'); q = b.ff(s[0], name='q'); a = b.ff(s[1], name='a')
    x1 = b.g(XOR, a, p, name='x1'); x2 = b.g(XOR, a, q, name='x2'); y = b.g(XOR, x1, x2, name='y')
    yr = b.ff(y, name='yr')
    b.c.ports['o'] = ('output', [yr])
    return Problem(b.c, 3, [(yr, True)], sites={p, q, a}, label='xor_cancel'), a


def twin_sites():
    """a and b feed a non-site XOR whose output drives two observed registers: no site post-dominates a or b, and
    flipping a always has exactly the effect of flipping b."""
    b = B(); s = b.inp('sig', 2)
    a = b.ff(s[0], name='a'); bb = b.ff(s[1], name='b')
    x = b.g(XOR, a, bb, name='x')
    o1 = b.ff(x, name='o1'); o2 = b.ff(b.g(NOT, x, name='nx'), name='o2')
    b.c.ports['o'] = ('output', [o1, o2])
    return Problem(b.c, 3, [(o1, True), (o2, True)], sites={a, bb}, label='twin'), (a, bb)


def wide_error():
    """Module M with outputs y0 = a&c and y1 = a|c, inputs tied to a=1, c=0 and register a starting at 1 (so y0=0, y1=1 in every cycle). Goal: the registered
    outputs show y0=1, y1=0, which needs BOTH outputs wrong: two flips. The abstraction first prices a broken
    module at one flip, so the composed analysis has to refine."""
    b = B(); s = b.inp('sig', 2)
    a = b.ff(s[0], init=True, name='a'); c_ = b.ff(s[1], name='c')
    m0 = b.g(AND, a, c_, name='M.y0'); m1 = b.g(OR, a, c_, name='M.y1')
    r0 = b.ff(m0, name='r0'); r1 = b.ff(m1, name='r1')
    b.c.ports['o'] = ('output', [r0, r1])
    P = Problem(b.c, 3, [(r0, True), (r1, False)], in_mode={s[0]: 1, s[1]: 0}, sites={m0, m1}, label='wide')
    return P, [('M', {m0, m1})]
