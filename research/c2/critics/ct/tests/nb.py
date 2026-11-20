import json
class NB:
    def __init__(s): s.n=1; s.cells={}; s.ports={}; s.names={}; s.init={}
    def net(s): s.n+=1; return s.n
    def inp(s,name,w): b=[s.net() for _ in range(w)]; s.ports[name]=dict(direction='input',bits=b); return b
    def gate(s,t,**pins):
        y=s.net(); con={k:[v] for k,v in pins.items()}; con['Y']=[y]; s.cells[f'g{y}']=dict(type='$_'+t+'_',connections=con); return y
    def dff(s,d,init=0):
        q=s.net(); s.cells[f'f{q}']=dict(type='$_DFF_P_',connections=dict(D=[d],Q=[q],C=[s.clk])); 
        if init: s.init[q]=1
        return q
    def dffq(s):  # allocate q first for feedback
        q=s.net(); return q
    def dffat(s,q,d,init=0):
        s.cells[f'f{q}']=dict(type='$_DFF_P_',connections=dict(D=[d],Q=[q],C=[s.clk]))
        if init: s.init[q]=1
    def out(s,name,bits): s.ports[name]=dict(direction='output',bits=bits)
    def save(s,path,top='t'):
        nn={}
        for q,v in s.init.items(): nn[f'q{q}']=dict(bits=[q],attributes=dict(init='1'))
        json.dump(dict(creator='ct',modules={top:dict(ports=s.ports,cells=s.cells,netnames=nn)}),open(path,'w'))
def base():
    b=NB(); b.clk=b.inp('clk',1)[0]; b.sig=b.inp('sig',8); return b
