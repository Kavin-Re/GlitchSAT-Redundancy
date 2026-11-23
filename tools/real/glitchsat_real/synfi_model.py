"""GlitchSAT analysis of a SYNFI fault specification, encoded directly as CNF (fastsat's Encoding).

One CNF instance holds a fault-free ("golden") and a faulty copy of SYNFI's target region (region.py), with one
selector variable per (fault location, fault option). Selectors are switched on and off by solver assumptions, so

  * check(faults)          answers one SYNFI injection (SYNFI builds and solves a fresh formula per injection);
  * min_faults(kmax)       answers "what is the smallest number of simultaneous faults that is effective", with a
                           totalizer over "location used" literals (at most one option per location);
  * all_min_attacks()      lists every effective fault set of that smallest size (blocking clauses).

Semantics follow SYNFI's injector (lowRISC/synfi injector_class.py, fi_injector.py, cell library), re-implemented:
  * region nodes are copied per stage; registers inside a region are transparent (Q = D, QN = !D);
  * stage input end points listed in input_values are constants; other stage inputs ("in_node") take the value of
    the same register's stage output ("out_node") in another stage; all other fan-in of the region ("side inputs",
    and readers of registers cut by unrolling) are free variables shared by the golden and faulty copies;
  * fault options (model='synfi'): a cell is replaced by another cell type from node_fault_mapping, with SYNFI's
    pin re-mapping (port_in_mapping) when the pin sets differ; 'input_fault' inverts a constant input node (all its
    pins) or makes a free side input arbitrary in the faulty copy; 'output_fault' inverts an output node; 'output'
    (as in the AES control spec) leaves it unchanged;
  * effective (no output_fault_values, "FE"/"FD"): golden outputs equal output_values AND some faulty output pin
    differs AND golden and faulty alerts equal alert_values; with output_fault_values ("FS"): faulty outputs equal
    them instead of "some pin differs".
model='flip' replaces the options by one bit flip per (location, output pin) (GlitchSAT's native fault model,
applied to the same locations: cell outputs, side inputs, input and output end points)."""
import collections
import itertools
import time

from . import engine, nangate as ng, region as rg

fs = engine.fastsat()
T_, F_ = fs.T_, fs.F_


def fs_add_clause(e, be, c):
    """Add a clause to the encoding and to a live incremental backend (the DIMACS backend re-reads e)."""
    e.add(list(c))
    if hasattr(be, 's') and be.s is not None:
        be.s.add_clause(list(c))


class SpecError(Exception):
    pass


