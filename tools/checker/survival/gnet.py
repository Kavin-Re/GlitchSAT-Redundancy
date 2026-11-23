"""One gate-level view for every stage: Yosys JSON (generic gates or Nangate45 cells) and placed sky130 Verilog.

The checker tracks a countermeasure across stages by the *Boolean function* its nets compute, not by names, because
names are the first thing a synthesis flow changes. This module provides:

  load(path, top)            -> GNet (format detected from the file)
  GNet.signatures()          -> per net, a bit-parallel simulation signature (exact truth table over the primary
                                inputs when the design has at most 12 input bits)
  GNet.classes()             -> groups of nets computing the same function (or its complement)
  GNet.roots(nets)           -> the members of a group that do not merely pass another member on, the cells shared
                                between them, and the number of mutually independent copies
  GNet.reachable_codes(reg)  -> fault-free reachable values of a register (small designs)

Reused, not re-implemented: the Nangate45 cell functions come from glitchsat_real.nangate (each checked against
SYNFI's clauses there); the sky130 cell functions and the placed-Verilog reader come from ext/shots (each checked
against the PDK transistor netlists there).
"""
import hashlib
import json
import re

import numpy as np

from . import paths

FULL = np.uint64(0xFFFFFFFFFFFFFFFF)


class NetlistError(Exception):
    pass


def _mux(a, b, s):
    return (a & ~s) | (b & s)


# Yosys internal gate library: type -> (input pin order, function)
GATES = {
    "$_BUF_": (("A",), lambda a: a),
    "$_NOT_": (("A",), lambda a: ~a),
    "$_AND_": (("A", "B"), lambda a, b: a & b),
    "$_NAND_": (("A", "B"), lambda a, b: ~(a & b)),
    "$_OR_": (("A", "B"), lambda a, b: a | b),
    "$_NOR_": (("A", "B"), lambda a, b: ~(a | b)),
    "$_XOR_": (("A", "B"), lambda a, b: a ^ b),
    "$_XNOR_": (("A", "B"), lambda a, b: ~(a ^ b)),
    "$_ANDNOT_": (("A", "B"), lambda a, b: a & ~b),
    "$_ORNOT_": (("A", "B"), lambda a, b: a | ~b),
    "$_MUX_": (("A", "B", "S"), _mux),
    "$_NMUX_": (("A", "B", "S"), lambda a, b, s: ~_mux(a, b, s)),
    "$_AOI3_": (("A", "B", "C"), lambda a, b, c: ~((a & b) | c)),
    "$_OAI3_": (("A", "B", "C"), lambda a, b, c: ~((a | b) & c)),
    "$_AOI4_": (("A", "B", "C", "D"), lambda a, b, c, d: ~((a & b) | (c & d))),
    "$_OAI4_": (("A", "B", "C", "D"), lambda a, b, c, d: ~((a | b) & (c | d))),
}
_FLOP_RE = re.compile(r"^\$_(S?DFF|DFFE|SDFFE|SDFFCE|DFFSR|ALDFF|DFFSRE|ALDFFE)[A-Z0-9_]*_$|^\$(dff|adff|sdff|dffe|adffe|sdffe|sdffce|aldff)$")
_NANGATE_RE = re.compile(r"^[A-Z][A-Z0-9]*_X\d+$")
_CLOCK_PINS = ("C", "CLK", "CK")


class Gate:
    __slots__ = ("cell", "type", "ins", "fn")

    def __init__(self, cell, type_, ins, fn):
        self.cell, self.type, self.ins, self.fn = cell, type_, ins, fn


class Flop:
    __slots__ = ("cell", "d", "ctl", "init", "type")

    def __init__(self, cell, d, ctl, init, type_):
        self.cell, self.d, self.ctl, self.init, self.type = cell, d, ctl, init, type_


def _clean(name):
    return name.lstrip("\\")


