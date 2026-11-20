#!/usr/bin/env python3
"""glitchsat: bounded fault-injection model checker for gate-level Verilog (Yosys JSON + z3).

Fault model (MODELLED, not physical): a fault is a single-cycle bit flip of
  (a) the output net of any combinational gate, or (b) the Q net of any flip-flop, at one clock cycle t.
At most K faults in total over cycles 0..N-1. The attacker input (default `sig`) is a free value held constant.
Attack goal: some output port equals a goal value (default boot_word == 0x96) at some cycle < N while the
attacker input differs from the legitimate key.
Verdicts are BOUNDED: NO_ATTACK_UP_TO_BOUND means no attack with <=K faults within N cycles. It is not a proof for
more cycles or more faults.
"""
import argparse, json, os, subprocess, sys, time, hashlib, collections
from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, PbLe, sat, unsat,
                is_true, simplify, set_param)

HERE = os.path.dirname(os.path.abspath(__file__))
NOTE = ("BOUNDED, NOT UNBOUNDED: verdict holds only for <= {k} single-cycle bit-flip faults (gate outputs and flop Q) "
        "within {n} cycles on this synthesized netlist. It says nothing about more faults, longer runs, other fault "
        "types (stuck-at, multi-bit/spatial, clock/voltage effects), or physical feasibility. Toy design; modelled faults.")


# ---------------------------------------------------------------- netlist
class Netlist:
    def __init__(self, path, top):
        self.m = json.load(open(path))['modules'][top]
        m = self.m
        self.top = top
        self.ports = m['ports']
        self.drivers = {}   # net -> (cellname, type, connections)
        self.dffs = []      # (cellname, D, Q)
        for cn, c in m['cells'].items():
            t, con = c['type'], c['connections']
            if t == '$_DFF_P_':
                self.dffs.append((cn, con['D'][0], con['Q'][0]))
            else:
                self.drivers[con['Y'][0]] = (cn, t, con)
        self.names = {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, f"{n}[{i}]" if len(x['bits']) > 1 else n)
        self.init = {}
        for n, x in m['netnames'].items():
            iv = x['attributes'].get('init')
            if iv:
                for i, b in enumerate(reversed(iv)):
                    self.init[x['bits'][i]] = (b == '1')
        self.qs = [q for _, _, q in self.dffs]
        for q in self.qs:
            self.init.setdefault(q, False)
        self.dq = {q: d for _, d, q in self.dffs}

    def fanins(self, b):
        if b in self.drivers:
            _, t, con = self.drivers[b]
            return [v[0] for p, v in con.items() if p != 'Y']
        return []

    def stats(self):
        return dict(gates=len(self.drivers), flops=len(self.dffs))

    def coi_and_dist(self, goal_bits):
        """Backward cone of the goal output bits. dist[b] = min #clock edges between a flip of b and a goal bit."""
        dist = {}
        dq = collections.deque()
        for b in goal_bits:
            if isinstance(b, int):
                dist[b] = 0; dq.append(b)
        while dq:
            b = dq.popleft()
            if b in self.drivers:
                nxt = [(f, dist[b]) for f in self.fanins(b)]
            elif b in self.dq:
                nxt = [(self.dq[b], dist[b] + 1)]
            else:
                nxt = []
            for f, d in nxt:
                if isinstance(f, int) and (f not in dist or d < dist[f]):
                    dist[f] = d; dq.append(f)
        return dist


