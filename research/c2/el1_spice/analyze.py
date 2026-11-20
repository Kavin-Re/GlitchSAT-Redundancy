# Post-processes SIMULATED ngspice results into fault_windows.json + PNGs. NOT silicon.
import json, glob, collections
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
D="research/c2/el1_spice/"
def cls(v,hi=1.8):
    return "1" if v>0.8*hi else ("0" if v<0.2*hi else "U")   # U = undefined / mid-rail
A=[];B=[];C=[]
for f in sorted(glob.glob(D+"part*.json")):
    r=json.load(open(f))
    if 'partA' in f and not f.endswith('_wd1n.json'): r=[x for x in r if abs(x['wd']-1e-9)>1e-12]  # original wd=1n rows invalid (meas-at-tstop artifact), replaced by rerun
    (A if "partA" in f else B if "partB" in f else C).extend(r)
out=dict(label="SIMULATED circuit-level (ngspice-41, sky130A tt/ss/ff, sky130_fd_sc_hd cells). NOT silicon, NOT physical validation.",
 classification="Q/outputs read as 1 if >1.44 V, 0 if <0.36 V, else U (undefined/mid-rail at the sample time)",
 corners={"tt":"27C","ss":"100C","ff":"-40C"}, vdd_nominal=1.8)
# ---- A
wa=[]
for r in A:
    e=dict(corner=r["corner"],clk_phase_held="high" if r["ph"] else "low",vmin=r["vmin"],width_ns=r["wd"]*1e9,
      flop_stored0_before=cls(r["q0s"]),flop_stored0_after=cls(r["q0f"]),flop_stored1_before=cls(r["q1s"]),flop_stored1_after=cls(r["q1f"]),
      inv_out_high_min_V=r["yhmin"],nand_out_high_min_V=r["nhmin"],inv_out_low_max_V=r["ylmax"],nand_out_low_max_V=r["nlmax"],
      sampled_inv_high_by_clean_flop=cls(r["sy"]),sampled_nand_high_by_clean_flop=cls(r["sn"]))
    e["flop0_result"]="holds" if e["flop_stored0_after"]=="0" else ("FLIPPED" if e["flop_stored0_after"]=="1" else "UNDEFINED")
    e["flop1_result"]="holds" if e["flop_stored1_after"]=="1" else ("FLIPPED" if e["flop_stored1_after"]=="0" else "UNDEFINED")
    e["simultaneous_wrong_flops"]=int(e["flop0_result"]!="holds")+int(e["flop1_result"]!="holds")
    e["gate_output_droops_below_0p9V"]=bool(r["yhmin"]<0.9 or r["nhmin"]<0.9)
    wa.append(e)
out["A_supply_dip"]=wa
out["B_clock_runt"]=[dict(corner=r["corner"],stored=r["sv"],amp_V=r["amp"],width_ns=r["pw"]*1e9,q_before=cls(r["qs"]),q_after=cls(r["qf"]),
   result="holds" if cls(r["qf"])==str(r["sv"]) else ("FLIPPED" if cls(r["qf"]) in "01" else "UNDEFINED")) for r in B]
# C: window
wc=[]
grp=collections.defaultdict(list)
for r in C: grp[(r["corner"],r["sv"],r["vdd"])].append(r)
for k,rs in grp.items():
    rs.sort(key=lambda r:r["dt"])
    new=str(1-k[1]); seq=[(r["dt"]*1e12,cls(r["qf"],k[2])) for r in rs]
    cap=[d for d,c in seq if c==new]; und=[d for d,c in seq if c=="U"]
    wc.append(dict(corner=k[0],stored=k[1],vdd=k[2],
      latest_data_arrival_ps_rel_edge_that_still_captures_new=max(cap) if cap else None,
      first_dt_ps_that_captures_new=min(cap) if cap else None,undefined_dt_ps=und,sequence_ps_to_result=seq,
      note="dt<0: data changes before clock edge (setup side); dt>0 after edge (hold side)"))
out["C_setup_hold"]=wc
json.dump(out,open(D+"fault_windows.json","w"),indent=1)
# plots
cm={"0":"#4c78a8","1":"#e45756","U":"#999999"}
fig,axs=plt.subplots(1,max(1,len({(r['corner'],r['ph']) for r in A})),figsize=(4*max(1,len({(r['corner'],r['ph']) for r in A})),3.6),squeeze=False)
for ax,key in zip(axs[0],sorted({(r['corner'],r['ph']) for r in A})):
    for r in A:
        if (r['corner'],r['ph'])!=key: continue
        res=("hold" if (cls(r['q0f'])=='0' and cls(r['q1f'])=='1') else "wrong")
        n=int(cls(r['q0f'])!='0')+int(cls(r['q1f'])!='1')
        ax.scatter(r['wd']*1e9,r['vmin'],c=["#2a9d8f","#e9c46a","#d62828"][n],s=90,edgecolor="k")
    ax.set_xscale("log");ax.set_title(f"{key[0]} clk held {'high' if key[1] else 'low'}");ax.set_xlabel("dip width (ns)");ax.set_ylabel("dip floor Vmin (V)")
fig.suptitle("SIMULATED: flops on dipping rail; green=both hold, yellow=1 wrong, red=2 wrong (stored 0 and 1 together)",fontsize=8);fig.tight_layout();fig.savefig(D+"plot_A_supply_dip.png",dpi=110)
fig,ax=plt.subplots(figsize=(5,3.5))
for r in B:
    res=cls(r["qf"]); ax.scatter(r["pw"]*1e9,r["amp"],c=("#2a9d8f" if res==str(r["sv"]) else "#d62828" if res in "01" else "#999"),marker={"tt":"o","ss":"s","ff":"^"}[r["corner"]],s=60,edgecolor="k")
ax.set_xscale("log");ax.set_xlabel("runt clock pulse width (ns)");ax.set_ylabel("runt amplitude (V)");ax.set_title("SIMULATED clock runt: green=holds red=flipped (o tt, s ss, ^ ff)",fontsize=8);fig.tight_layout();fig.savefig(D+"plot_B_clock_runt.png",dpi=110)
fig,ax=plt.subplots(figsize=(6,3.6))
for k,rs in grp.items():
    ax.plot([r["dt"]*1e12 for r in rs],[r["qf"] for r in rs],marker=".",label=f"{k[0]} stored{k[1]} vdd{k[2]}")
ax.set_xlabel("data transition time relative to clock edge (ps)");ax.set_ylabel("Q at +4 ns (V)");ax.legend(fontsize=6);ax.set_title("SIMULATED setup/hold sweep (Q final)",fontsize=8);fig.tight_layout();fig.savefig(D+"plot_C_setup_hold.png",dpi=110)
print(len(A),len(B),len(C))
