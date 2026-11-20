import itertools,sys,os; from netsim import *
S=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','reference','spike_netlists','v2.json')
n=Net(S,'v2'); T=6; c=0; succ=[]
for tr in itertools.combinations(n.sites,3):
    c+=1
    a=attacks(n,T,{1:set(tr)})
    if a: succ.append(tr)
print(f"v2 T=6 k=3 all triples all at cycle 1 (EXHAUSTIVE for that slice): {c} sets, successful={len(succ)}")
for tr in succ[:3]: print([n.names.get(b,b) for b in tr])
