# SIMULATED. E1: stored-value (dfxtp_1) retention vs supply dip depth/width.
import sys, json; sys.path.insert(0,'.')
from spl import *
VM=[1.4,1.2,1.0,0.8,0.7,0.6,0.5,0.4,0.3,0.2,0.0]
WD=[0.3e-9,1e-9,3e-9,10e-9,30e-9,100e-9]
def run(a):
    corner,temp,vdd,sv,ph=a
    body=f"""Vdd vpwr 0 PWL(0 {{vdd}} 8n {{vdd}} 8.1n {{vmin}} {{8.1n+wd}} {{vmin}} {{8.2n+wd}} {{vdd}})
Vss vgnd 0 0
Vclk clk0 0 PWL(0 0 3n 0 3.05n {{vdd}} 4n {{vdd}} 4.05n {{c1}} 500n {{c1}})
Vd d0 0 PWL(0 {{dA}} 6n {{dA}} 6.05n {{dB}} 500n {{dB}})
Xcb clk0 vgnd vgnd vpwr vpwr clk sky130_fd_sc_hd__clkbuf_1
Xdb d0 vgnd vgnd vpwr vpwr d sky130_fd_sc_hd__buf_1
X1 clk d vgnd vgnd vpwr vpwr q sky130_fd_sc_hd__dfxtp_1
Cl q 0 5f
"""
    # D buffer sits on the dipping rail, so D tracks the rail (same-rail logic).  Stored sv, then D flips to ~sv at 6n.
    dA = "{vdd}" if sv else "0"; dB = "0" if sv else "{vdd}"
    c1 = "{vdd}" if ph else "0"
    params=f".param vdd={vdd} vmin=0.5 wd=1n c1={c1} dA={dA} dB={dB}\n"
    # note: Vd source swings to vdd (nominal) not following rail; buf1 clamps to its own rail
    out=sess(body,corner,temp,[("wd",WD),("vmin",VM)],pre="let ts = $wdv + 16e-9",tran="50p $&ts",
        meas="meas tran qs find v(q) at=5n\nmeas tran qf find v(q) at=ts",echo="echo RES $wdv $vminv $&qs $&qf",params=params,tag="ret")
    return [(corner,temp,vdd,sv,ph,float(w),float(v),float(qs),float(qf)) for w,v,qs,qf in out]
if __name__=="__main__":
    jobs=[("tt",27,1.8,sv,ph) for sv in (0,1) for ph in (0,1)]
    res=sum(pmap(run,jobs),[])
    json.dump(res,open("/tmp/work_el1/e1.json","w")); print(len(res))
