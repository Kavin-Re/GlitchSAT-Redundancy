"""Cell / wire delay model.

PRECEDENCE
  1. SOURCED: if an SDF file is supplied (interconnect + IOPATH delays from OpenSTA/OpenROAD), it is
     used verbatim.  None is shipped in the repo, so eda/regen_sdf.sh regenerates a true one and
     drops it next to the netlist; load_sdf() will pick it up automatically.
  2. ASSUMED: otherwise a documented linear model built from data that IS in the repo -- the LEF cell
     SIZE (a drive-strength proxy), the fanout of each net, and the placement coordinates (wirelength).
     Every number below is an engineering guess at sky130 typical-corner scale and is labelled ASSUMED.
     It is NOT a measurement.  Absolute picoseconds are arbitrary; only the RELATIVE ordering of path
     delays (which flop is slowest) and the shape of the glitch-period sweep are meaningful.

The model returns, for each combinational cell, a single pin-to-output delay (ps):
    delay = INTRINSIC[base] / strength(master)  +  K_LOAD * load_cap(net)  +  K_WIRE * wirelength(net)
with load_cap(net) = fanout_pins * PIN_CAP and wirelength from the half-perimeter of the driver +
reader cell centres (um).  Flip-flop clk->Q and buffer delays feed the clock-latency computation.
"""
import math

# ---- ASSUMED parameters (sky130-typical scale, ps / fF / um). Not sourced from a .lib. ----
INTRINSIC = {           # unloaded pin->output delay of a drive-strength-1 cell, ps
    "inv": 32, "buf": 40, "clkbuf": 45,
    "nand2": 45, "nand3": 58, "nand4": 72,
    "nand2b": 52, "nand3b": 64, "nand4bb": 90,
    "nor2": 50, "nor4": 95, "nor4bb": 110,
    "and2": 60, "and4": 95,
    "o21a": 78, "o21ai": 60, "a21o": 80, "a21bo": 92, "a21boi": 70,
    "a22o": 92, "a2bb2oi": 88, "mux2": 85,
    "dfxtp": 120,       # clk -> Q
}
K_LOAD = 9.0            # ps per fF of load capacitance                       (ASSUMED)
K_WIRE = 6.0            # ps per um of driver->reader half-perimeter wirelength (ASSUMED)
PIN_CAP = 1.8          # fF per driven input pin                              (ASSUMED)
SETUP = 40.0           # flip-flop setup time, ps                             (ASSUMED)
SOURCE = "ASSUMED"     # flipped to "SOURCED(sdf)" when an SDF is loaded


def strength(master):
    """Drive-strength multiplier from the master suffix (_1,_2,_4,_0). Stronger cell -> faster."""
    suf = master.rsplit("_", 1)[-1]
    try:
        s = int(suf)
    except ValueError:
        return 1.0
    return {0: 0.9, 1: 1.0, 2: 1.6, 4: 2.4}.get(s, 1.0)


def _base(master):
    import re
    return re.sub(r"_\d+$", "", master[len("sky130_fd_sc_hd__"):])


