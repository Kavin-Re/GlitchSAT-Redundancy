"""GlitchSAT ext/masking (Labs, EXPERIMENTAL): exact first-order probing check of a small gate-level netlist.

Question it tries to answer: "can an attacker who measures ONE wire (or, with glitches, everything that
wire's logic cone sees) learn anything about a secret?"

Method (exhaustive, exact for the model):
  * The netlist is a Yosys JSON file with single-bit cells ($_AND_ $_OR_ $_XOR_ $_NOT_ $_MUX_ ... and
    $_DFF_P_), produced by scripts/build.py.
  * Every input bit gets a label in the format of the GlitchSAT project file (ext/byod docs/SCHEMA.md,
    checks[].labels): `secret N` (one share of secret bit N), `static_random` / `volatile_random` (uniform
    random bit), `unimportant`, or (added here) `fixed 0` / `fixed 1` (control inputs held constant).
  * Every wire is computed as a truth table over ALL share and random bits (numpy, 2^n rows; n <= 20).
    Flip-flops are evaluated as "D settled" (inputs held stable long enough, enable active): Q = D.
  * Probe sites: every input bit and every cell output. A probe set of size `order` is SECURE when the
    joint distribution of what it observes is the same for every value of the secrets (counted exactly).
  * Models: `standard` (a probe sees the value of its wire) and `glitch` (a probe sees every input bit
    and flip-flop output in the wire's combinational cone - the usual glitch-extended probing model).

Not modelled (README): transition leakage, couplings, more than one cycle of history, order > 1 is
implemented but not validated. Results are SIMULATED (exact counting on a model), not measured on silicon.
"""
import itertools
import json

import numpy as np

COMB = {
    '$_AND_': lambda a: a['A'] & a['B'], '$_OR_': lambda a: a['A'] | a['B'], '$_XOR_': lambda a: a['A'] ^ a['B'],
    '$_NAND_': lambda a: ~(a['A'] & a['B']), '$_NOR_': lambda a: ~(a['A'] | a['B']), '$_XNOR_': lambda a: ~(a['A'] ^ a['B']),
    '$_ANDNOT_': lambda a: a['A'] & ~a['B'], '$_ORNOT_': lambda a: a['A'] | ~a['B'], '$_NOT_': lambda a: ~a['A'],
    '$_BUF_': lambda a: a['A'], '$_MUX_': lambda a: np.where(a['S'], a['B'], a['A']),
}
FLOPS = {'$_DFF_P_', '$_DFF_N_'}
MAX_VARS = 20


class NetlistError(Exception):
    pass


def load(path, top):
    d = json.load(open(path))
    if top not in d['modules']:
        raise NetlistError('module %s not in %s' % (top, path))
    return d['modules'][top]


def parse_label(s):
    s = s.strip()
    if s.startswith('secret'):
        return ('secret', int(s.split()[1]))
    if s in ('static_random', 'volatile_random'):
        return ('random', None)
    if s == 'unimportant':
        return ('unimportant', None)
    if s in ('fixed 0', 'fixed 1'):
        return ('fixed', int(s[-1]))
    raise NetlistError('unknown label %r' % s)


