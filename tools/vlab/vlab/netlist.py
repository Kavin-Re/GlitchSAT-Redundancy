"""Placed design = post-route gate-level Verilog (OpenROAD write_verilog) + DEF placement + LEF cell
sizes, joined by instance name.  Self-contained parser (no EDA tools needed).

Conventions are shared with the spatial model in ext/shots (see interface/README.md): KEY=0xC3,
GOOD=0x96, INIT=0xF0; the 8 state flops are ordered by the boot_word bit they drive (flop i = bit i);
the ordered list `logic` = flops (bit 0..7) then combinational cells in topological order.
"""
import os
import re

KEY = 0xC3    # honest key; an attack is "boot accepted while sig != KEY"
GOOD = 0x96   # boot_word value that means "boot accepted"
INIT = 0xF0   # power-up state of the 8 flops (RTL `initial st = 8'hF0`); dfxtp has no reset, see eda/README.md

from . import cells  # noqa: E402

# design_id -> (top, def, netlist) relative to the GlitchSAT repo root
DESIGNS = {
    "v1": ("v1", "layout/v_designs/out_patched/v1.def", "layout/v_designs/out_patched/v1_pnr.v"),
    "v2": ("v2", "layout/v_designs/out_patched/v2.def", "layout/v_designs/out_patched/v2_pnr.v"),
}
LEF = "research/c4/l2_inputs/lef/sky130_fd_sc_hd_sizes_only.lef"


def _is_repo(d):
    return bool(d) and os.path.isdir(os.path.join(d, "layout", "v_designs"))


def repo_root():
    """GlitchSAT checkout to read (read-only). Order: $GLITCHSAT_ROOT (the name used by ext/surface and
    ext/unbounded), then $GLITCHSAT_REPO (older alias), then the nearest enclosing directory of this file
    that contains layout/v_designs (the checkout the lab sits in, e.g. <repo>/ext/vlab). No home-directory
    or workspace-specific fallback: if none is found a clear error is raised."""
    for var in ("GLITCHSAT_ROOT", "GLITCHSAT_REPO"):
        env = os.environ.get(var)
        if env:
            if not _is_repo(env):
                raise FileNotFoundError("%s=%s has no layout/v_designs" % (var, env))
            return env
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        here = os.path.dirname(here)
        if _is_repo(here):
            return here
    raise FileNotFoundError("GlitchSAT checkout not found: put ext/vlab inside the repository or set "
                            "GLITCHSAT_ROOT to the repository root")


def read_lef_sizes(path):
    sizes, cur = {}, None
    with open(path) as fh:
        for line in fh:
            t = line.split()
            if len(t) >= 2 and t[0] == "MACRO":
                cur = t[1]
            elif len(t) >= 4 and t[0] == "SIZE" and cur:
                sizes[cur] = (float(t[1]), float(t[3]))
    return sizes


def read_def(path):
    txt = open(path).read()
    dbu = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    die = [int(v) / dbu for v in
           re.search(r"DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", txt).groups()]
    sec = txt[txt.index("\nCOMPONENTS"):txt.index("END COMPONENTS")]
    n_decl = int(re.search(r"COMPONENTS (\d+)", sec).group(1))
    comps = {}
    for m in re.finditer(
            r"-\s+(\S+)\s+(\S+)\s[^;]*?\+\s+(PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)\s*;", sec):
        name, master, _st, x, y, orient = m.groups()
        comps[name] = (master, int(x) / dbu, int(y) / dbu, orient)
    if len(comps) != n_decl:
        raise ValueError("%s: COMPONENTS says %d, parsed %d" % (path, n_decl, len(comps)))
    return dict(die=die, comps=comps)


def read_netlist(path, top):
    txt = re.sub(r"//[^\n]*", "", open(path).read())
    mods = re.findall(r"\bmodule\s+(\S+)\s*\(", txt)
    if mods != [top]:
        raise ValueError("%s: expected one module %r, found %r" % (path, top, mods))
    if re.search(r"\bassign\b", txt):
        raise ValueError("%s: assign statements not supported" % path)
    ports = {}
    for m in re.finditer(r"^\s*(input|output)\s*(?:\[(\d+):(\d+)\])?\s*(\w+)\s*;", txt, re.M):
        d, hi, lo, name = m.groups()
        ports[name] = (d, [name] if hi is None else
                       ["%s[%d]" % (name, i) for i in range(int(lo), int(hi) + 1)])
    inst = {}
    body = txt[txt.index(");") + 2:]
    for m in re.finditer(r"(sky130_fd_sc_hd__\w+)\s+(\\\S+\s|\w+)\s*\((.*?)\)\s*;", body, re.S):
        master, name, con = m.groups()
        name = name.strip().lstrip("\\")
        pins = {}
        for pm in re.finditer(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)", con):
            pins[pm.group(1)] = pm.group(2).strip().lstrip("\\").strip()
        inst[name] = (master, pins)
    return ports, inst


