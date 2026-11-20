#!/usr/bin/env python3
"""For a v2 netlist: min attack, and for each fault net: which compare-copy cones (m0,m1,m2) it lies in,
and how many state-flop D inputs it reaches combinationally."""
import sys, json
sys.path.insert(0,'/tmp/work_e2/scripts')
import glitchsat as G
nl=G.Netlist(sys.argv[1],'v2')
def cone(b,acc):
    if b in nl.drivers and b not in acc:
        acc.add(b)
        for f in nl.fanins(b):
            if isinstance(f,int): cone(f,acc)
    return acc
named={n:x['bits'][0] for n,x in nl.m['netnames'].items() if n in('m0','m1','m2')}
cones={n:cone(b,set()) for n,b in named.items()}
fan={}
for o in nl.drivers:
    for f in nl.fanins(o): fan.setdefault(f,[]).append(o)
def reach_d(b):
    seen={b};st=[b];ds=set(nl.dq.values());r=set()
    while st:
        x=st.pop()
        if x in ds: r.add(x)
        for y in fan.get(x,[]):
            if y not in seen: seen.add(y);st.append(y)
    return len(r)
v,info,res=G.solve(nl,6,3)
print(sys.argv[1],v,'min',len(res['faults']) if res else None,'gates',len(nl.drivers))
for t,b in (res['faults'] if res else []):
    inc=[n for n,c in cones.items() if b in c]
    print('  cycle',t,nl.names.get(b,b),nl.drivers[b][1] if b in nl.drivers else 'DFF','in_cones_of',inc,'reaches_state_D_bits',reach_d(b))
print('  attacker sig=',res['inputs'] if res else None)
# fan-out of each copy output (how many gates / D bits depend on it)
for n,b in named.items(): print('  copy',n,'fanout gates',len(fan.get(b,[])),'reaches_D',reach_d(b))
