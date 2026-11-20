import sys,json,time;sys.path.insert(0,'scripts')
import glitchsat as g
for d in ('v1','v2'):
  for fl in ('plain','opt'):
    for k in (1,2):
      nl=g.Netlist(f'../x1/{d}_{fl}.json',d)
      t=time.time()
      r=g.solve(nl,6,k,timeout_ms=100000)
      print(d,fl,k,{x:r[x] for x in r if x in('verdict','min_faults','faults')} if isinstance(r,dict) else r, round(time.time()-t,1),flush=True)
