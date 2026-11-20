import csv, random, sys, time
from faultbound_wt import runner, config
rows=list(csv.DictReader(open('research/c3/m1/m1_all_masks.csv')))
random.seed(7)
rows=[r for r in rows if r['popcount']=='4']
by={}
for r in rows: by.setdefault(r['v2_spike_min_flips'],[]).append(r)
print({k:len(v) for k,v in by.items()})
pick=[]
for k,n in (('0',0),('1',4),('2',4),('3',2)): pick+=random.sample(by[k],n)
for r in pick:
    m=int(r['mask_hex'],16); th=config.load('src/faultbound_wt/examples/threat.toml'); th.max_flips=3; th.consumer_bits=m
    t=time.time(); rep=runner.analyze('src/faultbound_wt/examples/v2.json',th)
    got=rep['min_faults'] if rep['verdict']=='ATTACK_FOUND' else '>3'
    print(r['mask_hex'], 'M1',r['v2_spike_min_flips'],'got',got, 'OK' if str(got)==r['v2_spike_min_flips'] else 'MISMATCH', round(time.time()-t,1),flush=True)
