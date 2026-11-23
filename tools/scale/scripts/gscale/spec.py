"""Problem from a netlist file and a few plain options (used by the CLI and the benchmark)."""
import json
from . import fastsat, circuit


def load_problem(netlist, top, cycles, goal_out='boot_word', goal_value=0x96, attack_input='sig', key=0xC3,
                 goal=None, quiet=None, fix=None, inputs='const', no_key=False, sites_meta=None, clock=None):
    """Without goal/quiet/fix/inputs/sites_meta/no_key this is exactly the question of scripts/glitchsat.py.
    goal, quiet, fix: lists of "PORT=VALUE". inputs: 'const' (one value per run) or 'cycle' (a new value every
    cycle). sites_meta: JSON file with "sites" (net ids that may be flipped) and optionally "resets"
    ([{net, active}], tied to the inactive level)."""
    fs = fastsat()
    nl = fs.gs.Netlist(netlist, top)
    generic = bool(goal or quiet or fix or inputs != 'const' or sites_meta or no_key)
    if not generic:
        return circuit.engine_problem(nl, cycles, goal_out, goal_value, attack_input, key)
    c = circuit.from_engine(nl, clock_ports=tuple(clock or ['clk', 'clk_i']))

    def port(name, direction):
        if name not in c.ports or c.ports[name][0] != direction:
            raise circuit.CircuitError('%r is not an %s port of %s' % (name, direction, top))
        return c.ports[name][1]

    def pairs(specs, direction):
        out = []
        for sp in specs or []:
            name, eq, val = sp.partition('=')
            if not eq: raise circuit.CircuitError('expected PORT=VALUE, got %r' % sp)
            v = int(val, 0)
            for i, b in enumerate(port(name, direction)):
                out.append((b, (v >> i) & 1))
        return out
    g = pairs(goal, 'output') or pairs(['%s=%d' % (goal_out, goal_value)], 'output')
    q = pairs(quiet, 'output')
    in_mode = {b: inputs for b in c.inputs}
    sites = None
    if sites_meta:
        meta = json.load(open(sites_meta)) if isinstance(sites_meta, str) else sites_meta
        sites = {int(n) for n in meta['sites']}
        for r in meta.get('resets', []):
            if isinstance(r.get('net'), int) and r['net'] in c.inputs:
                in_mode[r['net']] = 1 - int(r['active'])
    for b, v in pairs(fix, 'input'):
        if isinstance(b, int): in_mode[b] = int(v)
    neq = None
    if not no_key:
        ab = port(attack_input, 'input')
        for b in ab: in_mode[b] = 'const'
        neq = (list(ab), key & ((1 << len(ab)) - 1))
    return circuit.Problem(c, cycles, g, q, neq, in_mode, sites, label=top)
