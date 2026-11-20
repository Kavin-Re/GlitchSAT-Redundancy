import sys, json, copy, subprocess, os
sys.path.insert(0,'/tmp/work_rt/scripts')
CLI=['python3','-I','/tmp/work_rt/scripts/glitchsat.py','check']
PCLI=['env','PYTHONPATH=/tmp/work_rt/product/src','python3','-I','-m','faultbound_wt.cli','analyze']
def base():
    # sig[1:0] input, key=2'b11 (fix via --key 3); out boot_word[1:0]; goal 0b10 ... gate-level
    return dict(modules=dict(t=dict(ports=dict(clk=dict(direction='input',bits=[2]),sig=dict(direction='input',bits=[3,4]),
        boot_word=dict(direction='output',bits=[5,6])),cells={},netnames={})))
def add(d,name,ty,**con): d['modules']['t']['cells'][name]=dict(type=ty,connections={k:(v if isinstance(v,list) else [v]) for k,v in con.items()})
def run(name,d,args,raw=None):
    p=f'/tmp/work_rt/rt/e_{name}.json'
    if raw is not None: open(p,'w').write(raw)
    else: json.dump(d,open(p,'w'))
    r=subprocess.run(CLI+[p,'--top','t']+args,capture_output=True,text=True,timeout=120)
    out=(r.stdout.strip().split('\n')[0] if r.stdout.strip() else '')+' | '+r.stderr.strip().split('\n')[-1][:140]
    print(f'{name:28s} rc={r.returncode} {out}')
    return r
