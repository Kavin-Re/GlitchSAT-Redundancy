"""Security goals on a chip, and the goal-directed slice that the exact search works on.

A goal says: these nets have these values in one cycle (optionally for `hold` consecutive cycles), these other
nets stayed at their quiet values up to then, and (optionally) an attacker-controlled input word differs from a
key. build() turns it into a gscale Problem on a slice of the chip:

  slice = every net whose least number of clock edges to an observed net is at most T-1.

Soundness (README section 4.2): a net outside the slice cannot change any observed value within T cycles, so the
slice has exactly the same attacks as the chip for this goal and this T. A flop at distance exactly T-1 only
matters through its value in cycle 0; its D input is cut and it holds.
"""
import re

from . import gscale
from .chip import ChipError

G = gscale()
C = G.circuit
AND, OR, XOR, NOT, MUX = C.AND, C.OR, C.XOR, C.NOT, C.MUX


def parse_assign(chip, specs):
    """['name=value', 'name[3]=1', ...] -> [(net, bool)]; a multi-bit name spreads the value over its bits."""
    out = []
    for sp in specs or []:
        name, eq, val = str(sp).partition('=')
        name = name.strip()
        if not eq:
            raise ChipError('expected NAME=VALUE, got %r' % sp)
        v = int(val.strip(), 0)
        if re.match(r'^.*\[\d+\]$', name) or (name in chip.bits and len(chip.bits[name]) == 1):
            out.append((chip.net(name), bool(v & 1)))
        else:
            for i, b in enumerate(chip.word(name)):
                out.append((b, bool((v >> i) & 1)))
    for b, _ in out:
        if not isinstance(b, int):
            raise ChipError('goal bit is a constant in the netlist (%r): choose another net' % (b,))
    return out


class Built:
    pass


def build(chip, goal, reset=None, state=None):
    """goal: dict(id, hit=[...], hold=1, quiet=[...], attacker=dict(port, differs_from), fix={port: value},
    cycles=T, const_inputs=[ports held at one free value for the whole run]).
    reset: dict(port, active) -> that input is tied inactive during the analysed window.
    state: {flop: True/False/None} at reset release (from sim.reset_state); None values are free. Without `state`
    every flop starts at its initial/0 value."""
    src = chip.circ
    T = int(goal['cycles'])
    hit = parse_assign(chip, goal.get('hit'))
    quiet = parse_assign(chip, goal.get('quiet'))
    if not hit:
        raise ChipError('goal %s: empty hit condition' % goal.get('id'))
    hold = int(goal.get('hold', 1))

    dist = src.dist([b for b, _ in hit + quiet])
    # monitor flops add (hold-1) edges in front of the hit nets
    keep = {}
    for b, d in dist.items():
        if d <= T - 1:
            keep[b] = d

    c = C.Circuit()
    nxt = [chip._next + 1]

    def new(name):
        nxt[0] += 1
        c.names[nxt[0]] = name
        return nxt[0]
    sites = set()
    in_mode = {}
    first = None
    init_in = {}
    cut = 0
    for b, d in keep.items():
        if b in src.gates:
            c.gates[b] = src.gates[b]
            if b in chip.sites: sites.add(b)
        elif b in src.flops:
            dn, _ = src.flops[b]
            if d == T - 1 or (isinstance(dn, int) and dn not in keep):
                dn = b; cut += 1                                   # only its cycle-0 value matters
            v0 = state.get(b) if state is not None else bool(chip.init_attr.get(b, False))
            if v0 is None:
                if first is None:
                    first = new('$first_cycle')
                    c.flops[first] = ('0', True)
                raw = new('$raw$' + src.name(b))
                iv = new('$init$' + src.name(b))
                c.inputs[iv] = ('$init', len(init_in)); in_mode[iv] = 'const'
                init_in[iv] = b
                c.flops[raw] = (dn, False)
                c.gates[b] = (MUX, (first, iv, raw))
                sites.add(b)
            else:
                c.flops[b] = (dn, bool(v0))
                sites.add(b)
        elif b in src.inputs:
            c.inputs[b] = src.inputs[b]
            in_mode[b] = 'cycle'
        else:
            raise ChipError('net %s has no driver' % src.name(b))
        if b in src.names: c.names[b] = src.names[b]
        if b in src.cell: c.cell[b] = src.cell[b]
    for p, (d, bits) in src.ports.items():
        c.ports[p] = (d, [b for b in bits])

    def port_bits(p):
        if p not in src.ports or src.ports[p][0] not in ('input', 'inout'):
            raise ChipError('%r is not an input port' % p)
        return src.ports[p][1]
    tied = {}
    if reset:
        for b in port_bits(reset['port']):
            tied[b] = 0 if int(reset.get('active', 0)) else 1
    for p, val in (goal.get('fix') or {}).items():
        for i, b in enumerate(port_bits(p)):
            tied[b] = (int(val) >> i) & 1
    for b, v in tied.items():
        if b in c.inputs: in_mode[b] = v
    for p in goal.get('const_inputs') or []:
        for b in port_bits(p):
            if b in c.inputs and b not in tied: in_mode[b] = 'const'
    neq = None
    att = goal.get('attacker')
    if att:
        ab = list(port_bits(att['port']))
        for b in ab:
            if b not in c.inputs:               # outside the slice: still needed by the "differs" condition
                c.inputs[b] = src.inputs[b]; c.names[b] = src.name(b)
            in_mode[b] = 'const'
        neq = (ab, int(att['differs_from']) & ((1 << len(ab)) - 1))

    # monitor: hit condition as fault-free logic, held for `hold` cycles
    goal_list = list(hit)
    if hold > 1:
        cond = None
        for b, v in hit:
            x = b
            if not v:
                x = new('$mon$not'); c.gates[x] = (NOT, (b,))
            if cond is None: cond = x
            else:
                y = new('$mon$and'); c.gates[y] = (AND, (cond, x)); cond = y
        if cond in sites or cond in c.flops or cond in c.inputs or cond in [b for b, _ in hit]:
            y = new('$mon$cond'); c.gates[y] = (AND, (cond, '1')); cond = y
        goal_list = [(cond, True)]
        prev = cond
        for j in range(1, hold):
            p = new('$mon$held%d' % j)
            c.flops[p] = (prev, False)
            goal_list.append((p, True))
            prev = p

    P = C.Problem(c, T, goal_list, quiet, neq, in_mode, sites, label='%s/%s' % (chip.name, goal.get('id', 'goal')))
    out = Built()
    out.P = P
    out.init_in = init_in
    out.hit, out.quiet, out.hold, out.T = hit, quiet, hold, T
    out.tied = tied
    out.neq = neq
    n_gate_sites = sum(1 for b in sites if b in src.gates)
    n_flop_sites = len(sites) - n_gate_sites
    prof = {}
    for b in sites:
        prof[keep[b]] = prof.get(keep[b], 0) + 1
    info = chip.info
    out.info = dict(
        cycles=T, slice_cells=len(sites), slice_gates=n_gate_sites, slice_flops=n_flop_sites,
        chip_cells=info['cells'], chip_gates=info['gates'], chip_flops=info['flops'],
        slice_share=round(len(sites) / max(1, info['cells']), 6),
        slice_inputs=sum(1 for b in c.inputs if not c.inputs[b][0].startswith('$')),
        free_values_in_slice={k: n for k, n in _count(chip.free[b].split(':')[0] for b in c.inputs if b in chip.free).items()},
        flops_free_initial_value=len(init_in), flops_cut_at_horizon=cut,
        cells_by_distance={str(k): v for k, v in sorted(prof.items())},
        fault_candidates=len(sites) * T,
    )
    return out


