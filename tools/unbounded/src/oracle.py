"""Explicit-state oracle: exhaustive search over every reachable state, with a fault budget, in plain Python.

This is the second, independent method of ext/unbounded. It shares no code with the solver path (own netlist
reader, own gate simulator, no CNF, no SAT solver).

What it computes, for one netlist and one attacker input value at a time:
    cost[s] = the smallest number of single-cycle flips after which the flip-flops can hold the value s
              (0 for the power-up state and everything the fault-free run visits).
It is a shortest-path search (Dijkstra with unit weights) over the flip-flop values. From a state reached with c flips
it tries EVERY set of at most (k - c) fault sites in the next cycle. The search stops when no new state appears; that
is a fixed point, so the result holds for any number of cycles. Why keeping only the cheapest way to reach a state is
enough: a run that arrives with fewer flips used can do everything a run with more flips used can do.

Fault sets are simulated in parallel: one Python integer holds one net for all fault sets (one bit per set).

Limits: the state space must be small enough to enumerate (flip-flops <= 20, attacker/input bits <= 16).
"""
import itertools, json, time

MAX_FLOPS, MAX_INPUT_BITS = 20, 16


class OracleError(Exception):
    pass


class Net:
    """Yosys JSON gate netlist ($_AND_/OR/XOR/NOT/MUX and $_DFF_P_). Independent of scripts/glitchsat.py."""
    PINS = {'$_AND_': 'AB', '$_OR_': 'AB', '$_XOR_': 'AB', '$_NOT_': 'A', '$_MUX_': 'ABS'}

    def __init__(self, path, top):
        with open(path) as f:
            doc = json.load(f)
        if top not in doc.get('modules', {}):
            raise OracleError(f'{path}: no module {top!r}')
        m = doc['modules'][top]
        self.ports = m['ports']
        self.gates = {}        # output net -> (type, [input nets in PINS order])
        self.flops = []        # (D net, Q net)
        for cn, c in m['cells'].items():
            t, con = c['type'], c.get('connections', {})
            if t == '$scopeinfo':
                continue
            if t == '$_DFF_P_':
                self.flops.append((con['D'][0], con['Q'][0]))
            elif t in self.PINS:
                y = con['Y'][0]
                if y in self.gates:
                    raise OracleError(f'net {y} has two drivers')
                self.gates[y] = (t, [con[p][0] for p in self.PINS[t]])
            else:
                raise OracleError(f'unsupported cell type {t} ({cn})')
        self.names = {}
        init = {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, f'{n}[{i}]' if len(x['bits']) > 1 else n)
            iv = x.get('attributes', {}).get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)):
                    if ch in '01':
                        init[x['bits'][i]] = ch == '1'
                    elif any(q == x['bits'][i] for _, q in self.flops):
                        raise OracleError(f'flop net {n}: unknown init bit {ch!r}')
        self.qs = [q for _, q in self.flops]
        if len(set(self.qs)) != len(self.qs):
            raise OracleError('two flops drive one net')
        self.init_state = sum(1 << i for i, q in enumerate(self.qs) if init.get(q, False))
        self.inputs = [(p, v['bits']) for p, v in self.ports.items() if v['direction'] == 'input' and p != 'clk']
        self.in_bits = [b for _, bits in self.inputs for b in bits]
        known = set(self.qs) | set(self.in_bits)
        self.order = []        # every gate, inputs before outputs
        state = {}
        for root in self.gates:
            stack = [root]
            while stack:
                b = stack[-1]
                if b in known or state.get(b) == 2 or not isinstance(b, int):
                    stack.pop(); continue
                if b not in self.gates:
                    raise OracleError(f'net {b} is used but not driven')
                pend = [f for f in self.gates[b][1] if isinstance(f, int) and f not in known and state.get(f) != 2]
                if state.get(b) == 1 or not pend:
                    if any(state.get(f) == 1 for f in pend):
                        raise OracleError(f'combinational loop through net {b}')
                    state[b] = 2; self.order.append(b); stack.pop()
                else:
                    state[b] = 1; stack.extend(pend)

    def input_value(self, values):
        """dict port -> int  ->  packed int in in_bits order."""
        x, i = 0, 0
        for p, bits in self.inputs:
            for j in range(len(bits)):
                if (values.get(p, 0) >> j) & 1:
                    x |= 1 << i
                i += 1
        return x

    def unpack_input(self, x):
        out, i = {}, 0
        for p, bits in self.inputs:
            out[p] = (x >> i) & ((1 << len(bits)) - 1)
            i += len(bits)
        return out


