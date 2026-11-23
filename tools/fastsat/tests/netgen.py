"""Random small netlists in Yosys JSON form (for fuzzing the encoder against the exhaustive reference)."""
import json, random


def random_netlist(rng, max_gates=10, max_flops=3, max_out=3):
    w_sig = rng.randint(1, 3)
    extra = rng.random() < 0.3                       # a second free input port
    nid = [2]

    def new():
        nid[0] += 1
        return nid[0]
    ports = {'clk': {'direction': 'input', 'bits': [2]}}
    sig = [new() for _ in range(w_sig)]
    ports['sig'] = {'direction': 'input', 'bits': sig}
    srcs = list(sig)
    if extra:
        aux = [new() for _ in range(rng.randint(1, 2))]
        ports['aux'] = {'direction': 'input', 'bits': aux}
        srcs += aux
    nf = rng.randint(0, max_flops)
    qs = [new() for _ in range(nf)]
    srcs += qs
    cells = {}; netnames = {}
    ng = rng.randint(1, max_gates)
    gate_out = []
    for i in range(ng):
        y = new()
        ty = rng.choice(['$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_', '$_AND_', '$_XOR_'])
        def pick():
            r = rng.random()
            if r < 0.06: return rng.choice(['0', '1'])
            pool = srcs + gate_out
            if gate_out and r < 0.6: return rng.choice(gate_out[-4:])
            return rng.choice(pool)
        pins = {'$_NOT_': ['A'], '$_MUX_': ['A', 'B', 'S']}.get(ty, ['A', 'B'])
        con = {p: [pick()] for p in pins}
        con['Y'] = [y]
        cells[f'g{i}'] = {'type': ty, 'connections': con}
        gate_out.append(y)
        netnames[f'n{y}'] = {'bits': [y], 'attributes': {}}
    for i, q in enumerate(qs):
        d = rng.choice(gate_out + srcs + (['0', '1'] if rng.random() < 0.1 else []))
        cells[f'ff{i}'] = {'type': '$_DFF_P_', 'connections': {'D': [d], 'Q': [q]}}
        att = {}
        if rng.random() < 0.4:
            att['init'] = rng.choice('01')
        netnames[f'q{i}'] = {'bits': [q], 'attributes': att}
    w_out = rng.randint(1, max_out)
    pool = gate_out + qs + (sig if rng.random() < 0.15 else []) + (['0', '1'] if rng.random() < 0.1 else [])
    out = [rng.choice(pool) for _ in range(w_out)]
    ports['boot_word'] = {'direction': 'output', 'bits': out}
    for i, b in enumerate(sig):
        netnames[f'sig{i}'] = {'bits': [b], 'attributes': {}}
    doc = {'modules': {'t': {'ports': ports, 'cells': cells, 'netnames': netnames}}}
    return doc, dict(w_sig=w_sig, w_out=w_out)


def write(doc, path):
    with open(path, 'w') as f:
        json.dump(doc, f)
