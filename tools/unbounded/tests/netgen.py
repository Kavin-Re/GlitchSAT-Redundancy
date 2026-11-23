"""Random tiny netlists in Yosys JSON form (for the method-against-method tests)."""
import json, random


def random_netlist(rng, n_flops=3, n_gates=7, n_in=2, n_out=2):
    nid = 2
    def new():
        nonlocal nid
        nid += 1
        return nid
    clk = 2
    sig = [new() for _ in range(n_in)]
    qs = [new() for _ in range(n_flops)]
    avail = sig + qs
    cells = {}
    for g in range(n_gates):
        t = rng.choice(['$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'])
        y = new()
        pick = lambda: rng.choice(avail + (['0', '1'] if rng.random() < 0.05 else []))
        con = {'A': [pick()], 'Y': [y]}
        if t != '$_NOT_': con['B'] = [pick()]
        if t == '$_MUX_': con['S'] = [pick()]
        cells[f'g{g}'] = dict(type=t, connections=con)
        avail.append(y)
    for i, q in enumerate(qs):
        cells[f'ff{i}'] = dict(type='$_DFF_P_', connections={'C': [clk], 'D': [rng.choice(avail)], 'Q': [q]})
    outs = [rng.choice(avail[n_in:]) for _ in range(n_out)]
    init = ''.join(rng.choice('01') for _ in range(n_flops))
    ports = {'clk': dict(direction='input', bits=[clk]), 'sig': dict(direction='input', bits=sig),
             'boot_word': dict(direction='output', bits=outs)}
    netnames = {'clk': dict(bits=[clk], attributes={}), 'sig': dict(bits=sig, attributes={}),
                'st': dict(bits=qs, attributes={'init': init}), 'boot_word': dict(bits=outs, attributes={})}
    return dict(modules={'t': dict(ports=ports, cells=cells, netnames=netnames)})


def write(path, doc):
    with open(path, 'w') as f:
        json.dump(doc, f)
