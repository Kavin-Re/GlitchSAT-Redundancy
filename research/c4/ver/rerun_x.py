import sys,csv,json,time
sys.path.insert(0,'/tmp/work_ver')
from multiprocessing import Pool
import gs_mask2 as G
rows=list(csv.DictReader(open('heldout.csv')))
man={m['json']:m for m in json.load(open('manifest.json'))}
def hasx(p):
    d=json.load(open(p))['modules']; m=d[list(d)[0]] if len(d)==1 else d[[k for k in d if k[0] in 'tv'][0]]
    return any('x' in str(x['attributes'].get('init','')) for x in m['netnames'].values())
todo=[r for r in rows if r['json'] in man and hasx(r['json'])]
def job(r):
    m=man[r['json']]; nl=G.Netlist(m['json'],m['top'])
    v,i,a=G.solve(nl,6,3,timeout_ms=150000,goal_out='boot_word',goal_value=m['acc'],key=m['key'],goal_mask=int(r['mask'],16))
    return dict(json=r['json'],mask=r['mask'],old=r['solver'],new={'ATTACK_FOUND':len(a['faults']) if a else None,'NO_ATTACK_UP_TO_BOUND':'>3'}.get(v,'unk'))
if __name__=='__main__':
    with Pool(3) as p: out=p.map(job,todo)
    json.dump(out,open('rerun_x.json','w'))
    ch=[o for o in out if str(o['new'])!=o['old']];print(len(out),'changed',len(ch),ch)
