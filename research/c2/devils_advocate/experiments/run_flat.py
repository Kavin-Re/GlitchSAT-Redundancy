import sys,glob,os;sys.path.insert(0,'scripts')
import glitchsat as g
for p in sorted(glob.glob('../x3/*.json')):
    d=os.path.basename(p)[:2]
    try:
        nl=g.Netlist(p,d)
        out=[]
        for k in (1,2,3):
            v,info,res=g.solve(nl,6,k,timeout_ms=120000)
            out.append((k,v[:2],len(res['faults']) if res else None))
            if res: break
        print(os.path.basename(p)[:-5],nl.stats(),out,flush=True)
    except Exception as e:
        print(os.path.basename(p),'ERR',repr(e)[:100])
