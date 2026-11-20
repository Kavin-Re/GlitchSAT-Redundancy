import sys,json,time,glob,os
eng=sys.argv[1]
if eng=='main':
    sys.path.insert(0,'/tmp/work_m1b'); import gs_main as g
else:
    import faultbound_wt._engine as g
rows=[]
for d in ['v0','v1','v2']:
  for n in ['spike','apt033_plain','apt033_opt','conda038_plain','conda038_opt']:
    p=f'b2nl/{d}_{n}.json'
    nl=g.Netlist(p,d)
    for goal,gv in (('boot_word',0x96),('boot_ok',1)):
        res=None
        for k in range(0,4):
            v,i,r=g.solve(nl,6,k,goal_out=goal,goal_value=gv,minimize=False,timeout_ms=120000)
            if v=='ATTACK_FOUND': res=k;break
            if v!='NO_ATTACK_UP_TO_BOUND': res='UNKNOWN';break
        if res is None: res='>3'
        rows.append(dict(design=d,netlist=n,goal=goal,min=res)); print(rows[-1],flush=True)
json.dump(rows,open(f'out/b2_{eng}.json','w'))
