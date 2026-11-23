"""Placed design = DEF placement + LEF cell sizes + post-route gate-level netlist, joined BY INSTANCE NAME.

The mapping "placed cell <-> logic" is exact and checked: the set of instance names in the DEF COMPONENTS section must
equal the set of instance names in the post-route Verilog netlist, with the same cell master for each.
"""
import re
from . import cells, paths

KEY = 0xC3
GOOD = 0x96
INIT = 0xF0          # power-up state of the 8 state flops, copied from the RTL (`initial st = 8'hF0`).
                     # The placed dfxtp flops have no reset; the flow did not carry the init value (repo README).


class Cell:
    __slots__ = ("name", "master", "kind", "x", "y", "w", "h", "orient", "pins", "out", "idx", "role")

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


def read_lef_sizes(path):
    sizes, cur = {}, None
    for line in open(path):
        t = line.split()
        if len(t) >= 2 and t[0] == "MACRO":
            cur = t[1]
        elif len(t) >= 4 and t[0] == "SIZE" and cur:
            sizes[cur] = (float(t[1]), float(t[3]))
    return sizes


def read_def(path):
    txt = open(path).read()
    dbu = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    die = [int(v) / dbu for v in re.search(r"DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", txt).groups()]
    sec = txt[txt.index("\nCOMPONENTS"):txt.index("END COMPONENTS")]
    n_decl = int(re.search(r"COMPONENTS (\d+)", sec).group(1))
    comps = {}
    for m in re.finditer(r"-\s+(\S+)\s+(\S+)\s[^;]*?\+\s+(PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)\s*;", sec):
        name, master, _st, x, y, orient = m.groups()
        if name in comps:
            raise ValueError("duplicate component %s in %s" % (name, path))
        comps[name] = (master, int(x) / dbu, int(y) / dbu, orient)
    if len(comps) != n_decl:
        raise ValueError("%s: COMPONENTS says %d, parsed %d" % (path, n_decl, len(comps)))
    rows = [(int(m.group(2)) / dbu, m.group(3)) for m in
            re.finditer(r"^ROW (\S+) \S+ -?\d+ (-?\d+) (\w+) ", txt, re.M)]
    return dict(die=die, comps=comps, rows=rows)