class GNet:
    def __init__(self, top, source, fmt):
        self.top, self.source, self.fmt = top, source, fmt
        self.ports = {}        # name -> (direction, [net or const])
        self.gates = {}        # out net -> Gate
        self.flops = {}        # q net -> Flop
        self.names = {}        # net -> [names], public names first
        self.cell_type = {}    # original cell name -> original type (the cells a designer sees)
        self.site_cell = {}    # net -> original cell that drives it (differs from Gate.cell for mapped libraries)
        self.notes = []
        self.tied = {}         # net -> bool: inputs held constant by the model (inactive resets)
        self._sig = None

    # ------------------------------------------------------------------ construction helpers
    def _finish(self):
        self.clock_nets = {v for f in self.flops.values() for p, v in f.ctl.items() if p in _CLOCK_PINS}
        self.in_bits = {}
        for p, (d, bits) in sorted(self.ports.items()):
            if d != "input":
                continue
            for i, b in enumerate(bits):
                if b in self.clock_nets or (not self.clock_nets and p in ("clk", "clk_i", "clock")):
                    continue
                if not _is_const(b):
                    self.in_bits[b] = (p, i)
        for n in self.names:
            self.names[n].sort(key=lambda s: (s.startswith("$") or "$" in s, len(s), s))
        # topological order of the gates
        order, state = [], {}
        for root in self.gates:
            if root in state:
                continue
            stack = [(root, iter(self.gates[root].ins))]
            state[root] = 1
            while stack:
                n, it = stack[-1]
                for f in it:
                    if f in self.gates:
                        if state.get(f) == 1:
                            raise NetlistError(f"combinational loop through net {self.name(f)}")
                        if f not in state:
                            state[f] = 1
                            stack.append((f, iter(self.gates[f].ins)))
                            break
                else:
                    state[n] = 2
                    order.append(n)
                    stack.pop()
        self.order = order
        self.idx = {n: i for i, n in enumerate(order)}
        self.leaves = sorted(set(self.in_bits) | set(self.flops), key=self.leaf_key)
        lidx = {n: i for i, n in enumerate(self.leaves)}
        self.cone, self.supp = {}, {}
        for n in order:
            c, s = 1 << self.idx[n], 0
            for f in self.gates[n].ins:
                if f in self.gates:
                    c |= self.cone[f]
                    s |= self.supp[f]
                elif f in lidx:
                    s |= 1 << lidx[f]
            self.cone[n], self.supp[n] = c, s
        self.fanout = {}
        for n, g in self.gates.items():
            for f in g.ins:
                self.fanout.setdefault(f, []).append(n)
        self.flop_d_readers = {}
        for q, f in self.flops.items():
            self.flop_d_readers.setdefault(f.d, []).append(q)
        self.out_bits = {}
        for p, (d, bits) in self.ports.items():
            if d == "output":
                for i, b in enumerate(bits):
                    if not _is_const(b):
                        self.out_bits.setdefault(b, []).append((p, i))
        return self

    # ------------------------------------------------------------------ names
    def name(self, n):
        v = self.names.get(n)
        return v[0] if v else str(n)

    def leaf_key(self, n):
        if n in self.in_bits:
            p, i = self.in_bits[n]
            return f"in:{p}[{i}]"
        return "ff:" + self.canon(n)

    def canon(self, n):
        """Stage-independent name of a net: the alphabetically first public name (display uses the shortest)."""
        pub = sorted(s for s in self.names.get(n, []) if "$" not in s)
        return pub[0] if pub else self.name(n)

    def cell_of(self, n):
        """Name of the cell a designer would see driving net n."""
        if n in self.site_cell:
            return self.site_cell[n]
        if n in self.gates:
            return self.gates[n].cell
        if n in self.flops:
            return self.flops[n].cell
        return None

    def find(self, pattern):
        """Nets whose (any) name matches the regular expression, as {name: net}."""
        rx = re.compile(pattern)
        out = {}
        for n, names in self.names.items():
            for s in names:
                if rx.search(s):
                    out[s] = n
        return out

    def register(self, base):
        """Flop Q nets of register `base` as a list indexed by bit (None where a bit has no flop), or None."""
        rx = re.compile(r"(?:^|[./\\])" + re.escape(base) + r"(?:\[(\d+)\])?$")
        bits = {}
        for q in self.flops:
            for s in self.names.get(q, []):
                m = rx.search(s)
                if m:
                    bits.setdefault(int(m.group(1) or 0), q)
        if not bits:
            return None
        return [bits.get(i) for i in range(max(bits) + 1)]

    def stats(self):
        return dict(gates=len(self.gates), flops=len(self.flops), cells=len(self.cell_type) or len(self.gates) + len(self.flops),
                    inputs=len(self.in_bits))

    # ------------------------------------------------------------------ cones
    def cone_nets(self, n):
        c = self.cone.get(n, 0)
        return [self.order[i] for i in _bits(c)]

    def support(self, n):
        if n in self.gates:
            return [self.leaves[i] for i in _bits(self.supp[n])]
        return [n] if n in self.in_bits or n in self.flops else []

    def sinks(self, n):
        """Flop names and output port bits that net n reaches through gates only."""
        seen, st, out = {n}, [n], set()
        while st:
            x = st.pop()
            for q in self.flop_d_readers.get(x, []):
                out.add("ff:" + self.canon(q))
            for p, i in self.out_bits.get(x, []):
                out.add(f"out:{p}[{i}]")
            for y in self.fanout.get(x, []):
                if y not in seen:
                    seen.add(y)
                    st.append(y)
        return sorted(out)

    # ------------------------------------------------------------------ simulation signatures
    def input_order(self):
        return tuple(sorted(self.in_bits.values()))

    def signatures(self, mode=None):
        """net -> uint64 array. mode 'exh': every combination of the primary inputs (<= 12 bits), flop leaves random;
        'rand': every leaf random (seeded by its name, so the same leaf gets the same pattern in every netlist)."""
        if mode is None:
            mode = "exh" if len(self.in_bits) <= 12 else "rand"
        if self._sig and self._sig[0] == mode:
            return self._sig[1]
        val = {}
        if mode == "exh":
            n_in = len(self.in_bits)
            lanes = max(4096, 1 << n_in)
            L = np.arange(lanes, dtype=np.uint64)
            for j, (p, i) in enumerate(self.input_order()):
                net = next(b for b, pi in self.in_bits.items() if pi == (p, i))
                val[net] = np.packbits(((L >> np.uint64(j)) & np.uint64(1)).astype(np.uint8), bitorder="little").view(np.uint64)
            words = lanes // 64
            for q in self.flops:
                val[q] = _rand_words(self.leaf_key(q), words)
        else:
            words = 128
            for n in self.leaves:
                val[n] = _rand_words(self.leaf_key(n), words)
        zero = np.zeros(words, dtype=np.uint64)
        one = ~zero

        def get(x):
            if x in val:
                return val[x]
            if x == "1":
                return one
            if _is_const(x):
                return zero
            if x in self.tied:
                return one if self.tied[x] else zero
            val[x] = _rand_words("undriven:" + self.name(x), words)   # undriven net: its own free variable
            return val[x]
        for n in self.order:
            g = self.gates[n]
            val[n] = g.fn(*[get(f) for f in g.ins])
        self._sig = (mode, val)
        self.sig_mode = mode
        return val

    def classes(self, mode=None, min_support=3):
        """Groups of gate nets with equal or complementary signatures. Returns {key: {'pos': [...], 'neg': [...]}};
        constant-looking nets and nets with fewer than `min_support` leaves are left out."""
        val = self.signatures(mode)
        out = {}
        for n in self.order:
            if _popcount(self.supp[n]) < min_support:
                continue
            v = val[n]
            if not v.any() or not (~v).any():
                continue
            a, b = v.tobytes(), (~v).tobytes()
            if a <= b:
                out.setdefault(a, {"pos": [], "neg": []})["pos"].append(n)
            else:
                out.setdefault(b, {"pos": [], "neg": []})["neg"].append(n)
        return out

    def sig_key(self, n, mode=None):
        v = self.signatures(mode)[n]
        a, b = v.tobytes(), (~v).tobytes()
        return (a, False) if a <= b else (b, True)

    def exact(self, n):
        """True when the signature of n is its complete truth table (input-only support, exhaustive mode)."""
        return getattr(self, "sig_mode", None) == "exh" and all(l in self.in_bits for l in self.support(n))

    def verify_equal(self, a, b, complement=False, max_leaves=18):
        """Exhaustive check that nets a and b compute the same (or complementary) function of their leaves.
        Returns True/False, or None when the union support is too wide to enumerate."""
        leaves = sorted(set(self.support(a)) | set(self.support(b)), key=self.leaf_key)
        if len(leaves) > max_leaves:
            return None
        lanes = max(64, 1 << len(leaves))
        L = np.arange(lanes, dtype=np.uint64)
        val = {l: np.packbits(((L >> np.uint64(j)) & np.uint64(1)).astype(np.uint8), bitorder="little").view(np.uint64)
               for j, l in enumerate(leaves)}
        zero = np.zeros(lanes // 64, dtype=np.uint64)
        need = self.cone.get(a, 0) | self.cone.get(b, 0)
        for i in _bits(need):
            n = self.order[i]
            g = self.gates[n]
            val[n] = g.fn(*[val[f] if f in val else (~zero if f == "1" else zero) for f in g.ins])
        va, vb = val[a], val[b]
        return bool(np.array_equal(va, ~vb if complement else vb))

    def roots(self, nets):
        """Among nets computing one function: drop every net whose cone contains another member (it only passes that
        member on), then group the remaining roots by overlapping cones.
        Returns dict(roots, components (lists of roots), shared (gate nets inside two or more root cones))."""
        nets = [n for n in nets if n in self.gates]
        ids = {n: 1 << self.idx[n] for n in nets}
        roots = [n for n in nets if not any(m != n and (self.cone[n] & ids[m]) for m in nets)]
        parent = {r: r for r in roots}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        shared = 0
        for i, a in enumerate(roots):
            for b in roots[i + 1:]:
                ov = self.cone[a] & self.cone[b]
                if ov:
                    shared |= ov
                    parent[find(a)] = find(b)
        comp = {}
        for r in roots:
            comp.setdefault(find(r), []).append(r)
        return dict(roots=roots, components=sorted(comp.values(), key=lambda c: self.name(c[0])),
                    shared=[self.order[i] for i in _bits(shared)])

    def register_groups(self):
        """{base name: [Q nets, LSB first]} for every complete multi-bit register (public names only)."""
        regs = {}
        for q in self.flops:
            for s in self.names.get(q, []):
                m = re.match(r"(.+)\[(\d+)\]$", s)
                if m and "$" not in s:
                    regs.setdefault(m.group(1), {})[int(m.group(2))] = q
        out, seen = {}, set()
        for base, bits in sorted(regs.items(), key=lambda kv: (len(kv[0]), kv[0])):
            if sorted(bits) != list(range(len(bits))):
                continue
            reg = tuple(bits[i] for i in range(len(bits)))
            if reg not in seen:
                seen.add(reg)
                out[base] = list(reg)
        return out

    def registers(self, base):
        """Every instance of register `base` (one per hierarchy path): {full name: [Q nets]}."""
        rx = re.compile(r"(?:^|[./\\])" + re.escape(base) + r"$")
        return {b: r for b, r in self.register_groups().items() if rx.search(b)}

    def sample_codes(self, reg, cycles=48, lanes=2048):
        """Values of a register seen in fault-free random simulation from the power-up state (inputs random in every
        cycle, tied nets held). A sample: every value listed is reachable, values not listed may be too.
        None when a flop has no known power-up value or has an enable/reset pin the model does not hold."""
        if any(f.init is None for f in self.flops.values()):
            return None
        if self.fmt != "nangate" and any(set(f.ctl) - set(_CLOCK_PINS) for f in self.flops.values()):
            return None
        words = lanes // 64
        zero = np.zeros(words, dtype=np.uint64)
        one = ~zero
        state = {q: (one.copy() if f.init else zero.copy()) for q, f in self.flops.items()}
        seen = set()
        ins = sorted(self.in_bits, key=self.leaf_key)

        def codes():
            vals = np.zeros(lanes, dtype=np.uint64)
            for i, q in enumerate(reg):
                vals |= np.unpackbits(state[q].view(np.uint8), bitorder="little").astype(np.uint64) << np.uint64(i)
            return set(int(v) for v in np.unique(vals))
        seen |= codes()
        for t in range(cycles):
            val = dict(state)
            for n in ins:
                val[n] = _rand_words(f"{self.leaf_key(n)}@{t}", words)

            def get(x):
                if x in val:
                    return val[x]
                if x == "1":
                    return one
                if x in self.tied:
                    return one if self.tied[x] else zero
                return zero
            for n in self.order:
                gt = self.gates[n]
                val[n] = gt.fn(*[get(f) for f in gt.ins])
            state = {q: get(f.d) for q, f in self.flops.items()}
            seen |= codes()
        return sorted(seen)

    # ------------------------------------------------------------------ fault-free reachability (small designs)
    def reachable_codes(self, reg, max_states=4096):
        """Values the register (list of Q nets, LSB first) takes in fault-free runs from the power-up state, with the
        primary inputs free in every cycle. None when the design is too large or has flops with enables/resets."""
        if len(self.in_bits) > 12 or len(self.flops) > 24 or any(q is None for q in reg):
            return None
        if any(set(f.ctl) - set(_CLOCK_PINS) for f in self.flops.values()):
            return None
        if any(f.init is None for f in self.flops.values()):
            return None
        qs = sorted(self.flops, key=self.name)
        n_in = len(self.in_bits)
        lanes = 1 << n_in
        mask = (1 << lanes) - 1
        ins = {}
        for j, (p, i) in enumerate(self.input_order()):
            net = next(b for b, pi in self.in_bits.items() if pi == (p, i))
            ins[net] = sum(1 << L for L in range(lanes) if (L >> j) & 1)
        pyfn = {n: _int_fn(self.gates[n]) for n in self.order}
        start = tuple(bool(self.flops[q].init) for q in qs)
        seen, frontier = {start}, [start]
        while frontier:
            nxt = []
            for s in frontier:
                val = dict(ins)
                for q, b in zip(qs, s):
                    val[q] = mask if b else 0
                for n in self.order:
                    g = self.gates[n]
                    val[n] = pyfn[n](*[val.get(f, mask if f == "1" else 0) for f in g.ins], mask)
                dv = [val.get(self.flops[q].d, mask if self.flops[q].d == "1" else 0) for q in qs]
                for L in range(lanes):
                    t = tuple(bool((d >> L) & 1) for d in dv)
                    if t not in seen:
                        seen.add(t)
                        nxt.append(t)
                        if len(seen) > max_states:
                            return None
            frontier = nxt
        pos = {q: i for i, q in enumerate(qs)}
        return sorted({sum(int(s[pos[q]]) << i for i, q in enumerate(reg)) for s in seen})


def _int_fn(g):
    """The gate function on Python integers used as lane bit-vectors (mask = all lanes)."""
    f = g.fn

    def run(*a):
        *vals, mask = a
        r = f(*[_Lane(v, mask) for v in vals])
        return r.v
    return run


class _Lane:
    """Integer with a width, so that the numpy-style functions (using ~, &, |, ^) also run on Python ints."""
    __slots__ = ("v", "m")

    def __init__(self, v, m):
        self.v, self.m = v, m

    def __invert__(self):
        return _Lane(self.v ^ self.m, self.m)

    def __and__(self, o):
        return _Lane(self.v & o.v, self.m)

    def __or__(self, o):
        return _Lane(self.v | o.v, self.m)

    def __xor__(self, o):
        return _Lane(self.v ^ o.v, self.m)


def _is_const(b):
    return isinstance(b, str) and b in ("0", "1", "x", "z")


def _bits(x):
    i = 0
    while x:
        low = x & -x
        yield low.bit_length() - 1
        x ^= low


def _popcount(x):
    return bin(x).count("1")


def _rand_words(key, words):
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 1 << 63, size=words, dtype=np.uint64) << np.uint64(1) | rng.integers(0, 2, size=words, dtype=np.uint64)
    return a


