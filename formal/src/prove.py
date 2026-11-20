import sys; sys.path.insert(0,'src')
import matrix, json
cases = [('s2','v2',1),('s2','v2',2),('s2','v2',3),('w2','v2',1),('w2','v2',2),('s1','v1',1),('s0','v0',1),('s2','v2',0),('s1','v1',0)]
for eng in ['abc pdr', 'smtbmc boolector']:
    for nl, top, k in cases:
        try: matrix.run(nl, top, k, mode='prove', eng=eng, depth=20 if 'smtbmc' in eng else 6)
        except Exception as e: print(json.dumps(dict(netlist=nl,k=k,engine=eng,error=str(e)[:100])), flush=True)
json.dump(matrix.rows, open('runs/prove_matrix.json','w'), indent=1)
