import subprocess, itertools, json, re
M='/tmp/mm_root/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/verilog/'
cells={'nand4bb_1':(['A_N','B_N','C','D'],'Y'),'nor4bb_1':(['A','B','C_N','D_N'],'Y'),'a21boi_0':(['A1','A2','B1_N'],'Y'),
'a2bb2oi_1':(['A1_N','A2_N','B1','B2'],'Y'),'a22o_1':(['A1','A2','B1','B2'],'X'),'a21o_1':(['A1','A2','B1'],'X'),
'mux2_1':(['A0','A1','S'],'X'),'and4_1':(['A','B','C','D'],'X'),'nand4_1':(['A','B','C','D'],'Y'),'nor4_1':(['A','B','C','D'],'Y'),
'clkinv_1':(['A'],'Y'),'nand2_1':(['A','B'],'Y'),'nor2_1':(['A','B'],'Y')}
out={}
for c,(ins,o) in cells.items():
    tb=['module t;']
    for i in ins: tb.append(f'reg {i};')
    tb.append(f'wire {o}; sky130_fd_sc_hd__{c} u('+','.join(f'.{i}({i})' for i in ins)+f',.{o}({o}));')
    tb.append('initial begin')
    for v in range(2**len(ins)):
        tb.append(' '.join(f'{i}=1\'b{(v>>j)&1};' for j,i in enumerate(ins))+f' #1 $display("%b",{o});')
    tb.append('end endmodule')
    open('t.v','w').write('\n'.join(tb))
    r=subprocess.run(['iverilog','-o','-DFUNCTIONAL','-DUNIT_DELAY=','-o','t.vvp','t.v',M+'primitives.v',M+'sky130_fd_sc_hd.v'],capture_output=True,text=True)
    if r.returncode: print(c,r.stderr[:300]); continue
    r=subprocess.run(['vvp','t.vvp'],capture_output=True,text=True)
    out[c]=dict(ins=ins,o=o,tt=[int(x) for x in r.stdout.split()])
json.dump(out,open('tt.json','w'))
print({c:len(v['tt']) for c,v in out.items()})
