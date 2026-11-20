import sys,glob,os,collections;sys.path.insert(0,'scripts')
import glitchsat as g
from z3 import PbLe, sat, unsat, is_true, Solver, Not, Bool
def fanout(nl):
    fo=collections.Counter()
    for b,(cn,t,con) in nl.drivers.items():
        for p,v in con.items():
            if p!='Y' and isinstance(v[0],int): fo[v[0]]+=1
    for _,d,q in nl.dffs: fo[d]+=1
    # output-port bits count as a fanout too
    for pn,pv in nl.ports.items():
        if pv['direction']=='output':
            for b in pv['bits']:
                if isinstance(b,int): fo[b]+=1
    return fo
def minimize(nl,N,mode,cap=8):
    fo=fanout(nl)
    s,F,inputs,info=g.build(nl,N)
    items=[(key,f) for key,f in F.items()]
    if mode=='private_only':   # forbid flipping any net with fanout>=2
        for (t,b),f in items:
            if fo[b]>=2: s.add(Not(f))
        w=lambda b:1
    elif mode=='fanout_weighted':   # a stem flip costs its fanout (= flipping each branch separately)
        w=lambda b:max(1,fo[b])
    else: w=lambda b:1
    for bound in range(1,cap+1):
        s.push(); s.add(PbLe([(f,w(key[1])) for key,f in items],bound))
        r=s.check()
        if r==sat:
            m=s.model(); fl=[key for key,f in items if is_true(m.eval(f,model_completion=True))]
            s.pop(); return bound,[(t,nl.names.get(b,b),fo[b]) for t,b in fl]
        s.pop()
    return None,None
if __name__=='__main__':
    files=sys.argv[1:]
    for p in files:
        d=os.path.basename(p)[:2]; nl=g.Netlist(p,d)
        res=[]
        for mode in ('plain','fanout_weighted','private_only'):
            b,fl=minimize(nl,6,mode)
            res.append((mode,b))
        print(os.path.basename(p),nl.stats()['gates'],res,flush=True)
