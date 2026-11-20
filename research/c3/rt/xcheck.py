import sys, json, random, itertools, os
sys.path.insert(0,'/tmp/work_rt/scripts'); sys.path.insert(0,'/tmp/work_rt/product/src')
import glitchsat as G
from faultbound_wt import _engine as P

def gen(rng):
    wi = rng.choice([1,2,3]); wo = rng.choice([1,2,3])
    nin=wi; nff=rng.choice([0,1,2,3]); ngate=rng.randint(2,9)
    nid=[2]
    def new():
        nid[0]+=1; return nid[0]-1
    inb=[new() for _ in range(wi)]; clk=new()
    qs=[new() for _ in range(nff)]
    avail=list(inb)+list(qs)+['0','1']
    cells={}; gouts=[]
    for g in range(ngate):
        ty=rng.choice(['$_AND_','$_OR_','$_XOR_','$_NOT_','$_MUX_'])
        o=new()
        pick=lambda: rng.choice(avail+gouts[-3:])
        if ty=='$_NOT_': con={'A':[pick()],'Y':[o]}
        elif ty=='$_MUX_': con={'A':[pick()],'B':[pick()],'S':[pick()],'Y':[o]}
        else: con={'A':[pick()],'B':[pick()],'Y':[o]}
        cells[f'g{g}']=dict(type=ty,connections=con); gouts.append(o)
    pool=avail+gouts
    for i,q in enumerate(qs):
        cells[f'ff{i}']=dict(type='$_DFF_P_',connections={'C':[clk],'D':[rng.choice(pool)],'Q':[q]})
    outb=[rng.choice(gouts+qs+ (inb if rng.random()<.2 else [])+(['0','1'] if rng.random()<.1 else [])) for _ in range(wo)]
    names={}
    for i,q in enumerate(qs):
        a={}
        if rng.random()<.5: a['init']=format(rng.randint(0,1),'01b')
        names[f'q{i}']=dict(bits=[q],attributes=a)
    ports={'clk':dict(direction='input',bits=[clk]),'sig':dict(direction='input',bits=inb),'boot_word':dict(direction='output',bits=outb)}
    key=rng.randrange(1<<wi); gv=rng.randrange(1<<wo)
    return dict(modules={'t':dict(ports=ports,cells=cells,netnames=names)}),key,gv,wi,wo

def sim(doc,N,key,gv,wi,faults,sigv):
    m=doc['modules']['t']; cells=m['cells']
    drv={}; ffs=[]
    for c in cells.values():
        if c['type']=='$_DFF_P_': ffs.append((c['connections']['D'][0],c['connections']['Q'][0]))
        else: drv[c['connections']['Y'][0]]=c
    init={}
    for n in m['netnames'].values():
        iv=n['attributes'].get('init')
        if iv: init[n['bits'][0]]=(iv[-1]=='1')
    st={q:init.get(q,False) for _,q in ffs}
    inb=m['ports']['sig']['bits']; outb=m['ports']['boot_word']['bits']
    fs=set(faults)
    for t in range(N):
        val={}
        def get(b):
            if b=='0' or b=='1': return b=='1'
            if b in val: return val[b]
            if b in inb: return bool((sigv>>inb.index(b))&1)
            if b in st: v=st[b]
            else:
                c=drv[b]; con=c['connections']; g=lambda p:get(con[p][0]); ty=c['type']
                v={'$_AND_':lambda:g('A') and g('B'),'$_OR_':lambda:g('A') or g('B'),'$_XOR_':lambda:g('A')!=g('B'),
                   '$_NOT_':lambda:not g('A'),'$_MUX_':lambda:g('B') if g('S') else g('A')}[ty]()
            if (t,b) in fs: v=not v
            val[b]=v; return v
        nxt={q:get(d) for d,q in ffs}
        w=sum(int(get(b))<<i for i,b in enumerate(outb))
        if w==gv: return True
        st=nxt
    return False

def brute(doc,N,k,key,gv,wi):
    m=doc['modules']['t']
    sites=[c['connections']['Y'][0] for c in m['cells'].values() if c['type']!='$_DFF_P_']+[c['connections']['Q'][0] for c in m['cells'].values() if c['type']=='$_DFF_P_']
    allf=[(t,b) for t in range(N) for b in sites]
    best=None
    for r in range(k+1):
        for fl in itertools.combinations(allf,r):
            for s in range(1<<wi):
                if s==key: continue
                if sim(doc,N,key,gv,wi,fl,s):
                    return r, fl, s
    return None

def solver_verdict(mod,nl,N,k,key,gv,**kw):
    v,info,res=mod.solve(nl,N,k,key=key,goal_value=gv,**kw)
    return v,(len(res['faults']) if res else None)

if __name__=='__main__':
    seed=int(sys.argv[1]); cnt=int(sys.argv[2]); rng=random.Random(seed)
    bad=0; stats=dict(att=0,none=0)
    for i in range(cnt):
        doc,key,gv,wi,wo=gen(rng); N=rng.choice([1,2,3,4]); k=rng.choice([0,1,2])
        p=f'/tmp/work_rt/rt/n{seed}_{i}.json'; json.dump(doc,open(p,'w'))
        b=brute(doc,N,k,key,gv,wi)
        exp=('ATTACK_FOUND',b[0]) if b else ('NO_ATTACK_UP_TO_BOUND',None)
        stats['att' if b else 'none']+=1
        try:
            nl=G.Netlist(p,'t'); nl2=P.Netlist(p,'t')
        except Exception as e:
            print('LOADFAIL',i,repr(e)); bad+=1; continue
        for name,mod,n_ in (('glitchsat',G,nl),('product',P,nl2)):
            for red in ('none','coi','full'):
                try: got=solver_verdict(mod,n_,N,k,key,gv,reduce=red)
                except Exception as e: got=('EXC',repr(e)[:80])
                if got!=exp:
                    bad+=1; print('DISAGREE',i,name,red,'N',N,'k',k,'exp',exp,'got',got,p)
    print('done',cnt,'netlists; disagreements',bad,stats)
