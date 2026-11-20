import json,glob
for p in sorted(glob.glob('nl/*.json')):
    d=json.load(open(p))
    for top,m in d['modules'].items():
        seen={}
        for n,x in m['netnames'].items():
            iv=x['attributes'].get('init')
            if iv:
                for i,b in enumerate(reversed(iv)):
                    seen.setdefault(x['bits'][i],set()).add((n,b))
        conf={k:v for k,v in seen.items() if len({b for _,b in v})>1}
        print(p,top,'init bits',len(seen),'conflicts',conf)
