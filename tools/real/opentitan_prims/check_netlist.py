#!/usr/bin/env python3
"""GlitchSAT ext/opentitan: check one synthesised experiment netlist before the solver sees it.
Own code, Apache-2.0.

usage: check_netlist.py NETLIST.json TOP RESET_MODE      RESET_MODE = sim | cycle0

Checks (each failure prints a reason and exits 3):
  * every cell is one the engine models: $_AND_ $_OR_ $_XOR_ $_NOT_ $_MUX_ $_DFF_P_
    (asynchronous-reset flops such as $_DFF_PN0_ must have been removed by async2sync);
  * every flop is clocked by the top-level port `clk` (the engine assumes one clock);
  * ports `sig` (input) and `gout` (output) exist;
  * RESET_MODE sim:    every flop output has a 0/1 init value and `rst_q` starts at 1
                       (the reset cycle was simulated and written back by `sim -w`);
    RESET_MODE cycle0: `rst_q` starts at 0 (the solver's cycle 0 is the reset cycle).
Prints gate, flop and port counts on success.
"""
import collections
import json
import sys

SUPPORTED = {'$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'}
FLOP = '$_DFF_P_'


def fail(msg):
    print(f'check_netlist: FAIL: {msg}', file=sys.stderr)
    sys.exit(3)


def main(argv):
    if len(argv) != 4 or argv[3] not in ('sim', 'cycle0'):
        fail('usage: check_netlist.py NETLIST.json TOP sim|cycle0')
    path, top, mode = argv[1], argv[2], argv[3]
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        fail(f'cannot read {path}: {e}')
    mods = doc.get('modules', {})
    if top not in mods:
        fail(f'module {top!r} not in {path} (found: {sorted(mods)})')
    if len(mods) != 1:
        fail(f'expected one flattened module, found {len(mods)}: {sorted(mods)}')
    m = mods[top]
    ports = m.get('ports', {})
    for name, direction in (('clk', 'input'), ('sig', 'input'), ('gout', 'output')):
        if ports.get(name, {}).get('direction') != direction:
            fail(f'port {name!r} missing or not an {direction}')
    clk_bits = ports['clk']['bits']

    types = collections.Counter(c.get('type') for c in m['cells'].values())
    bad = {t: n for t, n in types.items() if t not in SUPPORTED and t != FLOP and t != '$scopeinfo'}
    if bad:
        fail(f'cells the engine does not model: {dict(sorted(bad.items()))}')

    qbits = []
    for name, c in m['cells'].items():
        if c['type'] != FLOP:
            continue
        con = c['connections']
        if con.get('C') != clk_bits:
            fail(f'flop {name} is not clocked by port clk (C={con.get("C")})')
        qbits.append(con['Q'][0])

    init = {}
    for name, n in m['netnames'].items():
        iv = n.get('attributes', {}).get('init')
        if not iv:
            continue
        for i, b in enumerate(reversed(iv)):
            if i < len(n['bits']) and isinstance(n['bits'][i], int):
                init.setdefault(n['bits'][i], b)

    rst = m['netnames'].get('rst_q')
    if rst is None:
        fail('net rst_q not found (wrapper reset register removed or renamed?)')
    rst_init = init.get(rst['bits'][0])
    if mode == 'sim':
        missing = [b for b in qbits if init.get(b) not in ('0', '1')]
        if missing:
            fail(f'{len(missing)} of {len(qbits)} flops have no 0/1 init after `sim -w` '
                 '(power-up state unknown; the engine would assume 0)')
        if rst_init != '1':
            fail(f'rst_q init is {rst_init!r}, expected 1 after the simulated reset cycle')
    else:
        if rst_init != '0':
            fail(f'rst_q init is {rst_init!r}, expected 0 (reset during cycle 0)')

    ones = sum(1 for b in qbits if init.get(b) == '1')
    gates = sum(n for t, n in types.items() if t in SUPPORTED)
    print(f'netlist OK: {top}: gates={gates} flops={len(qbits)} (flops starting at 1: {ones}) '
          f'reset_mode={mode} sig={len(ports["sig"]["bits"])} bit(s) gout={len(ports["gout"]["bits"])} bit(s) '
          f'cells={dict(sorted(types.items()))}')


if __name__ == '__main__':
    main(sys.argv)
