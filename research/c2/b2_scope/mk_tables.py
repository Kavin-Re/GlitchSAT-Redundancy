import json,glob
rows=[json.loads(l) for l in open('matrix.jsonl')]+[json.loads(l) for f in glob.glob('v3_*.jsonl') for l in open(f)]
rows=[r for r in rows if 'verdict' in r]
def c(r): return '?' if r is None else (str(r['min_cost']) if r['min_cost'] is not None else '>'+str(r['cost_gt']))
def cell(sub,goal,isite,init):
    out=[]
    for fi in (False,True):
        m=[r for r in sub if r['goal']==goal and r['input_sites']==isite and r['init']==init and r['free_input']==fi]
        out.append(c(m[0] if m else None))
    return '/'.join(out)
hdr='| design | netlist | '+' | '.join(f"{g} {'+in' if i else 'noin'} {n}" for g in ('word','ok') for i in (False,True) for n in ('known','nongoal','free'))+' |'
print(hdr); print('|'+'---|'*(2+12))
for d in ('v0','v1','v2','v3'):
  for n in ['spike','apt033_plain','apt033_opt','conda038_plain','conda038_opt']:
    sub=[r for r in rows if r['design']==d and r['netlist']==n]
    if not sub: continue
    print(f'| {d} | {n} | '+' | '.join(cell(sub,g,i,n2) for g in ('boot_word','boot_ok') for i in (False,True) for n2 in ('known','free_nongoal','free'))+' |')
