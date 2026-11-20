# Convert OpenROAD write_verilog -include_pwr_gnd netlist to SPICE (hierarchical, std cells as subckt calls)
import re,sys
v=open(sys.argv[1]).read(); out=[]
hdr=re.search(r'module\s+\w+\s*\((.*?)\);',v,re.S).group(1)
ports=[p.strip() for p in hdr.replace('\n',' ').split(',')]
decl={}
for m in re.finditer(r'^\s*(input|output|inout)\s*(\[(\d+):(\d+)\])?\s*(\w+);',v,re.M):
    decl[m.group(5)]=(int(m.group(3)),int(m.group(4))) if m.group(2) else None
pl=[]
for p in ports:
    r=decl.get(p)
    if r: pl+= [f"{p}[{i}]" for i in range(r[0],r[1]-1,-1)]
    else: pl.append(p)
pl+=['VPWR','VGND']
out.append('.subckt '+re.search(r'module\s+(\w+)',v).group(1)+' '+' '.join(pl))
body=v.split(');',1)[1]
for m in re.finditer(r'^\s*(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\((.*?)\);',body,re.M|re.S):
    cell,name,con=m.groups()
    pins=re.findall(r'\.(\w+)\(([^)]*)\)',con)
    # order of pins is resolved by netgen via subckt order -> need lib order
    out.append(('X'+name,cell,pins))
open(sys.argv[2]+'.pins','w').write(repr(out[1:]))
import pickle
lib=open(sys.argv[3]).read()
order={m.group(1):m.group(2).split() for m in re.finditer(r'^\.subckt\s+(\S+)\s+(.*)$',lib,re.M)}
lines=[out[0]]
for n,c,p in out[1:]:
    d={a:b.strip().replace('\\','') for a,b in p}
    o=order.get(c)
    if o is None: lines.append(f"* no lib subckt for {c} {n}"); continue
    lines.append(' '.join([n]+[d.get(x,{'VPWR':'VPWR','VPB':'VPWR','VGND':'VGND','VNB':'VGND'}.get(x,'NC_%s_%s'%(n,x))) for x in o]+[c]))
lines.append('.ends')
open(sys.argv[2],'w').write('\n'.join(lines)+'\n')