# ---------------------------------------------------------------- model + solve
def build(nl, N, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3,
          reduce='full', bad_only=True, fixed_in=None, goal_mask=0xFF):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    inputs = {p: BitVec(f'in_{p}', len(v['bits'])) for p, v in ports.items()
              if v['direction'] == 'input' and p != 'clk'}
    inbit = {}
    for p, v in ports.items():
        if p in inputs:
            for i, b in enumerate(v['bits']):
                inbit[b] = Extract(i, i, inputs[p]) == 1
    dist = nl.coi_and_dist(goal_bits)
    allsites = list(nl.qs) + list(nl.drivers.keys())
    if reduce == 'none':
        usable = lambda t, b: True
    elif reduce == 'coi':
        usable = lambda t, b: b in dist
    else:  # full: cone of influence + temporal reach (flip must be able to reach goal bit before the horizon)
        usable = lambda t, b: b in dist and t + dist[b] <= N - 1
    F = {}
    for t in range(N):
        for b in allsites:
            if usable(t, b):
                F[(t, b)] = Bool(f"f_{t}_{b}")
    state = {q: BoolVal(nl.init[q]) for q in nl.qs}
    hits = []
    simp = reduce != 'none'
    for t in range(N):
        val = {}

        def get(b):
            if b == '0' or b == 'x' or b == 'z': return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b in val: return val[b]
            if b in inbit: return inbit[b]
            if b in state: v = state[b]
            else:
                _, ty, con = nl.drivers[b]
                g = lambda p: get(con[p][0])
                if ty == '$_AND_': v = And(g('A'), g('B'))
                elif ty == '$_OR_': v = Or(g('A'), g('B'))
                elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                elif ty == '$_NOT_': v = Not(g('A'))
                elif ty == '$_MUX_': v = If(g('S'), g('B'), g('A'))
                else: raise Exception('unsupported cell ' + ty)
            if (t, b) in F: v = Xor(v, F[(t, b)])
            if simp: v = simplify(v)
            val[b] = v
            return v
        nxt = {q: get(d) for q, d in nl.dq.items()}
        w = [get(b) for b in goal_bits]
        hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w)) if (goal_mask >> i) & 1]))
        state = nxt
    s = Solver()
    s.add(Or(*hits))
    ain = inputs[attack_in]
    if bad_only: s.add(ain != key)
    if fixed_in is not None: s.add(ain == fixed_in)
    return s, F, inputs, dict(sites_total=len(allsites) * N, sites_modelled=len(F), reduce=reduce)


