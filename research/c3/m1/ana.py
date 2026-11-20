import json,glob,collections,csv,sys,os;sys.path.insert(0,'/tmp/work_m1')
from pred import *
OUT='research/c3/m1'
names=[('v0_spike','m_v0_spike'),('v1_spike','m_v1_spike'),('v2_spike','m_v2_spike'),('v2m_apt033','m_v2m'),('v2s_apt033','m_v2s'),('v2_apt033','m_v2_apt033'),('v1_apt033','m_v1_apt033')]
D={}
for n,f in names:
    if os.path.exists(f+'.jsonl'):
        D[n]={}
        for l in open(f+'.jsonl'):
            x=json.loads(l); D[n][x['mask']]=(x['min'],x['status'])
def ntouch(m): return sum(1 for g in G if m&g)
comp=lambda m:tuple(pop(m&g) for g in G)
with open(OUT+'/m1_all_masks.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['mask_hex','mask_bin','popcount','bits_m0','bits_m1','bits_m2','copies_touched','collides_with_legit_state']+[n+'_min_flips' for n in D]+['v2_rule_prediction'])
    for m in range(1,256):
        c=comp(m)
        w.writerow([f'0x{m:02X}',format(m,'08b'),pop(m),*c,ntouch(m),int(any((s&m)==(0x96&m) for s in (0xF0,0xCC))),*[ (D[n][m][0] if D[n][m][0] is not None else 'UNKNOWN') if m in D[n] else 'NA' for n in D],pred(m)])
# summary: per design, per popcount: histogram
rows=[]
for n in D:
    for p in range(1,9):
        h=collections.Counter(D[n][m][0] if D[n][m][0] is not None else 'U' for m in D[n] if pop(m)==p)
        rows.append((n,p,dict(sorted(h.items(),key=str))))
        print(n,p,dict(sorted(h.items(),key=str)))
# V2: excluding collision masks, by (popcount, copies touched)
for n in D:
    print('==',n,'(non-colliding masks) min flips by popcount x copies touched: avg/min/max, count')
    for p in range(1,9):
        for t in (1,2,3):
            v=[D[n][m][0] for m in D[n] if pop(m)==p and ntouch(m)==t and not any((s&m)==(0x96&m) for s in (0xF0,0xCC)) and D[n][m][0] is not None]
            if v: print(' pop',p,'touch',t,'n',len(v),'min',min(v),'max',max(v),collections.Counter(v))
for n in D:
    bad=[m for m in D[n] if D[n][m][0] is not None and min(pred(m),4)!=D[n][m][0]]
    print(n,'V2-rule mismatches',len(bad),'unknown',sum(1 for m in D[n] if D[n][m][0] is None))
json.dump({n:{m:D[n][m][0] for m in D[n]} for n in D},open('all.json','w'))
