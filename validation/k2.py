import sys,itertools,random,time; from netsim import *
path,top,T,k=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]); cap=int(sys.argv[5]) if len(sys.argv)>5 else 0
n=Net(path,top); pairs=[(t,b) for t in range(T) for b in n.sites]
tot=0;succ=[];t0=time.time()
if cap==0: it=itertools.combinations(pairs,k)
else:
    random.seed(1); it=(tuple(random.sample(pairs,k)) for _ in range(cap))
for c in it:
    f={}
    for t,b in c: f.setdefault(t,set()).add(b)
    tot+=1
    a=attacks(n,T,f)
    if a: succ.append((c,len(lane_list(a))))
print(f"{top} T={T} k={k} {'EXHAUSTIVE' if cap==0 else 'RANDOM SAMPLE'}: {tot} fault sets x 255 sigs; successful sets={len(succ)}; {time.time()-t0:.0f}s")
for c,nl in succ[:5]: print("  ",[(t,n.names.get(b,b)) for t,b in c],"sigs:",nl)