class Circuit:
    def __init__(self, mod, labels):
        """labels: {port or port[i]: label string}. Every input bit must be covered."""
        self.mod = mod
        self.bitname = {}
        for n, w in mod['netnames'].items():
            for i, b in enumerate(w['bits']):
                if isinstance(b, int) and (b not in self.bitname or not n.startswith('$')):
                    self.bitname[b] = n if len(w['bits']) == 1 else '%s[%d]' % (n, i)
        self.inputs = {}        # bit -> (kind, arg)
        for p, pd in mod['ports'].items():
            if pd['direction'] != 'input':
                continue
            for i, b in enumerate(pd['bits']):
                key = '%s[%d]' % (p, i)
                lab = labels.get(key, labels.get(p))
                if lab is None:
                    raise NetlistError('input %s has no label' % key)
                self.inputs[b] = parse_label(lab)
        self.outputs = {p: pd['bits'] for p, pd in mod['ports'].items() if pd['direction'] == 'output'}
        self.vars = [b for b, (k, _a) in self.inputs.items() if k in ('secret', 'random')]
        if len(self.vars) > MAX_VARS:
            raise NetlistError('%d share/random bits: too many for exhaustive counting (limit %d)' % (len(self.vars), MAX_VARS))
        self.secrets = sorted({a for k, a in self.inputs.values() if k == 'secret'})
        self.cells = []
        for name, c in mod['cells'].items():
            if c['type'] not in COMB and c['type'] not in FLOPS:
                raise NetlistError('cell type %s (%s) not supported' % (c['type'], name))
            self.cells.append((name, c))
        self._eval()

    # -- truth tables
    def _eval(self):
        n = len(self.vars)
        rows = 1 << n
        idx = np.arange(rows, dtype=np.uint32)
        val = {0: np.zeros(rows, bool), 1: np.ones(rows, bool), '0': np.zeros(rows, bool), '1': np.ones(rows, bool),
               'x': np.zeros(rows, bool)}
        for i, b in enumerate(self.vars):
            val[b] = ((idx >> i) & 1).astype(bool)
        for b, (k, a) in self.inputs.items():
            if k == 'fixed':
                val[b] = np.full(rows, bool(a))
            elif k == 'unimportant':
                val[b] = np.zeros(rows, bool)
        self.driver = {}
        for name, c in self.cells:
            for p, bits in c['connections'].items():
                if c['port_directions'][p] == 'output':
                    self.driver[bits[0]] = (name, c)
        flops = [(nm, c) for nm, c in self.cells if c['type'] in FLOPS]
        for _nm, c in flops:
            val[c['connections']['Q'][0]] = np.zeros(rows, bool)
        order = self._topo()
        for _it in range(len(flops) + 2):          # settle: Q = D until nothing changes
            for nm, c in order:
                args = {p: val[bits[0]] for p, bits in c['connections'].items() if c['port_directions'][p] == 'input'}
                val[c['connections']['Y'][0]] = COMB[c['type']](args).astype(bool)
            changed = False
            for _nm, c in flops:
                d = val[c['connections']['D'][0]]
                q = c['connections']['Q'][0]
                if not np.array_equal(val[q], d):
                    val[q] = d.copy()
                    changed = True
            if not changed:
                break
        else:
            raise NetlistError('flip-flops did not settle (oscillating loop?)')
        self.val = val
        sec = np.zeros(rows, dtype=np.int64)
        for j, s in enumerate(self.secrets):
            x = np.zeros(rows, bool)
            for i, b in enumerate(self.vars):
                if self.inputs[b] == ('secret', s):
                    x ^= val[b]
            sec |= x.astype(np.int64) << j
        self.secret_code = sec

    def _topo(self):
        comb = [(nm, c) for nm, c in self.cells if c['type'] in COMB]
        ready = set(self.inputs) | {0, 1, '0', '1', 'x'}
        ready |= {c['connections']['Q'][0] for _nm, c in self.cells if c['type'] in FLOPS}
        out, todo = [], comb
        while todo:
            nxt = []
            for nm, c in todo:
                ins = [bits[0] for p, bits in c['connections'].items() if c['port_directions'][p] == 'input']
                if all(b in ready for b in ins):
                    out.append((nm, c))
                    ready.add(c['connections']['Y'][0])
                else:
                    nxt.append((nm, c))
            if len(nxt) == len(todo):
                raise NetlistError('combinational loop')
            todo = nxt
        return out

    # -- probes
    def sites(self):
        s = [b for b in self.inputs if self.inputs[b][0] in ('secret', 'random')]
        for _nm, c in self.cells:
            for p, bits in c['connections'].items():
                if c['port_directions'][p] == 'output' and bits[0] not in s:
                    s.append(bits[0])
        return s

    def cone(self, b):
        """Glitch-extended observation of wire b: input bits and flip-flop outputs in its combinational cone."""
        seen, leaves, stack = set(), set(), [b]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            if x in self.inputs or not isinstance(x, int):
                if x in self.inputs and self.inputs[x][0] in ('secret', 'random'):
                    leaves.add(x)
                continue
            nm, c = self.driver[x]
            if c['type'] in FLOPS:
                leaves.add(x)
                continue
            for p, bits in c['connections'].items():
                if c['port_directions'][p] == 'input':
                    stack.append(bits[0])
        return sorted(leaves, key=str)

    def leaks(self, observed):
        """True when the joint distribution of the observed bits depends on the secrets (exact count)."""
        if not observed:
            return False
        m = np.stack([self.val[b] for b in observed])
        _u, obs = np.unique(np.packbits(m, axis=0).T, axis=0, return_inverse=True)
        obs = obs.reshape(-1)
        nobs = int(obs.max()) + 1
        ns = 1 << len(self.secrets)
        t = np.bincount(self.secret_code * nobs + obs, minlength=ns * nobs).reshape(ns, nobs)
        return not bool((t == t[0]).all())

    def check(self, model='standard', order=1, max_report=8):
        sites = self.sites()
        obs = {b: ([b] if model == 'standard' else self.cone(b)) for b in sites}
        leaks, n = [], 0
        for combo in itertools.combinations(sites, order):
            n += 1
            seen = sorted({x for b in combo for x in obs[b]}, key=str)
            if self.leaks(seen):
                leaks.append(dict(probes=[self.bitname.get(b, str(b)) for b in combo],
                                  observes=[self.bitname.get(x, str(x)) for x in seen]))
        return dict(model=model, order=order, probe_sets=n, leaking_sets=len(leaks), secure=not leaks,
                    examples=leaks[:max_report])

    def output_ok(self, pairs):
        """Each (out0, out1) share pair XORs to a value fixed by the secrets alone (randomness cancels out)."""
        ok = True
        for o0, o1 in pairs:
            for b0, b1 in zip(self.outputs[o0], self.outputs[o1]):
                u = (self.val[b0] ^ self.val[b1]).astype(np.int64)
                for s in range(1 << len(self.secrets)):
                    v = u[self.secret_code == s]
                    if v.size and not (v == v[0]).all():
                        ok = False
        return ok

    def stats(self):
        import collections
        return dict(cells=len(self.cells), types=dict(collections.Counter(c['type'] for _n, c in self.cells)),
                    share_and_random_bits=len(self.vars), secret_bits=len(self.secrets))
