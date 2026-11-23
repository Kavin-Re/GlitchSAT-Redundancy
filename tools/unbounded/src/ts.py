"""Fault-augmented transition system of a gate netlist, as CNF.

State of the system (one copy per clock cycle when unrolled):
    q[i]   the design's flip-flops
    in[i]  the input bits (attacker input `sig`): free at the start, then frozen (in' = in)
    u[j]   fault counter, unary and saturating at the budget: u[j] is true when at least j flips were used so far
    h      "the goal value has been observed" (sticky)
Free choices in every cycle: one flip variable per fault site (flop Q nets and gate outputs; input nets on request).
A flip inverts the value that every reader of that net sees in that cycle only (the stored flop value is not touched),
which is the fault model of scripts/glitchsat.py. The property is "h never becomes true".

The step relation is split in two parts because IC3 needs the difference:
    func  definitions only: for any state and any flip choice they fix every other variable (always satisfiable)
    cons  restrictions: the budget is not exceeded, the counter is well formed, the attacker input is not the key
The netlist reader is the engine's own (scripts/glitchsat.py, class Netlist), so both read a netlist the same way.
"""
import importlib.util, os, sys

from sat import find_repo_root


class TSError(Exception):
    pass


def load_engine():
    """scripts/glitchsat.py as a module (it imports without z3)."""
    if 'glitchsat' in sys.modules:
        return sys.modules['glitchsat']
    root = find_repo_root()
    if not root:
        raise TSError('repository root not found (need scripts/glitchsat.py); set GLITCHSAT_ROOT')
    spec = importlib.util.spec_from_file_location('glitchsat', os.path.join(root, 'scripts', 'glitchsat.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['glitchsat'] = mod
    spec.loader.exec_module(mod)
    return mod


class TS:
    def __init__(self, nl, k, goal_out='boot_word', goal_value=0x96, goal_mask=None, attack_in='sig', key=0xC3,
                 init_mode='known', input_sites=False, honest=False, init_blocked=None):
        """nl: glitchsat.Netlist. k: fault budget. init_mode: 'known' (netlist init values), 'arbitrary' (any power-up
        state) or 'free_nongoal' (any power-up state from which the fault-free run never shows the goal; the excluded
        (state, input) pairs must be passed as init_blocked, see unbounded.nongoal_blocked).
        honest=True replaces 'input != key' by 'input == key' (sanity check that the goal is reachable at all)."""
        if k < 0:
            raise TSError('k must be >= 0')
        if init_mode not in ('known', 'arbitrary', 'free_nongoal'):
            raise TSError(f'init_mode {init_mode!r}')
        if init_mode == 'free_nongoal' and init_blocked is None:
            raise TSError('free_nongoal needs init_blocked')
        ports = nl.ports
        if goal_out not in ports or ports[goal_out].get('direction') != 'output':
            raise TSError(f'{goal_out!r} is not an output port')
        if attack_in not in ports or ports[attack_in].get('direction') != 'input':
            raise TSError(f'{attack_in!r} is not an input port')
        self.nl, self.k, self.init_mode = nl, k, init_mode
        self.opts = dict(goal_out=goal_out, goal_value=goal_value, goal_mask=goal_mask, attack_in=attack_in, key=key,
                         init_mode=init_mode, input_sites=input_sites, honest=honest)
        self.qs = list(nl.qs)
        self.in_ports = [(p, v['bits']) for p, v in ports.items() if v['direction'] == 'input' and p != 'clk']
        self.in_bits = [b for _, bits in self.in_ports for b in bits]
        nq, ni = len(self.qs), len(self.in_bits)
        self.nq, self.ni = nq, ni
        self.S = S = nq + ni + k + 1
        self.q_pos = list(range(nq))
        self.in_pos = list(range(nq, nq + ni))
        self.u_pos = list(range(nq + ni, nq + ni + k))
        self.h_pos = S - 1
        self._n = 2 * S                       # template variables: 1..S current, S+1..2S next, then auxiliaries
        cur = lambda pos: pos + 1
        nxt = lambda pos: S + pos + 1
        func, cons = [], []
        TRUE = self._new(); func.append([TRUE])

        goal_bits = ports[goal_out]['bits']
        goal = [(b, (goal_value >> i) & 1) for i, b in enumerate(goal_bits) if goal_mask is None or (goal_mask >> i) & 1]
        if not goal:
            raise TSError('goal mask selects no bit')
        # cone of influence: everything that can reach a flop input or a goal bit
        order, seen = [], set(self.qs) | set(self.in_bits)
        for root in [nl.dq[q] for q in self.qs] + [b for b, _ in goal]:
            stack = [root]
            while stack:
                b = stack[-1]
                if b in ('0', '1') or b in seen:
                    stack.pop(); continue
                if b in ('x', 'z'):
                    raise TSError('constant x/z bit in the logic cone; refusing')
                if b not in nl.drivers:
                    raise TSError(f'net {nl.names.get(b, b)!r} is used but has no driver')
                pend = [f for f in nl.fanins(b) if f not in ('0', '1') and f not in seen]
                if pend:
                    stack.extend(pend); continue
                seen.add(b); order.append(b); stack.pop()
        self.sites_all = len(nl.qs) + len(nl.drivers) + (ni if input_sites else 0)
        site_nets = (self.qs + order + (self.in_bits if input_sites else [])) if k > 0 else []
        self.fault = {b: self._new() for b in site_nets}      # site net -> template flip variable
        self.sites = site_nets

        def xor(a, b):
            y = self._new()
            func.extend([[-y, a, b], [-y, -a, -b], [y, -a, b], [y, a, -b]])
            return y
        val = {'0': -TRUE, '1': TRUE}
        for i, q in enumerate(self.qs):
            val[q] = xor(cur(self.q_pos[i]), self.fault[q]) if q in self.fault else cur(self.q_pos[i])
        for i, b in enumerate(self.in_bits):
            val[b] = xor(cur(self.in_pos[i]), self.fault[b]) if b in self.fault else cur(self.in_pos[i])
        for b in order:
            _, ty, con = nl.drivers[b]
            g = lambda p: val[con[p][0]]
            if ty == '$_NOT_':
                y = -g('A')
            elif ty == '$_AND_':
                a, c = g('A'), g('B'); y = self._new()
                func.extend([[-y, a], [-y, c], [y, -a, -c]])
            elif ty == '$_OR_':
                a, c = g('A'), g('B'); y = self._new()
                func.extend([[y, -a], [y, -c], [-y, a, c]])
            elif ty == '$_XOR_':
                y = xor(g('A'), g('B'))
            elif ty == '$_MUX_':
                a, c, s = g('A'), g('B'), g('S'); y = self._new()
                func.extend([[-s, -c, y], [-s, c, -y], [s, -a, y], [s, a, -y], [-a, -c, y], [a, c, -y]])
            else:
                raise TSError('unsupported cell ' + str(ty))
            val[b] = xor(y, self.fault[b]) if b in self.fault else y
        # next state of the design flops and the frozen inputs
        for i, q in enumerate(self.qs):
            d = val[nl.dq[q]]
            func.extend([[-nxt(self.q_pos[i]), d], [nxt(self.q_pos[i]), -d]])
        for pos in self.in_pos:
            func.extend([[-nxt(pos), cur(pos)], [nxt(pos), -cur(pos)]])
        # fault counter: lev[j] = "at least j flips used", j = 1..k+1; exact (both directions)
        lev = [TRUE] + [cur(p) for p in self.u_pos] + [-TRUE]
        for b in site_nets:
            f = self.fault[b]
            new = [TRUE]
            for j in range(1, k + 2):
                c = self._new()
                func.extend([[-lev[j], c], [-f, -lev[j - 1], c], [-c, lev[j], f], [-c, lev[j], lev[j - 1]]])
                new.append(c)
            lev = new
        for j, pos in enumerate(self.u_pos, start=1):
            func.extend([[-nxt(pos), lev[j]], [nxt(pos), -lev[j]]])
        self.c_overflow = lev[k + 1]
        cons.append([-lev[k + 1]])                                          # budget not exceeded
        for a, b in zip(self.u_pos, self.u_pos[1:]):
            cons.append([-cur(b), cur(a)])                                  # well-formed unary counter
        # attacker input is not the key (or is the key, for the honest sanity run)
        off = 0
        for p, bits in self.in_ports:
            if p == attack_in:
                lits = [cur(self.in_pos[off + i]) if (key >> i) & 1 else -cur(self.in_pos[off + i]) for i in range(len(bits))]
                if honest:
                    cons.extend([[l] for l in lits])
                else:
                    cons.append([-l for l in lits])
            off += len(bits)
        # goal observed in this cycle (on the possibly flipped nets) -> sticky h
        g = self._new()
        gl = [val[b] if want else -val[b] for b, want in goal]
        func.extend([[-g, l] for l in gl]); func.append([g] + [-l for l in gl])
        h, h2 = cur(self.h_pos), nxt(self.h_pos)
        func.extend([[-h, h2], [-g, h2], [-h2, h, g]])
        self.goal_now = g
        # initial states
        init = [[-cur(p)] for p in self.u_pos] + [[-cur(self.h_pos)]]
        self.init_cube = {cur(p): False for p in self.u_pos}
        self.init_cube[cur(self.h_pos)] = False
        if init_mode == 'known':
            for i, q in enumerate(self.qs):
                init.append([cur(self.q_pos[i]) if nl.init[q] else -cur(self.q_pos[i])])
                self.init_cube[cur(self.q_pos[i])] = bool(nl.init[q])
        elif init_mode == 'free_nongoal':
            for st, inp in init_blocked:          # inp None = for every input value
                c = [-cur(self.q_pos[i]) if (st >> i) & 1 else cur(self.q_pos[i]) for i in range(nq)]
                if inp is not None:
                    c += [-cur(self.in_pos[i]) if (inp >> i) & 1 else cur(self.in_pos[i]) for i in range(ni)]
                init.append(c)
        self.func, self.cons, self.init = func, cons, init
        self.naux = self._n - 2 * S

    def _new(self):
        self._n += 1
        return self._n

    # ------------------------------------------------------------ instantiation
    def mapper(self, cur, nxt, aux_base):
        """Template variable -> solver variable. cur/nxt: lists of S solver variables; auxiliaries start at aux_base+1."""
        S = self.S
        def m(l):
            v = l if l > 0 else -l
            if v <= S: w = cur[v - 1]
            elif v <= 2 * S: w = nxt[v - S - 1]
            else: w = aux_base + (v - 2 * S)
            return w if l > 0 else -w
        return m

    def stats(self):
        return dict(state_bits=self.S, design_flops=self.nq, input_bits=self.ni, counter_bits=self.k,
                    fault_sites_in_cone=len(self.sites), fault_sites_total=self.sites_all,
                    step_vars=self._n, step_clauses=len(self.func) + len(self.cons))

    # ------------------------------------------------------------ decoding
    def decode_state(self, bits):
        """bits: list of S booleans -> dict(flops=int, input=int, used=int, hit=bool)."""
        return dict(flops=sum(1 << i for i, p in enumerate(self.q_pos) if bits[p]),
                    input=sum(1 << i for i, p in enumerate(self.in_pos) if bits[p]),
                    used=sum(1 for p in self.u_pos if bits[p]), hit=bool(bits[self.h_pos]))

    def state_holds(self, clause, flops, inp, used, hit=False):
        """Evaluate a clause over current-state template literals on one concrete state."""
        for l in clause:
            p = abs(l) - 1
            if p < self.nq: v = (flops >> p) & 1
            elif p < self.nq + self.ni: v = (inp >> (p - self.nq)) & 1
            elif p < self.S - 1: v = used >= (p - self.nq - self.ni + 1)
            else: v = hit
            if bool(v) == (l > 0):
                return True
        return False

    def lit_name(self, l):
        p = abs(l) - 1
        if p < self.nq: nm = self.nl.names.get(self.qs[p], f'q{p}')
        elif p < self.nq + self.ni: nm = self.nl.names.get(self.in_bits[p - self.nq], f'in{p - self.nq}')
        elif p < self.S - 1: nm = f'used>={p - self.nq - self.ni + 1}'
        else: nm = 'goal_seen'
        return nm if l > 0 else '!' + nm


class Unroll:
    """T unrolled over frames 0..n in one solver: frame t state variables are self.X[t]."""
    def __init__(self, ts, backend, with_init):
        self.ts, self.b = ts, backend
        self.nv = 0
        self.X = [self._alloc(ts.S)]
        self.maps = []
        if with_init:
            m = ts.mapper(self.X[0], self.X[0], 0)
            for c in ts.init:
                backend.add([m(l) for l in c])

    def _alloc(self, n):
        base = self.nv
        self.nv += n
        self.b.reserve(self.nv)
        return list(range(base + 1, base + n + 1))

    def new_var(self):
        return self._alloc(1)[0]

    def extend(self):
        ts = self.ts
        nxt = self._alloc(ts.S)
        aux = self._alloc(ts.naux)
        m = ts.mapper(self.X[-1], nxt, aux[0] - 1 if aux else 0)
        for c in ts.func: self.b.add([m(l) for l in c])
        for c in ts.cons: self.b.add([m(l) for l in c])
        self.X.append(nxt)
        self.maps.append(m)

    def h(self, t):
        return self.X[t][self.ts.h_pos]

    def state(self, t):
        return [self.b.val(v) for v in self.X[t]]

    def faults(self, t):
        """Fault sites flipped in the step from frame t to t+1 (last model)."""
        m = self.maps[t]
        return [b for b in self.ts.sites if self.b.val(m(self.ts.fault[b]))]

    def trace(self, n):
        """Attack read from the last model: frames 0..n."""
        s0 = self.ts.decode_state(self.state(0))
        return dict(init_state=s0['flops'], input=s0['input'],
                    faults=[(t, b) for t in range(n) for b in self.faults(t)], cycles=n)
