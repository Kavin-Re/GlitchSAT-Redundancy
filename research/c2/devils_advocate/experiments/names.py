import sys,json;sys.path.insert(0,'scripts')
import glitchsat as g
cases={('v2','plain'):[(0,67),(2,51)],('v2','opt'):[(0,51),(0,67)],('v1','plain'):[(1,46)],('v1','opt'):[(1,26)]}
for (d,fl),fs in cases.items():
    nl=g.Netlist(f'../x1/{d}_{fl}.json',d)
    print(d,fl)
    # fanout count
    fo={}
    for b,(cn,t,con) in nl.drivers.items():
        for p,v in con.items():
            if p!='Y':
                fo[v[0]]=fo.get(v[0],0)+1
    for _,dd,q in nl.dffs: fo[dd]=fo.get(dd,0)+1
    for t,b in fs:
        drv=nl.drivers.get(b)
        print('  cycle',t,'net',b,nl.names.get(b),'type',drv[1] if drv else 'FLOP/INPUT','fanout',fo.get(b,0))
