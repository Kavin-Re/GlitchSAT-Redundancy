#!/usr/bin/env python3
"""R27. Generalised fault-injection wrapper, counter variants.
usage: gen2.py netlist.json top K out.sv goal_port goal_val key attack_port counter_style
 counter_style: 'proj' = 16-bit adder 'used' (project style); 'sat' = ceil(log2(K+2))-bit counter, assume(count+popcnt<=K);
                'onehot' = K+1 unary thermometer counter. Free-flip sites are restricted to cone-of-influence of goal (coi=1 default)."""
import json, sys
nl, top, K, out, gport, gval, key, aport, style = sys.argv[1:10]; K=int(K); gval=int(gval,0); key=int(key,0)
m = json.load(open(nl))['modules'][top]; ports = m['ports']
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
qs = [q for _, q in dffs]; dq = {q: d for d, q in dffs}
# COI of goal
gb = ports[gport]['bits']; coi=set(); st=[b for b in gb if isinstance(b,int)]
while st:
    b=st.pop()
    if b in coi: continue
    coi.add(b)
    if b in drivers: st += [v[0] for p,v in drivers[b][1].items() if p!='Y' and isinstance(v[0],int)]
    elif b in dq and isinstance(dq[b],int): st.append(dq[b])
sites = [b for b in list(qs)+list(drivers) if b in coi]
sidx = {b: i for i, b in enumerate(sites)}
def ref(b):
    if b in ('0','x','z'): return "1'b0"
    if b == '1': return "1'b1"
    if b in inbit: return inbit[b]
    return f"n{b}"
def fl(b): return f" ^ flip[{sidx[b]}]" if b in sidx else ""
sw = len(ports[aport]['bits']); gw = len(gb)
L=[f"module fi_{top}(input clk, input [{sw-1}:0] sig, input [{len(sites)-1}:0] flip);"]
L.append(f"  reg [{sw-1}:0] sig_q; reg started = 0;")
for q in qs:
    if q in coi: L.append(f"  reg r{q} = 1'b{int(init.get(q, False))};")
for q in qs:
    if q in coi: L.append(f"  wire n{q} = r{q}{fl(q)};")
for b,(t,con) in drivers.items():
    if b not in coi: continue
    g=lambda p: ref(con[p][0])
    e={'$_AND_':lambda:f"{g('A')} & {g('B')}",'$_OR_':lambda:f"{g('A')} | {g('B')}",'$_XOR_':lambda:f"{g('A')} ^ {g('B')}",'$_NOT_':lambda:f"~{g('A')}",'$_MUX_':lambda:f"{g('S')} ? {g('B')} : {g('A')}"}[t]()
    L.append(f"  wire n{b} = ({e}){fl(b)};")
L.append("  always @(posedge clk) begin")
for d,q in dffs:
    if q in coi: L.append(f"    r{q} <= {ref(d)};")
L.append("  end")
L.append(f"  wire [{gw-1}:0] gw = {{" + ", ".join(ref(b) for b in reversed(gb)) + "};")
pc = ' + '.join(f"flip[{i}]" for i in range(len(sites)))
if style == 'proj':
    L.append(f"  reg [15:0] used = 0; wire [15:0] this = {pc};")
    L.append("  always @(posedge clk) used <= used + this;")
    cond=f"used + this <= {K}"
elif style == 'sat':
    W=max(1,(K+1).bit_length())
    L.append(f"  reg [{W-1}:0] used = 0; wire [15:0] this = {pc}; wire [15:0] tot = used + this;")
    L.append(f"  always @(posedge clk) used <= tot[{W-1}:0];")   # safe: assume tot<=K so no wrap
    cond=f"tot <= {K}"
else:
    L.append(f"  reg [{K}:0] th = 0; wire [15:0] this = {pc}; wire [15:0] cnt = this + {' + '.join(f'th[{i}]' for i in range(K+1))};")
    L.append(f"  always @(posedge clk) begin : u integer i; for (i=0;i<={K};i=i+1) th[i] <= (cnt > i); end")
    cond=f"cnt <= {K}"
L.append("  always @(posedge clk) begin started <= 1; sig_q <= sig; end")
L.append("`ifdef FORMAL\n  always @* begin")
L.append(f"    assume(sig != {sw}'d{key});")
L.append("    if (started) assume(sig == sig_q);")
L.append(f"    assume({cond});")
L.append(f"    assert(gw != {gw}'d{gval});")
L.append("  end\n`endif\nendmodule")
open(out,'w').write("\n".join(L)+"\n")
print(f"{out}: {len(sites)} sites in COI ({len(qs)} flops total, {len(drivers)} gates total)")
