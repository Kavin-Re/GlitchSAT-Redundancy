import sys,json,time
sys.path.insert(0,'/home/user/project/research/c2/e1_timevarying')
import glitchsat_tv as g
rows=[]
names={'V0':'v0','V1':'v1','V2':'v2'}
for d,top in names.items():
    nl=g.Netlist(f'/home/user/project/reference/spike_netlists/{top}.json',top)
    for T in (4,6,8):
        for mode in ('const','free_never','free_hit'):
            mn=None
            for k in range(4):
                t0=time.time()
                v,info,res=g.solve(nl,T,k,timeout_ms=600000,inmode=mode)
                dt=time.time()-t0
                row=dict(design=d,T=T,k=k,mode=mode,verdict=v,runtime_s=round(dt,2))
                if res:
                    row['min_faults']=len(res['faults'])
                    row['faults']=[(t,nl.names.get(b,str(b))) for t,b in res['faults']]
                    row['inputs']=res['inputs'] if isinstance(res['inputs'],dict) else [hex(x['sig']) for x in res['inputs']]
                    if isinstance(row['inputs'],dict): row['inputs']={p:hex(x) for p,x in row['inputs'].items()}
                rows.append(row); print(json.dumps(row),flush=True)
                if res: break
json.dump(rows,open('matrix_bmc_z3.json','w'),indent=1)