class Model:
    def __init__(self, doc, top, spec, lib=None, model='synfi', auto_fl=True, flip_cells_only=False):
        if model not in ('synfi', 'flip'):
            raise ValueError(model)
        self.lib = lib or ng.load_cell_lib()
        self.funcs = ng.cell_functions(self.lib)
        self.doc, self.top, self.spec, self.model = doc, top, spec, model
        self.m = doc['modules'][top]
        self.g = rg.CellGraph(doc, top)
        self.regions, self.cuts = rg.extract(self.g, spec)
        self.e = fs.Encoding()
        self.sel = {}            # (loc, option) -> selector var
        self.locs = collections.OrderedDict()   # loc name -> dict(stage, node, kind, type, options)
        self.loc_used = {}       # loc -> literal "some option of loc is on"
        self.gold, self.faul = {}, {}            # (stage, node, pin) -> literal
        self.auto_fl = auto_fl
        self.side_keys = []
        self.t_build = time.time()
        self._build(auto_fl, flip_cells_only)
        self.t_build = time.time() - self.t_build
        self.be = None
        self.card = None

    # ---------------------------------------------------------------- helpers
    def _is_flop(self, node):
        return self.g.kind.get(node) == 'flop'

    def _cell(self, node):
        return self.m['cells'][node]

    def _fn(self, typ, pin, env):
        """Literal of cell function typ.pin over env {pin: literal}, built from the adapter's verified primitives."""
        e = self.e

        def ev(p):
            k = p[0]
            if k == 'var': return env[p[1]]
            if k == 'NOT': return -ev(p[1])
            if k == 'AND': return e.g_and(ev(p[1]), ev(p[2]))
            if k == 'OR': return e.g_or(ev(p[1]), ev(p[2]))
            if k == 'XOR': return e.g_xor(ev(p[1]), ev(p[2]))
            if k == 'MUX': return e.g_mux(ev(p[1]), ev(p[2]), ev(p[3]))
            raise SpecError(k)
        return ev(ng.to_prims(self.funcs[typ][pin][1]))

    def _replacement(self, cur, new, pin, env):
        """SYNFI gate replacement: value of cell `new` driving the output pin `pin` of a `cur` cell."""
        lib = self.lib
        gi_c, gi_n = lib.gate_in_type[cur], lib.gate_in_type[new]
        if gi_c != gi_n:
            pm = lib.port_in_mapping[gi_c][gi_n]
            env = {pm[p]: v for p, v in env.items()}
        go_c, go_n = lib.gate_out_type[cur], lib.gate_out_type[new]
        npin = pin
        if go_c != go_n:
            npin = lib.port_out_mapping[go_c][go_n][pin]
        return self._fn(new, npin, env)

    def _new(self):
        return self.e.new_var()

    # ---------------------------------------------------------------- construction
    def _build(self, auto_fl, flip_cells_only):
        spec, g = self.spec, self.g
        mapping = spec['node_fault_mapping']
        in_vals = spec.get('input_values', {})
        out_keys = set(spec.get('output_values', {})) | set(spec.get('alert_values', {}))
        excl = spec.get('exclude_auto_fl', [])
        cutset = self.cuts
        self.end_in, self.end_out = {}, {}      # (stage, node) -> 'input' | 'in_node' ; 'output' | 'out_node'
        for s, st in spec['stages'].items():
            for a in st['inputs']:
                a = g.node_of(a)
                self.end_in[(s, a)] = 'input' if (self._parent(a) in in_vals and st['type'] in ('input', 'inout')) else 'in_node'
            for b in st['outputs']:
                b = g.node_of(b)
                self.end_out[(s, b)] = 'output' if (self._parent(b) in out_keys and st['type'] in ('output', 'inout')) else 'out_node'
        # topological order per stage; end-point registers are split (inputs drive, outputs read D)
        self.order = {s: self._topo(s) for s in spec['stages']}
        self.eligible = {s: self._eligible_parents(s) for s in spec['stages']}
        self._pending_in = []
        # pass 1: all stages, golden then faulty values; in_node values are resolved after out_nodes exist
        side = {}
        self.side_inputs = collections.defaultdict(set)
        for s in spec['stages']:
            reg = self.regions[s]
            for node in self.order[s]:
                kind = self._node_kind(s, node)
                if kind in ('input', 'in_node'):
                    self._make_input_end(s, node, kind, in_vals, mapping, excl, auto_fl)
                    continue
                if kind in ('output', 'out_node'):
                    continue                           # evaluated after its drivers (below)
                self._make_cell(s, node, reg, side, in_vals, mapping, excl, auto_fl, flip_cells_only)
            for node in self.order[s]:
                kind = self._node_kind(s, node, out_side=True)
                if kind in ('output', 'out_node'):
                    self._make_output_end(s, node, kind, reg, side, in_vals, mapping, excl, auto_fl)
        self._resolve_in_nodes()
        self._goal()

    def _parent(self, node):
        return node[3:] if node.startswith('in:') else node[4:] if node.startswith('out:') else node

    def _node_kind(self, s, node, out_side=False):
        if out_side and (s, node) in self.end_out:
            return self.end_out[(s, node)]
        if not out_side and (s, node) in self.end_in:
            return self.end_in[(s, node)]
        if (s, node) in self.end_out and (s, node) not in self.end_in:
            return self.end_out[(s, node)]
        return 'cell'

    def _topo(self, s):
        reg = self.regions[s]
        ends_in = {n for (st, n) in self.end_in if st == s}
        ends_out = {n for (st, n) in self.end_out if st == s}
        succ = collections.defaultdict(set)
        indeg = collections.Counter()
        for u in reg:
            for v in self.g.succ.get(u, ()):
                if v in reg and (u, v) not in self.cuts and v not in ends_in and u not in (ends_out - ends_in):
                    succ[u].add(v); indeg[v] += 1
        q = collections.deque(sorted(n for n in reg if indeg[n] == 0))
        out = []
        while q:
            u = q.popleft(); out.append(u)
            for v in sorted(succ[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        if len(out) != len(reg):
            raise SpecError(f'stage {s}: region is not acyclic after unrolling ({len(reg) - len(out)} nodes on a loop)')
        return out

    def _loc(self, name, s, node, kind, typ, options):
        if name in self.locs:
            raise SpecError(f'duplicate fault location {name}')
        sels = []
        for o in options:
            v = self._new(); self.sel[(name, o)] = v; sels.append(v)
        for a, b in itertools.combinations(sels, 2):
            self.e.add([-a, -b])
        if len(sels) == 1:
            used = sels[0]
        else:
            used = self._new()
            self.e.add([-used] + sels)
            for x in sels: self.e.add([used, -x])
        self.loc_used[name] = used
        self.locs[name] = dict(stage=s, node=node, kind=kind, type=typ, options=list(options), sel=sels)
        return sels

    def _eligible_parents(self, s):
        """SYNFI gen_fault_locations keys fault locations by PARENT name: every node of the stage whose type is not
        in_node/out_node/register contributes its parent; afterwards every node of the stage with such a parent
        (registers included) is a location. Returns that parent set (before exclusions)."""
        reg = self.regions[s]
        par = set()
        for n in reg:
            k_in, k_out = self.end_in.get((s, n)), self.end_out.get((s, n))
            if k_in == 'input' or k_out == 'output':
                par.add(self._parent(n))
            if k_in or k_out:
                if not (k_out and not k_in and self._is_flop(n)):
                    continue
            if self.g.kind.get(n) == 'cell':
                par.add(n)
            if n.startswith('out:'):
                continue
            c = self._cell(n)
            for pin, d in c['port_directions'].items():
                if d != 'input':
                    continue
                net = c['connections'][pin][0]
                if not isinstance(net, int):
                    continue
                u = self.g.driver[net][0]
                if u not in reg or (u, n) in self.cuts:
                    par.add(self._parent(u))
        return par

    def _lazy(self, name, s, node, kind, typ, opts, npins):
        """Selector lists per output pin. Gate-replacement model: one location for the node (all pins together,
        as SYNFI). Bit-flip model: one location per pin when the node has several (a flip is one bit)."""
        if not opts:
            return lambda pin: []
        if self.model != 'flip' or npins <= 1:
            sels = self._loc(name, s, node, kind, typ, opts)
            return lambda pin: sels
        cache = {}

        def f(pin):
            if pin not in cache:
                cache[pin] = self._loc(f'{name}#{pin[0]}{pin[1]}', s, node, kind, typ, opts)
            return cache[pin]
        return f

    def _allowed(self, parent, stage):
        """Is (parent, stage) a fault location? auto_fl: every region node except exclude_auto_fl substrings (SYNFI
        gen_fault_locations); otherwise the spec's explicit fault_locations {parent: [stages]}."""
        if self.auto_fl:
            return (parent in self.eligible[stage]
                    and not any(x in parent for x in self.spec.get('exclude_auto_fl', [])))
        return stage in self.spec.get('fault_locations', {}).get(parent, [])

    def _make_input_end(self, s, node, kind, in_vals, mapping, excl, auto_fl):
        """Stage input end point: constants (SYNFI 'input' with input_values) or an in_node."""
        g = self.g
        name = self._synfi_name(s, node, 'in')
        par = self._parent(node)
        pins = self._out_pins(node)
        if kind == 'in_node':
            ph = self._new()                          # placeholder for Q, tied to the source out_node later
            pf = self._new()
            for pin in pins:
                sg = -1 if pin == ('QN', 0) else 1
                self.gold[(s, node, pin)] = sg * ph
                self.faul[(s, node, pin)] = sg * pf
            self._pending_in.append((s, node, ('Q', 0)))
            return
        vals = self._input_values(node, in_vals[par])
        opts = []
        if self._allowed(par, s):
            opts = self._options('input', mapping, name)
        getsels = self._lazy(name, s, node, 'input_end', 'input', opts, len(pins))
        for pin in pins:
            gv = vals.get(pin)
            if gv is None:
                gv = self._new()
            self.gold[(s, node, pin)] = gv
            fv = gv
            for o, sv in zip(opts, getsels(pin)):
                alt = (-gv if pin in vals else self._new()) if o in ('input_fault', 'flip') else gv
                fv = self.e.g_mux(sv, alt, fv)
            self.faul[(s, node, pin)] = fv

    def _has_edges(self, s, node):
        return True

    def _input_values(self, node, spec_vals):
        """{(out_port, bit): constant literal} for an input end point. Ports: bit i of the port. Registers: SYNFI
        gives the value on pin D; Q = value, QN = !value."""
        out = {}
        if node.startswith('in:') or node.startswith('out:'):
            for _port, pins in spec_vals.items():
                for i, v in pins.items():
                    out[('P', int(i))] = T_ if v else F_
        else:
            for _port, pins in spec_vals.items():
                for i, v in pins.items():
                    out[('Q', 0)] = T_ if v else F_
                    out[('QN', 0)] = F_ if v else T_
        return out

    def _out_pins(self, node):
        if node.startswith('in:'):
            p = node[3:]
            return [('P', i) for i, b in enumerate(self.m['ports'][p]['bits']) if isinstance(b, int)]
        c = self._cell(node)
        return [(p, 0) for p, d in c['port_directions'].items() if d == 'output' and c['connections'].get(p)
                and isinstance(c['connections'][p][0], int)]

    def _options(self, typ, mapping, name):
        if self.model == 'flip':
            return ['flip']
        if typ not in mapping:
            raise SpecError(f'no node_fault_mapping entry for {typ} (location {name}); SYNFI would stop here too')
        return list(mapping[typ])

    def _synfi_name(self, s, node, role):
        par = self._parent(node)
        split = (s, node) in self.end_in and (s, node) in self.end_out
        if split:
            return f'{par}_{"in" if role == "in" else "out"}_{s}'
        if role == 'output' and not node.startswith('out:'):
            return f'{par}_output_{s}'
        return f'{par}_{s}'

    def _src(self, s, reader, net, reg, side, in_vals, mapping, excl, auto_fl):
        """(golden, faulty) literal of `net` as read by region node `reader` in stage s."""
        if net == '0': return F_, F_
        if net == '1': return T_, T_
        if not isinstance(net, int):
            raise SpecError(f'{reader}: constant {net!r}')
        u, upin = self.g.driver[net]
        pin = ('P', upin) if u.startswith('in:') else (upin, 0)
        if u in reg and (u, reader) not in self.cuts:
            if (s, u) in self.end_out and (s, u) not in self.end_in:
                raise SpecError(f'stage {s}: output end point {u} is also read inside the region (not modelled)')
            return self.gold[(s, u, pin)], self.faul[(s, u, pin)]
        # side input: a driver outside the region, or a register cut by unrolling (one free node per reader)
        if (u, reader) in self.cuts:
            key = (s, 'cut', u, reader); name = f'{u}_{reader}_{s}'
        else:
            key = (s, 'side', u); name = f'{self._parent(u)}_{s}'
        if key not in side:
            self.side_keys.append(key)
            side[key] = dict(name=name, pins={}, sels=None, opts=None)
            par = self._parent(u)
            if self._allowed(par, s):
                opts = self._options('input', mapping, name)
                side[key]['opts'] = opts
                side[key]['sels'] = self._lazy(name, s, u, 'side', 'input', opts, len(self._out_pins(u)))
            self.side_inputs[s].add(par)
        d = side[key]
        if pin not in d['pins']:
            par = self._parent(u)
            if par in in_vals:
                vals = self._input_values(u, in_vals[par])
                gv = vals.get(pin) or self._new()
                const = pin in vals
            else:
                gv = self._new(); const = False
            fv = gv
            for o, sv in zip(d['opts'] or [], d['sels'](pin) if d['sels'] else []):
                alt = (-gv if const else self._new()) if o in ('input_fault', 'flip') else gv
                fv = self.e.g_mux(sv, alt, fv)
            d['pins'][pin] = (gv, fv)
        return d['pins'][pin]

    def _make_cell(self, s, node, reg, side, in_vals, mapping, excl, auto_fl, flip_cells_only):
        c = self._cell(node)
        t = c['type']
        name = f'{node}_{s}'
        envg, envf = {}, {}
        for p, d in c['port_directions'].items():
            if d != 'input':
                continue
            gv, fv = self._src(s, node, c['connections'][p][0], reg, side, in_vals, mapping, excl, auto_fl)
            envg[p], envf[p] = gv, fv
        if t in ng.FLOP_PINS:                         # transparent register inside a region (SYNFI: Q = D)
            dp = ng.FLOP_PINS[t][0]
            fq = self._flop_fault(s, node, t, envf[dp], mapping, f'{node}_{s}')
            for p in ('Q', 'QN'):
                if c['connections'].get(p) and isinstance(c['connections'][p][0], int):
                    sgn = 1 if p == 'Q' else -1
                    self.gold[(s, node, (p, 0))] = sgn * envg[dp]
                    self.faul[(s, node, (p, 0))] = fq if p == 'Q' else -envf[dp]
            return
        outs = [p for p, d in c['port_directions'].items() if d == 'output' and c['connections'].get(p)
                and isinstance(c['connections'][p][0], int)]
        opts = []
        if self._allowed(node, s):
            opts = self._options(t, mapping, name)
        getsels = self._lazy(name, s, node, 'cell', t, opts, len(outs))
        for p in outs:
            gv = self._fn(t, p, envg)
            self.gold[(s, node, (p, 0))] = gv
            fv = self._fn(t, p, envf)
            for o, sv in zip(opts, getsels((p, 0))):
                if o == 'flip':
                    alt = -fv
                elif o == 'prim_flop_fault':
                    raise SpecError('prim_flop_fault on a combinational cell')
                else:
                    alt = self._replacement(t, o, p, envf)
                fv = self.e.g_mux(sv, alt, fv)
            self.faul[(s, node, (p, 0))] = fv

    def _flop_fault(self, s, node, t, fd, mapping, name):
        """Faulty Q of a transparent register. SYNFI 'prim_flop_fault' gives Q = !D; its QN stays !D (the faulty
        function is looked up by cell type, not by pin, so QN is unchanged)."""
        if not self._allowed(node, s):
            return fd
        opts = self._options(t, mapping, name)
        sels = self._loc(name, s, node, 'flop', t, opts)
        fq = fd
        for o, sv in zip(opts, sels):
            if o not in ('prim_flop_fault', 'flip'):
                raise SpecError(f'{name}: register fault option {o} not modelled')
            fq = self.e.g_mux(sv, -fd, fq)
        return fq

    def _make_output_end(self, s, node, kind, reg, side, in_vals, mapping, excl, auto_fl):
        """Output end point. Port: value per bit = its driver. Register: its D (SYNFI: register Q = D feeds the
        output / out_node). 'output' nodes are fault locations (output_fault inverts all pins)."""
        if node.startswith('out:'):
            p = node[4:]
            bits = [(i, b) for i, b in enumerate(self.m['ports'][p]['bits'])]
            vals = {}
            for i, b in bits:
                if not isinstance(b, int) or b not in self.g.driver:
                    continue
                u = self.g.driver[b][0]
                if u not in reg:
                    continue                           # pin not driven from inside the region
                vals[('P', i)] = self._src(s, node, b, reg, side, in_vals, mapping, excl, auto_fl)
        else:
            c = self._cell(node)
            dp = ng.FLOP_PINS[c['type']][0]
            gv, fv = self._src(s, node, c['connections'][dp][0], reg, side, in_vals, mapping, excl, auto_fl)
            if kind == 'output' and not (s, node) in self.end_in:
                # SYNFI keeps the register node (Q = D) and adds a separate output node; the register itself also
                # carries its other pins as side inputs (clock, reset) and can be a fault location (parent rule)
                for pin, d in c['port_directions'].items():
                    if d == 'input' and pin != dp:
                        self._src(s, node, c['connections'][pin][0], reg, side, in_vals, mapping, excl, auto_fl)
                fq = self._flop_fault(s, node, c['type'], fv, mapping, f'{node}_{s}')
                vals = {('Q', 0): (gv, fq), ('QN', 0): (-gv, -fv)}
            else:
                vals = {('Q', 0): (gv, fv), ('QN', 0): (-gv, -fv)}
        name = self._synfi_name(s, node, 'output' if kind == 'output' else 'out')
        if kind == 'output':
            opts = []
            if self._allowed(self._parent(node), s):
                opts = self._options('output', mapping, name)
                if self.model == 'flip' and list(mapping.get('output', [])) == ['output']:
                    opts = []                          # the spec does not fault the observed output (no-op mapping)
            getsels = self._lazy(name, s, node, 'output_end', 'output', opts, len(vals) if node.startswith('out:') else 1)
            for pin, (gv, fv) in vals.items():
                for o, sv in zip(opts, getsels(pin if node.startswith('out:') else ('Q', 0))):
                    alt = -fv if o in ('output_fault', 'flip') else fv
                    fv = self.e.g_mux(sv, alt, fv)
                vals[pin] = (gv, fv)
        self.end_vals = getattr(self, 'end_vals', {})
        self.end_vals[(s, node, kind)] = vals

    def _resolve_in_nodes(self):
        """in_node of stage s gets the out_node value of the same register in another stage (SYNFI connect_graphs)."""
        pend = collections.defaultdict(list)
        for s, node, pin in self._pending_in:
            pend[(s, node)].append(pin)
        e = self.e
        for (s, node), pins in pend.items():
            srcs = [(st, n) for (st, n, k) in getattr(self, 'end_vals', {}) if k == 'out_node' and n == node and st != s]
            for pin in pins:
                if not srcs:
                    v = self._new(); gv = fv = v
                else:
                    st, n = srcs[0]
                    if len(srcs) > 1:
                        raise SpecError(f'in_node {node} of {s} fed by several stages {srcs}')
                    gv, fv = self.end_vals[(st, n, 'out_node')][pin if pin in self.end_vals[(st, n, 'out_node')] else ('Q', 0)]
                self._bind_pending(s, node, pin, gv, fv)

    def _bind_pending(self, s, node, pin, gv, fv):
        """Values of in_nodes are needed while building the stage; they are created lazily as placeholder variables
        tied by equivalence clauses once the source out_node is known."""
        pg = self.gold[(s, node, pin)]; pf = self.faul[(s, node, pin)]
        for ph, v in ((pg, gv), (pf, fv)):
            self.e.add([-ph, v]); self.e.add([ph, -v])

    def _goal(self):
        e, sp = self.e, self.spec
        conj = []
        diffs = []
        outv, alv, fv_ = sp.get('output_values', {}), sp.get('alert_values', {}), sp.get('output_fault_values', {})

        def pinvals(node, d):
            out = {}
            for _port, pins in d.items():
                for i, v in pins.items():
                    key = ('P', int(i)) if node.startswith('out:') else ('Q', int(i))
                    out[key] = v
            return out
        ends = getattr(self, 'end_vals', {})
        found = set()
        skipped = []
        for (s, node, kind), vals in ends.items():
            if kind != 'output':
                continue
            par = self._parent(node)
            if par in outv:
                found.add(par)
                for key, v in pinvals(node, outv[par]).items():
                    if key not in vals:
                        skipped.append((par, key))    # SYNFI skips pins not driven from the region
                        continue
                    gl, fl = vals[key]
                    conj.append(gl if v else -gl)
                    if not fv_:
                        diffs.append(-fl if v else fl)
                if fv_ and par in fv_:
                    for key, v in pinvals(node, fv_[par]).items():
                        if key not in vals:
                            skipped.append((par, key)); continue
                        conj.append(vals[key][1] if v else -vals[key][1])
            if par in alv:
                found.add(par)
                for key, v in pinvals(node, alv[par]).items():
                    gl, fl = vals[key]
                    conj += [gl if v else -gl, fl if v else -fl]
        missing = (set(outv) | set(alv)) - found
        if missing:
            raise SpecError(f'output/alert nodes not found in any stage: {missing}')
        for l in conj:
            e.add([l])
        if not fv_:
            e.add(sorted(set(diffs)) or [F_])
        self.goal_info = dict(constraints=len(conj), diff_pins=len(diffs), skipped_pins=sorted(set(map(str, skipped))))

    def placeholders(self):
        pass

    # ---------------------------------------------------------------- solving
    def backend(self, name='auto'):
        if self.be is None:
            self.be = fs.make_backend(self.e, name)
        return self.be

    def check(self, faults, backend='auto'):
        """faults: list of (location name, option). True if this injection is effective (SAT)."""
        be = self.backend(backend)
        on = set()
        for f in faults:
            if f not in self.sel:
                raise KeyError(f)
            on.add(self.sel[f])
        assum = [v if v in on else -v for v in self.sel.values()]
        return bool(be.solve(assum))

    def _card(self, kmax):
        if self.card is None or self.card[0] < kmax:
            if self.card is not None:
                raise SpecError('cardinality already built with a smaller bound')
            locs = list(self.locs)
            outs = fs.totalizer(self.e, [self.loc_used[l] for l in locs], kmax)
            self.card = (kmax, outs)
            if self.be is not None:                  # backend was created before: push new clauses
                self.be = None
        return self.card[1]

    def min_faults(self, kmax, backend='auto', timeout_s=None):
        """Smallest k <= kmax with an effective fault set (ascending sweep). Returns dict."""
        outs = self._card(kmax)
        be = self.backend(backend)
        t0 = time.time()
        rows = []
        deadline = None if timeout_s is None else time.time() + timeout_s
        for k in range(0, kmax + 1):
            ts = time.time()
            assum = [-outs[k]] if k < len(outs) else []
            r = be.solve(assum, deadline=deadline)
            rows.append(dict(k=k, result={True: 'SAT', False: 'UNSAT', None: 'UNKNOWN'}[r], solve_s=round(time.time() - ts, 3)))
            if r is None:
                return dict(min_faults=None, verdict='UNKNOWN', sweep=rows, runtime_s=round(time.time() - t0, 3))
            if r:
                return dict(min_faults=k, verdict='ATTACK_FOUND', witness=self._witness(be.model()), sweep=rows,
                            runtime_s=round(time.time() - t0, 3))
        return dict(min_faults=None, verdict=f'NO_ATTACK_UP_TO_{kmax}', sweep=rows, runtime_s=round(time.time() - t0, 3))

    def _witness(self, model):
        return [dict(location=l, option=o) for (l, o), v in self.sel.items() if model[v]]

    def all_min_attacks(self, k, backend='auto', cap=10000, timeout_s=None):
        """Every effective fault set with exactly k locations (k = the minimum), by blocking clauses over the
        location literals. Each set is re-checked by check() with exactly its own selectors."""
        outs = self._card(k)
        be = self.backend(backend)
        found = []
        assum = [-outs[k]] if k < len(outs) else []
        deadline = None if timeout_s is None else time.time() + timeout_s
        stop = 'exhausted'
        while True:
            if len(found) >= cap:
                stop = 'cap'; break
            r = be.solve(assum, deadline=deadline)
            if r is None:
                stop = 'timeout'; break
            if not r:
                break
            mdl = be.model()
            w = self._witness(mdl)
            locs = sorted({x['location'] for x in w})
            found.append(w)
            fs_add_clause(self.e, be, [-self.loc_used[l] for l in locs])
        return found, stop

    def stats(self):
        st = self.e.stats()
        return dict(cnf=st, locations=len(self.locs), options=len(self.sel), build_s=round(self.t_build, 3),
                    region_cells={s: sum(1 for n in r if self.g.kind.get(n) == 'cell') for s, r in self.regions.items()},
                    region_flops={s: sum(1 for n in r if self.g.kind.get(n) == 'flop') for s, r in self.regions.items()})

    def region_ge(self):
        """Gate equivalents counted as SYNFI's extract_ge does: every node of the target graph (region nodes per
        stage, plus side-input and cut nodes) whose parent is a cell contributes that cell's GE."""
        ge = 0.0
        for s, r in self.regions.items():
            for n in r:
                if n in self.m['cells']:
                    ge += self.lib.ge.get(self.m['cells'][n]['type'], 0)
                if (s, n) in self.end_out and (s, n) not in self.end_in and n in self.m['cells'] and self._is_flop(n) \
                        and self.end_out[(s, n)] == 'output':
                    ge += self.lib.ge.get(self.m['cells'][n]['type'], 0)     # the extra '<reg>_output' node
        for (s, kind, *rest) in self.side_keys:
            u = rest[0]
            if u in self.m['cells']:
                ge += self.lib.ge.get(self.m['cells'][u]['type'], 0)
        return round(ge, 2)
