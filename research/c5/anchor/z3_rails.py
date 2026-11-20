"""z3 side of the rail anchor: b3pack.min_cost on (netlist, model, goal) at T, cap. prints JSON lines."""
import sys, os, json
sys.path.insert(0, os.environ.get('B3DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'c4', 'b3'))   # unchanged B3 engine (run_all.sh sets B3DIR)
import faultpack as fp, b3pack as bp
T=int(sys.argv[1]); cap=int(sys.argv[2])
for d in sys.argv[3].split(','):
    top=d.split('_')[0]; nl=fp.Netlist(d+'.json',top); M=bp.models(nl)
    for m in sys.argv[4].split(','):
        for g in ('word','ok'):
            kw=dict(goal_out='boot_word',goal_value=0x96) if g=='word' else dict(goal_out='boot_ok',goal_value=1)
            r=bp.min_cost(nl,T,M[m],cap,120000,**kw)
            print(json.dumps(dict(netlist=d,model=m,goal=g,T=T,cap=cap,z3_min=bp.fmt(r),events=r.get('events'),n_events=r.get('n_events'))),flush=True)