def read_netlist(path, top):
    """Flat structural Verilog as written by OpenROAD write_verilog. Returns (ports, instances).
    ports: name -> (direction, [bit net names, LSB first]); instances: name -> (master, {pin: net})."""
    txt = re.sub(r"//[^\n]*", "", open(path).read())
    mods = re.findall(r"\bmodule\s+(\S+)\s*\(", txt)
    if mods != [top]:
        raise ValueError("%s: expected exactly one module %r, found %r (hierarchy must be flat)" % (path, top, mods))
    if re.search(r"\bassign\b", txt):
        raise ValueError("%s: assign statements are not supported" % path)
    ports = {}
    for m in re.finditer(r"^\s*(input|output)\s*(?:\[(\d+):(\d+)\])?\s*(\w+)\s*;", txt, re.M):
        d, hi, lo, name = m.groups()
        if hi is None:
            ports[name] = (d, [name])
        else:
            ports[name] = (d, ["%s[%d]" % (name, i) for i in range(int(lo), int(hi) + 1)])
    inst = {}
    body = txt[txt.index(");") + 2:]
    for m in re.finditer(r"(sky130_fd_sc_hd__\w+)\s+(\\\S+\s|\w+)\s*\((.*?)\)\s*;", body, re.S):
        master, name, con = m.groups()
        name = name.strip().lstrip("\\")
        pins = {}
        for pm in re.finditer(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", con):
            pins[pm.group(1)] = pm.group(2).strip().lstrip("\\").strip()
        if name in inst:
            raise ValueError("duplicate instance %s" % name)
        inst[name] = (master, pins)
    return ports, inst


class Design:
    """Joined netlist + placement of one placed design."""

    def __init__(self, design_id, root=None):
        root = root or paths.repo_root()
        self.id = design_id
        self.top, def_rel, nl_rel, self.note = paths.DESIGNS[design_id]
        self.files = {"def": def_rel, "netlist": nl_rel, "lef": paths.LEF}
        self.sha256 = {k: paths.sha256(root / v) for k, v in self.files.items()}
        sizes = read_lef_sizes(root / paths.LEF)
        d = read_def(root / def_rel)
        self.die = d["die"]
        self.rows = d["rows"]
        self.ports, inst = read_netlist(root / nl_rel, self.top)
        # ---- exact mapping check: DEF components == netlist instances, same master
        if set(d["comps"]) != set(inst):
            raise ValueError("%s: DEF and netlist instance names differ: %s" %
                             (design_id, sorted(set(d["comps"]) ^ set(inst))[:8]))
        for n, (master, pins) in inst.items():
            if d["comps"][n][0] != master:
                raise ValueError("%s: instance %s is %s in the DEF but %s in the netlist" %
                                 (design_id, n, d["comps"][n][0], master))
        self.all_cells = []
        for n in sorted(inst):
            master, pins = inst[n]
            c = Cell()
            c.name, c.master, c.kind = n, master, cells.kind(master)
            _, c.x, c.y, c.orient = d["comps"][n]
            c.w, c.h = sizes[master]
            c.pins = {p: v for p, v in pins.items() if p not in cells.POWER_PINS}
            c.out = None
            c.idx = None
            c.role = "physical"
            self.all_cells.append(c)
        self._build_logic()

    def _build_logic(self):
        clk_nets = {"clk"}
        # clock tree: buffers reachable from the clk port
        grew = True
        clkbufs = set()
        while grew:
            grew = False
            for c in self.all_cells:
                if c.kind == "comb" and c.name not in clkbufs and all(v in clk_nets for v in c.pins.values()
                                                                      if v != c.pins[cells.output_pin(c.master)]):
                    ins = [c.pins[p] for p in cells.input_pins(c.master)]
                    if ins and all(i in clk_nets for i in ins):
                        clkbufs.add(c.name)
                        clk_nets.add(c.pins[cells.output_pin(c.master)])
                        grew = True
        self.clk_nets = clk_nets
        self.flops, self.comb, self.clkbufs = [], [], []
        driver = {}
        for c in self.all_cells:
            if c.kind == "flop":
                f = cells.FLOP[cells.base(c.master)]
                if c.pins[f["clk"]] not in clk_nets:
                    raise ValueError("flop %s is not clocked from the clk port" % c.name)
                c.out, c.role = c.pins[f["q"]], "flop"
                self.flops.append(c)
            elif c.kind == "comb":
                c.out = c.pins[cells.output_pin(c.master)]
                if c.name in clkbufs:
                    c.role = "clkbuf"
                    self.clkbufs.append(c)
                    continue
                c.role = "comb"
                self.comb.append(c)
            else:
                continue
            if c.out in driver:
                raise ValueError("net %s has two drivers" % c.out)
            driver[c.out] = c
        self.inputs = [b for p, (d, bits) in self.ports.items() if d == "input" and p != "clk" for b in bits]
        for c in self.comb:
            for p in cells.input_pins(c.master):
                n = c.pins[p]
                if n not in driver and n not in self.inputs:
                    raise ValueError("cell %s pin %s reads undriven net %s" % (c.name, p, n))
                if n in clk_nets:
                    raise ValueError("clock net used as data at %s" % c.name)
        # topological order of the combinational cells
        order, state = [], {}

        def visit(c):
            st = state.get(c.name)
            if st == 2:
                return
            if st == 1:
                raise ValueError("combinational loop through %s" % c.name)
            state[c.name] = 1
            for p in cells.input_pins(c.master):
                d = driver.get(c.pins[p])
                if d is not None and d.role == "comb":
                    visit(d)
            state[c.name] = 2
            order.append(c)
        for c in sorted(self.comb, key=lambda c: c.name):
            visit(c)
        self.comb = order
        # state flops ordered by the boot_word bit they drive (bit i = flop i)
        word = self.ports["boot_word"][1]
        byq = {c.out: c for c in self.flops}
        if sorted(byq) != sorted(word):
            raise ValueError("the flops do not drive exactly boot_word[7:0]")
        self.flops = [byq[b] for b in word]
        self.word_nets = word
        self.ok_net = self.ports["boot_ok"][1][0]
        self.sig_nets = self.ports["sig"][1]
        # logic cells = shot-sensitive cells; fixed index order: flops (bit 0..7) then comb in topological order
        self.logic = self.flops + self.comb
        for i, c in enumerate(self.logic):
            c.idx = i
        self.driver = driver
        self.n = len(self.logic)
        if self.n > 62:
            raise ValueError("more than 62 logic cells: the uint64 mask encoding of this prototype is too small")
        self.flop_mask = sum(1 << c.idx for c in self.flops)
        self.comb_mask = sum(1 << c.idx for c in self.comb)

    def overlaps(self):
        """pairs of placed components whose bounding boxes overlap (a legal placement has none)"""
        out, cs = [], self.all_cells
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                if abs(a.y - b.y) < 1e-9 and not (a.x + a.w <= b.x + 1e-9 or b.x + b.w <= a.x + 1e-9):
                    out.append([a.name, b.name])
        return out

    def cell(self, name):
        for c in self.all_cells:
            if c.name == name:
                return c
        raise KeyError(name)

    def names(self, mask):
        return [c.name for c in self.logic if (mask >> c.idx) & 1]
