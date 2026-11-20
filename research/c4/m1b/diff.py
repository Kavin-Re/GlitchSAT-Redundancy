import json,sys
pre=sys.argv[1]
names=[('v0_spike','m_v0_spike'),('v1_spike','m_v1_spike'),('v2_spike','m_v2_spike'),('v2m_apt033','m_v2m'),('v2s_apt033','m_v2s'),('v2_apt033','m_v2_apt033'),('v1_apt033','m_v1_apt033')]
fn={'v0_spike':'v0_spike','v1_spike':'v1_spike','v2_spike':'v2_spike','v2m_apt033':'v2m','v2s_apt033':'v2s','v2_apt033':'v2_apt033','v1_apt033':'v1_apt033'}
tot=0;ch=[]
for n,o in names:
    old={}
    for l in open(f'/home/user/project/research/c3/m1/{o}.jsonl'):
        x=json.loads(l); old[x['mask']]=x['min']
    new={}
    for l in open(f'out/{pre}_{fn[n]}.jsonl'):
        x=json.loads(l); new[x['mask']]=x['min']
    assert set(old)==set(new)==set(range(1,256))
    d=[(m,old[m],new[m]) for m in old if old[m]!=new[m]]
    print(n,'cells',len(old),'changed',len(d),d); ch+=d
