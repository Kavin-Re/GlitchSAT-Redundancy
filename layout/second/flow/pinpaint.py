# Emit tcl that paints a metal rect (pin shape from DEF PINS) under every IO label so labels are not left on empty substrate
import re,sys
d=open(sys.argv[1]).read(); pins=d.split('\nPINS',1)[1].split('END PINS')[0]
out=[]
for m in re.finditer(r'\+ LAYER (\w+) \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)\s*\+ PLACED \( (-?\d+) (-?\d+) \)',pins):
    l,x1,y1,x2,y2,px,py=m.groups(); x1,y1,x2,y2,px,py=map(int,(x1,y1,x2,y2,px,py))
    f=lambda v: '%.3fum'%(v/1000.0)
    out.append(f"box {f(px+x1)} {f(py+y1)} {f(px+x2)} {f(py+y2)}; paint {l.replace('met','metal')}")
print('\n'.join(out))
