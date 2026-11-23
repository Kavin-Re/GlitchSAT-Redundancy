"""Gate-level replay of the model vectors on a synthesised netlist (Yosys JSON written by scripts/synth.sh).

Cell set: $_AND_ $_OR_ $_XOR_ $_NOT_ $_MUX_ and $_DFF_P_ (the set scripts/glitchsat.py accepts). Anything else is
an error. Flops start at their `init` attribute (0 when absent, as scripts/glitchsat.py does). Each cycle: outputs
are evaluated from the current flop values and the input, then every flop takes its D value (one rising edge).

Fault scenarios of the vector file are replayed too when every flipped register is found in the netlist by name
(e.g. `u_core.st`, `u_core.g_flag[0].q`); otherwise those scenarios are skipped and counted. This checks that the
synthesised netlist, its power-up values and its register bits behave like the Python model (and the RTL).

Usage: python3 -m engine.netsim NETLIST.json TOP vectors/<name>.vec  [--goal boot_word]
"""
import argparse, json, sys

GATES = {'$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'}


class NetsimError(Exception):
    pass


class GateNetlist:
    def __init__(self, path, top):
        with open(path) as fh:
            doc = json.load(fh)
        if top not in doc.get('modules', {}):
            raise NetsimError(f'no module {top} in {path}')
        m = doc['modules'][top]
        self.ports = m['ports']
        self.gates = []          # (type, out, ins)
        self.dffs = []           # (d, q)
        drv = {}
        for cn, c in m['cells'].items():
            t, con = c['type'], c['connections']
            if t == '$_DFF_P_':
                self.dffs.append((con['D'][0], con['Q'][0]))
            elif t in GATES:
                pins = {'$_NOT_': ('A',), '$_MUX_': ('A', 'B', 'S')}.get(t, ('A', 'B'))
                g = (t, con['Y'][0], tuple(con[p][0] for p in pins))
                drv[con['Y'][0]] = g
            elif t == '$scopeinfo':
                continue
            else:
                raise NetsimError(f'unsupported cell {cn} of type {t}')
        self.n_gates = len(drv)
        qs = {q for _, q in self.dffs}
        inputs = {b for p in self.ports.values() if p['direction'] == 'input' for b in p['bits'] if isinstance(b, int)}
        # topological order of the gates
        order, mark = [], {}
        for root in drv:
            if root in mark:
                continue
            mark[root] = 1
            stack = [(root, iter(drv[root][2]))]
            while stack:
                b, it = stack[-1]
                for f in it:
                    if isinstance(f, int) and f in drv:
                        if mark.get(f) == 1:
                            raise NetsimError(f'combinational loop at net {f}')
                        if f not in mark:
                            mark[f] = 1
                            stack.append((f, iter(drv[f][2])))
                            break
                else:
                    mark[b] = 2
                    order.append(drv[b])
                    stack.pop()
        self.order = order
        for t, y, ins in order:
            for f in ins:
                if isinstance(f, int) and f not in drv and f not in qs and f not in inputs:
                    raise NetsimError(f'net {f} is read but not driven')
        self.init = {q: 0 for q in qs}
        self.names = {}
        for n, x in m['netnames'].items():
            self.names[n] = x['bits']
            iv = x['attributes'].get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)):
                    b = x['bits'][i]
                    if b in self.init:
                        if ch not in '01':
                            raise NetsimError(f'flop net {n} has unknown init {iv}')
                        self.init[b] = int(ch)

    def reg_bits(self, name):
        """Flop Q nets of a register, LSB first, or None when not all bits are flop outputs."""
        bits = self.names.get(name)
        if not bits or not all(b in self.init for b in bits):
            return None
        return bits

    def run(self, inputs, n, flips=None):
        """inputs: {port: int} held constant; flips: {cycle: [net, ...]} (Q nets to invert in that cycle).
        Returns a list of {output port: value} per cycle."""
        st = dict(self.init)
        out = []
        for t in range(n):
            v = dict(st)
            for net in (flips or {}).get(t, ()):
                v[net] ^= 1
            for p, x in self.ports.items():
                if x['direction'] == 'input':
                    val = inputs.get(p, 0)
                    for i, b in enumerate(x['bits']):
                        v[b] = (val >> i) & 1

            def g(b):
                return 0 if b == '0' else 1 if b == '1' else v[b]
            for typ, y, ins in self.order:
                if typ == '$_AND_':
                    v[y] = g(ins[0]) & g(ins[1])
                elif typ == '$_OR_':
                    v[y] = g(ins[0]) | g(ins[1])
                elif typ == '$_XOR_':
                    v[y] = g(ins[0]) ^ g(ins[1])
                elif typ == '$_NOT_':
                    v[y] = 1 - g(ins[0])
                else:
                    v[y] = g(ins[1]) if g(ins[2]) else g(ins[0])
            o = {}
            for p, x in self.ports.items():
                if x['direction'] == 'output':
                    o[p] = sum(g(b) << i for i, b in enumerate(x['bits']))
            out.append(o)
            st = {q: g(d) for d, q in self.dffs}
        return out


def read_vectors(path):
    """Scenarios from a vector file: list of (sig, [(cycle, [(reg_id, mask), ...]) ...], [goal per cycle])."""
    sc = []
    with open(path) as fh:
        for line in fh:
            f = [int(x, 16) for x in line.split()]
            if not f:
                continue
            if f[0] == 1:
                sc.append(dict(sig=None, flips={}, goal=[]))
                continue
            s = sc[-1]
            s['sig'] = f[1]
            t = len(s['goal'])
            fl = [(f[2 + 2 * i], f[3 + 2 * i]) for i in range(4) if f[2 + 2 * i]]
            if fl:
                s['flips'][t] = fl
            s['goal'].append(f[10])
    return sc


def replay(netlist, top, vec, goal, reg_names):
    """reg_names: list of RTL register paths below the top, indexed by vector flip id - 1."""
    nl = GateNetlist(netlist, top)
    bits = [nl.reg_bits(n) for n in reg_names]
    res = dict(gates=nl.n_gates, flops=len(nl.dffs), scenarios=0, fault_scenarios_skipped=0, mismatches=[])
    for i, s in enumerate(read_vectors(vec)):
        flips = {}
        ok = True
        for t, fl in s['flips'].items():
            for rid, mask in fl:
                b = bits[rid - 1]
                if b is None:
                    ok = False
                    break
                flips.setdefault(t, []).extend(b[j] for j in range(len(b)) if mask >> j & 1)
        if not ok:
            res['fault_scenarios_skipped'] += 1
            continue
        tr = nl.run({'sig': s['sig']}, len(s['goal']), flips)
        res['scenarios'] += 1
        for t, (o, want) in enumerate(zip(tr, s['goal'])):
            if o[goal] != want:
                res['mismatches'].append(dict(scenario=i, cycle=t, got=o[goal], want=want))
                break
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('netlist'); ap.add_argument('top'); ap.add_argument('vec')
    ap.add_argument('--goal', default='boot_word')
    ap.add_argument('--regs', default='', help='comma-separated register net names in flip-id order')
    a = ap.parse_args()
    r = replay(a.netlist, a.top, a.vec, a.goal, [x for x in a.regs.split(',') if x])
    print(json.dumps(r))
    sys.exit(1 if r['mismatches'] else 0)


if __name__ == '__main__':
    main()
