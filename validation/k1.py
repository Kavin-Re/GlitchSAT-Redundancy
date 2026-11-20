import sys,time; from netsim import *
path,top,T=sys.argv[1],sys.argv[2],int(sys.argv[3])
n=Net(path,top)
print(f"{top}: {len(n.sites)} sites ({len(n.dffs)} flops, {len(n.gates)} gates), T={T}")
base=attacks(n,T,{}); honest=goal(n.run(T,{}))>>KEY&1
print("k=0: attacking sigs:",len(lane_list(base)),"honest KEY boots:",honest)
succ=[]
for t in range(T):
  for b in n.sites:
    a=attacks(n,T,{t:{b}})
    if a: succ.append((t,n.names.get(b,b),len(lane_list(a)),lane_list(a)[:4]))
print("k=1 successful (cycle,site,#sig values,examples):",len(succ),"of",T*len(n.sites),"(site,cycle) pairs; all 255 non-key sigs covered exhaustively")
for s in succ: print("  ",s)
