import json,glob,sys
for p in sorted(glob.glob(sys.argv[1]+"/*.json")):
    d=json.load(open(p)); top=list(d['modules'])[0] if len(d['modules'])==1 else None
    for top,m in d['modules'].items():
        qs=set(); 
        for c in m['cells'].values():
            if c['type'].startswith('$_DFF'): qs.add(c['connections']['Q'][0])
        for n,x in m['netnames'].items():
            iv=x['attributes'].get('init')
            if iv and any(b not in '01' for b in iv):
                print(p,top,n,iv,[ (i,x['bits'][i] in qs) for i,b in enumerate(reversed(iv)) if b not in '01'])
print('done')