class Cell:
    __slots__ = ("name", "master", "kind", "x", "y", "w", "h", "orient", "pins", "out", "idx", "role")

    @property
    def cx(self):
        return self.x + self.w / 2.0

    @property
    def cy(self):
        return self.y + self.h / 2.0


class Design:
    """Joined netlist + placement of one placed design, with the logic graph built and checked."""

    def __init__(self, design_id, root=None):
        root = root or repo_root()
        self.id = design_id
        self.top, def_rel, nl_rel = DESIGNS[design_id]
        sizes = read_lef_sizes(os.path.join(root, LEF))
        d = read_def(os.path.join(root, def_rel))
        self.die = d["die"]
        self.ports, inst = read_netlist(os.path.join(root, nl_rel), self.top)
        if set(d["comps"]) != set(inst):
            raise ValueError("%s: DEF vs netlist instance names differ" % design_id)
        for n, (master, _pins) in inst.items():
            if d["comps"][n][0] != master:
                raise ValueError("%s: instance %s master mismatch DEF/netlist" % (design_id, n))
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
        # clock tree: buffers reachable from the clk port (their output is a clock net)
        clk_nets = {"clk"}
        grew = True
        clkbufs = set()
        while grew:
            grew = False
            for c in self.all_cells:
                if c.kind != "comb" or c.name in clkbufs:
                    continue
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
                    raise ValueError("flop %s not clocked from clk" % c.name)
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
        self.inputs = [b for p, (d, bits) in self.ports.items()
                       if d == "input" and p != "clk" for b in bits]
        for c in self.comb:
            for p in cells.input_pins(c.master):
                n = c.pins[p]
                if n not in driver and n not in self.inputs:
                    raise ValueError("cell %s pin %s reads undriven net %s" % (c.name, p, n))
                if n in clk_nets:
                    raise ValueError("clock net used as data at %s" % c.name)
        # topological order of combinational cells
        order, state = [], {}

        def visit(c):
            st = state.get(c.name)
            if st == 2:
                return
            if st == 1:
                raise ValueError("combinational loop through %s" % c.name)
            state[c.name] = 1
            for p in cells.input_pins(c.master):
                dv = driver.get(c.pins[p])
                if dv is not None and dv.role == "comb":
                    visit(dv)
            state[c.name] = 2
            order.append(c)
        for c in sorted(self.comb, key=lambda c: c.name):
            visit(c)
        self.comb = order
        # flops ordered by the boot_word bit they drive (flop i drives bit i)
        word = self.ports["boot_word"][1]
        byq = {c.out: c for c in self.flops}
        if sorted(byq) != sorted(word):
            raise ValueError("flops do not drive exactly boot_word[7:0]")
        self.flops = [byq[b] for b in word]
        self.word_nets = word
        self.ok_net = self.ports["boot_ok"][1][0]
        self.sig_nets = self.ports["sig"][1]
        self.logic = self.flops + self.comb         # index order: flops bit0..7, then comb topo
        for i, c in enumerate(self.logic):
            c.idx = i
        self.driver = driver
        self.n = len(self.logic)
        self._sig_only_nets()

    def _sig_only_nets(self):
        """Comb nets whose fan-in cone contains no flop Q (pure functions of the held `sig`).
        Because a clock-glitch attacker holds `sig` constant, these nets never transition during the
        glitched cycle, so two `sig` values with the same sig-only vector give identical glitch
        behaviour -- the campaign memoises on this, collapsing 256 sigs to a few classes."""
        flop_outs = {f.out for f in self.flops}
        sig_only = {}
        order = []
        for c in self.comb:
            ins = [c.pins[p] for p in cells.input_pins(c.master)]
            ok = all((n in self.inputs) or (n in sig_only) for n in ins) and \
                all(n not in flop_outs for n in ins)
            if ok:
                sig_only[c.out] = c
                order.append(c.out)
        self.sig_only = order

    def sig_class(self, sig):
        """Canonical key: values of all sig-only nets for this held sig (independent of flop state)."""
        v = {n: (sig >> i) & 1 for i, n in enumerate(self.sig_nets)}
        for net in self.sig_only:
            c = self.driver[net]
            v[net] = cells.evaluate(c.master, {p: v[c.pins[p]] for p in cells.input_pins(c.master)},
                                    lambda a: a ^ 1) & 1
        return tuple(v[n] for n in self.sig_only)

    def cell(self, name):
        for c in self.all_cells:
            if c.name == name:
                return c
        raise KeyError(name)
