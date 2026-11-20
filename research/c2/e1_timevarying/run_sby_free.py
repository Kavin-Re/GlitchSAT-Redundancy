#!/usr/bin/env python3
"""Run sby on the spike netlists with CONST or FREE per-cycle sig. Usage: run_sby_free.py WORKDIR
needs formal env on PATH."""
import subprocess, sys, time, json, os, re
W=sys.argv[1]; os.makedirs(W+'/runs',exist_ok=True); os.makedirs(W+'/gen',exist_ok=True)
HERE=os.path.dirname(os.path.abspath(__file__))
NL='/home/user/project/reference/spike_netlists'
rows=[]
def run(des,k,inp,mode,eng,depth,honest=False):
    top=des; tag=f"{des}_k{k}_{inp}_{mode}_{eng.split()[-1]}_d{depth}{'_honest' if honest else ''}"
    sv=f"{W}/gen/fi_{tag}.sv"
    subprocess.run([sys.executable,HERE+'/gen_wrapper_free.py',f'{NL}/{des}.json',top,str(k),sv]+(['honest'] if honest else []),check=True,capture_output=True)
    d='-DFREEIN ' if inp=='free' else ''
    sby=f"{W}/runs/{tag}.sby"
    open(sby,'w').write(f"[tasks]\nx\n[options]\nmode {mode}\ndepth {depth}\n[engines]\n{eng}\n[script]\nread_verilog -formal {d}fi_{tag}.sv\nprep -top fi_{top}\n[files]\n{sv}\n")
    subprocess.run(['rm','-rf',f'{W}/runs/{tag}'])
    t=time.time()
    try:
        p=subprocess.run(['sby','-f',sby],capture_output=True,text=True,timeout=900); out=p.stdout
    except subprocess.TimeoutExpired: out='TIMEOUT'
    m=re.search(r'DONE \((\w+), rc=(\d+)\)',out)
    r=dict(design=des,k=k,input=inp,mode=mode,engine=eng,depth=depth,honest=honest,status=m.group(1) if m else 'NOSTATUS',
           wall_s=round(time.time()-t,2),proved='Property proved' in out)
    rows.append(r); print(json.dumps(r),flush=True)
for inp in ('const','free'):
    for des in ('v0','v1','v2'):
        for k in (0,1,2,3):
            run(des,k,inp,'prove','abc pdr',6)
    run('v2',0,inp,'prove','abc pdr',6,honest=True)
for k in (1,2):
    for T in (12,16):
        run('v2',k,'free','bmc','smtbmc boolector',T)
json.dump(rows,open(HERE+'/sby_free_results.json','w'),indent=1)