def hamming(a, b):
    return bin(a ^ b).count("1")


def min_distance(codes):
    codes = sorted(set(codes))
    if len(codes) < 2:
        return None
    return min(hamming(a, b) for i, a in enumerate(codes) for b in codes[i + 1:])


# ---------------------------------------------------------------------- loaders
def load(path, top=None):
    """Load a netlist: Yosys JSON (.json) or flat placed sky130 Verilog (.v)."""
    if str(path).endswith(".json"):
        with open(path) as f:
            doc = json.load(f)
        return from_yosys(doc, top, source=str(path))
    if str(path).endswith((".v", ".vg")):
        return from_placed_verilog(path, top)
    raise NetlistError(f"{path}: unknown netlist format (expected Yosys .json or placed structural .v)")


def from_yosys(doc, top=None, source="<doc>"):
    mods = doc.get("modules") if isinstance(doc, dict) else None
    if not isinstance(mods, dict) or not mods:
        raise NetlistError(f"{source}: not a Yosys JSON netlist (no 'modules')")
    if top is None:
        tops = [n for n, m in mods.items() if str((m.get("attributes") or {}).get("top", "0")).strip("0") != ""]
        top = tops[0] if len(tops) == 1 else (next(iter(mods)) if len(mods) == 1 else None)
        if top is None:
            raise NetlistError(f"{source}: several modules {sorted(mods)}; give `top`")
    if top not in mods:
        raise NetlistError(f"{source}: no module {top!r} (modules: {sorted(mods)})")
    m = mods[top]
    types = {c.get("type") for c in m["cells"].values()}
    sub = sorted(t for t in types if t in mods)
    if sub:
        raise NetlistError(f"{source}: module {top} still instantiates {sub}; the checker needs a flattened netlist "
                           "(add `flatten` to the script; `keep_hierarchy` modules can be flattened after mapping)")
    meta = None
    if any(_NANGATE_RE.match(t or "") for t in types):
        ng = paths.optional("glitchsat_real.nangate")
        if ng is None:
            raise NetlistError(f"{source}: Nangate45 cells found but the adapter (glitchsat_real.nangate) is not "
                               "available; set GLITCHSAT_REAL")
        doc2, meta = ng.convert(doc, top)
        m_orig, m = m, doc2["modules"][top]
    g = GNet(top, source, "nangate" if meta else "yosys")
    for p, v in m["ports"].items():
        g.ports[p] = (v.get("direction"), list(v["bits"]))
    for n, x in m["netnames"].items():
        for i, b in enumerate(x["bits"]):
            if not _is_const(b):
                g.names.setdefault(b, []).append(_clean(n) + (f"[{i}]" if len(x["bits"]) > 1 else ""))
    init = {}
    for n, x in m["netnames"].items():
        iv = (x.get("attributes") or {}).get("init")
        if isinstance(iv, str):
            for i, ch in enumerate(reversed(iv)):
                if i < len(x["bits"]) and ch in "01":
                    init[x["bits"][i]] = ch == "1"
        elif isinstance(iv, int):
            for i, b in enumerate(x["bits"]):
                init[b] = bool((iv >> i) & 1)
    unsupported = {}
    for cn, c in m["cells"].items():
        t, con = c.get("type"), c.get("connections") or {}
        if t == "$scopeinfo":
            continue
        if t in GATES:
            pins, fn = GATES[t]
            try:
                ins = [con[p][0] for p in pins]
                out = con["Y"][0]
            except (KeyError, IndexError):
                raise NetlistError(f"{source}: cell {cn} ({t}) has missing pins")
            if out in g.gates or out in g.flops:
                raise NetlistError(f"{source}: net {out} has two drivers")
            g.gates[out] = Gate(cn, t, ins, fn)
            if not meta:
                g.cell_type[cn] = t
        elif _FLOP_RE.match(t or ""):
            d, q = con.get("D", []), con.get("Q", [])
            if len(d) != len(q) or not q:
                raise NetlistError(f"{source}: flop {cn} ({t}) has no D/Q")
            ctl = {p: v[0] for p, v in con.items() if p not in ("D", "Q") and v}
            pinit = (c.get("parameters") or {})
            for i, (di, qi) in enumerate(zip(d, q)):
                iv = init.get(qi)
                if iv is None and t.startswith("$_DFF_P") and t in ("$_DFF_P_", "$_DFF_N_"):
                    iv = False       # same convention as scripts/glitchsat.py: no init attribute means 0
                g.flops[qi] = Flop(cn if len(q) == 1 else f"{cn}[{i}]", di, ctl, iv, t)
            if not meta:
                g.cell_type[cn] = t
        else:
            unsupported[t] = unsupported.get(t, 0) + 1
    if unsupported:
        raise NetlistError(f"{source}: cell types the checker cannot read: {unsupported}. It reads gate-level netlists "
                           "(Yosys $_*_ gates and flops, Nangate45, placed sky130). Run `techmap` (or `synth`) and "
                           "`flatten` before `write_json`.")
    _normalise_flops(g)
    if meta:
        g.cell_type = {cn: v["type"] for cn, v in meta["cells"].items()}
        for net, s in meta["sites"].items():
            g.site_cell[int(net) if not isinstance(net, int) else net] = s["cell"]
        g.reset_nets = [r["net"] for r in meta.get("resets", [])]
        g.notes.append("Nangate45 cells mapped to primitives by glitchsat_real.nangate (resets held inactive)")
        # reset inputs are held inactive in the adapter's model: remove them from the free inputs
        for r in meta.get("resets", []):
            g.tied[r["net"]] = not bool(r.get("active", 0)) if not isinstance(r.get("active"), str) else r["active"] in ("0", "low")
            for p, (d, bits) in list(g.ports.items()):
                if r["net"] in bits and d == "input":
                    g.ports[p] = ("reset", bits)
    return g._finish()


