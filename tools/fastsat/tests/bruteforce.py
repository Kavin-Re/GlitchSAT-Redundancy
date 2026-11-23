"""Exhaustive reference for the GlitchSAT question, written without the encoder, without glitchsat.py and without a
solver: plain gate-level simulation of a Yosys JSON netlist, bit-parallel over every value of every free input.

Model (the one stated at the top of scripts/glitchsat.py): every input port except `clk` is free and constant over the
run; flops start at their `init` attribute (0 when absent); a fault flips the output net of a gate or the Q net of a
flop for one cycle; the goal is `goal port == goal value` at some cycle < T with attacker input != key.
Fault sites are ALL gates and ALL flops at ALL cycles (no cone or timing reduction here)."""
import json, itertools


class Ref:
    def __init__(self, path, top, goal_out='boot_word', attack_in='sig'):
        m = json.load(open(path))['modules'][top]
        self.names = {}
        for n, x in m['netnames'].items():
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, n)
        free = [(p, v['bits']) for p, v in m['ports'].items() if v['direction'] == 'input' and p != 'clk']
        self.nin = sum(len(b) for _, b in free)
        if self.nin > 14:
            raise ValueError('too many free input bits for the exhaustive reference')
        L = 1 << self.nin
        self.ALL = (1 << L) - 1
        self.inl = {}; self.inpos = {}
        pos = 0
        for p, bits in free:
            for i, b in enumerate(bits):
                self.inl[b] = sum(1 << s for s in range(L) if (s >> pos) & 1)
                self.inpos[(p, i)] = pos
                pos += 1
        self.attack_bits = m['ports'][attack_in]['bits']
        self.attack_in = attack_in
        self.out = m['ports'][goal_out]['bits']
        self.gates = {}; self.dffs = []
        for c in m['cells'].values():
            t, con = c['type'], c.get('connections', {})
            if t == '$scopeinfo':
                continue
            if t == '$_DFF_P_':
                self.dffs.append((con['D'][0], con['Q'][0]))
            else:
                self.gates[con['Y'][0]] = (t, {p: v[0] for p, v in con.items() if p != 'Y'})
        init = {}
        for x in m['netnames'].values():
            iv = x.get('attributes', {}).get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)):
                    if ch in '01' and isinstance(x['bits'][i], int):   # an x at one alias must not overwrite a known value at another
                        init[x['bits'][i]] = ch == '1'
        self.init = {q: (self.ALL if init.get(q, False) else 0) for _, q in self.dffs}
        self.sites = [q for _, q in self.dffs] + list(self.gates)
        self.order = []
        seen = set(self.init) | set(self.inl)
        for root in [d for d, _ in self.dffs] + list(self.out):
            st = [root]
            while st:
                b = st[-1]
                if not isinstance(b, int) or b in seen:
                    st.pop(); continue
                pend = [v for v in self.gates[b][1].values() if isinstance(v, int) and v not in seen]
                if pend:
                    st.extend(pend); continue
                seen.add(b); self.order.append(b); st.pop()

    def bad_lanes(self, key):
        """Lanes (input assignments) whose attacker input differs from key."""
        eq = self.ALL
        for i, b in enumerate(self.attack_bits):
            l = self.inl[b]
            eq &= l if (key >> i) & 1 else self.ALL ^ l
        return self.ALL ^ eq

    def run(self, T, faults, goal_value):
        """faults: iterable of (cycle, net). Returns lanes where the goal port equals goal_value at some cycle < T."""
        ALL = self.ALL
        by = {}
        for t, b in faults:
            by.setdefault(t, set()).add(b)
        st = dict(self.init); hit = 0
        inl = self.inl
        for t in range(T):
            f = by.get(t, ())
            v = {}

            def g(b):
                if b == '0': return 0
                if b == '1': return ALL
                if b in inl: return inl[b]
                return v[b]
            for q in st:
                v[q] = st[q] ^ (ALL if q in f else 0)
            for b in self.order:
                ty, p = self.gates[b]
                if ty == '$_AND_': r = g(p['A']) & g(p['B'])
                elif ty == '$_OR_': r = g(p['A']) | g(p['B'])
                elif ty == '$_XOR_': r = g(p['A']) ^ g(p['B'])
                elif ty == '$_NOT_': r = ALL ^ g(p['A'])
                elif ty == '$_MUX_':
                    s = g(p['S']); r = (g(p['B']) & s) | (g(p['A']) & (ALL ^ s))
                else: raise ValueError(ty)
                if b in f: r ^= ALL
                v[b] = r
            m = ALL
            for i, b in enumerate(self.out):
                x = g(b)
                m &= x if (goal_value >> i) & 1 else ALL ^ x
            hit |= m
            st = {q: g(d) for d, q in self.dffs}
        return hit

    def attack_exists(self, T, j, goal_value, key, limit=None):
        """Exhaustive: is there a set of EXACTLY j faults (any sites, any cycles) and a non-key input reaching the goal?
        Returns (True/False, number of fault sets tried). limit: give up (None, n) after that many sets."""
        bad = self.bad_lanes(key)
        pairs = [(t, b) for t in range(T) for b in self.sites]
        n = 0
        for c in itertools.combinations(pairs, j):
            n += 1
            if self.run(T, c, goal_value) & bad:
                return True, n
            if limit and n >= limit:
                return None, n
        return False, n

    def min_faults(self, T, kmax, goal_value, key, limit=None):
        """Smallest j <= kmax with an attack (exhaustive over sizes 0..j), or None if there is none up to kmax.
        Returns (min or None, sets tried, complete?)."""
        tot = 0
        for j in range(kmax + 1):
            r, n = self.attack_exists(T, j, goal_value, key, limit)
            tot += n
            if r is None: return None, tot, False
            if r: return j, tot, True
        return None, tot, True

    def witness_ok(self, T, faults, inputs, goal_value, key):
        """Does this exact witness (fault list + input values per port) reach the goal with a non-key attacker input?"""
        lane = 0
        for (p, i), pos in self.inpos.items():
            lane |= ((inputs[p] >> i) & 1) << pos
        hit = self.run(T, faults, goal_value) & self.bad_lanes(key)
        return bool((hit >> lane) & 1)
