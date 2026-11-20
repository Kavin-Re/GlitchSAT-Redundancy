#!/usr/bin/env python3
"""BMC matrix with SymbiYosys. Run from formal/ with the formal env on PATH."""
import subprocess, sys, time, json, os, re
DEPTH = int(os.environ.get('DEPTH', 6))
ENG = os.environ.get('ENG', 'smtbmc boolector')
rows = []
def run(nl, top, k, mode='bmc', eng=ENG, honest=False, depth=DEPTH, tag=None):
    tag = tag or f"{nl}_{top}_k{k}_{mode}_{eng.replace(' ','_')}{'_honest' if honest else ''}_d{depth}"
    sv = f"gen/fi_{tag}.sv"
    subprocess.run([sys.executable, 'src/gen_wrapper.py', f'gen/{nl}.json', top, str(k), sv] + (['honest'] if honest else []),
                   check=True, capture_output=True)
    sby = f"runs/{tag}.sby"
    open(sby, 'w').write(f"[tasks]\nx\n[options]\nmode {mode}\ndepth {depth}\n[engines]\n{eng}\n[script]\nread_verilog -formal fi_{tag}.sv\nprep -top fi_{top}\n[files]\n{sv}\n")
    subprocess.run(['rm', '-rf', f'runs/{tag}'])
    t = time.time()
    p = subprocess.run(['sby', '-f', sby], capture_output=True, text=True, timeout=int(os.environ.get('TMO', 1500)))
    dt = time.time() - t
    out = p.stdout
    m = re.search(r'DONE \((\w+), rc=(\d+)\)', out)
    status = m.group(1) if m else 'NOSTATUS'
    fail_step = re.search(r'Assert failed in .* step (\d+)', out) or re.search(r'BMC failed!', out)
    step = re.search(r'failed assertion .* at step (\d+)', out)
    r = dict(netlist=nl, top=top, k=k, mode=mode, engine=eng, depth=depth, honest=honest, sby_status=status,
             wall_s=round(dt, 2), cex_step=int(step.group(1)) if step else None, dir=f'runs/{tag}')
    rows.append(r); print(json.dumps(r), flush=True)
    return r
if __name__ == '__main__':
    out = sys.argv[1]
    for nl, top in [('v0','v0'),('v1','v1'),('v2','v2'),('s0','v0'),('s1','v1'),('s2','v2')]:
        for k in (0,1,2,3):
            run(nl, top, k)
    for nl, top in [('v0','v0'),('v1','v1'),('v2','v2')]:
        run(nl, top, 0, honest=True)
    json.dump(rows, open(out, 'w'), indent=1)
