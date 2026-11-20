# usage: python3 flow_patched/render.py v1|v2   (from layout/v_designs)
import sys, re, klayout.lay as lay, klayout.db as db
from PIL import Image, ImageDraw, ImageFont
D=sys.argv[1]; N=2400
LYP="/tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/klayout/tech/sky130A.lyp"
LEF="/tmp/mm_root/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
size={}; cur=None
for l in open(LEF):
    m=re.match(r"MACRO (\S+)",l)
    if m: cur=m.group(1)
    m=re.match(r"\s+SIZE ([\d.]+) BY ([\d.]+)",l)
    if m and cur: size[cur]=(float(m.group(1)),float(m.group(2))); cur=None
comp={}
for l in open(f"out/{D}.def"):
    m=re.match(r"\s*- (\S+) (\S+) \+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \) (\w+)",l)
    if m:
        n,c,x,y,o=m.groups(); x=int(x)/1000; y=int(y)/1000; w,h=size[c]
        comp[n.replace("\\","")]=(c,x,y,x+w,y+h)
die=[float(v)/1000 for v in re.search(r"DIEAREA \( 0 0 \) \( (\d+) (\d+)",open(f"out/{D}.def").read()).groups()]
def render(box,fn,hl,title,lines):
    v=lay.LayoutView(); v.load_layout(f"out/{D}.gds",True); v.load_layer_props(LYP)
    v.max_hier(); v.set_config("background-color","#101018"); v.set_config("grid-visible","false")
    v.resize(N,N); v.zoom_box(db.DBox(*box)); v.save_image(fn,N,N)
    im=Image.open(fn).convert("RGB"); d=ImageDraw.Draw(im)
    f=ImageFont.load_default(size=34); fs=ImageFont.load_default(size=28)
    sx=N/(box[2]-box[0]); sy=N/(box[3]-box[1])
    P=lambda x,y:((x-box[0])*sx, N-(y-box[1])*sy)
    for (b,col,lab) in hl:
        x0,y0=P(b[0],b[3]); x1,y1=P(b[2],b[1]); p=6
        d.rectangle([x0-p,y0-p,x1+p,y1+p],outline=col,width=7)
        tx=min(max(x0,10),N-520); ty=y0-p-44 if y0>90 else y1+p+8
        d.rectangle([tx-4,ty-2,tx+len(lab)*19+8,ty+38],fill=(16,16,24)); d.text((tx,ty),lab,fill=col,font=f)
    d.rectangle([0,N-40-44*len(lines),N,N],fill=(16,16,24))
    for i,t in enumerate(lines): d.text((14,N-40-44*len(lines)+8+44*i),t,fill=(255,255,255),font=fs)
    im.save(fn)
def bb(names):
    r=[comp[n] for n in names]; return (min(c[1] for c in r),min(c[2] for c in r),max(c[3] for c in r),max(c[4] for c in r))
full=(0,0,max(die),max(die))
note="ANNOTATION: derived from post-synthesis netlist; solver fault model ran on a different generic gate netlist."
render(full,f"out/{D}_full.png",[],D,[f"{D}: MEASURED placed+routed sky130_fd_sc_hd layout (GDS via magic). router DRC 0, top-cell magic DRC none listed, netgen LVS match (see RESULT.md)"])
if D=="v1":
    ok=[n for n,c in comp.items() if c[0]=="sky130_fd_sc_hd__and2_0"]
    pn=open("out/v1_pnr.v").read()
    drv=re.search(r"sky130_fd_sc_hd__(\w+) (\S+)\s*\((?:[^;]*?)\.X\(ok\)\)",pn)
    print("driver of ok in pnr netlist:",drv.group(1),drv.group(2))
    n=drv.group(2); b=comp[n]; print("bbox",b)
    cx=(b[1]+b[3])/2; cy=(b[2]+b[4])/2; h=9
    box=(cx-h,cy-h,cx+h,cy+h)
    render(box,"out/v1_zoom_ok.png",[((b[1],b[2],b[3],b[4]),(255,60,60),"single point of failure: ok")],D,
      [f"ANNOTATION: instance {n} ({b[0].split('__')[1]}) drives net `ok` = m1 & m2 (found by net name in pnr netlist, name survived).",note])
else:
    cols={"c0":(255,80,80),"c1":(80,255,80),"c2":(90,160,255)}
    hl=[]
    for c,col in cols.items():
        names=[n for n in comp if n.startswith(c+"/")]
        for n in names: hl.append(((comp[n][1],comp[n][2],comp[n][3],comp[n][4]),col,n))
    render(full,"out/v2_zoom_copies.png",hl,D,["ANNOTATION: three cmp8 copies (c0 red, c1 green, c2 blue; each box = one placed cell, label = instance) from hierarchical instance names in the post-synthesis DEF.",note])
