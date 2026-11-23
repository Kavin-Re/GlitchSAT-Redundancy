"""Netlist-level fixes that need no re-synthesis: remove single points reported by the merge lint by giving every
copy group its own copy of the shared logic, and measure consumer masks.

Single points come from the merge lint written for the attack-surface work (scripts/merge_lint.py there). It is used
when it can be imported (GLITCHSAT_SURFACE=<dir with merge_lint.py>, and GLITCHSAT_ROOT=<repository root>);
otherwise the same shared-net computation is done here (`shared_nets`).
"""
import os, sys
from .netlist import Netlist


def parse_groups(s):
    return [[int(x) for x in g.split(',') if x.strip()] for g in s.split(';') if g.strip()]


def decision_nets(nl, goal_out='boot_word'):
    """Goal bit i -> the net that decides its next value (D of the flop when the goal bit is a flop output)."""
    dq = {q: d for d, q, _ in nl.flops}
    return [dq.get(b, b) for b in nl.ports[goal_out][1]]


def _input_dependent(nl):
    dep = set(nl.input_bits())
    for y in nl.topo():
        if any(x in dep for x in nl.fanins(y)):
            dep.add(y)
    return dep


def group_cones(nl, groups, goal_out='boot_word'):
    """Per group: the input-dependent gates in the combinational cone of the group's decision nets."""
    dec, dep = decision_nets(nl, goal_out), _input_dependent(nl)
    cones = []
    for g in groups:
        seen, stack = set(), [dec[i] for i in g]
        while stack:
            x = stack.pop()
            if x in nl.gates and x in dep and x not in seen:
                seen.add(x)
                stack.extend(nl.fanins(x))
        cones.append(seen)
    return cones


def shared_nets(nl, groups, goal_out='boot_word'):
    cones = group_cones(nl, groups, goal_out)
    out = {}
    for y in nl.gates:
        own = [i for i, c in enumerate(cones) if y in c]
        if len(own) > 1:
            out[y] = own
    return out


def _rel(p):
    """Path as written into evidence files: relative to ext/harden, never an absolute home path."""
    return os.path.relpath(os.path.abspath(p), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def run_lint(path, top, groups=None, goal_out='boot_word'):
    """The external merge lint, or None when it is not available."""
    d = os.environ.get('GLITCHSAT_SURFACE')
    cands = [d] if d else []
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [os.path.join(here, '..', '..', 'surface', 'scripts'), os.path.join(here, '..', '..', '..', 'scripts')]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'merge_lint.py')):
            if c not in sys.path:
                sys.path.insert(0, c)
            try:
                import merge_lint
                r = merge_lint.lint(merge_lint.load(path, top), goal_out, groups=groups, netlist_path=path)
                return dict(source=_rel(os.path.join(c, 'merge_lint.py')), verdict=r.get('verdict'), mode=r.get('mode'),
                            single_points=len(r.get('single_points', [])), shared_nets=len(r.get('shared_nets', [])),
                            examples=[p.get('net') for p in r.get('single_points', [])[:5]])
            except Exception as e:      # the lint is optional evidence, never a reason to stop
                return dict(source=_rel(c), error=f'{type(e).__name__}: {e}')
    return None


def unmerge(nl, groups, goal_out='boot_word'):
    """Give each group its own copy of every gate that two or more groups share.

    Group 0 keeps the original gates; each other group gets clones (marked keep) and its private logic and decision
    nets are rewired to them. The logic function is unchanged (every clone computes what its original computes); the
    caller re-checks that by simulation. Returns (new netlist, info)."""
    cones = group_cones(nl, groups, goal_out)
    shared = shared_nets(nl, groups, goal_out)
    out = nl.copy()
    nxt = nl.max_bit() + 1
    order = nl.topo()
    added = 0
    for gi in range(1, len(groups)):
        clone = {}
        for y in order:
            if y in shared and gi in shared[y]:
                clone[y] = nxt
                nxt += 1
        mp = lambda x: clone.get(x, x)
        for y, c in clone.items():
            t, a, b, s = nl.gates[y]
            out.gates[c] = (t, mp(a), mp(b) if b is not None else None, mp(s) if s is not None else None)
            out.names[c] = f'{nl.name(y)}__g{gi}'
            out.cellnames[c] = f'{nl.cellnames.get(y, "g" + str(y))}__g{gi}'
            out.keep_cells.add(c)
            added += 1
        for y in cones[gi]:
            if y in shared:
                continue
            t, a, b, s = out.gates[y]
            out.gates[y] = (t, mp(a), mp(b) if b is not None else None, mp(s) if s is not None else None)
        gbits = {nl.ports[goal_out][1][i] for i in groups[gi]}
        out.flops = [(mp(d) if q in gbits else d, q, init) for d, q, init in out.flops]
        if any(b in clone for b in gbits):     # a goal bit driven directly by a shared gate
            d, bits = out.ports[goal_out]
            out.ports[goal_out] = (d, [mp(b) if i in groups[gi] else b for i, b in enumerate(bits)])
    for y in shared:
        out.keep_cells.add(y)
    # remove gates nothing reads any more
    live, stack = set(), [d for d, _, _ in out.flops] + [b for _, (dr, bits) in out.ports.items() if dr == 'output' for b in bits]
    while stack:
        x = stack.pop()
        if x in out.gates and x not in live:
            live.add(x)
            stack.extend(out.fanins(x))
    for y in [y for y in out.gates if y not in live]:
        del out.gates[y]
    left = shared_nets(out, groups, goal_out)
    return out, dict(shared_before=len(shared), clones_added=added, shared_after=len(left), gates_before=len(nl.gates), gates_after=len(out.gates))