_FF_E = re.compile(r"^\$_DFFE_([NP])([NP])_$")
_FF_S = re.compile(r"^\$_SDFF_([NP])([NP])([01])_$")
_FF_SE = re.compile(r"^\$_SDFF(C?)E_([NP])([NP])([01])([NP])_$")


def _normalise_flops(g):
    """Flops with a clock enable or a synchronous reset become a plain flop plus explicit gates for the effective D
    (enable: hold Q; sync reset: load the reset value), so that reachability and signatures see their real behaviour.
    Asynchronous set/reset flops are left as they are (the reachability pass then declines)."""
    k = 0

    def gate(cell, typ, *ins):
        nonlocal k
        out = ("ffd", k)
        k += 1
        g.gates[out] = Gate(cell, typ, list(ins), GATES[typ][1])
        g.names.setdefault(out, []).append(f"$ffd${cell}${k}")
        return out

    def lit(net, pol, cell):
        return net if pol == "P" else gate(cell, "$_NOT_", net)
    for q, f in list(g.flops.items()):
        t, d, c = f.type, f.d, f.ctl
        m = _FF_E.match(t)
        if m and "E" in c:
            d = gate(f.cell, "$_MUX_", q, d, lit(c["E"], m.group(2), f.cell))
        m = _FF_S.match(t)
        if m and "R" in c:
            d = gate(f.cell, "$_MUX_", d, m.group(3), lit(c["R"], m.group(2), f.cell))
        m = _FF_SE.match(t)
        if m and "R" in c and "E" in c:
            ce_over, rpol, rval, epol = m.group(1) == "C", m.group(3), m.group(4), m.group(5)
            r, e = lit(c["R"], rpol, f.cell), lit(c["E"], epol, f.cell)
            if ce_over:        # enable gates everything, reset included
                d = gate(f.cell, "$_MUX_", q, gate(f.cell, "$_MUX_", d, rval, r), e)
            else:              # reset wins over enable
                d = gate(f.cell, "$_MUX_", gate(f.cell, "$_MUX_", q, d, e), rval, r)
        if d is not f.d:
            f.d = d
            f.ctl = {p: v for p, v in c.items() if p in _CLOCK_PINS}
        if f.init is None and (_FF_S.match(t) or _FF_SE.match(t)):
            f.init = (_FF_S.match(t) or _FF_SE.match(t)).group(3 if _FF_S.match(t) else 4) == "1"   # state after reset


