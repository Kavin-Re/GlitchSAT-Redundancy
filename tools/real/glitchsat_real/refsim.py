"""Two independent bit-parallel simulators used to prove the Nangate45 adapter correct.

* RefSim evaluates the ORIGINAL Nangate45 netlist. Each combinational cell output is computed from the truth table
  implied by SYNFI's own CNF clauses for that cell (nangate.clause_function / clause_truth); nothing from the
  adapter's primitive trees is used. Flip-flops follow the Nangate45 Liberty behaviour: Q <= D at the clock edge,
  RN = 0 clears, SN = 0 sets (asynchronous; evaluated at the cycle boundary, see `reset_sync`), SE selects SI.
* PrimSim evaluates the ADAPTED primitive netlist through the GlitchSAT engine's own parser (glitchsat.Netlist):
  $_AND_/$_OR_/$_XOR_/$_NOT_/$_MUX_ in topological order, $_DFF_P_ with the engine's init values.

Values are Python ints used as W-lane bit vectors (lane i = one random test vector)."""
import itertools
import random

from . import nangate as ng


class RefSim:
    def __init__(self, doc, top, lib=None):
        self.lib = lib or ng.load_cell_lib()
        self.m = doc['modules'][top]
        self.top = top
        self.tables = {}
        self.comb, self.flops = [], []
        drv = {}
        for cn, c in self.m['cells'].items():
            t = c['type']
            if t in ng.NO_LOGIC:
                continue
            if t in ng.FLOP_PINS:
                self.flops.append((cn, c))
                for p in ('Q', 'QN'):
                    for b in c['connections'].get(p, []):
                        drv[b] = ('flop', cn)
                continue
            outs = [p for p, d in c['port_directions'].items() if d == 'output']
            for p in outs:
                conn = c['connections'].get(p) or []
                if conn and isinstance(conn[0], int):
                    key = (t, p)
                    if key not in self.tables:
                        self.tables[key] = self._table(t, p)
                    drv[conn[0]] = ('comb', cn, p)
        self.drv = drv
        self.order = self._topo()

    def _table(self, t, p):
        pins = ng.cell_input_pins(self.lib, t, p)
        clauses, var, out = ng.clause_function(self.lib, f'{t}_{p}', pins)
        ones = []
        for bits in itertools.product((0, 1), repeat=len(pins)):
            env = dict(zip(pins, bits))
            r = ng.clause_truth(clauses, var, out, env)
            if len(r) != 1:
                raise ng.AdapterError(f'SYNFI clauses of {t}.{p} are not functional at {env}: {r}')
            if r[0]:
                ones.append(bits)
        return pins, ones

    def _topo(self):
        order, state = [], {}
        cells = self.m['cells']
        for root in list(self.drv):
            if self.drv[root][0] != 'comb' or root in state:
                continue
            stack = [root]
            while stack:
                b = stack[-1]
                if state.get(b) == 2:
                    stack.pop(); continue
                d = self.drv[b]
                c = cells[d[1]]
                pins = self.tables[(c['type'], d[2])][0]
                pend = [c['connections'][q][0] for q in pins
                        if isinstance(c['connections'][q][0], int) and c['connections'][q][0] in self.drv
                        and self.drv[c['connections'][q][0]][0] == 'comb' and state.get(c['connections'][q][0]) != 2]
                if pend and state.get(b) != 1:
                    state[b] = 1
                    stack.extend(pend); continue
                if pend:
                    raise ng.AdapterError('combinational loop')
                state[b] = 2; order.append(b); stack.pop()
        return order

    def run(self, T, inputs_per_cycle, W, init, reset_sync=False):
        """inputs_per_cycle[t]: {net: int}. init: {flop cell: 0/1}. Returns list of {net: int} per cycle (all nets).
        Flop with reset pin at 0 during cycle t: its Q in cycle t+1 is the reset value (sampled at the edge)."""
        mask = (1 << W) - 1
        cells = self.m['cells']
        st = {cn: (mask if init.get(cn, 0) else 0) for cn, _ in self.flops}
        trace = []
        for t in range(T):
            v = dict(inputs_per_cycle[t])

            def g(b):
                if b == '0': return 0
                if b == '1': return mask
                return v[b]
            for cn, c in self.flops:
                for b in c['connections'].get('Q', []):
                    v[b] = st[cn]
                for b in c['connections'].get('QN', []):
                    v[b] = st[cn] ^ mask
            for b in self.order:
                _, cn, p = self.drv[b]
                c = cells[cn]
                pins, ones = self.tables[(c['type'], p)]
                ins = [g(c['connections'][q][0]) for q in pins]
                acc = 0
                for row in ones:
                    term = mask
                    for x, bit in zip(ins, row):
                        term &= x if bit else (x ^ mask)
                    acc |= term
                v[b] = acc
            trace.append(v)
            nst = {}
            for cn, c in self.flops:
                dp, rp, sp, scan = ng.FLOP_PINS[c['type']]
                d = g(c['connections'][dp][0])
                if scan:
                    se = g(c['connections'][scan[1]][0]); si = g(c['connections'][scan[0]][0])
                    d = (se & si) | ((se ^ mask) & d)
                if rp:
                    d &= g(c['connections'][rp][0])          # RN = 0 -> 0
                if sp:
                    d |= g(c['connections'][sp][0]) ^ mask   # SN = 0 -> 1 (Nangate DFFRS: both low -> see below)
                nst[cn] = d
            st = nst
        return trace