def _count(it):
    d = {}
    for x in it: d[x] = d.get(x, 0) + 1
    return d


def cone_growth(chip, goal, tmax):
    """Slice size (cells) for T = 1..tmax: how fast the cone of influence of this goal grows."""
    hit = parse_assign(chip, goal.get('hit'))
    quiet = parse_assign(chip, goal.get('quiet'))
    dist = chip.circ.dist([b for b, _ in hit + quiet])
    hist = {}
    for b, d in dist.items():
        if b in chip.sites: hist[d] = hist.get(d, 0) + 1
    out = []; acc = 0
    for t in range(1, tmax + 1):
        acc += hist.get(t - 1, 0)
        out.append(dict(cycles=t, cells=acc, share=round(acc / max(1, chip.info['cells']), 6)))
    full = sum(hist.values())
    return out, dict(cells_any_depth=full, share_any_depth=round(full / max(1, chip.info['cells']), 6),
                     sequential_depth=max(hist) if hist else 0)


def replay_on_chip(chip, built, comp, witness_raw, state):
    """Referee at chip level: the witness found on the slice is simulated on the WHOLE chip with the compiled
    simulator (independent of gscale's unrolling, reductions, encoder and of gscale.sim.replay)."""
    ins, faults = witness_raw
    P = built.P
    src = chip.circ
    st = {}
    for q in src.flops:
        v = state.get(q) if state is not None else bool(chip.init_attr.get(q, False))
        st[q] = 1 if v else 0
    for iv, q in built.init_in.items():
        st[q] = 1 if ins.get(iv, False) else 0
    const = {b: (1 if v else 0) for b, v in ins.items() if not isinstance(b, tuple) and b in src.inputs}
    for b, v in built.tied.items(): const[b] = v
    per = {}
    for k, v in ins.items():
        if isinstance(k, tuple) and k[1] in src.inputs:
            per.setdefault(k[0], {})[k[1]] = 1 if v else 0
    fl = {}
    for t, b in faults:
        if b not in chip.sites:
            return dict(ok=False, reason='fault on %s is not a chip fault site' % P.circ.name(b))
        fl.setdefault(t, {})[b] = 1
    watch = [b for b, _ in built.hit + built.quiet]
    def inputs_at(t):
        d = dict(const)
        d.update(per.get(t, {}))
        return d
    tr = comp.run(1, built.T, st, inputs_at, lambda t: fl.get(t), watch)
    run = 0; quiet_ok = True; hit_at = None
    for t, row in enumerate(tr):
        quiet_ok = quiet_ok and all(bool(row[b]) == v for b, v in built.quiet)
        run = run + 1 if all(bool(row[b]) == v for b, v in built.hit) else 0
        if run >= built.hold and quiet_ok and hit_at is None:
            hit_at = t
    neq_ok = True
    if built.neq:
        val = sum(1 << i for i, b in enumerate(built.neq[0]) if ins.get(b, False))
        neq_ok = val != built.neq[1]
    return dict(ok=hit_at is not None and neq_ok, hit_cycle=hit_at, attacker_value_differs=neq_ok)
