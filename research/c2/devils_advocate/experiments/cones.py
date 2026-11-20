import sys,json;sys.path.insert(0,'scripts')
import glitchsat as g
def cone(nl,b,acc=None):
    acc=set() if acc is None else acc
    if b in nl.drivers and b not in acc:
        acc.add(b)
        for f in nl.fanins(b):
            if isinstance(f,int): cone(nl,f,acc)
    return acc
def run(p,d):
    nl=g.Netlist(p,d)
    byname={v:k for k,v in nl.names.items()}
    if d=='v1':
        ok=byname['ok']; _,t,con=nl.drivers[ok]
        ins=[v[0] for pn,v in con.items() if pn!='Y']
        cs=[cone(nl,i) for i in ins]
        print('  ok inputs cones sizes',[len(c) for c in cs],'shared gates',len(cs[0]&cs[1]),'type',t)
    if d=='v2':
        # next-state D of st flops -> cone; find per-st-bit D cone; compare m copies by looking at gates that depend only on sig
        dcs=[cone(nl,dd) for _,dd,q in nl.dffs]
        sig=[b for b in nl.ports['sig']['bits']] if isinstance(nl.ports['sig'],dict) else None
        # gates whose cone has no flop Q leaf: pure functions of sig = compare logic
        pure=[]
        for b in nl.drivers:
            c=cone(nl,b)|{b}
            leaves=set()
            for x in c:
                for f in nl.fanins(x):
                    if f in nl.dq: leaves.add(f)
            if not leaves: pure.append(b)
        print('  pure-sig gates',len(pure))
for lab,pat in (('0.33 plain','../x1/%s_plain.json'),('0.38 plain','../x2/%s_plain_038.json'),('0.33 opt','../x1/%s_opt.json'),('0.38 opt','../x2/%s_opt_038.json')):
    for d in('v1','v2'):
        print(lab,d); run(pat%d,d)
