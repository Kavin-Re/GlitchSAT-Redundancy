"""SYNFI-compatible target-region extraction, written independently of SYNFI's code (graph reachability).

SYNFI (fi_injector.extract_graph) analyses only the part of the netlist that lies between the stage input and
stage output nodes named in a fault specification:
  1. Registers that sit on a feedback loop and are not stage end points are cut: each register->reader edge that
     leads back to the register is replaced by a free input ("unrolling").
  2. Per stage, for every (input node, output node) pair: the nodes on a path from input to output; when input ==
     output (a register), the nodes on a cycle through the end-point registers.
  3. Every cell of the region gets its missing fan-in drivers added as free inputs ("side inputs").
Registers inside a region are transparent (SYNFI cell library: Q = D, QN = !D).

Here step 2 uses reachability where it is exact: a != b -> nodes reachable from a without passing b that reach b
without passing a; when that part of the graph has a cycle, simple paths are enumerated inside it; a == b ->
nodes in a strongly connected component with more than one node (each such node lies on a simple cycle). For an
acyclic graph the first is exactly the set of nodes on simple paths; tests/test_region.py checks equality with
SYNFI's own extracted graph for every shipped example.
"""
import collections

from . import nangate as ng


class CellGraph:
    """Cell-level graph of an original Nangate45 netlist. Node ids: cell names, 'in:<port>', 'out:<port>'."""

    def __init__(self, doc, top):
        m = doc['modules'][top]
        self.m = m
        self.kind = {}
        self.driver = {}                    # net -> (node, pin)
        self.readers = collections.defaultdict(list)   # net -> [(node, pin)]
        for p, x in m['ports'].items():
            if x['direction'] == 'input':
                self.kind['in:' + p] = 'in_port'
                for i, b in enumerate(x['bits']):
                    if isinstance(b, int):
                        self.driver[b] = ('in:' + p, i)
            elif x['direction'] == 'output':
                self.kind['out:' + p] = 'out_port'
                for i, b in enumerate(x['bits']):
                    if isinstance(b, int):
                        self.readers[b].append(('out:' + p, i))
        for cn, c in m['cells'].items():
            if c['type'] in ng.NO_LOGIC:
                continue
            self.kind[cn] = 'flop' if c['type'] in ng.FLOP_PINS else 'cell'
            for pin, d in c['port_directions'].items():
                for b in c['connections'].get(pin, []):
                    if not isinstance(b, int):
                        continue
                    if d == 'output':
                        self.driver[b] = (cn, pin)
                    else:
                        self.readers[b].append((cn, pin))
        self.succ = collections.defaultdict(set)
        self.pred = collections.defaultdict(set)
        for b, (u, _) in self.driver.items():
            for v, _ in self.readers.get(b, []):
                self.succ[u].add(v); self.pred[v].add(u)

    def node_of(self, name):
        """SYNFI names stage end points by cell name or port name."""
        if name in self.kind:
            return name
        for pre in ('in:', 'out:'):
            if pre + name in self.kind:
                return pre + name
        raise KeyError(name)


def _reach(start, succ, blocked=()):
    seen = {start}
    dq = collections.deque([start])
    while dq:
        u = dq.popleft()
        for v in succ.get(u, ()):
            if v not in seen and v not in blocked:
                seen.add(v); dq.append(v)
    return seen


def unroll(g, keep):
    """SYNFI's unrolling: for every flop r not in `keep`, cut r->s when s reaches a predecessor of r.
    Returns (succ, pred, cuts) with cuts = {(r, s)}: s reads r's output as a free value."""
    succ = {u: set(v) for u, v in g.succ.items()}
    cuts = set()
    for r, k in g.kind.items():
        if k != 'flop' or r in keep:
            continue
        preds = g.pred.get(r, set())
        for s in list(g.succ.get(r, ())):
            # has_path(s, p) for some predecessor p of r  <=>  s reaches r through the original graph
            if preds and (r in _reach(s, g.succ) or any(p == s for p in preds)):
                cuts.add((r, s))
    for r, s in cuts:
        succ[r].discard(s)
    pred = collections.defaultdict(set)
    for u, vs in succ.items():
        for v in vs:
            pred[v].add(u)
    return succ, pred, cuts


def _sccs(nodes, succ):
    """Tarjan (iterative). Returns list of SCCs (sets)."""
    index, low, on, st, out = {}, {}, set(), [], []
    ctr = [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(succ.get(root, ())))]
        index[root] = low[root] = ctr[0]; ctr[0] += 1; st.append(root); on.add(root)
        while work:
            u, it = work[-1]
            adv = False
            for v in it:
                if v not in index:
                    index[v] = low[v] = ctr[0]; ctr[0] += 1; st.append(v); on.add(v)
                    work.append((v, iter(succ.get(v, ())))); adv = True; break
                elif v in on:
                    low[u] = min(low[u], index[v])
            if adv:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[u])
            if low[u] == index[u]:
                comp = set()
                while True:
                    w = st.pop(); on.discard(w); comp.add(w)
                    if w == u: break
                out.append(comp)
    return out


def simple_path_nodes(a, b, succ, pred):
    """Nodes on some simple path a -> b. Superset first: reachable from a without passing b and reaching b without
    passing a. If that subgraph is acyclic the superset is exact; otherwise simple paths are enumerated inside it
    (networkx.all_simple_paths, the primitive SYNFI uses), which is exact because every simple a -> b path lies in it."""
    sup = (_reach(a, succ, blocked={b}) & _reach(b, pred, blocked={a})) | {a, b}
    if b not in _reach(a, succ):
        return set()
    import networkx as nx
    h = nx.DiGraph()
    h.add_nodes_from(sup)
    h.add_edges_from((u, v) for u in sup for v in succ.get(u, ()) if v in sup and v != a and u != b)
    if nx.is_directed_acyclic_graph(h):
        return sup
    out = set()
    for path in nx.all_simple_paths(h, a, b):
        out.update(path)
    return out


def extract(g, spec):
    """spec: one SYNFI fimodel dict. Returns {stage: set(nodes)} (cells, flops and end-point nodes)."""
    keep = set()
    for st in spec['stages'].values():
        for a, b in zip(st['inputs'], st['outputs']):
            if a == b:
                keep.add(g.node_of(a))
    succ, pred, cuts = unroll(g, keep)
    regions = {}
    cyc = None
    for sname, st in spec['stages'].items():
        ins = [g.node_of(x) for x in st['inputs']]
        outs = [g.node_of(x) for x in st['outputs']]
        reg = set()
        for a in set(ins):
            for b in set(outs):
                if a == b:
                    if cyc is None:
                        cyc = set()
                        for comp in _sccs(list(g.kind), succ):
                            if len(comp) > 1:
                                cyc |= comp
                    reg |= cyc
                else:
                    reg |= simple_path_nodes(a, b, succ, pred)
        regions[sname] = reg
    return regions, cuts
