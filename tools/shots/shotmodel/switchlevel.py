"""Switch-level evaluation of the PDK transistor netlists (SPICE .subckt) that ship with the repository.

Used only as a CHECK of the hand-written function table in cells.py: an nfet conducts when its gate is 1, a pfet when
its gate is 0; a node connected to VGND through conducting transistors is 0, to VPWR is 1. Nodes that are not driven
keep their previous value (charge storage), which is what lets the same routine exercise the flip-flop.
No strengths, no timing, no analogue behaviour.
"""
import re


def read_subckts(path, wanted=None):
    """name -> (ports, [(drain, gate, source, 'n'|'p')]); subckts that are not flat MOS netlists are skipped."""
    out = {}
    cur = None
    with open(path) as f:
        for line in f:
            if line.startswith(".subckt"):
                t = line.split()
                cur = t[1] if (wanted is None or t[1] in wanted) else None
                if cur is not None:
                    out[cur] = (t[2:], [])
            elif line.startswith(".ends"):
                cur = None
            elif cur is not None and line[:1] in "XM":
                t = line.split()
                model = t[5]
                if "pfet" in model:
                    ty = "p"
                elif "nfet" in model:
                    ty = "n"
                else:                      # hierarchical or non-MOS subckt: not supported, drop it
                    del out[cur]
                    cur = None
                    continue
                out[cur][1].append((t[1], t[2], t[3], ty))
    return out


def _reach(devs, val, rail, other):
    """nodes connected to `rail` through conducting transistors, without passing through the other rail"""
    adj = {}
    for d, g, s, ty in devs:
        if (val[g] == 1) == (ty == "n"):
            adj.setdefault(d, []).append(s)
            adj.setdefault(s, []).append(d)
    seen, stack = {rail}, [rail]
    while stack:
        x = stack.pop()
        for y in adj.get(x, ()):
            if y not in seen and y != other:
                seen.add(y)
                stack.append(y)
    return seen


def settle(devs, val, max_sweeps=500):
    """Relax node values in place until stable. val: node -> 0/1 for every node (inputs and rails included).
    One node changes per sweep (sequential relaxation). A node that sees both rails keeps its value during the
    relaxation; if any node still sees both rails once stable, the evaluation is rejected."""
    skip = {"VPWR", "VGND", "__inputs__"} | set(val["__inputs__"])
    for _ in range(max_sweeps):
        up, dn = _reach(devs, val, "VPWR", "VGND"), _reach(devs, val, "VGND", "VPWR")
        changed = False
        for n in val:
            if n in skip:
                continue
            new = val[n] if (n in up) == (n in dn) else 1 if n in up else 0
            if new != val[n]:
                val[n] = new
                changed = True
                break
        if not changed:
            if (up & dn) - skip or "VGND" in _reach(devs, val, "VPWR", None):
                raise RuntimeError("contention (a node sees both rails) in the settled state")
            return val
    raise RuntimeError("switch-level evaluation did not settle")


def _nodes(ports, devs):
    ns = set(ports)
    for d, g, s, _ in devs:
        ns.update((d, g, s))
    return ns


def comb_truth_table(subckt, in_pins, out_pin):
    """Truth table (index = sum(pin_i << i), pins in the given order) of a static cell, from its transistors.
    Every input vector is evaluated from two different starting charges (all 0, all 1); they must agree."""
    ports, devs = subckt
    tt = []
    for x in range(1 << len(in_pins)):
        res = []
        for start in (0, 1):
            val = {n: start for n in _nodes(ports, devs)}
            val.update(VPWR=1, VGND=0, VPB=1, VNB=0)
            for i, p in enumerate(in_pins):
                val[p] = (x >> i) & 1
            val["__inputs__"] = set(in_pins) | {"VPB", "VNB"}
            settle(devs, val)
            res.append(val[out_pin])
        if res[0] != res[1]:
            raise RuntimeError("output depends on stored charge: not a static combinational cell")
        tt.append(res[0])
    return tuple(tt)


def flop_trace(subckt, stimulus, clk="CLK", d="D", q="Q"):
    """Apply a list of (clk, d) input pairs one after the other; return the list of settled Q values."""
    ports, devs = subckt
    val = {n: 0 for n in _nodes(ports, devs)}
    val.update(VPWR=1, VGND=0, VPB=1, VNB=0)
    val["__inputs__"] = {clk, d, "VPB", "VNB"}
    out = []
    for c, dv in stimulus:
        val[clk], val[d] = c, dv
        settle(devs, val)
        out.append(val[q])
    return out
