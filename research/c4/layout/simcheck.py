import json,sys
def load(p,top):
    m=json.load(open(p))['modules'][top]; return m
def sim(m,sig,N=5):
    cells=m['cells']; ports=m['ports']
    val={}
    init={}
    for n,x in m['netnames'].items():
        iv=x['attributes'].get('init')
        if iv:
            for i,b in enumerate(reversed(iv)): init[x['bits'][i]]=b=='1'
    ffs=[c for c in cells.values() if c['type']=='$_DFF_P_']
    st={c['connections']['Q'][0]:init.get(c['connections']['Q'][0],False) for c in ffs}
    gates={c['connections']['Y'][0]:c for c in cells.values() if c['type']!='$_DFF_P_'}
    sb=ports['sig']['bits']; outs=[]
    for t in range(N):
        v=dict(st)
        for i,b in enumerate(sb): v[b]=bool(sig>>i&1)
        def g(b):
            if b=='0' or b=='x': return False
            if b=='1': return True
            if b in v: return v[b]
            c=gates[b]; con=c['connections']; ty=c['type']
            a=lambda p:g(con[p][0])
            r={'$_AND_':lambda:a('A') and a('B'),'$_OR_':lambda:a('A') or a('B'),'$_NOT_':lambda:not a('A'),'$_XOR_':lambda:a('A')!=a('B'),'$_MUX_':lambda:a('B') if a('S') else a('A')}[ty]()
            v[b]=r; return r
        bw=sum(g(b)<<i for i,b in enumerate(ports['boot_word']['bits'])); ok=g(ports['boot_ok']['bits'][0])
        outs.append((bw,ok))
        st={c['connections']['Q'][0]:g(c['connections']['D'][0]) for c in ffs}
    return outs
if __name__=='__main__':
    for d in ('v1','v2'):
        a=load(f'nl/{d}.json',d); b=load(f'nl/{d}_layout.json',d)
        bad=[s for s in range(256) if sim(a,s)!=sim(b,s)]
        print(d,'sig values with different 5-cycle (boot_word,boot_ok) trace spike vs layout:',len(bad),'of 256', sim(b,0xC3),sim(b,0x00))
