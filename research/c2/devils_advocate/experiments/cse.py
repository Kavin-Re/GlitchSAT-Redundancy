import sys,json;sys.path.insert(0,'scripts')
import glitchsat as g
def cse(path,top):
    nl=g.Netlist(path,top)
    memo={}
    canon={}
    def c(b):
        if not isinstance(b,int): return ('const',b)
        if b in memo: return memo[b]
        if b in nl.drivers:
            _,t,con=nl.drivers[b]
            ins=[c(v[0]) for p,v in con.items() if p!='Y']
            if t in('$_AND_','$_OR_','$_XOR_'): ins=sorted(ins,key=repr)
            r=(t,tuple(ins))
        else: r=('leaf',b)   # input or flop Q
        memo[b]=r;return r
    sig=[c(b) for b in nl.drivers]
    return len(sig),len(set(sig))
for tag in ('x1/%s_%s','x2/%s_%s_038'):
    for d in('v0','v1','v2'):
        for fl in('plain','opt'):
            p='../'+(tag%(d,fl)) +'.json'
            print(tag[:2],d,fl,cse(p,d), g.Netlist(p,d).stats())
