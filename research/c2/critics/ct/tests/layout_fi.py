import re, json, itertools, sys
tt=json.load(open('tt.json'))
txt=open('layout/v_designs/out_patched/v2_net.v').read()
mods={}
for m in re.finditer(r'module (\w+)\(.*?endmodule',txt,re.S):
    mods[m.group(1)]=m.group(0)
def cells(body):
    out=[]
    for c in re.finditer(r'(sky130_fd_sc_hd__\w+|cmp8)\s+(\w+)\s*\((.*?)\);',body,re.S):
        pins=dict(re.findall(r'\.(\w+)\(([^)]*)\)',c.group(3)))
        out.append((c.group(1),c.group(2),{k:v.strip() for k,v in pins.items()}))
    return out
# alias assigns in v2
v2=mods['v2']
alias={}
a=re.search(r'assign \{ word\[7\], word\[4:0\] \} = \{ (.*?) \};',v2).group(1).split(', ')
names=['word[7]','word[4]','word[3]','word[2]','word[1]','word[0]']
for n,s in zip(names,a): alias[n]=s
alias['word[6]']=None
# note: word[6], word[5] are driven by clkinv cells
CELLS=[]  # (name, type, pins) flattened
for t,n,p in cells(v2):
    if t=='cmp8':
        for t2,n2,p2 in cells(mods['cmp8']):
            q={}
            for k,v in p2.items():
                if v=='a[0]' or re.match(r'a\[\d\]',v): q[k]=v.replace('a','sig')
                elif v=='m': q[k]=p['m']
                else: q[k]=n+'/'+v
            CELLS.append((t2.replace('sky130_fd_sc_hd__',''),n+'/'+n2,q))
    else: CELLS.append((t.replace('sky130_fd_sc_hd__',''),n,p))
def res(s):
    while s in alias and alias[s] is not None: s=alias[s]
    return s
M=(1<<256)-1; HON=[0]
sigv={}
for b in range(8):
    x=0
    for s in range(256):
        if (s>>b)&1: x|=1<<s
    sigv[f'sig[{b}]']=x
notkey=M & ~(1<<0xC3)
dffs=[c for c in CELLS if c[0].startswith('dfxtp')]
comb=[c for c in CELLS if not c[0].startswith('dfxtp')]
def outpin(c): return 'X' if 'X' in c[2] else 'Y'
# topo order
order=[];defined=set(['sig[%d]'%i for i in range(8)])|{c[2]['Q'] for c in dffs}
pend=list(comb)
while pend:
    prog=False
    for c in list(pend):
        ins=[res(v) for k,v in c[2].items() if k not in ('X','Y')]
        if all(i in defined for i in ins):
            order.append(c);defined.add(res(c[2][outpin(c)]));pend.remove(c);prog=True
    if not prog: print('cycle?',[c[1] for c in pend]);break
def evalcell(c,val):
    d=tt[c[0]] if c[0] in tt else None
    ins=tt[c[0]]['ins']
    vs=[val[res(c[2][i])] for i in ins]
    r=0
    # lane-wise via truth table minterms
    for idx,o in enumerate(d['tt']):
        if not o: continue
        m=M
        for j,v in enumerate(vs): m&= v if (idx>>j)&1 else (~v)&M
        r|=m
    return r
sites=[res(c[2][outpin(c)]) for c in comb]+[c[2]['Q'] for c in dffs]
def run(T,faults,init):
    st={c[2]['Q']:(M if (init>>i)&1 else 0) for i,c in enumerate(sorted(dffs,key=lambda c:int(re.search(r'\d+',c[2]['Q'].split('[')[1]).group())))}
    good=0
    for t in range(T):
        val=dict(sigv); val.update(st)
        for q in list(st):
            if (t,q) in faults: val[q]^=M
        for c in order:
            o=res(c[2][outpin(c)])
            v=evalcell(c,val)
            if (t,o) in faults: v^=M
            val[o]=v
        w=M
        for i in range(8):
            b=val[f'boot_word[{i}]']
            w&= b if (0x96>>i)&1 else (~b)&M
        good|=w&notkey; HON[0]|=w
        st={c[2]['Q']:val[res(c[0 if False else 2]['D'])] for c in dffs}
    return good
INIT=0xF0
if __name__=='__main__':
    T=int(sys.argv[1]);K=int(sys.argv[2])
    print('sites',len(sites),'cells',len(CELLS))
    # sanity: honest
    h=run(T,set(),INIT); print('k=0 attack lanes',bin(h).count('1'),' honest boots:', bool(run(T,set(),INIT)|0) )
    allf=[(t,s) for t in range(T) for s in sites]
    found={}
    for k in range(1,K+1):
        cnt=0;ex=[]
        for fs in itertools.combinations(allf,k):
            g=run(T,set(fs),INIT)
            if g:
                cnt+=1
                if len(ex)<6: ex.append((fs,[s for s in range(256) if (g>>s)&1][:3]))
        print('k',k,'successful sets',cnt,'of',len(list(itertools.combinations(range(len(allf)),k))) if k<2 else 'n/a'); 
        for e in ex: print('  ',e)
        if cnt: break
    print('honest C3 lane boots:', bool((HON[0]>>0xC3)&1), 'count lanes ever 0x96:', bin(HON[0]).count('1'))
