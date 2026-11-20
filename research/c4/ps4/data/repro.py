import json, sys
from faultbound_wt import runner, config
exp=json.load(open('ci/expected_reproduce.json'))['expected']
bad=n=0
for key,(v,m) in exp.items():
    d,flow,k=key.split('|'); k=int(k[1:])
    if flow not in ('rtl/plain','spike/given-netlist'): continue
    path = f'rtl/{d}.v' if flow=='rtl/plain' else f'reference/spike_netlists/{d}.json'
    th=config.load('product/src/faultbound_wt/examples/threat.toml'); th.max_flips=k; th.top=d; config.validate(th)
    r=runner.analyze(path,th); n+=1
    ok=(r['verdict'],r.get('min_faults'))==(v,m)
    if not ok: bad+=1; print('DIFF',key,r['verdict'],r.get('min_faults'),v,m)
print('compared',n,'diffs',bad)
