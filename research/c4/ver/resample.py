import sys,csv,random,json,time
sys.path.insert(0,'/tmp/work_ver'); sys.path.insert(0,'research/c4/pre')
from multiprocessing import Pool
import gs_mask as G
from predictor import predict
rows=list(csv.DictReader(open('research/c4/test/cells_all.csv')))
rnd=random.Random(20261119)
def pick(f,n):
    c=[r for r in rows if f(r)]; rnd.shuffle(c); return c[:n]
S=[]
S+=pick(lambda r:r['group']=='E2' and r['solver_min']=='3',20)
S+=pick(lambda r:r['group']=='E2' and r['solver_min']=='2',12)
S+=pick(lambda r:r['group']=='E2' and r['solver_min']=='1',6)
S+=pick(lambda r:r['group']=='M1_V2_apt033' and r['solver_min']=='2',8)
S+=pick(lambda r:r['group']=='M1_V2_apt033' and r['solver_min']=='1',4)
S+=pick(lambda r:r['group']=='M1_V1_apt033' and r['solver_min']=='1',3)
S+=pick(lambda r:r['group'].startswith('M1') and r['solver_min']=='0',3)
S+=pick(lambda r:r['group']=='R20' and r['cell'] in('sbox_unprot_T4','crc_plain_T4','keymem_T8','uart_T6'),4)
def job(r):
    path=r['netlist']; top=r['top']; T=int(r['T']); mask=int(r['mask'],16)
    kw=dict(goal_out=r['goal_out'],mask=mask,T=T)
    if r['group']=='R20':
        import re
        # R20 params from run_test.py table
        P={'sbox_unprot_T4':(0x7c,1),'crc_plain_T4':(1,0xA5),'keymem_T8':(1,0),'uart_T6':(7,0)}
        acc,key=P[r['cell']]; kw.update(accept=acc,key=key)
    else: acc,key=0x96,0xC3
    t=time.time(); p=predict(path,top,**kw); pt=time.time()-t
    nl=G.Netlist(path,top)
    t=time.time()
    gk=dict(goal_out=r['goal_out'],goal_value=acc,key=key,goal_mask=mask)
    res=None
    for k in (3,):
        v,info,atk=G.solve(nl,T,k,timeout_ms=300000,**gk)
        if v=='ATTACK_FOUND': res=len(atk['faults'])
        elif v=='NO_ATTACK_UP_TO_BOUND': res='>3'
        else: res='unk'
    st=time.time()-t
    if res==1 or res is None: pass
    return dict(cell=r['cell'],group=r['group'],csv_solver=r['solver_min'],my_solver=res,csv_pred=r['pred'],my_pred=p['pred'],my_lb=p['lb'],my_est=p['est'],flag=p['flag'],pred_s=round(pt,2),solve_s=round(st,2))
if __name__=='__main__':
    print(len(S),flush=True)
    with Pool(4) as pl: out=pl.map(job,S,chunksize=1)
    w=csv.DictWriter(open('resample.csv','w',newline=''),fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    bad=[o for o in out if str(o['my_solver'])!=o['csv_solver'] or str(o['my_pred'])!=o['csv_pred']]
    print('n',len(out),'mismatch',len(bad));[print(b) for b in bad]
