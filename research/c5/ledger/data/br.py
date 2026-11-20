import sys, json, time
sys.path.insert(0,'/tmp/work_ledger/br'); import faultpack as fp
T='/tmp/work_ledger/tree'
name,path,top,model=sys.argv[1:5]
nl=fp.Netlist(path,top); t0=time.time()
r=fp.min_cost(nl,6,fp.MODELS[model],3,100000)
print(json.dumps(dict(cell=name,model=model,min=fp.fmt(r),status=r['status'],secs=round(time.time()-t0,1))),flush=True)
