import json, subprocess, sys
res = {}
for nl, top in [('v0','v0'),('v1','v1'),('v2','v2'),('s0','v0'),('s1','v1'),('s2','v2'),('w0','v0'),('w1','v1'),('w2','v2'),('w2o','v2')]:
    for k in (0,1,2,3):
        out = f'/tmp/gs_{nl}_{k}.json'
        subprocess.run(['/usr/bin/python3', '../scripts/glitchsat.py', 'check', f'gen/{nl}.json', '--top', top, '--k', str(k), '--cycles', '6', '--out', out], capture_output=True)
        d = json.load(open(out)); res[f'{nl}_k{k}'] = (d['verdict'], d.get('min_faults'), d['runtime_s'])
json.dump(res, open('runs/glitchsat_crosscheck.json', 'w'), indent=1); print(json.dumps(res))
