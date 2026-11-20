import sys;sys.path.insert(0,'/tmp/work_m1')
import gs_mask as g
for f,t,m,k in [('spike/v2.json','v2',0xFF,3),('v2m.json','v2m',0xFF,2),('v2s.json','v2s',0xFF,1),('spike/v2.json','v2',0x49,1),('spike/v2.json','v2',0x08,1)]:
    nl=g.Netlist(f,t); v,i,r=g.solve(nl,6,k,goal_mask=m)
    print(f,hex(m),v,[(c,nl.names.get(b,b)) for c,b in r['faults']] if r else None)
