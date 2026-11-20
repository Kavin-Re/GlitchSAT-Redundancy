import json
def nl(ports, cells, names=None):
    return dict(creator="x", modules=dict(t=dict(ports=ports, cells=cells, netnames=names or {})))
def P(d, bits): return dict(direction=d, bits=bits)
# A: output = input (no gates, no flops); sig 2 bits, boot_word 2 bits = sig
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',[3,4])},{}), open('a_passthru.json','w'))
# B: constant outputs: boot_word = 0b10 constant
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',['0','1'])},{}), open('b_const.json','w'))
# C: no flops, gate: out0 = sig0 & sig1, out1 = ~sig0
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',[5,6])},
 {'g0':dict(type='$_AND_',connections=dict(A=[3],B=[4],Y=[5])),'g1':dict(type='$_NOT_',connections=dict(A=[3],Y=[6]))}), open('c_gates.json','w'))
# D: buffer cells ($_BUF_)
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',[5,6])},
 {'g0':dict(type='$_BUF_',connections=dict(A=[3],Y=[5])),'g1':dict(type='$_BUF_',connections=dict(A=[4],Y=[6]))}), open('d_buf.json','w'))
# E: one flop, no init attr, D=sig0, out = {q, ~q}
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',[5,6])},
 {'f':dict(type='$_DFF_P_',connections=dict(C=[2],D=[3],Q=[5])),'g1':dict(type='$_NOT_',connections=dict(A=[5],Y=[6]))},
 {'q':dict(bits=[5],attributes={})}), open('e_flop_noinit.json','w'))
# F: same with init attr
d=json.load(open('e_flop_noinit.json')); d['modules']['t']['netnames']['q']['attributes']={'init':'1'}; json.dump(d,open('f_flop_init1.json','w'))
# G: hostile names
cells={'g0':dict(type='$_AND_',connections=dict(A=[3],B=[4],Y=[5])),'g1':dict(type='$_NOT_',connections=dict(A=[3],Y=[6]))}
bad = "n</script><img src=x onerror=alert(1)>\"'&amp;]]>--\x01\x1f‮ ${jndi:x}%s\n../../etc/passwd"
json.dump(nl({'clk':P('input',[2]),'sig':P('input',[3,4]),'boot_word':P('output',[5,6])},cells,{bad:dict(bits=[5],attributes={}),bad+"2":dict(bits=[6],attributes={})}), open('g_hostile.json','w'))
