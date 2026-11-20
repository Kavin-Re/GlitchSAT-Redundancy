import csv, random, os, json, sys, time, collections
sys.path.insert(0,'/tmp/work_ledger/pre')
from concurrent.futures import ProcessPoolExecutor
R=list(csv.DictReader(open('/home/user/project/research/c2/e2_variance/raw/matrix.csv')))
S=[r for r in R if r['status']=='SOLVED']
tag=lambda r:'__'.join([r['build'],r['design'],r['flow'],r['order'],r['abc'],r['merge'],r['keep']])
random.seed(20261119)
# one config per canonical sha (unique netlists), stratified
seen=set(); uniq=[]
for r in S:
    k=(r['sha256_canon'],r['design'])
    if k in seen: continue
    seen.add(k); uniq.append(r)
strata=collections.defaultdict(list)
for r in uniq: strata[(r['design'],r['min_flips'])].append(r)
want={('v2','3'):12,('v2','2'):12,('v2','1'):12,('v1','2'):10,('v1','1'):8,('v0','1'):8}
pick=[]
for k,n in want.items():
    L=strata[k]; random.shuffle(L); pick+=L[:n]
    print(k,len(L),'unique;',min(n,len(L)),'picked')
cells=[]
for r in pick:
    p=f'/tmp/work_e2/nl/{tag(r)}/r1.json'
    cells.append(dict(src='E2 resynth',tag=tag(r),path=p,top=r['design'],solver=int(r['min_flips'])))
# baselines
B='/home/user/project/research/c2/e2_variance/baseline_netlists/'
base={'apt0.33':{'v0':1,'v1':1,'v2':2},'conda-formal0.38':{'v0':1,'v1':1,'v2':3},'conda-eda0.38':{'v0':1,'v1':1,'v2':3}}
for b,d in base.items():
    for v,m in d.items(): cells.append(dict(src='E2 baseline',tag=f'{b}_{v}',path=B+f'{b}_{v}.json',top=v,solver=m))
def run(c):
    import predictor
    t0=time.time()
    try:
        r=predictor.predict(c['path'],c['top'])
        return dict(c,pred=r['pred'],lb=r['lb'],est=r['est'],flag=r['flag'],secs=round(time.time()-t0,1))
    except Exception as e: return dict(c,pred=None,flag='ERR '+str(e)[:60],secs=round(time.time()-t0,1))
if __name__=='__main__':
    with ProcessPoolExecutor(4) as ex: out=list(ex.map(run,cells))
    json.dump(out,open('e2_sample.json','w'),indent=1)
    cm=collections.Counter((o['solver'],o['pred']) for o in out)
    print(len(out)); print(sorted(cm.items()))
    print('exact',sum(o['pred']==o['solver'] for o in out),'/',len(out))