class Oracle:
    def __init__(self, net, goal_out='boot_word', goal_value=0x96, goal_mask=None, attack_in='sig', key=0xC3,
                 input_sites=False):
        self.net = net
        if len(net.qs) > MAX_FLOPS or len(net.in_bits) > MAX_INPUT_BITS:
            raise OracleError(f'too large to enumerate: {len(net.qs)} flops, {len(net.in_bits)} input bits '
                              f'(limits {MAX_FLOPS}, {MAX_INPUT_BITS})')
        gb = net.ports[goal_out]['bits']
        self.goal = [(b, (goal_value >> i) & 1) for i, b in enumerate(gb) if goal_mask is None or (goal_mask >> i) & 1]
        self.attack_in, self.key = attack_in, key
        self.sites = list(net.qs) + list(net.gates) + (list(net.in_bits) if input_sites else [])
        self.site_idx = {b: i for i, b in enumerate(self.sites)}
        self._lay = {}
        self.evals = 0
        self.scenarios = 0

    # ------------------------------------------------------------ fault-set layouts
    def layout(self, r):
        """All fault sets with at most r sites, smallest first. Returns (W, subsets, site masks, size masks)."""
        if r in self._lay:
            return self._lay[r]
        n = len(self.sites)
        subsets = [()]
        bounds = [0, 1]
        for j in range(1, r + 1):
            subsets.extend(itertools.combinations(range(n), j))
            bounds.append(len(subsets))
        W = len(subsets)
        nbytes = (W + 7) // 8
        arrs = [bytearray(nbytes) for _ in range(n)]
        for idx, sub in enumerate(subsets):
            for s in sub:
                arrs[s][idx >> 3] |= 1 << (idx & 7)
        masks = {self.sites[i]: int.from_bytes(arrs[i], 'little') for i in range(n)}
        size = [((1 << bounds[j + 1]) - 1) ^ ((1 << bounds[j]) - 1) for j in range(r + 1)]
        self._lay[r] = (W, subsets, masks, size)
        return self._lay[r]

    # ------------------------------------------------------------ one clock cycle, all fault sets at once
    def step(self, state, inp, r):
        """Returns (next-state bit lanes, goal-hit lanes) for every fault set of size <= r applied in this cycle."""
        net = self.net
        W, _, masks, _ = self.layout(r)
        ALL = (1 << W) - 1
        v = {'0': 0, '1': ALL}
        for i, q in enumerate(net.qs):
            v[q] = (ALL if (state >> i) & 1 else 0) ^ masks[q]
        for i, b in enumerate(net.in_bits):
            v[b] = (ALL if (inp >> i) & 1 else 0) ^ masks.get(b, 0)
        gates = net.gates
        for y in net.order:
            t, ins = gates[y]
            if t == '$_AND_': x = v[ins[0]] & v[ins[1]]
            elif t == '$_OR_': x = v[ins[0]] | v[ins[1]]
            elif t == '$_XOR_': x = v[ins[0]] ^ v[ins[1]]
            elif t == '$_NOT_': x = ALL ^ v[ins[0]]
            else:
                s = v[ins[2]]; x = (v[ins[1]] & s) | (v[ins[0]] & (ALL ^ s))
            v[y] = x ^ masks[y]
        hit = ALL
        for b, want in self.goal:
            hit &= v[b] if want else ALL ^ v[b]
        self.evals += 1
        self.scenarios += W
        return [v[d] for d, _ in net.flops], hit

    @staticmethod
    def _split(m, lanes):
        """Distinct next states among the fault sets selected by mask m: yields (state, mask of the sets giving it)."""
        todo = [(m, 0, 0)]
        n = len(lanes)
        while todo:
            m, i, pref = todo.pop()
            if i == n:
                yield pref, m
                continue
            a = m & lanes[i]
            b = m ^ a
            if a: todo.append((a, i + 1, pref | (1 << i)))
            if b: todo.append((b, i + 1, pref))

    # ------------------------------------------------------------ power-up assumption
    def fault_free_accepting(self, inp, horizon=None):
        """States from which the fault-free run (this input) shows the goal value: ever (horizon None) or within
        `horizon` cycles. Used for the 'free_nongoal' power-up assumption."""
        n = len(self.net.qs)
        nxt, hit0 = {}, set()
        for s in range(1 << n):
            lanes, hit = self.step(s, inp, 0)
            nxt[s] = sum(1 << i for i, l in enumerate(lanes) if l & 1)
            if hit & 1:
                hit0.add(s)
        acc = set(hit0)
        rounds = 0
        while True:
            rounds += 1
            if horizon is not None and rounds >= horizon:
                break
            new = {s for s in nxt if s not in acc and nxt[s] in acc}
            if not new:
                break
            acc |= new
        return acc

    def init_states(self, inp, init_mode, horizon=None):
        n = len(self.net.qs)
        if init_mode == 'known':
            return [self.net.init_state]
        if init_mode == 'arbitrary':
            return list(range(1 << n))
        if init_mode == 'free_nongoal':
            acc = self.fault_free_accepting(inp, horizon)
            return [s for s in range(1 << n) if s not in acc]
        raise OracleError(f'init_mode {init_mode!r}')

    # ------------------------------------------------------------ unbounded search
    def search_input(self, inp, kmax, init_mode='known', stop_at_first=True):
        """Shortest-path search for one input value. Returns dict(min_faults or None, witness, cost={state: min flips}).
        cost is the complete set of states reachable with <= kmax flips when no attack exists (a fixed point)."""
        inits = self.init_states(inp, init_mode)
        cost = {s: 0 for s in inits}
        parent = {}
        buckets = [list(inits)] + [[] for _ in range(kmax)]
        best, wit = None, None
        for c in range(kmax + 1):
            i = 0
            while i < len(buckets[c]):
                s = buckets[c][i]; i += 1
                if cost[s] != c:
                    continue
                r = (kmax if best is None or not stop_at_first else best - 1) - c
                if r < 0:
                    continue
                lanes, hit = self.step(s, inp, r)
                _, subsets, _, size = self.layout(r)
                for j in range(r + 1):
                    h = hit & size[j]
                    if h and (best is None or c + j < best):
                        best = c + j
                        idx = (h & -h).bit_length() - 1
                        wit = (s, subsets[idx])
                    for ns, mm in self._split(size[j], lanes):
                        if cost.get(ns, kmax + 1) > c + j:
                            cost[ns] = c + j
                            parent[ns] = (s, subsets[(mm & -mm).bit_length() - 1])
                            buckets[c + j].append(ns)
        out = dict(min_faults=best, cost=cost, witness=None)
        if best is not None:
            s, last = wit
            steps = [(s, last)]
            while s in parent:      # power-up states never get a parent
                s, sub = parent[s]
                steps.append((s, sub))
            steps.reverse()
            # steps[i] = (state before cycle i, fault set applied in cycle i); the first state is a power-up state
            out['witness'] = dict(init_state=steps[0][0], input=inp,
                                  faults=[(t, self.sites[x]) for t, (_, sub) in enumerate(steps) for x in sub],
                                  cycles=len(steps))
        return out

    def input_values(self, honest=False):
        """Attacker input values to try: every value of every input port, except attack_in == key (or only the key)."""
        net = self.net
        total = len(net.in_bits)
        off = 0
        for p, bits in net.inputs:
            if p == self.attack_in:
                lo, w = off, len(bits)
            off += len(bits)
        for x in range(1 << total):
            is_key = ((x >> lo) & ((1 << w) - 1)) == self.key
            if is_key == honest:
                yield x

    def unbounded(self, kmax, init_mode='known', progress=None):
        """Exact minimum number of flips (<= kmax) that reaches the goal at ANY time, or proof that none exists."""
        t0 = time.time()
        best, wit = None, None
        reach = {}
        n_states = 0
        for inp in self.input_values():
            # an attack with fewer flips than the best one so far is all that matters
            lim = kmax if best is None else best - 1
            if lim < 0:
                break
            r = self.search_input(inp, lim, init_mode)
            if r['min_faults'] is not None:
                best, wit = r['min_faults'], r['witness']
            else:
                reach[inp] = r['cost']
                n_states += len(r['cost'])
            if progress:
                progress(inp, best)
        return dict(min_faults=best, witness=wit, kmax=kmax, init_mode=init_mode, reach=reach,
                    reachable_pairs=n_states, step_evals=self.evals, fault_sets_simulated=self.scenarios,
                    seconds=round(time.time() - t0, 3))

    # ------------------------------------------------------------ bounded variant (for comparison with the engine)
    def bounded(self, kmax, cycles, init_mode='known'):
        """Minimum flips that reach the goal within `cycles` cycles (same meaning as scripts/glitchsat.py --cycles)."""
        best = None
        for inp in self.input_values():
            lim = kmax if best is None else best - 1
            if lim < 0:
                break
            if init_mode == 'free_nongoal':
                acc = self.fault_free_accepting(inp, cycles)
                front = {s: 0 for s in range(1 << len(self.net.qs)) if s not in acc}
            else:
                front = {s: 0 for s in self.init_states(inp, init_mode)}
            for t in range(cycles):
                nxt = {}
                for s, c in front.items():
                    r = lim - c
                    if r < 0:
                        continue
                    lanes, hit = self.step(s, inp, r)
                    _, _, _, size = self.layout(r)
                    for j in range(r + 1):
                        if hit & size[j]:
                            best = c + j; lim = best - 1
                            break
                        for ns, _ in self._split(size[j], lanes):
                            if nxt.get(ns, kmax + 1) > c + j:
                                nxt[ns] = c + j
                    if lim < 0:
                        break
                front = {s: c for s, c in nxt.items() if c <= lim}
                if lim < 0 or not front:
                    break
        return best

    # ------------------------------------------------------------ replay of one concrete run
    def simulate(self, init_state, inp, faults, cycles):
        """faults: iterable of (cycle, site net). Returns (list of observed goal hits per cycle, list of states)."""
        by_t = {}
        for t, b in faults:
            if b not in self.site_idx:
                raise OracleError(f'net {b} is not a fault site')
            by_t.setdefault(t, set()).add(b)
        net = self.net
        s = init_state
        hits, states = [], [s]
        for t in range(cycles):
            f = by_t.get(t, ())
            v = {'0': 0, '1': 1}
            for i, q in enumerate(net.qs):
                v[q] = ((s >> i) & 1) ^ (q in f)
            for i, b in enumerate(net.in_bits):
                v[b] = ((inp >> i) & 1) ^ (b in f)
            for y in net.order:
                ty, ins = net.gates[y]
                if ty == '$_AND_': x = v[ins[0]] & v[ins[1]]
                elif ty == '$_OR_': x = v[ins[0]] | v[ins[1]]
                elif ty == '$_XOR_': x = v[ins[0]] ^ v[ins[1]]
                elif ty == '$_NOT_': x = 1 - v[ins[0]]
                else: x = v[ins[1]] if v[ins[2]] else v[ins[0]]
                v[y] = x ^ (y in f)
            hits.append(all(v[b] == want for b, want in self.goal))
            s = sum(1 << i for i, (d, _) in enumerate(net.flops) if v[d])
            states.append(s)
        return hits, states
