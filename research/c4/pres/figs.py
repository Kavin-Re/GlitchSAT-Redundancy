import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
INK="#1b2430"; TEAL="#1f7a6d"; AMB="#c77d0a"; RED="#b3342b"; GREY="#6b7683"; BG="#faf8f3"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":16,"axes.edgecolor":GREY,"text.color":INK,"axes.labelcolor":INK,"xtick.color":INK,"ytick.color":INK})
def base(w=9,h=4.6):
    f,a=plt.subplots(figsize=(w,h),dpi=150); f.patch.set_facecolor(BG); a.set_facecolor(BG)
    for s in ("top","right"): a.spines[s].set_visible(False)
    return f,a
# widths curve (NUMBERS M1.width)
f,a=base()
ns=list(range(1,9)); v=[0,1,1,2,2,3,3,3]
b=a.bar(ns,v,color=[GREY if x==0 else TEAL for x in v],width=0.65)
for n,x in zip(ns,v): a.text(n,x+0.08,str(x),ha="center",fontsize=22,fontweight="bold")
a.set_xticks(ns); a.set_ylim(0,3.8); a.set_yticks([0,1,2,3])
a.set_xlabel("bits of the result word the consumer reads (lowest n)"); a.set_ylabel("minimum flips")
f.tight_layout(); f.savefig("fig/width_curve.png",facecolor=BG)
# E2 variance (E2.v2.min)
f,a=base(9,4.6)
lab=["1 flip","2 flips","3 flips"]; val=[180,60,24]
a.bar(lab,val,color=[RED,AMB,TEAL],width=0.6)
for i,x in enumerate(val): a.text(i,x+4,str(x),ha="center",fontsize=26,fontweight="bold")
a.set_ylim(0,205); a.set_ylabel("synthesis settings (of 264 solved)")
f.tight_layout(); f.savefig("fig/e2.png",facecolor=BG)
# layout radius (L2 report table)
f,a=base(9,4.6)
names=["original layout","spread v8","spread v15","spread rr","spread s8"]
rad=[2.95,11.15,15.16,15.30,17.91]
cols=[RED,AMB,AMB,AMB,AMB]
y=list(range(len(names)))[::-1]
a.barh(y,rad,color=cols,height=0.6)
for yy,r,n in zip(y,rad,names):
    a.text(r+0.4,yy,f"{r} um",va="center",fontsize=16,fontweight="bold")
a.set_yticks(y); a.set_yticklabels(names); a.set_xlim(0,24)
a.set_xlabel("smallest circle that holds a sufficient set of cells (um)")
f.tight_layout(); f.savefig("fig/layout_radius.png",facecolor=BG)
