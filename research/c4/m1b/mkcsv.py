import json,csv,collections
from pred import *
names=[('v0_spike','v0_spike'),('v1_spike','v1_spike'),('v2_spike','v2_spike'),('v2m_apt033','v2m'),('v2s_apt033','v2s'),('v2_apt033','v2_apt033'),('v1_apt033','v1_apt033')]
D={n:{json.loads(l)['mask']:json.loads(l)['min'] for l in open(f'out/prod_{f}.jsonl')} for n,f in names}
coll=lambda m:int(any((s&m)==(0x96&m) for s in (0xF0,0xCC)))
with open('/home/user/project/research/c4/m1b/m1b_all_masks.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['mask_hex','mask_bin','popcount','bits_m0','bits_m1','bits_m2','copies_touched','collides_with_legit_state']+[n+'_min_flips' for n,_ in names]+['v2_rule_prediction'])
    for m in range(1,256):
        w.writerow([f'0x{m:02X}',format(m,'08b'),pop(m),*[pop(m&g) for g in G],sum(1 for g in G if m&g),coll(m),*[D[n][m] for n,_ in names],pred(m)])
for n,_ in names:
    bad=[m for m in D[n] if min(pred(m),4)!=D[n][m]]
    print(n,'rule mismatches',len(bad),'max',max(D[n].values()),'>3',sum(v>3 for v in D[n].values()))
nc=[m for m in range(1,256) if not coll(m)]
print('collide',255-len(nc))
for n in ('v2_spike','v2_apt033'):
    print(n,'noncolliding',collections.Counter(D[n][m] for m in nc),'full',D[n][255])
    print(' pop<=4 noncoll:',collections.Counter(D[n][m] for m in nc if pop(m)<=4))
print('v2_spike all255',collections.Counter(D['v2_spike'].values()))
