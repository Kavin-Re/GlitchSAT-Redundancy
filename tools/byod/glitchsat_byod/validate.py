"""Validation by simulation: the netlist that is analysed (synthesised design + generated monitor + reset handling)
against the RTL as written (user sources + generated wrapper, elaborated by Yosys without optimisation).

Both start at power-up, run the reset sequence, and get the same random values on the free inputs (attacker and
secret inputs; a secret, or an attacker input with `attacker_changes: once`, keeps one value per run). Unknown
power-up values are X (three-valued simulation). In every cycle, every design output, `bad` and `ok` are compared
wherever both sides are known. One difference stops the analysis (GS050)."""
import random

from . import monitor as MON
from . import sim as SIM
from .errors import GSError


def run(X, Rref, res, ports, cycles, runs=256, seed=1):
    """X: Composed (mode from_powerup). Rref: Imported reference wrapper. Returns stats dict; raises GSError(GS050)."""
    rng = random.Random(seed)
    W = runs
    mask = (1 << W) - 1
    cc, rc = X.circ, Rref.circ
    oc, orf = SIM.order(cc), SIM.order(rc)
    roles = res['roles']
    free_ports = [p for p, (d, w) in ports.items() if d == 'input' and roles.get(p) in ('attacker', 'secret')]
    const = {p: (roles[p] == 'secret' or res['changes'] == 'const') for p in free_ports}
    cvals = {(p, i): rng.getrandbits(W) for p in free_ports for i in range(ports[p][1])}
    # composed side: input nets by port
    cin = {}
    for b, (p, i) in cc.inputs.items():
        cin.setdefault(p, {})[i] = b
    rin = {}
    for b, (p, i) in rc.inputs.items():
        rin.setdefault(p, {})[i] = b
    for p in free_ports:
        if p not in rin:
            raise GSError('GS050', 'internal: input `%s` missing in the reference wrapper' % p)
    # compared signals: (label, composed bit, reference bit)
    pairs = []
    for p, (d, w) in ports.items():
        if d != 'output':
            continue
        cb = X.out_bits[p]
        rb = Rref.port_bits.get(MON.OUT + p)
        for i in range(w):
            pairs.append(('%s[%d]' % (p, i) if w > 1 else p, cb[i], rb[i]))
    pairs.append(('bad', X.bad, Rref.port_bits[MON.BAD][0]))
    pairs.append(('ok', X.ok, Rref.port_bits[MON.OK][0]))

    def st0(c, R, composed):
        s = {}
        for q, (d, i) in c.flops.items():
            if composed:
                s[q] = (mask if i else 0, mask)
            else:
                iv = R.flop_init.get(q)
                if iv is None:
                    iv = None if res['powerup'] == 'any' else False
                s[q] = (0, 0) if iv is None else (mask if iv else 0, mask)
        return s
    sc, sr = st0(cc, X, True), st0(rc, Rref, False)
    compared = unknown = 0
    first = None
    for t in range(cycles):
        ic, ir = {}, {}
        for p in free_ports:
            for i in range(ports[p][1]):
                v = cvals[(p, i)] if const[p] else rng.getrandbits(W)
                if i in cin.get(p, {}):
                    ic[cin[p][i]] = (v, mask)
                if i in rin.get(p, {}):
                    ir[rin[p][i]] = (v, mask)
        bbv = {}
        for b, (p, i) in cc.inputs.items():
            if b in ic:
                continue
            md = X.in_mode.get(b)
            if md in (0, 1):
                ic[b] = (mask if md else 0, mask)
            elif b in X.free_init:
                ic[b] = (0, 0)                          # unknown power-up value
            else:
                ic[b] = (rng.getrandbits(W), mask)      # black-box outputs: free, the same values on both sides
                bbv[(MON.DUT + '.' + p, i)] = ic[b]
        for b, (p, i) in rc.inputs.items():
            if b not in ir:
                ir[b] = bbv.get((p, i), (0, 0))
        vc, sc = SIM.step3w(cc, oc, sc, ic, mask)
        vr, sr = SIM.step3w(rc, orf, sr, ir, mask)

        def val(v, b):
            if b == '0': return (0, mask)
            if b == '1': return (mask, mask)
            return v.get(b, (0, 0))
        for lab, cb, rb in pairs:
            (a, ka), (r, kr) = val(vc, cb), val(vr, rb)
            both = ka & kr
            compared += bin(both).count('1')
            unknown += W - bin(both).count('1')
            diff = (a ^ r) & both
            if diff and first is None:
                run_i = (diff & -diff).bit_length() - 1
                first = dict(cycle=t, signal=lab, run=run_i, analysed=(a >> run_i) & 1, rtl=(r >> run_i) & 1)
    st = dict(runs=W, cycles=cycles, compared_values=compared, unknown_values=unknown,
              share_compared=round(compared / max(1, compared + unknown), 4), mismatch=first)
    if first:
        raise GSError('GS050', 'the analysed netlist differs from the RTL: `%s` in cycle %d is %d, the RTL gives %d'
                      % (first['signal'], first['cycle'], first['analysed'], first['rtl']),
                      note='random run %d of %d; cycle 0 is power-up, the reset sequence comes first' % (first['run'], W),
                      help='if a probe reads a state register, the flow may have re-encoded it: try flow synth-nofsm or '
                           'plain, or use an output; if registers have no reset, set `powerup: any`')
    return st
