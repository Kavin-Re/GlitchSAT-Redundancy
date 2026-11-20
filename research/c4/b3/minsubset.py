"""Smallest number of gate outputs (plus flop D pins) one 'dip_subset' event must force to 0 for the goal, T=6, ONE event."""
import sys, json; sys.path.insert(0,'/tmp/work_b3')
import faultpack as fp, b3pack as bp
from z3 import PbLe, sat, is_true
for d in sys.argv[1].split(','):
  for goal in ['word','ok']:
    nl=fp.Netlist(f'/tmp/work_b3/nl/{d}.json',d.split('_')[0]); ev=bp.models(nl)['dip_subset']
    kw=dict(goal_out='boot_word',goal_value=0x96) if goal=='word' else dict(goal_out='boot_ok',goal_value=1)
    s,A,cost,inp=bp.build(nl,6,ev,**kw); s.set('timeout',60000); s.add(PbLe([(c,1) for c in cost],1))
    subs=list(bp.SUBS); res=None
    for m in range(1,len(subs)+1):
        s.push(); s.add(PbLe([(c,1) for c in subs],m)); r=s.check()
        if r==sat:
            mo=s.model(); t=[t for (t,ei),a in A.items() if is_true(mo.eval(a,model_completion=True))]
            res=(m,t,mo.eval(inp['sig'],model_completion=True).as_long()); s.pop(); break
        s.pop()
        if str(r)!='unsat': res=('unknown',); break
    print(d,goal,'min dip size (gates+flop D pins) =',res,'of',len(subs),flush=True)
