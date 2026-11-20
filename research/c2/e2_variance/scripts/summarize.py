#!/usr/bin/env python3
# table from matrix jsonl files
import json,sys,collections
rows=collections.defaultdict(dict)
for f in sys.argv[1:]:
    for l in open(f):
        d=json.loads(l.replace("\\","\\\\")); r=d["r"]
        if r.get('synth_failed'): s='SYNTHFAIL'
        elif 'cells' in r: s='ENGINE-UNSUPPORTED '+','.join(k for k in r['cells'] if k not in('$_AND_','$_OR_','$_XOR_','$_NOT_','$_MUX_','$_DFF_P_'))
        elif 'solver' in r: s=r['solver'][:30]
        else:
            h=','.join(f"{k.strip('$_')}{v}" for k,v in sorted(r['hist'].items()))
            st=r['struct']; nm=st['named_copy_nets_distinct']
            sh=sum(st['named_copy_shared_gates'].values()) if st.get('named_copy_shared_gates') else '-'
            s=f"g{r['gates']}[{h}] k={r['min_k']} copies={nm}/shg={sh}"
        rows[(d['yosys'],d['variant'])][d['design']]=s
for (y,v),x in rows.items(): print(y,v,'|',' | '.join(f"{d}:{x.get(d)}" for d in ('v0','v1','v2')))
