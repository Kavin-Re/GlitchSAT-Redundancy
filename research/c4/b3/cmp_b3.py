import sys, json, time, os
sys.path.insert(0,'/tmp/work_b3')
import faultpack as fp, b3pack as bp, bf_b3 as bf
rows=[]; bad=0
T=int(sys.argv[1]); K=int(sys.argv[2]); designs=sys.argv[3].split(','); mods=sys.argv[4].split(',')
for d in designs:
    path=f'/tmp/work_b3/nl/{d}.json'; top=d.split('_')[0]
    nl=fp.Netlist(path,top); sim=bf.Sim2(path,top); M=bp.models(nl)
    for m in mods:
        t0=time.time()
        r=bp.min_cost(nl,T,M[m],K,120000)
        kb,w,tried=bf.min_cost(sim,T,m,K)
        zk = r['min'] if r['status']=='ATTACK' else None
        ok = (zk==kb) and r['status']!='UNKNOWN'
        if ok and r['status']=='ATTACK':   # replay z3 witness events in brute-force sim
            pass
        bad += (not ok)
        row=dict(design=d,model=m,T=T,kmax=K,z3=bp.fmt(r),brute=('>%d'%K if kb is None else kb),tried=tried,agree=ok,secs=round(time.time()-t0,1))
        print(row,flush=True); rows.append(row)
json.dump(rows,open(sys.argv[5],'w'),indent=1); print('DISAGREE',bad,'of',len(rows))
