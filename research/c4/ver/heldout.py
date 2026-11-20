import sys,csv,random,json,time,glob
sys.path.insert(0,'/tmp/work_ver'); sys.path.insert(0,'/home/user/project/research/c4/pre')
from multiprocessing import Pool
import gs_mask as G
from predictor import predict
man=json.load(open('manifest.json'))
for p in sorted(glob.glob('gen/V456_*.json')):
    d=p.split('V456_')[1].split('_')[0]; man.append(dict(fam='V456',seed=0,flow=p.rsplit('_',1)[1][:-5],top=d,json=p,W=8,OW=8,key=0xC3,acc=0x96))
rnd=random.Random(777); cells=[]
for m in man:
    cells.append((m,(1<<m['OW'])-1))
    nm=3 if m['fam']=='V456' else 1
    for _ in range(nm):
        mk=rnd.randrange(1,1<<m['OW'])
        if mk!=(1<<m['OW'])-1 and OW_ok(mk) if False else mk!=(1<<m['OW'])-1: cells.append((m,mk))
def job(a):
    m,mask=a
    kw=dict(goal_out='boot_word',mask=mask,accept=m['acc'],key=m['key'],T=6)
    row=dict(fam=m['fam'],seed=m['seed'],flow=m['flow'],json=m['json'],top=m['top'],mask=hex(mask))
    try:
        t=time.time(); p=predict(m['json'],m['top'],**kw); row.update(lb=p['lb'],est=p['est'],pred=p['pred'],flag=p['flag'],pred_s=round(time.time()-t,2),perr='')
    except Exception as e: row.update(perr=repr(e)[:150])
    try:
        nl=G.Netlist(m['json'],m['top']); t=time.time()
        v,info,atk=G.solve(nl,6,3,timeout_ms=150000,goal_out='boot_word',goal_value=m['acc'],key=m['key'],goal_mask=mask)
        row['solver']={'ATTACK_FOUND':len(atk['faults']) if atk else None,'NO_ATTACK_UP_TO_BOUND':'>3'}.get(v,'unk'); row['solve_s']=round(time.time()-t,2)
        if v=='ATTACK_FOUND': row['witness']=json.dumps(atk['faults'])
    except Exception as e: row['serr']=repr(e)[:150]
    return row
if __name__=='__main__':
    print(len(cells),flush=True)
    with Pool(3) as pl: out=pl.map(job,cells,chunksize=1)
    keys=sorted({k for o in out for k in o},key=lambda k:k)
    w=csv.DictWriter(open('heldout.csv','w',newline=''),fieldnames=keys);w.writeheader();w.writerows(out)
    print('done')
