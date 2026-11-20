import sys,json;sys.path.insert(0,'/tmp/work_m1')
import gs_mask as g
nl=g.Netlist('/tmp/work_m1/spike/v2.json','v2')
bf=json.load(open('bf_v2_T4_k2.json'))['min']
bad=[];n=0;res={}
for m in range(1,256):
    mn=99
    for k in range(3):
        v,_,_=g.solve(nl,4,k,goal_mask=m,minimize=False)
        if v=='ATTACK_FOUND': mn=k;break
    res[m]=mn
    if mn!=bf[str(m)]: bad.append((m,mn,bf[str(m)]))
print('masks compared',255,'disagreements',bad)
json.dump(res,open('val_solver_T4.json','w'))