def solve(nl, N, k, timeout_ms=0, minimize=True, **kw):
    t0 = time.time()
    s, F, inputs, info = build(nl, N, **kw)
    info['build_s'] = round(time.time() - t0, 3)
    if timeout_ms: s.set('timeout', timeout_ms)
    allf = list(F.values())
    if allf: s.add(PbLe([(f, 1) for f in allf], k))
    elif k > 0: pass
    t0 = time.time(); r = s.check(); info['solve_s'] = round(time.time() - t0, 3)
    if r == unsat: return 'NO_ATTACK_UP_TO_BOUND', info, None
    if r != sat: return 'UNKNOWN_TIMEOUT', info, None
    def extract(mod):
        return [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]
    mod = s.model(); best = extract(mod)
    t0 = time.time()
    while minimize and best:
        s.push(); s.add(PbLe([(f, 1) for f in allf], len(best) - 1))
        if s.check() == sat:
            mod = s.model(); best = extract(mod); s.pop()
        else:
            s.pop(); break
    info['minimize_s'] = round(time.time() - t0, 3)
    atk = {p: mod.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
    return 'ATTACK_FOUND', info, dict(inputs=atk, faults=sorted(best, key=lambda x: (x[0], x[1])))


def honest_boots(nl, N, **kw):
    """Sanity: fault-free run with the legitimate key reaches the goal."""
    kw = dict(kw); key = kw.get('key', 0xC3)
    v, info, res = solve(nl, N, 0, minimize=False, bad_only=False, fixed_in=key, **kw)
    return v == 'ATTACK_FOUND'


# ---------------------------------------------------------------- explanation
def support(nl, b, memo=None):
    memo = {} if memo is None else memo
    if b in memo: return memo[b]
    if b in nl.drivers:
        r = frozenset().union(*[support(nl, f, memo) for f in nl.fanins(b) if isinstance(f, int)])
    elif b in nl.dq:
        r = frozenset([('flop', b)])
    else:
        r = frozenset([b])
    memo[b] = r; return r

def forward_reach(nl, b, goal_bits, maxcyc):
    """goal bits reachable from b through combinational fanout (<= maxcyc flop crossings)."""
    fan = collections.defaultdict(list)
    for o, (_, _, con) in nl.drivers.items():
        for f in nl.fanins(o): fan[f].append(o)
    for d, q in [(d, q) for _, d, q in nl.dffs]: fan[d].append(('Q', q))
    seen = {(b, 0)}; st = [(b, 0)]; goals = set(goal_bits)
    reach = set()
    while st:
        x, c = st.pop()
        if x in goals: reach.add(x)
        for y in fan.get(x, []):
            if isinstance(y, tuple): y, c2 = y[1], c + 1
            else: c2 = c
            if c2 <= maxcyc and (y, c2) not in seen: seen.add((y, c2)); st.append((y, c2))
    return reach

def explain(nl, res, k_found, N, goal_out='boot_word', attack_in='sig'):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    in_bits = set(ports[attack_in]['bits'])
    faults = res['faults']
    lines, nets = [], []
    for t, b in faults:
        nm = nl.names.get(b, str(b))
        kind = 'flip-flop Q' if b in nl.dq else 'gate output'
        gt = nl.drivers[b][1].strip('$_') if b in nl.drivers else 'DFF'
        sup = support(nl, b)
        n_in = len(sup & in_bits)
        reach = forward_reach(nl, b, goal_bits, N)
        nets.append(dict(net=nm, cycle=t, kind=kind, gate=gt, input_bits_in_fanin_cone=n_in,
                         goal_bits_reached=len(reach), goal_bits_total=len(goal_bits)))
    ncyc = len({t for t, _ in faults})
    if k_found == 1:
        n = nets[0]
        if n['kind'] == 'gate output' and n['goal_bits_reached'] >= len(goal_bits) // 2 and n['input_bits_in_fanin_cone'] > 1:
            summary = (f"SINGLE POINT OF FAILURE: one {n['gate']} gate output, net `{n['net']}`, combines {n['input_bits_in_fanin_cone']} "
                       f"input bits of `{attack_in}` (the redundant checks converge here) and alone drives {n['goal_bits_reached']} of "
                       f"{n['goal_bits_total']} bits of `{goal_out}`. Flipping it for ONE cycle (cycle {n['cycle']}) makes a wrong "
                       f"`{attack_in}` look valid, even though the checks upstream are duplicated.")
            fix = ("Do not let any one net decide. Split the decision across independent bits: give each redundant check its own "
                   "disjoint group of result-word bits (no shared AND/OR of the checks), use a sparse result encoding with Hamming "
                   "distance > fault budget, and make the final accept require all groups to agree bit-by-bit.")
        elif n['kind'] == 'flip-flop Q':
            summary = (f"SINGLE POINT OF FAILURE: the state register bit `{n['net']}` can be flipped for one cycle (cycle {n['cycle']}) "
                       f"and the state/output word then reads as the accept value.")
            fix = ("Encode state with Hamming distance greater than the fault budget (e.g. sparse one-hot-ish codes), add a parity/redundant "
                   "shadow register compared every cycle, and make illegal codes latch a sticky FAIL state.")
        else:
            summary = (f"SINGLE POINT OF FAILURE: gate output `{n['net']}` ({n['gate']}), flipped for one cycle at cycle {n['cycle']}, "
                       f"reaches {n['goal_bits_reached']}/{n['goal_bits_total']} bits of `{goal_out}` and is enough to reach the accept value.")
            fix = ("Duplicate the logic that feeds this net and keep the copies independent (no shared gate), then compare/decide per bit "
                   "instead of through one net.")
    else:
        names = ', '.join(f"`{n['net']}`@{n['cycle']}" for n in nets)
        summary = (f"MINIMUM ATTACK COST = {k_found} faults ({names}). No single net decides, but the faults found hit "
                   f"{'independent redundant copies' if len({n['net'] for n in nets}) == len(nets) else 'repeated nets'}; the attacker needs {k_found} "
                   f"coordinated single-cycle flips (spanning {ncyc} distinct cycle(s)).")
        fix = (f"Raise the cost above the attacker's fault budget: add another independent copy (so quorum needs >{k_found}), "
               "keep every copy's result in its own disjoint output bits, and add a sticky alarm on any disagreement. Re-run the tool at k=%d." % (k_found))
    return dict(summary=summary, fix_pattern=fix, fault_details=nets)


# ---------------------------------------------------------------- CLI
def synth(verilog, top, out, flow='plain'):
    r = subprocess.run([os.path.join(HERE, 'synth.sh'), verilog, top, out, flow], capture_output=True, text=True)
    if r.returncode: sys.exit('synthesis failed:\n' + r.stderr)

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

def run_check(verilog, top, k, N, out=None, reduce='full', goal_out='boot_word', goal_value=0x96, attack_in='sig',
              key=0xC3, timeout_ms=0, workdir=None, label='MEASURED', flow='plain'):
    workdir = workdir or os.path.join(os.path.dirname(HERE), 'results', 'work')
    os.makedirs(workdir, exist_ok=True)
    jpath = os.path.join(workdir, f'{top}.json' if flow == 'plain' else f'{top}_{flow}.json')
    t0 = time.time()
    if verilog.endswith('.json'):   # pre-synthesized Yosys JSON netlist (e.g. reference/spike_netlists)
        jpath = verilog; flow = 'given-netlist'
    else:
        synth(verilog, top, jpath, flow)
    t_syn = time.time() - t0
    nl = Netlist(jpath, top)
    kw = dict(goal_out=goal_out, goal_value=goal_value, attack_in=attack_in, key=key, reduce=reduce)
    t0 = time.time()
    verdict, info, res = solve(nl, N, k, timeout_ms=timeout_ms, **kw)
    wall = time.time() - t0
    out_d = dict(label=label, tool='glitchsat.py', design=os.path.relpath(verilog, os.path.dirname(HERE)) if os.path.isabs(verilog) else verilog,
                 design_sha256_16=sha(verilog), top=top, synth_flow=flow, verdict=verdict,
                 bound=dict(max_faults=k, cycles=N, fault_model='single-cycle bit flip of any gate output or flop Q',
                            attacker_input=f'`{attack_in}` free, held constant, != key 0x{key:02X}',
                            goal=f'{goal_out} == 0x{goal_value:X} at some cycle < {N}'),
                 note=NOTE.format(k=k, n=N), netlist=nl.stats(),
                 honest_key_boots_fault_free=honest_boots(nl, N, **kw),
                 model=info, runtime_s=dict(synth=round(t_syn, 3), solve_and_minimize=round(wall, 3)),
                 netlist_json=os.path.relpath(jpath, os.path.dirname(HERE)))
    if res:
        faults = [dict(net=nl.names.get(b, str(b)), net_id=b, cycle=t, kind='flop_Q' if b in nl.dq else 'gate_output') for t, b in res['faults']]
        out_d['min_faults'] = len(faults)
        out_d['faults'] = faults
        out_d['attacker_input'] = {p: f'0x{v:02X}' if v < 256 else hex(v) for p, v in res['inputs'].items()}
        out_d['attacker_input_raw'] = res['inputs']
        out_d['explanation'] = explain(nl, res, len(faults), N, goal_out, attack_in)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        json.dump(out_d, open(out, 'w'), indent=2)
    return out_d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('check', help='bounded attack search')
    c.add_argument('verilog'); c.add_argument('--top', required=True)
    c.add_argument('--k', type=int, required=True, help='max number of faults'); c.add_argument('--cycles', type=int, required=True)
    c.add_argument('--out'); c.add_argument('--reduce', choices=['none', 'coi', 'full'], default='full')
    c.add_argument('--goal-out', default='boot_word'); c.add_argument('--goal-value', type=lambda x: int(x, 0), default=0x96)
    c.add_argument('--attack-input', default='sig'); c.add_argument('--key', type=lambda x: int(x, 0), default=0xC3)
    c.add_argument('--timeout-ms', type=int, default=0)
    c.add_argument('--flow', choices=['plain', 'opt'], default='plain', help='synthesis flow (see scripts/synth.sh)')
    a = ap.parse_args()
    r = run_check(a.verilog, a.top, a.k, a.cycles, a.out, a.reduce, a.goal_out, a.goal_value, a.attack_input, a.key, a.timeout_ms, flow=a.flow)
    print(f"{a.top}: {r['verdict']}  (k<={a.k}, cycles={a.cycles}, reduce={a.reduce})  solve={r['runtime_s']['solve_and_minimize']}s")
    if 'faults' in r:
        print('  min faults:', r['min_faults'], [(f['net'], f['cycle']) for f in r['faults']], 'input', r['attacker_input'])
        print('  ' + r['explanation']['summary']); print('  FIX: ' + r['explanation']['fix_pattern'])
    print('  ' + r['note'])
    sys.exit(0 if r['verdict'] in ('NO_ATTACK_UP_TO_BOUND', 'ATTACK_FOUND') else 2)

if __name__ == '__main__':
    main()
