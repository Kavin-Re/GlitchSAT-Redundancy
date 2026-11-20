import json,sys,os; from netsim import *
HERE=os.path.dirname(os.path.abspath(__file__))
W=os.path.join(HERE,'..','reference','spike_netlists')+os.sep   # spike netlists v0/v1/v2.json
R=os.path.join(HERE,'data')+os.sep                           # spike SAT witnesses spike_<v>_results.json
ok=bad=0
for v in ('v0','v1','v2'):
    n=Net(W+v+'.json',v); inv={nm:b for b,nm in n.names.items()}
    for (vv,T,k,r,dt,res) in json.load(open(R+f'spike_{v}_results.json')):
        if r!='sat': continue
        sig,fl=res; f={}
        for t,nm in fl: f.setdefault(t,set()).add(inv[nm])
        a=attacks(n,T,f); good=bool(a>>sig&1)
        ok+=good; bad+=not good
        print(v,'T',T,'k<=',k,'sig',sig,'faults',fl,'-> replay',"CONFIRMED" if good else "NOT CONFIRMED")
print("confirmed",ok,"not",bad)
