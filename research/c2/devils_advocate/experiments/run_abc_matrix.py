import sys,glob,os;sys.path.insert(0,'scripts')
import glitchsat as g
rows=[]
for p in sorted(glob.glob('../x4/*.json')):
    b=os.path.basename(p)[:-5]; d=b[:2]
    try:
        nl=g.Netlist(p,d); out=None
        for k in (1,2,3):
            v,info,res=g.solve(nl,6,k,timeout_ms=120000)
            if res: out=len(res['faults']); break
        print(b,nl.stats()['gates'],'min_flips=',out if out else '>3',flush=True)
    except Exception as e: print(b,'ERR',repr(e)[:80],flush=True)
