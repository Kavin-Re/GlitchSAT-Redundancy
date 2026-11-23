"""Netlist stage: find countermeasures in a gate-level netlist and decide whether each one is still there.

How a countermeasure is followed from stage to stage
  redundant copies    by the Boolean function the copies compute (simulation signature, exact truth table when the
                      design has <= 12 input bits), so renamed or re-mapped copies are still found; hierarchy names
                      are used as extra evidence when they survive. Copies are "independent" when their logic cones
                      share no cell.
  sparse encoding     by the register's flop names; the codes are re-derived by fault-free reachability on the
                      netlist (small designs) and their minimum Hamming distance is compared with the RTL's.
  redundant register  by flop names: are both registers still separate flops?
  alarm               is the alarm net still driven by logic that can be 1?
  multi-bit boolean   are all bits still separate nets?

Verdict rule for N intended copies (R = distinct nets still computing the function, C = groups of them whose cones
share no cell):
  SURVIVED  C >= N
  WEAKENED  2 <= C < N               (some copies share cells, at least two are still independent)
  REMOVED   C <= 1                   (one net, or every copy shares a cell with the others: one fault site acts on all)
When no net computes the function any more (the logic was restructured), the number of independent groups among
the decision flops' input logic is compared with the reference stage instead.
"""
import re

from . import gnet as G
from .model import Countermeasure, StageResult, SURVIVED, WEAKENED, REMOVED, UNTRACKED

MAX_LIST = 8


def _classmap(g):
    if getattr(g, "_cm", None) is None:
        g._cm = g.classes(min_support=1)
    return g._cm


def _short(names, n=MAX_LIST):
    names = list(names)
    return ", ".join(names[:n]) + (f" (+{len(names) - n} more)" if len(names) > n else "")


def _anchor_patterns(cm):
    """Regexes for the net names of the copies' outputs, per copy label."""
    i = cm.intent
    pats = {}
    for inst in i.get("instances", []):
        outs = i.get("outputs", {}).get(inst, {})
        alts = [r"(?:^|[./\\])" + re.escape(inst) + r"[./]" + re.escape(p) + r"$" for p in outs]
        alts += [r"(?:^|[./\\])" + re.escape(w) + r"$" for w in outs.values() if re.fullmatch(r"\w+", w)]
        if alts:
            pats[inst] = "|".join(alts)
    for w in i.get("nets", []):
        pats[w] = r"(?:^|[./\\])" + re.escape(w) + r"$"
    return pats


def _key_token(g, n):
    k, neg = g.sig_key(n)
    return dict(mode=g.sig_mode, inputs=[list(x) for x in g.input_order()], key=k.hex(), exact=g.exact(n))


def _lookup(g, tok):
    if tok is None:
        return None
    g.signatures()
    if tok["mode"] != g.sig_mode or [list(x) for x in g.input_order()] != tok["inputs"]:
        return None
    c = _classmap(g).get(bytes.fromhex(tok["key"]))
    return (c["pos"] + c["neg"]) if c else []


def _dep_cone(g, net):
    """Gate nets in the cone of `net` that depend on a primary input (bitmask over g.order)."""
    in_mask = 0
    for i, l in enumerate(g.leaves):
        if l in g.in_bits:
            in_mask |= 1 << i
    c = g.cone.get(net, 0)
    out = 0
    for i in G._bits(c):
        if g.supp[g.order[i]] & in_mask:
            out |= 1 << i
    return out


