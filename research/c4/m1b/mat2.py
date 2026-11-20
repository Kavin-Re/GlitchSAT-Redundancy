import sys,json,time
eng,path,top,out,tmo=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5])
if eng=='main':
    sys.path.insert(0,'/tmp/work_m1b'); import gs_main as g
else:
    import faultbound_wt._engine as g
from multiprocessing import Pool
def cell(m):
    nl=g.Netlist(path,top); t0=time.time()   # raises on x init of a flop
    for k in range(0,4):
        v,i,r=g.solve(nl,6,k,goal_mask=m,minimize=False,timeout_ms=tmo)
        if v=='ATTACK_FOUND': return dict(mask=m,min=k,status='MEASURED')
        if v!='NO_ATTACK_UP_TO_BOUND': return dict(mask=m,min=None,status=f'UNKNOWN(k={k})')
    return dict(mask=m,min=4,status='MEASURED(>3)')
if __name__=='__main__':
    with Pool(4) as p, open(out,'w') as f:
        for r in p.imap_unordered(cell,range(1,256)):
            f.write(json.dumps(r)+'\n')
