import re,sys
d=open("layout/triage/out/ct_cmp.def").read()
# li1 wires inside NETS
nets=d.split("\nNETS ")[1]
segs=[]
for m in re.finditer(r"li1 \( (\d+) (\d+) \) \( (\*|\d+) (\*|\d+) \)",nets):
    x1,y1=int(m[1]),int(m[2]); x2=x1 if m[3]=='*' else int(m[3]); y2=y1 if m[4]=='*' else int(m[4])
    segs.append((min(x1,x2)-85,min(y1,y2)-85,max(x1,x2)+85,max(y1,y2)+85))
# fillers
W={"fill_1":460,"fill_2":920,"fill_4":1840,"fill_8":3680,"decap_3":1380,"decap_4":1840}
bad=[]
for m in re.finditer(r"- (\S+) sky130_fd_sc_hd__(fill_\d|decap_\d) \+ SOURCE DIST \+ PLACED \( (\d+) (\d+) \) (\w+)",d):
    n,c,x,y,o=m[1],m[2],int(m[3]),int(m[4]),m[5]
    w=W[c]
    for ry in (y, y+2720):  # both rails (ry of origin and top)
        r=(x,ry-85,x+w,ry+85)
        if any(s[0]<r[2] and r[0]<s[2] and s[1]<r[3] and r[1]<s[3] for s in segs):
            bad.append(n); break
print(len(segs),"li1 segs; conflicting fillers:",bad)
open("bad.txt","w").write(" ".join(bad))