def decision_groups(g, sinks):
    """Independent groups among the input-dependent logic in front of the named decision flops / outputs."""
    nets = {}
    for s in sinks:
        kind, nm = s.split(":", 1)
        if kind == "ff":
            for q, f in g.flops.items():
                if nm in g.names.get(q, []):
                    nets[s] = f.d
        else:
            m = re.match(r"(.+)\[(\d+)\]$", nm)
            if m and m.group(1) in g.ports:
                bits = g.ports[m.group(1)][1]
                if int(m.group(2)) < len(bits):
                    nets[s] = bits[int(m.group(2))]
    cones = {s: _dep_cone(g, n) for s, n in nets.items()}
    cones = {s: c for s, c in cones.items() if c}
    keys = sorted(cones)
    parent = {s: s for s in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if cones[a] & cones[b]:
                parent[find(a)] = find(b)
    groups = {}
    for s in keys:
        groups.setdefault(find(s), []).append(s)
    return sorted(groups.values()), len(nets)


# ---------------------------------------------------------------------- detection on a netlist (no RTL needed)
def detect(g, min_support=3):
    """Countermeasure intent visible in the netlist itself: sibling cones, complemented rails, sparse registers."""
    out = []
    cands = []
    for key, c in g.classes(min_support=min_support).items():
        nets = c["pos"] + c["neg"]
        if len(nets) < 2:
            continue
        r = g.roots(nets)
        if len(r["components"]) < 2:
            continue
        roots = [comp[0] for comp in r["components"]]
        if not any(g.sinks(x) for x in roots):
            continue
        cands.append((len(g.support(roots[0])), sum(G._popcount(g.cone[x]) for x in roots), key, c, r))
    cands.sort(key=lambda t: (-t[0], -t[1]))
    taken = 0
    k = 0
    for supp, _, key, c, r in cands:
        mask = 0
        for x in r["roots"]:
            mask |= g.cone[x]
        if mask & ~taken == 0:          # every cell already belongs to a larger detected copy set: a sub-expression
            continue
        if all(g.cone[x] & taken for x in r["roots"]):
            continue
        taken |= mask
        roots = [comp[0] for comp in r["components"]]
        neg = [x for x in roots if x in c["neg"]]
        pos = [x for x in roots if x in c["pos"]]
        kind = "complement_pair" if (pos and neg and len(roots) == 2) else "redundant_copies"
        cm = Countermeasure(
            id=f"{'rails' if kind == 'complement_pair' else 'copies'}:{g.top}.n{k}", kind=kind, origin="netlist-scan",
            where=g.source,
            intent=dict(copies=len(roots), module=g.top, instances=[], nets=[g.name(x) for x in roots],
                        complemented=[g.name(x) for x in neg] if pos and neg else [],
                        what=f"a function of {supp} bits ({_short(sorted({g.leaf_key(l).split('[')[0] for l in g.support(roots[0])}), 4)})"))
        out.append(cm)
        k += 1
    regs = {}
    for q in g.flops:
        for s in g.names.get(q, []):
            m = re.match(r"(.+)\[(\d+)\]$", s)
            if m and "$" not in s:
                regs.setdefault(m.group(1), {})[int(m.group(2))] = q
    seen = set()
    for base, bits in sorted(regs.items()):
        if len(bits) < 3 or sorted(bits) != list(range(len(bits))):
            continue
        reg = [bits[i] for i in range(len(bits))]
        if tuple(reg) in seen:
            continue
        seen.add(tuple(reg))
        codes = g.reachable_codes(reg)
        d = G.min_distance(codes) if codes else None
        if codes and len(codes) >= 3 and d and d >= 2:
            out.append(Countermeasure(
                id=f"encoding:{g.top}.{base.split('.')[-1]}", kind="sparse_encoding", origin="netlist-scan", where=g.source,
                intent=dict(register=base.split(".")[-1], aliases=[], module=g.top, width=len(reg), codes=codes, min_distance=d)))
    return out


# ---------------------------------------------------------------------- checks
def check(cm, g, stage, first):
    """One countermeasure on one netlist. `first` is True for the reference stage (it fixes what is tracked)."""
    fn = {"redundant_copies": _copies, "complement_pair": _copies, "sparse_encoding": _encoding,
          "redundant_register": _dup, "alarm": _alarm, "mubi": _mubi}.get(cm.kind)
    if fn is None:
        return None
    return fn(cm, g, stage, first)


def _copies(cm, g, stage, first):
    n_intent = cm.intent.get("copies", 2)
    ev, meas = [], {}
    pats = _anchor_patterns(cm)
    named = {}
    for lab, pat in pats.items():
        hits = sorted({n for n in g.find(pat).values()}, key=g.name)
        hits = [n for n in hits if n in g.gates] or hits
        if hits:
            named[lab] = hits[0]
    tok = cm.track.get("function")
    if tok is None and named:
        anchors = [n for n in named.values() if n in g.gates]
        if anchors:
            tok = cm.track["function"] = _key_token(g, anchors[0])
            cm.track["function_from"] = stage
    nets = _lookup(g, tok)
    if nets is None and named:
        nets = sorted(set(named.values()), key=g.name)
        ev.append("function signature not comparable at this stage (different primary inputs); copies followed by name")
    if tok is None and nets is None:
        return StageResult(cm.id, stage, UNTRACKED, evidence=[
            "the copies could not be located: no net name of the form " + _short(pats or ["<instance>.<output>"], 3) +
            " exists in this netlist and no earlier stage gave their function"])
    nets = nets or []
    r = g.roots(nets)
    R, C = len(r["roots"]), len(r["components"])
    meas.update(intended=n_intent, distinct_nets=R, independent=C, shared_cells=len({g.cell_of(x) for x in r["shared"]}),
                exact_function=bool(tok and tok.get("exact")))
    if "sinks" not in cm.track and r["roots"]:
        cm.track["sinks"] = sorted({s for x in r["roots"] for s in g.sinks(x)})
    sinks = cm.track.get("sinks", [])
    groups, found = decision_groups(g, sinks) if sinks else ([], 0)
    meas.update(decision_groups=len(groups), decision_bits_found=found)
    if first:
        cm.track["ref_groups"] = len(groups)
        cm.track["ref_independent"] = C
    same = {}
    for lab, n in named.items():
        same.setdefault(n, []).append(lab)
    aliased = [labs for labs in same.values() if len(labs) > 1]
    for labs in aliased:
        ev.append(f"the outputs of copies {', '.join(sorted(labs))} are one and the same net ({g.name(named[labs[0]])})")
    if R:
        ev.append(f"{R} net(s) compute the copies' function: " + _short(g.name(x) for x in r["roots"]))
        meas["copy_cells"] = [g.cell_of(x) for x in r["roots"]][:20]
    if r["shared"]:
        cells = sorted({f"{g.cell_of(x)} [{g.gates[x].type if x not in g.site_cell else g.cell_type.get(g.cell_of(x), '?')}]"
                        for x in r["shared"]})
        ev.append(f"{len(cells)} cell(s) lie in the logic of more than one copy: " + _short(cells))
        meas["shared_cell_names"] = sorted({g.cell_of(x) for x in r["shared"]})[:50]
        meas["shared_on_inputs"] = all(len(g.support(x)) == 1 for x in r["shared"])    # buffer-like cells only
    target = n_intent
    if R == 0:
        ref = cm.track.get("ref_groups")
        ev.append("no net computes the copies' function any more (the logic was restructured)")
        if not sinks or not found:
            verdict = REMOVED if not named else UNTRACKED
            ev.append("the decision flops fed by the copies were not found by name either")
        else:
            ev.append(f"independent groups of input logic in front of the {found} decision bits: {len(groups)} "
                      f"(reference stage: {ref})")
            ref = ref or target
            verdict = SURVIVED if len(groups) >= ref else (WEAKENED if len(groups) >= 2 else REMOVED)
            meas["independent"] = len(groups)
    elif C >= target:
        verdict = SURVIVED
    elif C >= 2:
        verdict = WEAKENED
    else:
        verdict = REMOVED
    n_ind = meas["independent"]
    if verdict == SURVIVED:
        ev.insert(0, f"{n_ind} independent copies of {target} intended, no shared cell")
    elif verdict != UNTRACKED:
        ev.insert(0, f"{n_ind} independent cop{'y' if n_ind == 1 else 'ies'} left of {target} intended"
                     + (f": {R} net(s) still compute the function" + (f" but share {meas['shared_cells']} cell(s)" if r["shared"] else "")
                        if R else ""))
    if first and sinks and len(groups) < min(C, target) and len(groups) <= 1 and C >= 2:
        meas["design_note"] = ("the copies are combined into one net before the decision register (single voter); "
                               "this is in the design itself, not caused by a tool")
        ev.append(meas["design_note"])
    return StageResult(cm.id, stage, verdict, measured=meas, evidence=ev)


def _find_register(g, cm):
    """First instance of the register found by name: (name, [Q nets]) or (None, None)."""
    for nm in [cm.intent.get("register")] + list(cm.intent.get("aliases", [])):
        if nm:
            reg = g.register(nm)
            if reg and all(q is not None for q in reg):
                return nm, reg
    return None, None


def _codes(g, reg):
    """(codes, how): exact reachability when the design is small, else a random-simulation sample, else (None, None)."""
    c = g.reachable_codes(reg)
    if c is not None:
        return c, "exact"
    c = g.sample_codes(reg)
    return (c, "sampled") if c is not None else (None, None)


def _encoding_candidates(g, cm):
    """Instances of the state register: by name (every hierarchy path), else by value (a register of the same width
    that holds only codes of the RTL list). Returns ({name: [Q nets]}, how)."""
    i = cm.intent
    for nm in [i.get("register")] + list(i.get("aliases", [])):
        if nm:
            regs = g.registers(nm)
            if regs:
                return regs, "name"
            reg = g.register(nm)
            if reg and all(q is not None for q in reg):
                return {nm: reg}, "name"
    want, width = set(i.get("codes") or []), i.get("width")
    out = {}
    if want and width:
        for base, reg in g.register_groups().items():
            if len(reg) != width:
                continue
            codes, how = _codes(g, reg)
            if codes and len(codes) >= 2 and set(codes) <= want:
                out[base] = reg
    return out, "value"


def _encoding(cm, g, stage, first):
    i = cm.intent
    width, d_ref = i.get("width"), i.get("min_distance")
    ev, meas = [], dict(intended_width=width, intended_distance=d_ref, intended_codes=[f"0x{c:x}" for c in i.get("codes", [])])
    if first:
        cm.track["flop_names"] = sorted(g.canon(q) for q in g.flops)
    cands, how = _encoding_candidates(g, cm)
    if not cands:
        known = set(cm.track.get("flop_names", []))
        new = [q for q in g.flops if g.canon(q) not in known] if known else []
        ev.append(f"no flops named {i.get('register')}[...] in this netlist, and no {width}-bit register holds only the RTL codes")
        if not new:
            return StageResult(cm.id, stage, UNTRACKED, measured=meas, evidence=ev)
        new.sort(key=g.name)
        codes, chow = _codes(g, new)
        meas.update(width=len(new), state_flops=[g.name(q) for q in new])
        ev.append(f"{len(new)} flop(s) not present before now hold state: " + _short(g.name(q) for q in new))
        if codes is None:
            return StageResult(cm.id, stage, UNTRACKED, measured=meas, evidence=ev + ["their codes could not be derived"])
        d = G.min_distance(codes) or 0
        meas.update(codes=[f"0x{c:x}" for c in codes], distance=d, recoded=True, codes_how=chow)
        ev.insert(0, f"state register re-encoded: {len(new)} new flop(s) with codes {_short(meas['codes'], 12)}, minimum "
                     f"Hamming distance {d} (intended {d_ref})")
        v = SURVIVED if d_ref and d >= d_ref else (WEAKENED if d >= 2 else REMOVED)
        return StageResult(cm.id, stage, v, measured=meas, evidence=ev)
    verdicts, inst = [], []
    for nm, reg in sorted(cands.items()):
        codes, chow = _codes(g, reg)
        row = dict(register=nm, width=len(reg), found_by=how)
        if width and len(reg) != width:
            ev.append(f"register {nm} has {len(reg)} flops, the RTL declares {width}")
        if codes is None:
            ev.append(f"{nm}: all {len(reg)} flops present; codes not re-derived on this netlist (flops with enable/reset "
                      "pins or without a known power-up value), so the distance is the RTL's, unverified here")
            row["distance"] = None
            verdicts.append(SURVIVED if (not width or len(reg) >= width) else WEAKENED)
        else:
            d = G.min_distance(codes) or 0
            row.update(codes=[f"0x{c:x}" for c in codes], distance=d, codes_how=chow)
            extra = sorted(set(codes) - set(i.get("codes", codes)))
            ev.append(f"{nm}" + (" (matched by its values)" if how == "value" else "") + ": fault-free "
                      + ("reachable" if chow == "exact" else "sampled (random simulation from power-up)")
                      + f" codes {_short(row['codes'], 12)}; minimum Hamming distance {d}" + (f" (intended {d_ref})" if d_ref else ""))
            if extra and i.get("codes"):
                ev.append(f"{nm}: codes that are not in the RTL list: " + _short(f"0x{c:x}" for c in extra))
                row["unlisted_codes"] = [f"0x{c:x}" for c in extra]
                if len(set(codes) & set(i["codes"])) * 2 < len(set(i["codes"])):
                    row["recoded"] = meas["recoded"] = True
                    ev.append(f"{nm}: fewer than half of the RTL codes are still reachable: the register was re-encoded")
            ref = d_ref if d_ref is not None else cm.track.setdefault("ref_distance", d)
            verdicts.append(SURVIVED if d >= ref else (WEAKENED if d >= 2 else REMOVED))
        inst.append(row)
    from .model import worst
    meas.update(instances=inst, width=inst[0]["width"], register=inst[0]["register"], distance=min(
        (r["distance"] for r in inst if r.get("distance") is not None), default=None))
    if inst[0].get("codes"):
        meas["codes"] = inst[0]["codes"]
    return StageResult(cm.id, stage, worst(verdicts), measured=meas, evidence=ev)


def _dup(cm, g, stage, first):
    regs = cm.intent.get("registers", [])
    found, ev = {}, []
    for r in regs:
        reg = g.register(r)
        found[r] = [q for q in (reg or []) if q is not None]
    meas = dict(flops={r: len(v) for r, v in found.items()}, intended_width=cm.intent.get("width"))
    missing = [r for r in regs if not found[r]]
    allq = [q for v in found.values() for q in v]
    if len(missing) == len(regs):
        return StageResult(cm.id, stage, UNTRACKED, measured=meas, evidence=[f"no flops named {' / '.join(regs)} in this netlist"])
    if missing:
        ev.append(f"no flop is left for {', '.join(missing)}: only {', '.join(r for r in regs if found[r])} remain(s)")
        return StageResult(cm.id, stage, REMOVED, measured=meas, evidence=ev)
    if len(set(allq)) < len(allq):
        ev.append("bits of the redundant registers are the same flop (identical flops were merged)")
        return StageResult(cm.id, stage, REMOVED, measured=meas, evidence=ev)
    w = cm.intent.get("width") or max(len(v) for v in found.values())
    short = [r for r in regs if len(found[r]) < w]
    if short:
        ev.append("fewer flops than declared: " + ", ".join(f"{r} {len(found[r])}/{w}" for r in short))
        return StageResult(cm.id, stage, WEAKENED, measured=meas, evidence=ev)
    ev.append(f"all registers present as separate flops ({', '.join(f'{r}: {len(found[r])}' for r in regs)})")
    return StageResult(cm.id, stage, SURVIVED, measured=meas, evidence=ev)


def _alarm(cm, g, stage, first):
    sig = cm.intent.get("signal")
    bits = g.ports[sig][1] if sig in g.ports else [n for s, n in sorted(g.find(r"(?:^|[./\\])" + re.escape(sig) + r"(\[\d+\])?$").items())]
    if not bits:
        return StageResult(cm.id, stage, REMOVED if not first else UNTRACKED, evidence=[f"no net or port named {sig} in this netlist"])
    val = g.signatures()
    live, ev = 0, []
    for b in bits:
        n = b
        if G._is_const(n):
            ev.append(f"{sig} is tied to constant {n}")
            continue
        if n in g.flops:
            n = g.flops[n].d
            if G._is_const(n):
                ev.append(f"the flop behind {sig} has a constant D input ({n})")
                continue
        if n in g.gates:
            v = val[n]
            if not v.any() or not (~v).any():
                ce = _const_exact(g, n)
                if ce:
                    ev.append(f"{sig} is driven by logic that is constant {'1' if v.any() else '0'} for every value of its "
                              f"{len(g.support(n))} inputs/flops (checked exhaustively): the alarm can never change")
                    continue
                if ce is None:
                    ev.append(f"{sig} did not change on any of the simulated patterns (support too wide to prove it constant)")
        live += 1
    meas = dict(bits=len(bits), live_bits=live)
    if live == len(bits):
        return StageResult(cm.id, stage, SURVIVED, measured=meas, evidence=ev or [f"{sig} is driven by non-constant logic"])
    return StageResult(cm.id, stage, REMOVED if live == 0 else WEAKENED, measured=meas, evidence=ev)


def _const_exact(g, n):
    """True/False when constancy of gate net n can be decided exhaustively over its leaves, else None."""
    import numpy as np
    leaves = g.support(n)
    if len(leaves) > 18:
        return None
    lanes = max(64, 1 << len(leaves))
    L = np.arange(lanes, dtype=np.uint64)
    val = {l: np.packbits(((L >> np.uint64(j)) & np.uint64(1)).astype(np.uint8), bitorder="little").view(np.uint64)
           for j, l in enumerate(leaves)}
    zero = np.zeros(lanes // 64, dtype=np.uint64)
    for i in G._bits(g.cone[n]):
        x = g.order[i]
        gt = g.gates[x]
        val[x] = gt.fn(*[val[f] if f in val else (~zero if f == "1" else zero) for f in gt.ins])
    v = val[n]
    return bool(not v.any() or not (~v).any())


def _mubi(cm, g, stage, first):
    sig, w = cm.intent.get("signal"), cm.intent.get("width")
    hits = g.find(r"(?:^|[./\\])" + re.escape(sig) + r"\[\d+\]$")
    bits = {}
    for s, n in hits.items():
        bits.setdefault(int(re.search(r"\[(\d+)\]$", s).group(1)), n)
    meas = dict(intended_width=w, bits_found=len(bits), distinct_nets=len(set(bits.values())))
    if not bits:
        return StageResult(cm.id, stage, UNTRACKED, measured=meas, evidence=[f"no net named {sig}[i] in this netlist"])
    if first:
        cm.track["ref_distinct"] = meas["distinct_nets"]
    ref = cm.track.get("ref_distinct", w or len(bits))
    ev = [f"{len(bits)} bit(s) of {sig} found, driven by {meas['distinct_nets']} distinct net(s)"]
    d = meas["distinct_nets"]
    v = SURVIVED if d >= ref else (WEAKENED if d >= 2 else REMOVED)
    return StageResult(cm.id, stage, v, measured=meas, evidence=ev)


def copy_init(g, ref):
    """Give flops without a power-up value the value of the same-named flop of an earlier stage."""
    by = {}
    for q, f in ref.flops.items():
        for s in ref.names.get(q, []):
            by[s] = f.init
    n = 0
    for q, f in g.flops.items():
        if f.init is None:
            for s in g.names.get(q, []):
                if by.get(s) is not None:
                    f.init = by[s]
                    n += 1
                    break
    return n
