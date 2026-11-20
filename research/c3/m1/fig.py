import json,sys;sys.path.insert(0,'/tmp/work_m1')
from pred import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
A=json.load(open('all.json'))
ok=lambda m:not any((s&m)==(0x96&m) for s in (0xF0,0xCC))
series=[('v1_spike','V1 (spike)','#888888','s'),('v2_spike','V2 (spike)','#1f77b4','o'),('v2_apt033','V2 (apt-0.33 re-synth)','#2ca02c','^'),('v2m_apt033','V2m per-bit vote','#d62728','D'),('v2s_apt033','V2s one shared vote','#9467bd','x')]
fig,ax=plt.subplots(1,2,figsize=(11,4.2))
for n,l,c,mk in series:
    xs=range(1,9);avg=[];lo=[];hi=[]
    for p in xs:
        v=[A[n][str(m)] for m in range(1,256) if pop(m)==p and ok(m) and A[n].get(str(m)) is not None]
        avg.append(sum(v)/len(v) if v else None);lo.append(min(v) if v else None);hi.append(max(v) if v else None)
    px=[x+ (series.index((n,l,c,mk))-2)*0.07 for x in xs]
    ax[0].plot(px,avg,marker=mk,color=c,label=l)
    ax[1].plot(px,hi,marker=mk,color=c,label=l)
ax[0].set_title('mean min-flips over consumer masks of that width');ax[1].set_title('best-protected mask of that width (max over masks)')
for a in ax: a.set_xlabel('bits of the result word the consumer checks (popcount)');a.set_ylabel('min flips (T=6, k<=3)');a.set_ylim(0.5,3.5);a.grid(alpha=.3)
ax[0].legend(fontsize=8)
fig.suptitle('M1: flips needed vs what the consumer checks (MEASURED, modelled bit flips, toy designs; non-colliding masks)',fontsize=9)
fig.tight_layout();fig.savefig('/home/user/project/research/c3/m1/m1_flips_vs_mask.png',dpi=130)
