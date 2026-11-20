import sys,json,time;sys.path.insert(0,'/tmp/work_m1')
import gs_mask as g
from multiprocessing import Pool
def cell(a):
    path,top,T,mask,tmo=a
    nl=g.Netlist(path,top); t0=time.time()
    for k in range(0,4):
        v,i,r=g.solve(nl,T,k,goal_mask=mask,minimize=False,timeout_ms=tmo)
        if v=='ATTACK_FOUND': return dict(netlist=path,top=top,T=T,mask=mask,min=k,status='MEASURED',s=round(time.time()-t0,1))
        if v!='NO_ATTACK_UP_TO_BOUND': return dict(netlist=path,top=top,T=T,mask=mask,min=None,status=f'UNKNOWN(timeout at k={k})',s=round(time.time()-t0,1))
    return dict(netlist=path,top=top,T=T,mask=mask,min=4,status='MEASURED(>3)',s=round(time.time()-t0,1))
if __name__=='__main__':
    path,top,T,out=sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4]
    tmo=int(sys.argv[5]) if len(sys.argv)>5 else 120000
    args=[(path,top,T,m,tmo) for m in range(1,256)]
    with Pool(4) as p, open(out,'w') as f:
        for r in p.imap_unordered(cell,args):
            f.write(json.dumps(r)+'\n'); f.flush()