args=['--k','1','--cycles','3','--key','3','--goal-value','2']
# E1 sanity: out0 = sig0&sig1 ... goal 0b10 (bit1=1, bit0=0): wrong key reachable without faults? out1 = sig1 & !sig0
d=base(); add(d,'n','$_NOT_',A=3,Y=7); add(d,'a','$_AND_',A=4,B=7,Y=5); d['modules']['t']['ports']['boot_word']['bits']=[8,5]
add(d,'z','$_AND_',A=3,B='0',Y=8)
run('control',d,args)
# E2 multi-driver: two gates drive net 5
d=base(); add(d,'g1','$_AND_',A=3,B=4,Y=5); add(d,'g2','$_OR_',A=3,B=4,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('multidriver',d,['--k','0','--cycles','2','--key','3','--goal-value','1'])
# swap order -> verdict change?
d2=base(); add(d2,'g2','$_OR_',A=3,B=4,Y=5); add(d2,'g1','$_AND_',A=3,B=4,Y=5); add(d2,'z','$_AND_',A=3,B='0',Y=6)
run('multidriver_swapped',d2,['--k','0','--cycles','2','--key','3','--goal-value','1'])
# E3 undriven net feeding output
d=base(); add(d,'g1','$_AND_',A=3,B=99,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('undriven',d,['--k','0','--cycles','2','--key','3','--goal-value','1'])
# E4 'x' constant
d=base(); add(d,'g1','$_OR_',A=3,B='x',Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('const_x',d,['--k','0','--cycles','2','--key','3','--goal-value','1'])
# E5 latch
d=base(); add(d,'l','$_DLATCH_P_',D=3,E=4,Q=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('latch',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E6 tribuf
d=base(); add(d,'t','$_TBUF_',A=3,E=4,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('tbuf',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E6b unsupported cell NOT in goal cone
d=base(); add(d,'t','$_TBUF_',A=3,E=4,Y=50); add(d,'g','$_BUF_',A=3,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('unsupported_outside_cone',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E7 negedge/ enable flop / async reset flop
for ty in ['$_DFF_N_','$_DFFE_PP_','$_SDFF_PP0_','$_DFF_PN0_']:
    d=base(); add(d,'f',ty,C=2,D=3,Q=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
    run('flop'+ty,d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E8 $mem / $dff coarse
d=base(); add(d,'f','$dff',CLK=2,D=[3],Q=[5]); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('coarse_$dff',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
d=base(); add(d,'m','$mem_v2',A=3,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('mem',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E9 comb loop
d=base(); add(d,'a','$_NOT_',A=7,Y=5); add(d,'b','$_NOT_',A=5,Y=7); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('comb_loop',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
# E10 zero flops pure comb: out0=sig0 ^ sig1 ; goal 1; key=3 ->  wrong key gives 1 with k0
d=base(); add(d,'x','$_XOR_',A=3,B=4,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('zero_flops_k0',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
# k=0 cycles=1 ok; cycles=0, k=-1, goal value too wide, key too wide
run('cycles0',d,['--k','0','--cycles','0','--key','3','--goal-value','1'])
run('k_negative',d,['--k','-1','--cycles','1','--key','3','--goal-value','1'])
run('goalvalue_wide(0x101 vs 2bit)',d,['--k','0','--cycles','1','--key','3','--goal-value','0x101'])
run('goalvalue_wide_0x5',d,['--k','0','--cycles','1','--key','3','--goal-value','0x5'])
run('key_wide(0x103)',d,['--k','0','--cycles','1','--key','0x103','--goal-value','1'])
# attacker input = clk / missing output / goal is input port
run('attack_input_missing',d,['--k','0','--cycles','1','--key','3','--goal-value','1','--attack-input','nope'])
run('goal_missing',d,['--k','0','--cycles','1','--key','3','--goal-value','1','--goal-out','nope'])
# goal net is input bit directly
d=base(); d['modules']['t']['ports']['boot_word']['bits']=[3,4]; add(d,'z','$_AND_',A=3,B='0',Y=6)
run('goal_is_input_k0',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
# goal bits constant
d=base(); d['modules']['t']['ports']['boot_word']['bits']=['1','0']; add(d,'z','$_AND_',A=3,B='0',Y=6)
run('goal_const_k0',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
# huge fanout: 3000 consumers of net 5, and a 2500-deep chain
d=base(); add(d,'g','$_AND_',A=3,B=4,Y=5)
outs=[]
nid=100
for i in range(3000):
    add(d,f'f{i}','$_NOT_',A=5,Y=nid+i)
add(d,'x','$_XOR_',A=3,B=4,Y=6); 
run('fanout3000_k1',d,['--k','1','--cycles','2','--key','3','--goal-value','1'])
d=base(); prev=3
for i in range(1500): add(d,f'c{i}','$_NOT_',A=prev,Y=1000+i); prev=1000+i
d['modules']['t']['ports']['boot_word']['bits']=[prev,'0']
run('chain1500_k0',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
# duplicate JSON keys (cell defined twice)
raw='{"modules":{"t":{"ports":{"clk":{"direction":"input","bits":[2]},"sig":{"direction":"input","bits":[3,4]},"boot_word":{"direction":"output","bits":[5,6]}},"cells":{"g":{"type":"$_AND_","connections":{"A":[3],"B":[4],"Y":[5]}},"g":{"type":"$_OR_","connections":{"A":[3],"B":[4],"Y":[5]}},"z":{"type":"$_AND_","connections":{"A":[3],"B":["0"],"Y":[6]}}},"netnames":{}}}}'
run('dup_json_key_OR_last',None,['--k','0','--cycles','1','--key','3','--goal-value','1'],raw=raw)
# flop with Q also gate-driven
d=base(); add(d,'f','$_DFF_P_',C=2,D='1',Q=5); add(d,'g','$_AND_',A=3,B='0',Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('flopQ_and_gate_same_net',d,['--k','0','--cycles','3','--key','3','--goal-value','1'])
# init x / init len
d=base(); add(d,'f','$_DFF_P_',C=2,D=5,Q=5); d['modules']['t']['netnames']['q']=dict(bits=[5],attributes=dict(init='x')); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('init_x_selfloop',d,['--k','0','--cycles','3','--key','3','--goal-value','1'])
# missing netnames attributes
raw=json.dumps(dict(modules=dict(t=dict(ports=base()['modules']['t']['ports'],cells={},netnames={'a':dict(bits=[5])}))))
run('no_attributes_key',None,['--k','0','--cycles','1','--key','3','--goal-value','1'],raw=raw)
# input port also output (inout)
d=base(); d['modules']['t']['ports']['io']=dict(direction='inout',bits=[5]); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('inout_port',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
# multiple input ports besides sig (free per-run)
d=base(); d['modules']['t']['ports']['en']=dict(direction='input',bits=[9]); add(d,'g','$_AND_',A=3,B=9,Y=5); add(d,'z','$_AND_',A=3,B='0',Y=6)
run('extra_input_free',d,['--k','0','--cycles','1','--key','3','--goal-value','1'])
