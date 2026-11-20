#!/usr/bin/env python3
"""Matrix runner: one cell = (netlist, model, goal) -> min event cost at T, cap, z3 timeout. Parallel, resumable (jsonl)."""
import sys, os, json, time, subprocess
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
T = int(os.environ.get('T', 6)); CAP = int(os.environ.get('CAP', 3)); TMO = int(os.environ.get('TMO', 90000))
out = sys.argv[1]; designs = sys.argv[2].split(','); models = sys.argv[3].split(','); goals = sys.argv[4].split(',')
done = set()
if os.path.exists(out):
    for l in open(out): r = json.loads(l); done.add((r['design'], r['model'], r['goal']))
def cell(c):
    d, m, g = c; top = d.split('_')[0]
    t0 = time.time()
    code = f"""
import sys; sys.path.insert(0,'{HERE}')
import faultpack as fp, b3pol as bp, json
nl=fp.Netlist('{HERE}/nl/{d}.json','{top}'); ev=bp.models(nl)['{m}']
kw=dict(goal_out='boot_word',goal_value=0x96) if '{g}'=='word' else dict(goal_out='boot_ok',goal_value=1)
r=bp.min_cost(nl,{T},ev,{CAP},{TMO},**kw); r['fmt']=bp.fmt(r); print(json.dumps(r))
"""
    try:
        p = subprocess.run(['python3', '-c', code], capture_output=True, text=True, timeout=TMO / 1000 * (CAP + 1) + 60)
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:
        r = dict(status='UNKNOWN', fmt='unknown', note='hard timeout/err ' + str(e)[:80])
    row = dict(design=d, model=m, goal=g, T=T, cap=CAP, min=r['fmt'], status=r['status'], events=r.get('events'), sig=r.get('sig'),
               n_events=r.get('n_events'), secs=round(time.time() - t0, 1), z3_timeout_ms=TMO)
    with open(out, 'a') as f: f.write(json.dumps(row) + '\n')
    print(d, m, g, row['min'], row['secs'], flush=True)
cells = [(d, m, g) for d in designs for g in goals for m in models if (d, m, g) not in done]
with ThreadPoolExecutor(4) as ex: list(ex.map(cell, cells))
