import subprocess, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
TR='/tmp/work_ledger/tree'; E2='/tmp/work_e2/nl'
env0=dict(os.environ, PYTHONPATH=TR+'/product/src')
V2=TR+'/reference/spike_netlists/v2.json'; V1=TR+'/reference/spike_netlists/v1.json'; V0=TR+'/reference/spike_netlists/v0.json'
conda=E2+'/conda-formal0.38__v2__plain__abc_then_flatten__default__nomerge__keep_on/r1.json'
merge=E2+'/apt0.33__v2__plain__abc_then_flatten__default__opt_merge__keep_on/r1.json'
apt=TR+'/research/c4/b3/nl/v2_apt033.json'
cells=[
 # id, tool, netlist, k, extra, label
 ('V2 spike word k=2 (none)','gs',V2,2,[], 'headline'),
 ('V2 spike word k=3 (min 3)','gs',V2,3,[], 'headline'),
 ('V2 spike boot_ok k=1','gs',V2,1,['--goal-out','boot_ok','--goal-value','1'], 'headline'),
 ('V1 spike word k=1','gs',V1,1,[], 'headline'),
 ('V0 spike word k=1','gs',V0,1,[], 'headline'),
 ('V2 apt0.33 plain k=1 (none)','gs',apt,1,[], 'headline'),
 ('V2 apt0.33 plain k=2 (min 2)','gs',apt,2,[], 'headline'),
 ('V2 conda0.38 plain (E2) k=2 (none)','gs',conda,2,[], 'E2'),
 ('V2 conda0.38 plain (E2) k=3 (min 3)','gs',conda,3,[], 'E2'),
 ('V2 apt opt_merge (E2) k=1 (min 1)','gs',merge,1,[], 'E2'),
 ('V2 spike mask 0x02 k=3 (min 1)','pr',V2,3,['--consumer-bits','0x02'], 'mask'),
 ('V2 spike mask 0x0E k=3 (min 2)','pr',V2,3,['--consumer-bits','0x0E'], 'mask'),
 ('V2 spike mask 0x3E k=3 (min 3)','pr',V2,3,['--consumer-bits','0x3E'], 'mask'),
 ('V2 spike input-sites=all k=3 (min 1)','pr',V2,3,['--input-sites','all'], 'B2'),
 ('V2 spike init=free_nongoal k=3 (min 1)','pr',V2,3,['--init','free_nongoal'], 'B2'),
 ('V2 spike init=arbitrary k=3 (min 0)','pr',V2,3,['--init','arbitrary'], 'B2'),
 ('V2 spike count-rule=branch k=3','pr',V2,3,['--count-rule','branch'], 'count rule'),
]
def run(c,amk):
    cid,tool,nl,k,ex,lab=c; out=f'/tmp/work_ledger/t3/o_{abs(hash((cid,amk)))}.json'
    t0=time.time()
    try:
        if tool=='gs':
            cmd=['python3',TR+'/scripts/glitchsat.py','check',nl,'--top','v2' if 'v2' in nl.lower() else ('v1' if 'v1' in nl else 'v0'),'--k',str(k),'--cycles','6','--amk',amk,'--timeout-ms','100000','--out',out]+ex
            e=env0
        else:
            cmd=['python3','-m','faultbound_wt.cli','analyze',nl,'--top','v2','--max-flips',str(k),'--cycles','6','--report',out,'--exit-zero']+ex
            e=dict(env0,FAULTBOUND_AMK=amk)
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=170,env=e,cwd='/tmp/work_ledger/tree')
        d=json.load(open(out))
        return dict(id=cid,amk=amk,tool=tool,verdict=d['verdict'],min=d.get('min_faults'),secs=round(time.time()-t0,1))
    except Exception as ex_:
        return dict(id=cid,amk=amk,tool=tool,verdict='ERR/TIMEOUT',min=None,secs=round(time.time()-t0,1),err=str(ex_)[:100])
jobs=[(c,a) for c in cells for a in('counter','legacy')]
with ThreadPoolExecutor(4) as ex: res=list(ex.map(lambda j:run(*j),jobs))
json.dump(res,open('reg.json','w'),indent=1)
by={}
for r in res: by.setdefault(r['id'],{})[r['amk']]=r
n=0
for c in cells:
    a,b=by[c[0]]['counter'],by[c[0]]['legacy']
    agree=(a['verdict']==b['verdict'] and a['min']==b['min']); n+=agree
    print(f"{c[0]:45s} counter={a['verdict']}/{a['min']} ({a['secs']}s)  legacy={b['verdict']}/{b['min']} ({b['secs']}s)  {'AGREE' if agree else 'DIFF'}")
print('agree',n,'of',len(cells))
