#!/usr/bin/env python3
"""RUN2 adapter (own code, not derived): Yosys JSON gate netlist (reference/spike_netlists) -> flat structural
Verilog with one 1-bit wire per net (n<bit>), so a Yosys 'wire' == one net. Used to feed uArchiFI.
Usage: python3 -I j2v.py netlist.json top out.v"""
import json, sys
nl, top, out = sys.argv[1:4]
m = json.load(open(nl))['modules'][top]
ports = m['ports']
ins = {bb for p in ports.values() if p['direction'] == 'input' for bb in p['bits']}
def b(x):
    if isinstance(x, str): return {'0': "1'b0", '1': "1'b1"}[x]
    return f'i{x}' if x in ins else f'n{x}'
init = {}
for k, v in m['netnames'].items():
    iv = v['attributes'].get('init')
    if iv:
        for i, bit in enumerate(reversed(iv)):   # init string is MSB first
            pass
        for i, bit in enumerate(iv[::-1]):
            if i < len(v['bits']) and isinstance(v['bits'][i], int): init[v['bits'][i]] = bit
allbits = set()
L = []
for n, c in m['cells'].items():
    t = c['type']; cn = c['connections']
    for p in cn.values():
        for x in p:
            if isinstance(x, int): allbits.add(x)
for p in ports.values():
    for x in p['bits']:
        if isinstance(x, int): allbits.add(x)
hdr = f"module {top}(" + ", ".join(ports) + ");\n"
for pn, p in ports.items():
    w = len(p['bits'])
    hdr += f"  {p['direction']} " + (f"[{w-1}:0] " if w > 1 else "") + f"{pn};\n"
body = ""
dff_q = set()
for n, c in m['cells'].items():
    if c['type'] == '$_DFF_P_': dff_q.add(c['connections']['Q'][0])
for x in sorted(allbits):
    if x in ins: continue
    body += (f"  reg n{x}; " + (f"initial n{x} = 1'b{init.get(x,'0')};\n" if x in dff_q else "\n")) if x in dff_q else f"  wire n{x};\n"
for pn, p in ports.items():
    if p['direction'] == 'input':
        for i, x in enumerate(p['bits']):
            if isinstance(x, int) and pn != 'clk': body += f"  wire i{x}; assign i{x} = {pn}[{i}];\n"
            elif pn == 'clk': body += f"  wire i{x}; assign i{x} = clk;\n"
for n, c in m['cells'].items():
    t = c['type']; cn = c['connections']; g = lambda k: b(cn[k][0])
    if t == '$_NOT_': body += f"  assign {g('Y')} = ~{g('A')};\n"
    elif t in ('$_AND_', '$_OR_', '$_XOR_', '$_NAND_', '$_NOR_', '$_XNOR_'):
        op = {'AND': '&', 'OR': '|', 'XOR': '^', 'NAND': '&', 'NOR': '|', 'XNOR': '^'}[t[2:-1]]
        neg = t[2:-1] in ('NAND', 'NOR', 'XNOR')
        e = f"{g('A')} {op} {g('B')}"
        body += f"  assign {g('Y')} = {'~(' + e + ')' if neg else e};\n"
    elif t == '$_MUX_': body += f"  assign {g('Y')} = {g('S')} ? {g('B')} : {g('A')};\n"
    elif t == '$_DFF_P_': body += f"  always @(posedge {g('C')}) {g('Q')} <= {g('D')};\n"
    else: raise SystemExit('unsupported cell ' + t)
for pn, p in ports.items():
    if p['direction'] == 'output':
        for i, x in enumerate(p['bits']):
            body += f"  assign {pn}[{i}] = {b(x)};\n" if len(p['bits']) > 1 else f"  assign {pn} = {b(x)};\n"
open(out, 'w').write(hdr + body + "endmodule\n")
