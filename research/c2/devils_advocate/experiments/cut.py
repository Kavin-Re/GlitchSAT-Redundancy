import sys,glob,os,collections;sys.path.insert(0,'scripts')
import glitchsat as g
INF=10**6
def mincut(nl):
    cap=collections.defaultdict(lambda:collections.defaultdict(int))
    def add(u,v,c): cap[u][v]+=c; cap[v][u]+=0
    sig=nl.ports['sig']['bits']; goal=nl.ports['boot_word']['bits']
    nets=set(nl.drivers)|set(nl.qs)
    for b in nets: add(('i',b),('o',b),1)
    for b in sig: add('S',('o',b),INF)
    for b,(cn,t,con) in nl.drivers.items():
        for p,v in con.items():
            if p!='Y' and isinstance(v[0],int): add(('o',v[0]),('i',b),INF)
    for _,d,q in nl.dffs: add(('o',d),('i',q),INF)
    for b in goal:
        if isinstance(b,int): add(('o',b),'T',INF)
    flow=0
    while True:
        par={'S':None};dq=collections.deque(['S'])
        while dq and 'T' not in par:
            u=dq.popleft()
            for v,c in cap[u].items():
                if c>0 and v not in par: par[v]=u;dq.append(v)
        if 'T' not in par: return flow
        v='T'
        while par[v] is not None:
            u=par[v];cap[u][v]-=1;cap[v][u]+=1;v=u
        flow+=1
if __name__=='__main__':
    for p in sys.argv[1:]:
        d=os.path.basename(p)[:2]; nl=g.Netlist(p,d)
        print(os.path.basename(p),'structural_min_vertex_cut',mincut(nl))
