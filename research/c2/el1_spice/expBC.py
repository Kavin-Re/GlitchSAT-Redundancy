# SIMULATED (circuit-level, ngspice-41 + sky130A models). NOT silicon.
# Exp B: runt/extra clock pulse on a flop holding a value (D = opposite).  Exp C: data transition near the clock edge (setup/hold), incl. reduced static VDD.
import sys, json
sys.path.insert(0,'research/c2/el1_spice')
from spl import *
CORNERS=[("tt",27),("ss",100),("ff",-40)]
AMP=[0.5,0.9,1.3,1.8]
PW=[0.1e-9,0.4e-9,2e-9]
DT=[x*1e-12 for x in range(-300,201,25)]
def bodyB(sv):
    d0="vdd" if sv else "0"; d1="0" if sv else "vdd"
    return f"""Vdd vpwr 0 {{vdd}}
Vgn vgnd 0 0
Vclk clk 0 PWL(0 0 2n 0 2.05n {{vdd}} 4n {{vdd}} 4.05n 0 10n 0 {{10n+0.05n}} {{amp}} {{10n+0.05n+pw}} {{amp}} {{10n+0.1n+pw}} 0 400n 0)
Vd d 0 PWL(0 {d0} 6n {d0} 6.05n {d1} 400n {d1})
X1 clk d vgnd vgnd vpwr vpwr q sky130_fd_sc_hd__dfxtp_1
Cl q 0 5f
"""
def runB(a):
    corner,temp,sv=a
    out=sess(bodyB(sv),corner,temp,[("amp",AMP),("pw",PW)],pre="",tran="50p 14n",params=".param vdd=1.8 amp=1 pw=1n\n",
      meas="meas tran qs find v(q) at=8n\nmeas tran qf find v(q) at=13n",echo="echo RES $ampv $pwv $&qs $&qf",tag="expB")
    R=[dict(exp="B",corner=corner,temp=temp,sv=sv,amp=float(r[0]),pw=float(r[1]),qs=float(r[2]),qf=float(r[3])) for r in out]
    json.dump(R,open(f'research/c2/el1_spice/partB_{corner}_{sv}.json','w')); return R
def bodyC(sv):
    d0="vdd" if sv else "0"; d1="0" if sv else "vdd"
    return f"""Vdd vpwr 0 {{vdd}}
Vgn vgnd 0 0
Vclk clk 0 PWL(0 0 2n 0 2.05n {{vdd}} 4n {{vdd}} 4.05n 0 10n 0 10.05n {{vdd}} 14n {{vdd}} 14.05n 0 400n 0)
Vd d 0 PWL(0 {d0} 6n {d0} {{10.025n+dt-0.025n}} {d0} {{10.025n+dt+0.025n}} {d1} 400n {d1})
X1 clk d vgnd vgnd vpwr vpwr q sky130_fd_sc_hd__dfxtp_1
Cl q 0 5f
"""
def runC(a):
    corner,temp,sv,vdd=a
    out=sess(bodyC(sv),corner,temp,[("dt",DT)],pre="",tran="40p 15n",params=f".param vdd={vdd} dt=0\n",
      meas="meas tran qs find v(q) at=9n\nmeas tran qm find v(q) at=11n\nmeas tran qf find v(q) at=13n",echo="echo RES $dtv $&qs $&qm $&qf",tag="expC")
    R=[dict(exp="C",corner=corner,temp=temp,sv=sv,vdd=vdd,dt=float(r[0]),qs=float(r[1]),qm=float(r[2]),qf=float(r[3])) for r in out]
    json.dump(R,open(f'research/c2/el1_spice/partC_{corner}_{sv}_{vdd}.json','w')); return R
if __name__=="__main__":
    res=[]
    jb=[(c,t,s) for c,t in CORNERS for s in (0,) ]+[('tt',27,1)]
    jc=[(c,t,0,1.8) for c,t in CORNERS]+[('tt',27,0,1.2),('tt',27,1,1.8)]
    # parallel: run B and C jobs together
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        fb=[ex.submit(runB,j) for j in jb]; fc=[ex.submit(runC,j) for j in jc]
        for f in fb+fc: res+=f.result()
    json.dump(res,open("research/c2/el1_spice/expBC_raw.json","w")); print(len(res))
