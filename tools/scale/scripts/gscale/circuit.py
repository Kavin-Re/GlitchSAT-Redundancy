"""Circuit and Problem: the question that is asked, independent of how it is solved.

Circuit   primitive gates (AND, OR, XOR, NOT, MUX), D flops with a known power-up value, input bits.
Problem   horizon N, how each input behaves (one value for the whole run, a new value every cycle, or tied), the
          set of nets that may be flipped, and the goal:
            goal   list of (net, bit): all must hold at one cycle t < N (the "hit");
            quiet  list of (net, bit): must hold at every cycle <= t (for example "alert stayed 0");
            neq    (nets, key): the value on these run-constant input nets must differ from key.
Fault model (the one of scripts/glitchsat.py): a fault flips one net (a gate output or a flop Q) during one cycle;
a Q flip changes what the readers of Q see in that cycle, the stored value is not rewritten.
"""
import collections

AND, OR, XOR, NOT, MUX = 'AND', 'OR', 'XOR', 'NOT', 'MUX'
_YOSYS = {'$_AND_': AND, '$_OR_': OR, '$_XOR_': XOR, '$_NOT_': NOT, '$_MUX_': MUX}


class CircuitError(Exception):
    pass


class Circuit:
    def __init__(self):
        self.gates = {}      # net -> (op, fanins); MUX fanins are (s, b, a) meaning s ? b : a
        self.flops = {}      # q net -> (d net, init bool)
        self.inputs = {}     # net -> (port, index)
        self.names = {}      # net -> readable name
        self.cell = {}       # net -> name of the cell that drives it
        self.ports = {}      # port -> (direction, [nets])

    def name(self, b):
        return self.names.get(b, str(b))

    def fanins(self, b):
        g = self.gates.get(b)
        return g[1] if g else ()

    def dist(self, roots):
        """dist[b] = least number of clock edges between net b and one of the root nets (backward cone)."""
        dist = {}; dq = collections.deque()
        for b in roots:
            if isinstance(b, int) and b not in dist:
                dist[b] = 0; dq.append(b)
        while dq:
            b = dq.popleft()
            if b in self.gates: nxt = [(f, dist[b]) for f in self.gates[b][1]]
            elif b in self.flops: nxt = [(self.flops[b][0], dist[b] + 1)]
            else: nxt = []
            for f, d in nxt:
                if isinstance(f, int) and (f not in dist or d < dist[f]):
                    dist[f] = d; dq.append(f)
        return dist

    def topo(self, roots):
        """Gates in the combinational cone of the roots, fan-ins first. Raises on loops and undriven nets."""
        order = []; state = {}
        for root in roots:
            stack = [root]
            while stack:
                b = stack[-1]
                if not isinstance(b, int):
                    if b not in ('0', '1'):
                        raise CircuitError('constant %r (unknown value) in the logic cone; refusing' % (b,))
                    stack.pop(); continue
                if state.get(b) == 2 or b in self.inputs or b in self.flops:
                    stack.pop(); continue
                if b not in self.gates:
                    raise CircuitError('net %s is used but has no driver and is not an input' % self.name(b))
                pend = [f for f in self.gates[b][1]
                        if isinstance(f, int) and f in self.gates and state.get(f) != 2]
                if pend:
                    if state.get(b) == 1 and any(state.get(f) == 1 for f in pend):
                        raise CircuitError('combinational loop through net %s' % self.name(b))
                    state[b] = 1; stack.extend(pend); continue
                for f in self.gates[b][1]:
                    if not isinstance(f, int) and f not in ('0', '1'):
                        raise CircuitError('constant %r (unknown value) in the logic cone; refusing' % (f,))
                    if isinstance(f, int) and f not in self.gates and f not in self.inputs and f not in self.flops:
                        raise CircuitError('net %s is used but has no driver and is not an input' % self.name(f))
                state[b] = 2; order.append(b); stack.pop()
        return order

    def stats(self):
        return dict(gates=len(self.gates), flops=len(self.flops), inputs=len(self.inputs))


def from_engine(nl, clock_ports=('clk',)):
    """Circuit from a scripts/glitchsat.py Netlist (which has already rejected malformed input)."""
    c = Circuit()
    for y, (cn, ty, con) in nl.drivers.items():
        if ty not in _YOSYS:
            raise CircuitError('unsupported cell ' + str(ty))
        if ty == '$_MUX_': fi = (con['S'][0], con['B'][0], con['A'][0])
        elif ty == '$_NOT_': fi = (con['A'][0],)
        else: fi = (con['A'][0], con['B'][0])
        c.gates[y] = (_YOSYS[ty], fi); c.cell[y] = cn
    for cn, d, q in nl.dffs:
        c.flops[q] = (d, bool(nl.init.get(q, False))); c.cell[q] = cn
    for p, v in nl.ports.items():
        c.ports[p] = (v['direction'], list(v['bits']))
        if v['direction'] == 'input' and p not in clock_ports:
            for i, b in enumerate(v['bits']):
                if isinstance(b, int):
                    c.inputs[b] = (p, i)
    c.names = dict(nl.names)
    return c


class Problem:
    def __init__(self, circ, N, goal, quiet=(), neq=None, in_mode=None, sites=None, label=''):
        self.circ, self.N = circ, int(N)
        self.goal = [(b, bool(v)) for b, v in goal]
        self.quiet = [(b, bool(v)) for b, v in quiet]
        self.neq = neq                      # (list of input nets LSB first, key) or None
        self.in_mode = dict(in_mode or {})  # net -> 'const' | 'cycle' | 0 | 1   (default 'const')
        self.sites = set(sites) if sites is not None else set(circ.gates) | set(circ.flops)
        self.label = label
        if self.N < 1:
            raise CircuitError('horizon must be at least 1 cycle')
        if not self.goal:
            raise CircuitError('empty goal')
        for b in self.sites:
            if b not in circ.gates and b not in circ.flops:
                raise CircuitError('fault site %s is neither a gate output nor a flop output' % circ.name(b))
        if neq:
            for b in neq[0]:
                if self.mode(b) != 'const':
                    raise CircuitError('the "differs from key" input must be constant over the run')

    def mode(self, b):
        return self.in_mode.get(b, 'const')

    def observed_nets(self):
        return [b for b, _ in self.goal + self.quiet if isinstance(b, int)]


def engine_problem(nl, N, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, bad_only=True):
    """The question of scripts/glitchsat.py: goal port == goal value at some cycle < N, attacker input != key, every
    input except clk free and constant over the run, every gate output and flop Q may be flipped."""
    ports = nl.ports
    if goal_out not in ports or ports[goal_out].get('direction') != 'output':
        raise CircuitError('goal output %r is not an output port' % goal_out)
    if attack_in not in ports or ports[attack_in].get('direction') != 'input':
        raise CircuitError('attacker input %r is not an input port' % attack_in)
    c = from_engine(nl)
    goal = []
    for i, b in enumerate(ports[goal_out]['bits']):
        if not isinstance(b, int) and b not in ('0', '1'):
            raise CircuitError('goal bit %d is %r (unknown value); refusing' % (i, b))
        goal.append((b, bool((goal_value >> i) & 1)))
    ab = list(ports[attack_in]['bits'])
    return Problem(c, N, goal, neq=(ab, key & ((1 << len(ab)) - 1)) if bad_only else None, label=nl.top)
