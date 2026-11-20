# emit magic tcl labelling one met5 PDN stripe each for VGND/VPWR (from DEF SPECIALNETS)
import re,sys
d=open(sys.argv[1]).read(); s=d[d.find('SPECIALNETS'):]
for net,blk in [(m.group(1),m.group(0)) for m in re.finditer(r"- (VGND|VPWR) .*?(?=\n    - V|END SPECIALNETS)",s,re.S)]:
    m=re.search(r'met5 1600 \+ SHAPE STRIPE \( (\d+) (\d+) \) \( (\d+) (\d+) \)',blk)
    if m is None:
        continue  # no met5 stripe for this net (design too small for the PDN pitch to place one)
    x1,y1,x2,y2=[int(v)/1000 for v in m.groups()]
    cx=(x1+x2)/2; cy=(y1+y2)/2
    print(f"box {cx-0.3:.3f}um {cy-0.3:.3f}um {cx+0.3:.3f}um {cy+0.3:.3f}um\nlabel {net} FreeSans 0.25u 0 0 0 c metal5\nport make")
