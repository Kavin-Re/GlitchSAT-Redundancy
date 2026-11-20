import sys,glob,os;sys.path.insert(0,'scripts');sys.path.insert(0,'../x5')
import glitchsat as g, weighted as w, collections
tab=collections.defaultdict(collections.Counter)
for p in sorted(glob.glob('../x4/*.json')):
    b=os.path.basename(p)[:-5]; d=b[:2]; nl=g.Netlist(p,d)
    u,_=w.minimize(nl,6,'plain'); f,_=w.minimize(nl,6,'fanout_weighted')
    tab[d][(u,f)]+=1
    print(b,'unit',u,'fanout-weighted',f,flush=True)
print(dict(tab))
