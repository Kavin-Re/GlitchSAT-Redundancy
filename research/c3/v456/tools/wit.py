import sys,json; sys.path.insert(0,'/tmp/work_v456')
import gs
def run(design,net,goal='word',idx=0):
    nl=gs.Netlist(f'/tmp/work_v456/nl/{design}_{net}.json',design); m=nl.m
    names={n:x['bits'] for n,x in m['netnames'].items() if n in('st','sig','boot_ok')}
    rows=[r for r in json.load(open('/tmp/work_v456/all_rows.json')) if r['design']==design and r['netlist']==net and r['goal']==goal and not r['input_sites'] and r['init']=='known']
    faults=rows[0]['faults']; fl={(n,t) for n,t in faults}
    nb={nl.names.get(b,str(b)):b for b in list(nl.drivers)+list(nl.qs)}
    fb={(nb[n],t) for n,t in faults}
    def sim(sig):
        state=dict(nl.init); out=[]
        for t in range(6):
            val={}
            def get(b):
                if b in('0','x','z'):return False
                if b=='1':return True
                if b in val:return val[b]
                if b in names['sig']: v=bool((sig>>names['sig'].index(b))&1)
                elif b in state: v=state[b]
                else:
                    _,ty,con=nl.drivers[b]; g=lambda p:get(con[p][0])
                    v={'$_AND_':lambda:g('A') and g('B'),'$_OR_':lambda:g('A') or g('B'),'$_XOR_':lambda:g('A')!=g('B'),'$_NOT_':lambda:not g('A'),'$_MUX_':lambda:g('B') if g('S') else g('A')}[ty]()
                if (b,t) in fb: v=not v
                val[b]=v; return v
            out.append(sum(int(state[b])<<i for i,b in enumerate(names['st'])))
            state={q:get(d) for q,d in nl.dq.items()}
        return out
    for s in range(256):
        o=sim(s)
        if 0x96 in o and s!=0xC3: print(design,net,faults,'sig',hex(s),[hex(x) for x in o]); return
    print('no sig reproduces',design,net,faults)
if __name__=='__main__':
    for d in sys.argv[1].split(','):
        for n in sys.argv[2].split(','): run(d,n)