def from_placed_verilog(path, top=None):
    """Flat structural sky130 Verilog (OpenROAD write_verilog), read with ext/shots (cell functions checked there)."""
    design = paths.optional("shotmodel.design")
    cells = paths.optional("shotmodel.cells")
    if design is None or cells is None:
        raise NetlistError("placed Verilog needs ext/shots (shotmodel) for the sky130 cell functions; set GLITCHSAT_EXT")
    if top is None:
        txt = open(path).read()
        mm = re.findall(r"\bmodule\s+(\S+)\s*\(", txt)
        top = mm[0] if mm else None
    try:
        ports, inst = design.read_netlist(path, top)
    except ValueError as e:
        raise NetlistError(str(e))
    g = GNet(top, str(path), "placed")
    for p, (d, bits) in ports.items():
        g.ports[p] = (d, list(bits))
        for b in bits:
            g.names.setdefault(b, []).append(b)
    for name, (master, pins) in inst.items():
        try:
            kind = cells.kind(master)
        except ValueError as e:
            raise NetlistError(str(e))
        g.cell_type[name] = master
        if kind == "physical":
            continue
        if kind == "flop":
            f = cells.FLOP[cells.base(master)]
            q = pins[f["q"]]
            g.flops[q] = Flop(name, pins[f["d"]], {"CLK": pins[f["clk"]]}, None, master)
            g.names.setdefault(q, []).append(q)
            continue
        ipins = cells.input_pins(master)
        out = pins[cells.output_pin(master)]
        g.gates[out] = Gate(name, master, [pins[p] for p in ipins], _sky_fn(cells, master, ipins))
        g.names.setdefault(out, []).append(out)
    for q, f in g.flops.items():
        g.names.setdefault(f.d, []).append(f.d)
    # clock tree buffers: gates fed only by clock nets are not logic
    clk = {f.ctl["CLK"] for f in g.flops.values()}
    grew = True
    while grew:
        grew = False
        for out, gt in list(g.gates.items()):
            if out in clk:
                srcs = [i for i in gt.ins]
                del g.gates[out]
                for s in srcs:
                    if s not in clk:
                        clk.add(s)
                grew = True
    for f in g.flops.values():
        f.ctl = {"CLK": f.ctl["CLK"]}
    g._clock_tree = clk
    r = g._finish()
    r.clock_nets = clk
    r.in_bits = {b: pi for b, pi in r.in_bits.items() if b not in clk}
    r.leaves = sorted(set(r.in_bits) | set(r.flops), key=r.leaf_key)
    return _refinish(r)


def _refinish(g):
    lidx = {n: i for i, n in enumerate(g.leaves)}
    for n in g.order:
        s = 0
        for f in g.gates[n].ins:
            if f in g.gates:
                s |= g.supp[f]
            elif f in lidx:
                s |= 1 << lidx[f]
        g.supp[n] = s
    return g


def _sky_fn(cells, master, ipins):
    def fn(*vals):
        return cells.evaluate(master, dict(zip(ipins, vals)), lambda a: ~a)
    return fn
