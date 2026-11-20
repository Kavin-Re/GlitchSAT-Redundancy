"""Independent gate-level simulator for Yosys JSON ($_AND_/OR/XOR/NOT/MUX/DFF_P).
Bit-parallel over all 256 sig values (python big-int lanes). No z3."""
import json, itertools, random, sys
N=256; ALL=(1<<N)-1; KEY=0xC3
def lanes(i):  # lane s has bit i of s
    return sum(1<<s for s in range(N) if (s>>i)&1)
SIGL=[lanes(i) for i in range(8)]
class Net:
    def __init__(s,path,top):
        m=json.load(open(path))['modules'][top]; s.m=m
        s.names={}
        for n,x in m['netnames'].items():
            for i,b in enumerate(x['bits']):
                if isinstance(b,int): s.names.setdefault(b,f"{n}[{i}]" if len(x['bits'])>1 else n)
        s.sigbits=m['ports']['sig']['bits']; s.out=m['ports']['boot_word']['bits']
        s.gates={}; s.dffs=[]
        for cn,c in m['cells'].items():
            t=c['type'];con=c['connections']
            if t=='$_DFF_P_': s.dffs.append((con['D'][0],con['Q'][0]))
            else: s.gates[con['Y'][0]]=(t,{p:v[0] for p,v in con.items() if p!='Y'})
        init={}
        for n,x in m['netnames'].items():
            if 'init' in x['attributes']:
                for i,b in enumerate(reversed(x['attributes']['init'])): init[x['bits'][i]]=(b=='1')
        s.init={q:(ALL if init.get(q,False) else 0) for _,q in s.dffs}
        s.sites=[q for _,q in s.dffs]+list(s.gates)   # same site set as the solver
        s.order=[]; seen=set(s.init)|set(s.sigbits)
        def vis(b):
            if not isinstance(b,int) or b in seen: return
            seen.add(b); t,p=s.gates[b]
            for v in p.values(): vis(v)
            s.order.append(b)
        for d,_ in s.dffs: vis(d)
        for b in s.out: vis(b)
        s.sidx={b:i for i,b in enumerate(s.sigbits)}
    def run(s,T,faults):
        """faults: dict cycle->set(nets) flipped that cycle (gate output or flop Q).
        Returns list per cycle of (boot_word lanes as 8 masks)."""
        st=dict(s.init); res=[]
        for t in range(T):
            f=faults.get(t,())
            v={}
            def g(b):
                if b=='0' or b=='x': return 0
                if b=='1': return ALL
                if b in v: return v[b]
                if b in s.sidx: return SIGL[s.sidx[b]]
                return v[b]
            for q in st: v[q]=st[q]^(ALL if q in f else 0)
            for b in s.order:
                ty,p=s.gates[b]
                if ty=='$_AND_': r=g(p['A'])&g(p['B'])
                elif ty=='$_OR_': r=g(p['A'])|g(p['B'])
                elif ty=='$_XOR_': r=g(p['A'])^g(p['B'])
                elif ty=='$_NOT_': r=ALL^g(p['A'])
                elif ty=='$_MUX_': S=g(p['S']); r=(g(p['B'])&S)|(g(p['A'])&(ALL^S))
                else: raise Exception(ty)
                if b in f: r^=ALL
                v[b]=r
            res.append([g(b) for b in s.out])
            st={q:g(d) for d,q in s.dffs}
        return res
def goal(res,word=0x96):
    """lanes where boot_word==word at some cycle"""
    hit=0
    for w in res:
        m=ALL
        for i,x in enumerate(w): m&=x if (word>>i)&1 else ALL^x
        hit|=m
    return hit
BAD=ALL^(1<<KEY)   # lanes with sig != KEY
def attacks(net,T,faults):
    return goal(net.run(T,faults))&BAD
def lane_list(m): return [i for i in range(N) if (m>>i)&1]
