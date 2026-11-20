import sys,glob,os;sys.path.insert(0,'../x6')
import glitch_tv as g
N=int(sys.argv[1])
for p in sys.argv[2:]:
    d=os.path.basename(p)[:2]; nl=g.Netlist(p,d); out=None
    for k in (1,2,3):
        v,info,res=g.solve(nl,N,k,timeout_ms=200000)
        if res: out=(k,len(res['faults'])); break
        if v.startswith('UNK'): out='timeout';break
    print(os.path.basename(p),'N',N,'time-varying-input min flips',out,flush=True)
