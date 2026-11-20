# SIMULATED circuit-level helper (ngspice 41 + sky130A models). Not silicon.
import subprocess, os, tempfile, itertools, sys
from concurrent.futures import ThreadPoolExecutor
NG="/tmp/mm_root/envs/spice/bin/ngspice"
PDK="/tmp/mm_root/envs/eda/share/pdk/sky130A"
HDR=""".lib {PDK}/libs.tech/ngspice/sky130.lib.spice {corner}
.include {PDK}/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice
.temp {temp}
"""
def sess(body, corner="tt", temp=27, loops=None, tran="20p 12n", meas="", echo="", params="", tag="x", pre=""):
    """loops: list of (param, [values]) nested; body uses {param}. echo: ngspice echo string w/ $&meas and $param."""
    ctl="set noaskquit\n"; close=""
    for p,vals in loops:
        ctl+=f"foreach {p}v {' '.join(str(v) for v in vals)}\nalterparam {p}=${p}v\n"; close="end\n"+close
    # nested foreach needs distinct var names; echo uses $<p>v
    ctl+="reset\n"+pre+"\ntran "+tran+"\n"+meas+"\n"+echo+"\n"+close+"quit\n"
    net=f"* {tag}\n"+HDR.format(PDK=PDK,corner=corner,temp=temp)+params+"\n"+body+"\n.control\n"+ctl+".endc\n.end\n"
    d=tempfile.mkdtemp(prefix="el1_",dir="/tmp/work_el1"); f=d+"/n.cir"; open(f,"w").write(net)
    r=subprocess.run([NG,"-b",f],capture_output=True,text=True,timeout=1500)
    out=[l.split()[1:] for l in r.stdout.splitlines() if l.startswith("RES ")]
    if not out: sys.stderr.write(r.stdout[-1500:]+r.stderr[-500:])
    return out
def pmap(fn, items, n=4):
    with ThreadPoolExecutor(n) as ex: return list(ex.map(fn, items))
