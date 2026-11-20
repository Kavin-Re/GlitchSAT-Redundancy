import random, itertools, sys, json
sys.path.insert(0,'/tmp/work_ct/proj/scripts'); sys.path.insert(0,'/tmp/work_ct')
import glitchsat as G
from nb import *
def gen(seed):
    r=random.Random(seed); b=base()
    nf=r.randint(1,3); qs=[b.dffq() for _ in range(nf)]
    pool=[b.sig[0],b.sig[1]]+qs; gates=[]
    for _ in range(r.randint(3,7)):
        t=r.choice(['AND','OR','XOR','NOT','MUX'])
        pick=lambda: r.choice(pool)
        if t=='NOT': y=b.gate('NOT',A=pick())
        elif t=='MUX': y=b.gate('MUX',A=pick(),B=pick(),S=pick())
        else: y=b.gate(t,A=pick(),B=pick())
        pool.append(y); gates.append(y)
    for q in qs: b.dffat(q,r.choice(pool[2:]),r.randint(0,1))
    outs=[r.choice(pool[2:]) for _ in range(2)]
    b.out('boot_word',outs); return b
def brute(b,T,K,goal):
    cells=b.cells; qs=[c['connections']['Q'][0] for c in cells.values() if c['type']=='$_DFF_P_']
    gs=[(c['connections']['Y'][0],c) for c in cells.values() if c['type']!='$_DFF_P_']
    sites=qs+[y for y,_ in gs]; ow=b.ports['boot_word']['bits']
    def sim(fs,s0,s1):
        st={q:bool(b.init.get(q,0)) for q in qs}
        for t in range(T):
            v={b.sig[0]:bool(s0),b.sig[1]:bool(s1)}; v.update(st)
            for q in qs:
                if (t,q) in fs: v[q]=not v[q]
            for y,c in gs:  # creation order is topological
                con=c['connections']; ty=c['type'][2:-1]; g=lambda p:v[con[p][0]]
                x={'AND':lambda:g('A')&g('B'),'OR':lambda:g('A')|g('B'),'XOR':lambda:g('A')^g('B'),'NOT':lambda:not g('A'),'MUX':lambda:g('B') if g('S') else g('A')}[ty]()
                if (t,y) in fs: x=not x
                v[y]=x
            if all(v[ow[i]]==bool((goal>>i)&1) for i in range(2)): return True
            st={c['connections']['Q'][0]:v[c['connections']['D'][0]] for c in cells.values() if c['type']=='$_DFF_P_'}
        return False
    allf=[(t,s) for t in range(T) for s in sites]
    for k in range(K+1):
        for fs in itertools.combinations(allf,k):
            fs=set(fs)
            if any(sim(fs,s0,s1) for s0 in (0,1) for s1 in (0,1)): return k
    return None
bad=0
for seed in range(60):
    b=gen(seed); b.save(f'/tmp/work_ct/f.json'); T=4
    # b.init: Netlist reads attributes from netnames; nb saved them
    mk={}
    for red in ('none','coi','full'):
        nl=G.Netlist('/tmp/work_ct/f.json','t'); mn=None
        for k in range(0,3):
            v,_,res=G.solve(nl,T,k,goal_out='boot_word',goal_value=3,reduce=red)
            if v=='ATTACK_FOUND': mn=len(res['faults']); break
        mk[red]=mn
    bf=brute(b,T,2,3)
    if len(set(mk.values()))>1 or mk['none']!=bf:
        bad+=1; print('DISAGREE seed',seed,mk,'brute',bf)
print('done, disagreements',bad)
