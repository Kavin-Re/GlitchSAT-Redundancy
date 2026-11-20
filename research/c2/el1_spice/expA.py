# SIMULATED (circuit-level, ngspice-41 + sky130A models). NOT silicon.
# Exp A: supply dip on ONE rail shared by 2 flops (stored 0 / stored 1), clock+D buffers, 4 gates; plus clean-rail samplers.
import sys, json
sys.path.insert(0,'research/c2/el1_spice')
from spl import *
TAG=''
CORNERS=[("tt",27),("ss",100),("ff",-40)]
VM=[1.0,0.7,0.5,0.3,0.0]
WD=[0.3e-9,1e-9,3e-9]
def body(dop,ph):
    c1="vdd" if ph else "0"
    # stored-0 flop: D=0 at capture then dopp? 1:0 ; stored-1 flop: D=1 then dopp? 0:1
    d0b="vdd" if dop else "0"; d1b="0" if dop else "vdd"
    return f"""Vdd vpwr 0 PWL(0 {{vdd}} {{tdip}} {{vdd}} {{tdip+0.1n}} {{vmin}} {{tdip+0.1n+wd}} {{vmin}} {{tdip+0.2n+wd}} {{vdd}})
Vcl vcl 0 {{vdd}}
Vgn vgnd 0 0
Vclk clk0 0 PWL(0 0 2n 0 2.05n {{vdd}} 4n {{vdd}} 4.05n {{{c1}}} 400n {{{c1}}})
Vd0 d00 0 PWL(0 0 6n 0 6.05n {{{d0b}}} 400n {{{d0b}}})
Vd1 d10 0 PWL(0 {{vdd}} 6n {{vdd}} 6.05n {{{d1b}}} 400n {{{d1b}}})
Vlo alo0 0 0
Vhi ahi0 0 {{vdd}}
Vsc sclk 0 PWL(0 0 {{tcs}} 0 {{tcs+0.05n}} {{vdd}} {{tcs+1n}} {{vdd}} {{tcs+1.05n}} 0 400n 0)
Xcb clk0 vgnd vgnd vpwr vpwr clk sky130_fd_sc_hd__clkbuf_1
Xb0 d00 vgnd vgnd vpwr vpwr d0 sky130_fd_sc_hd__buf_1
Xb1 d10 vgnd vgnd vpwr vpwr d1 sky130_fd_sc_hd__buf_1
Xbl alo0 vgnd vgnd vpwr vpwr alo sky130_fd_sc_hd__buf_1
Xbh ahi0 vgnd vgnd vpwr vpwr ahi sky130_fd_sc_hd__buf_1
XF0 clk d0 vgnd vgnd vpwr vpwr q0 sky130_fd_sc_hd__dfxtp_1
XF1 clk d1 vgnd vgnd vpwr vpwr q1 sky130_fd_sc_hd__dfxtp_1
Xiy1 alo vgnd vgnd vpwr vpwr yH sky130_fd_sc_hd__inv_1
Xiy0 ahi vgnd vgnd vpwr vpwr yL sky130_fd_sc_hd__inv_1
Xn1 alo ahi vgnd vgnd vpwr vpwr nH sky130_fd_sc_hd__nand2_1
Xn0 ahi ahi vgnd vgnd vpwr vpwr nL sky130_fd_sc_hd__nand2_1
Xlyh yH vgnd vgnd vpwr vpwr z1 sky130_fd_sc_hd__inv_1
Xlyl yL vgnd vgnd vpwr vpwr z2 sky130_fd_sc_hd__inv_1
Xlnh nH vgnd vgnd vpwr vpwr z3 sky130_fd_sc_hd__inv_1
Xlnl nL vgnd vgnd vpwr vpwr z4 sky130_fd_sc_hd__inv_1
Xs1 sclk yH vgnd vgnd vcl vcl sy sky130_fd_sc_hd__dfxtp_1
Xs2 sclk nH vgnd vgnd vcl vcl sn sky130_fd_sc_hd__dfxtp_1
Cq0 q0 0 5f
Cq1 q1 0 5f
Cyh yH 0 5f
Cyl yL 0 5f
Cnh nH 0 5f
Cnl nL 0 5f
"""
def run(a):
    corner,temp,dop,ph=a
    params=".param vdd=1.8 tdip=8n vmin=0.5 wd=1n tcs={tdip+0.1n+wd/2}\n"
    pre="let tq = 8e-9 + $wdv + 8e-9\nlet ts = tq + 1e-9"
    meas=("meas tran q0s find v(q0) at=7n\nmeas tran q1s find v(q1) at=7n\n"
          "meas tran q0f find v(q0) at=$&tq\nmeas tran q1f find v(q1) at=$&tq\n"
          "meas tran yhmin min v(yH) from=8n to=$&tq\nmeas tran nhmin min v(nH) from=8n to=$&tq\n"
          "meas tran ylmax max v(yL) from=8n to=$&tq\nmeas tran nlmax max v(nL) from=8n to=$&tq\n"
          "meas tran sy find v(sy) at=$&tq\nmeas tran sn find v(sn) at=$&tq")
    echo="echo RES $wdv $vminv $&q0s $&q1s $&q0f $&q1f $&yhmin $&nhmin $&ylmax $&nlmax $&sy $&sn"
    out=sess(body(dop,ph),corner,temp,[("wd",WD),("vmin",VM)],pre=pre,tran="50p $&ts",meas=meas,echo=echo,params=params,tag="expA")
    keys="wd vmin q0s q1s q0f q1f yhmin nhmin ylmax nlmax sy sn".split()
    R=[dict(corner=corner,temp=temp,dopp=dop,ph=ph,**{k:float(x) for k,x in zip(keys,r)}) for r in out]
    json.dump(R,open(f'research/c2/el1_spice/partA_{corner}_{dop}_{ph}{TAG}.json','w')); return R
if __name__=="__main__":
    jobs=[(c,t,d,p) for c,t in CORNERS for d in (1,) for p in (0,1) if c=='tt' or p==0]
    if len(sys.argv)>1: jobs=jobs[:1]
    res=sum(pmap(run,jobs,6),[])
    json.dump(res,open("research/c2/el1_spice/expA_raw.json","w")); print(len(res))
