#!/usr/bin/env python3
"""Generate a SymbiYosys-ready fault-injection wrapper from a flattened Yosys JSON netlist
(same netlists glitchsat uses).  Usage: gen_wrapper.py netlist.json top K out.sv
Model (mirrors scripts/glitchsat.py): a free 1-bit input flip[i] per fault site (every gate output net and every
flop Q net) is XORed onto that net for the current cycle only (a Q flip does not change the stored state).
Across the run at most K flips total (running counter). sig is free but held constant, and != 8'hC3.
Property: boot_word never equals 8'h96 (observed, faults applied on the observed nets too)."""
import json, sys
nl, top, K, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
m = json.load(open(nl))['modules'][top]
ports = m['ports']
drivers, dffs = {}, []
for cn, c in m['cells'].items():
    t, con = c['type'], c['connections']
    if t == '$_DFF_P_': dffs.append((con['D'][0], con['Q'][0]))
    else: drivers[con['Y'][0]] = (t, con)
init = {}
for n, x in m['netnames'].items():
    iv = x['attributes'].get('init')
    if iv:
        for i, b in enumerate(reversed(iv)): init[x['bits'][i]] = (b == '1')
inbit = {}
for p, v in ports.items():
    if v['direction'] == 'input' and p != 'clk':
        for i, b in enumerate(v['bits']): inbit[b] = f"{p}[{i}]"
qs = [q for _, q in dffs]
sites = list(qs) + list(drivers)
sidx = {b: i for i, b in enumerate(sites)}
def ref(b):
    if b in ('0', 'x', 'z'): return "1'b0"
    if b == '1': return "1'b1"
    if b in inbit: return inbit[b]
    return f"n{b}"
L = []
L.append(f"module fi_{top}(input clk, input [7:0] sig, input [{len(sites)-1}:0] flip);")
L.append("  reg [7:0] sig_q; reg started = 0; reg [15:0] used = 0;")
for q in qs: L.append(f"  reg r{q} = 1'b{int(init.get(q, False))};")
# nets
for q in qs: L.append(f"  wire n{q} = r{q} ^ flip[{sidx[q]}];")
for b, (t, con) in drivers.items():
    g = lambda p: ref(con[p][0])
    e = {'$_AND_': lambda: f"{g('A')} & {g('B')}", '$_OR_': lambda: f"{g('A')} | {g('B')}", '$_XOR_': lambda: f"{g('A')} ^ {g('B')}",
         '$_NOT_': lambda: f"~{g('A')}", '$_MUX_': lambda: f"{g('S')} ? {g('B')} : {g('A')}"}[t]()
    L.append(f"  wire n{b} = ({e}) ^ flip[{sidx[b]}];")
L.append("  always @(posedge clk) begin")
for d, q in dffs: L.append(f"    r{q} <= {ref(d)};")
L.append("  end")
bw = ports['boot_word']['bits']
L.append("  wire [7:0] boot_word = {" + ", ".join(ref(b) for b in reversed(bw)) + "};")
L.append(f"  wire [15:0] this = {' + '.join(f'flip[{i}]' for i in range(len(sites)))};")
L.append("  always @(posedge clk) begin started <= 1; used <= used + this; sig_q <= sig; end")
L.append("`ifdef FORMAL")
L.append(f"  always @* begin")
L.append("    assume(sig == 8'hC3);" if len(sys.argv) > 5 and sys.argv[5] == 'honest' else "    assume(sig != 8'hC3);")
L.append("    if (started) assume(sig == sig_q);")
L.append(f"    assume(used + this <= {K});")
L.append("    assert(boot_word != 8'h96);")
L.append("  end")
L.append("`endif")
L.append("endmodule")
open(out, 'w').write("\n".join(L) + "\n")
print(f"{out}: {len(sites)} fault sites ({len(qs)} flop Q, {len(drivers)} gates)")
