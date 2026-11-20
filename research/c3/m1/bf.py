"""Independent brute-force simulator (no z3, no glitchsat import). Same MODELLED fault: one-cycle flip of a gate output net or flop Q net.
Enumerates ALL flip sets of size <=K over all (cycle,site) -- no cone reduction -- and ALL sig != key (bit-parallel over 256 values)."""
import json,sys,itertools,numpy as np
def load(path,top):
    m=json.load(open(path))['modules'][top]
    gates={};dffs=[]
    for cn,c in m['cells'].items():
        con=c['connections'];t=c['type']
        if t=='$_DFF_P_': dffs.append((con['D'][0],con['Q'][0]))
        else: gates[con['Y'][0]]=(t,con)
    init={}
    for n,x in m['netnames'].items():
        iv=x['attributes'].get('init')
        if iv:
            s=iv.strip()
            for i,ch in enumerate(reversed(s)): init[x['bits'][i]]=(ch=='1')
    return m,gates,dffs,init
SIG=np.arange(256,dtype=np.uint8)
def make(path,top,T,key=0xC3):
    m,gates,dffs,init=load(path,top)
    sigbits=m['ports']['sig']['bits']; wbits=m['ports']['boot_word']['bits']
    inp={b:((SIG>>i)&1).astype(bool) for i,b in enumerate(sigbits)}
    sites=[(t,b) for t in range(T) for b in list(gates)+[q for _,q in dffs]]
    good=SIG!=key
    def run(flips):
        fl=set(flips); state={q:np.full(256,init.get(q,False)) for _,q in dffs}
        seen=np.zeros(256,bool)
        for t in range(T):
            val={}
            def get(b):
                if b in('0','x','z'): return np.zeros(256,bool)
                if b=='1': return np.ones(256,bool)
                if b in val: return val[b]
                if b in inp: return inp[b]
                if b in state: v=state[b]
                else:
                    ty,con=gates[b]; g=lambda p:get(con[p][0])
                    if ty=='$_AND_': v=g('A')&g('B')
                    elif ty=='$_OR_': v=g('A')|g('B')
                    elif ty=='$_XOR_': v=g('A')^g('B')
                    elif ty=='$_NOT_': v=~g('A')
                    elif ty=='$_MUX_': v=np.where(g('S'),g('B'),g('A'))
                    else: raise Exception(ty)
                if (t,b) in fl: v=~v
                val[b]=v; return v
            word=np.zeros(256,np.uint8)
            for i,b in enumerate(wbits): word|=(get(b).astype(np.uint8)<<i)
            seen[np.unique(word[good])]=True
            state={q:get(d) for d,q in dffs}
        return seen
    return sites,run
if __name__=='__main__':
    design,T,K,out=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
    sites,run=make(f'/tmp/work_m1/spike/{design}.json',design,T)
    GOOD=0x96
    M=np.array([[ (w&m)==(GOOD&m) for w in range(256)] for m in range(256)],dtype=np.float32)
    best=np.full(256,99); wit={}
    uniq={}
    for k in range(0,K+1):
        for fs in itertools.combinations(sites,k):
            s=run(fs); key=s.tobytes()
            if key in uniq: continue
            uniq[key]=fs
            acc=(M@s.astype(np.float32))>0
            for m in np.nonzero(acc&(best>k))[0]:
                best[m]=k; wit[int(m)]=fs
        print(design,'k',k,'done; masks with min<=k:',int((best<=k).sum()),'distinct word-sets',len(uniq),flush=True)
    json.dump({'T':T,'K':K,'min':{int(m):int(best[m]) for m in range(1,256)}},open(out,'w'))