class PrimSim:
    def __init__(self, nl):
        """nl: glitchsat.Netlist of the adapted netlist."""
        self.nl = nl
        self.order = self._topo()

    def _topo(self):
        nl = self.nl
        order, state = [], {}
        for root in nl.drivers:
            if root in state:
                continue
            stack = [root]
            while stack:
                b = stack[-1]
                if state.get(b) == 2:
                    stack.pop(); continue
                pend = [f for f in nl.fanins(b) if f in nl.drivers and state.get(f) != 2]
                if pend:
                    state[b] = 1; stack.extend(pend); continue
                state[b] = 2; order.append(b); stack.pop()
        return order

    def run(self, T, inputs_per_cycle, W, init=None, flips=None):
        """flips: {(t, net): lane mask} XORed into the net value (bit-flip faults). init: {q net: 0/1} overrides."""
        nl = self.nl
        mask = (1 << W) - 1
        flips = flips or {}
        st = {q: (mask if (init or {}).get(q, nl.init[q]) else 0) for q in nl.qs}
        trace = []
        for t in range(T):
            v = dict(inputs_per_cycle[t])

            def g(b):
                if b == '0': return 0
                if b == '1': return mask
                return v[b]
            for q in nl.qs:
                v[q] = st[q] ^ flips.get((t, q), 0)
            for b in self.order:
                _, ty, con = nl.drivers[b]
                if ty == '$_AND_': r = g(con['A'][0]) & g(con['B'][0])
                elif ty == '$_OR_': r = g(con['A'][0]) | g(con['B'][0])
                elif ty == '$_XOR_': r = g(con['A'][0]) ^ g(con['B'][0])
                elif ty == '$_NOT_': r = g(con['A'][0]) ^ mask
                elif ty == '$_MUX_':
                    s = g(con['S'][0]); r = (s & g(con['B'][0])) | ((s ^ mask) & g(con['A'][0]))
                else:
                    raise ng.AdapterError(f'unexpected primitive {ty}')
                v[b] = r ^ flips.get((t, b), 0)
            trace.append(v)
            st = {q: g(d) for q, d in nl.dq.items()}
        return trace


def random_inputs(ports, T, W, rng, hold=None, skip=('clk_i',)):
    """Random W-lane values for every input port bit, per cycle; `hold`: {net: 0/1} held constant."""
    mask = (1 << W) - 1
    hold = hold or {}
    out = []
    for _ in range(T):
        v = {}
        for p, x in ports.items():
            if x['direction'] != 'input' or p in skip:
                continue
            for b in x['bits']:
                if isinstance(b, int):
                    v[b] = (mask if hold[b] else 0) if b in hold else rng.getrandbits(W)
        out.append(v)
    return out