class DelayModel:
    """Per-design delay model. Attributes: cell_delay[name] (ps), source ('ASSUMED'|'SOURCED(sdf)')."""

    def __init__(self, design, sdf=None, derate=1.0):
        """sdf: optional {instance_name: delay_ps} (see vlab.sdf.load_sdf). derate: multiplies every
        cell delay (clock buffers and clk->Q included); derate > 1 models a supply-voltage dip slowing
        the logic (ASSUMED uniform slow-down; a real droop is neither uniform nor instantaneous)."""
        self.design = design
        self.source = SOURCE
        self.derate = float(derate)
        self._fanout_pins = self._count_fanout(design)
        self.cell_delay = {c.name: self._assumed_delay(design, c)
                           for c in (design.comb + design.clkbufs)}
        self._tcq = {f.name: INTRINSIC["dfxtp"] / strength(f.master) for f in design.flops}
        if sdf:
            missing = [n for n in self.cell_delay if n not in sdf]
            if missing:
                raise ValueError("SDF lacks delays for %d cells, e.g. %s" % (len(missing), missing[:3]))
            for n in self.cell_delay:
                self.cell_delay[n] = float(sdf[n])
            for f in design.flops:
                if f.name in sdf:
                    self._tcq[f.name] = float(sdf[f.name])
            self.source = "SOURCED(sdf)"
        if self.derate != 1.0:
            self.cell_delay = {n: d * self.derate for n, d in self.cell_delay.items()}
            self._tcq = {n: d * self.derate for n, d in self._tcq.items()}
        # clock-latency per flop (ps): sum of clkbuf delays from clk to the flop's CLK leaf
        self.clk_latency = self._clock_latency(design)

    @staticmethod
    def _count_fanout(design):
        from . import cells
        fo = {}
        for c in design.comb + design.flops + design.clkbufs:
            for p in (cells.input_pins(c.master) if c.role != "flop" else ["D"]):
                net = c.pins[p]
                fo[net] = fo.get(net, 0) + 1
        return fo

    def _wirelength(self, design, c):
        """Half-perimeter (um) of the driver cell centre and all reader cell centres of its output net."""
        from . import cells
        net = c.out
        xs, ys = [c.cx], [c.cy]
        for r in design.comb + design.flops + design.clkbufs:
            pins = cells.input_pins(r.master) if r.role != "flop" else ["D", "CLK"]
            for p in pins:
                if r.pins.get(p) == net:
                    xs.append(r.cx)
                    ys.append(r.cy)
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def _assumed_delay(self, design, c):
        b = _base(c.master)
        load = self._fanout_pins.get(c.out, 1) * PIN_CAP
        wl = self._wirelength(design, c)
        return INTRINSIC.get(b, 60) / strength(c.master) + K_LOAD * load + K_WIRE * wl

    def _clock_latency(self, design):
        from . import cells
        # map clock net -> clkbuf driving it
        by_out = {c.out: c for c in design.clkbufs}
        lat = {}
        for f in design.flops:
            leaf = f.pins[cells.FLOP[cells.base(f.master)]["clk"]]
            total, net, guard = 0.0, leaf, 0
            while net in by_out and guard < 100:
                cb = by_out[net]
                total += (self.cell_delay[cb.name] if cb.name in self.cell_delay
                          else self._assumed_delay(design, cb))
                net = cb.pins[cells.input_pins(cb.master)[0]]
                guard += 1
            lat[f.out] = total
        return lat

    def tcq(self, flop):
        """clk->Q delay (ps) of one flop cell."""
        return self._tcq[flop.name]

    def flop_slack(self, design, period_ps):
        """Static setup slack per flop bit (ps) for a given period: negative => the static-timing
        fault model predicts this flop CAN miss its new value (value-independent, pessimistic)."""
        arr = self.flop_input_arrival(design)
        launch = max(self.clk_latency[f.out] + self.tcq(f) for f in design.flops)
        return {i: period_ps + self.clk_latency[design.flops[i].out] - (launch + arr[i])
                for i in range(len(design.flops))}

    def flop_input_arrival(self, design):
        """STATIC timing (value-independent): longest combinational delay from any launch point
        (flop Q or primary input) to each flop D pin. Returns {flop_bit_index: arrival_ps}.
        This is the per-flop path delay of the static-timing fault model."""
        from . import cells
        arr = {}                                   # net -> max arrival (ps)
        for n in design.sig_nets:
            arr[n] = 0.0
        for f in design.flops:
            arr[f.out] = 0.0                       # launched by the (ideal) clock edge
        for c in design.comb:                      # topological order
            a_in = max((arr[c.pins[p]] for p in cells.input_pins(c.master)), default=0.0)
            arr[c.out] = a_in + self.cell_delay[c.name]
        f = cells.FLOP["dfxtp"]
        out = {}
        for i, fl in enumerate(design.flops):
            d_net = fl.pins[f["d"]]
            out[i] = arr.get(d_net, 0.0)
        return out
