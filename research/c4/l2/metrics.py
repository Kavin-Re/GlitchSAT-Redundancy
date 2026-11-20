#!/usr/bin/env python3
"""MEASURED geometry of the three compare copies from a placed DEF. usage: metrics.py VAR"""
import sys, json, math, itertools, re
sys.path.insert(0,'/tmp/work_l2/lay/code')
import layout_extract as le
from geom_report import mec
V=sys.argv[1]; D=le.parse_def(f'/tmp/work_l2/out_{V}/v2.def'); sz=le.lef_sizes()
C={}
for k,c in D['comps'].items():
    w,h=sz[c['master']]; C[k]=dict(c,w=w,h=h,cx=c['x']+w/2,cy=c['y']+h/2)
rows=D['rows']; rowinfo={}
for n,x,y,o in rows:
    r=int(n.split('_')[1]); top,bot=y+2.72,y; rowinfo[round(y,3)]=dict(row=r,orient=o,vpwr=top if o=='N' else bot,vgnd=bot if o=='N' else top)
sp=D['special']
met4={n:sorted({s['x1'] for s in v['segs'] if s['layer']=='met4' and s['shape']=='STRIPE'}) for n,v in sp.items()}
met5={n:sorted({s['y1'] for s in v['segs'] if s['layer']=='met5' and s['shape']=='STRIPE'}) for n,v in sp.items()}
taps=[c for c in C.values() if 'tapvpwr' in c['master']]
cp={f'c{i}':[f'c{i}/{n}' for n in ('_2_','_3_','_4_')] for i in range(3)}
info={}
for k in sum(cp.values(),[]):
    c=C[k]; ri=rowinfo[round(c['y'],3)]
    tdist=sorted((math.hypot(c['cx']-t['cx'],c['cy']-t['cy']),) for t in taps)[0][0]
    # which met4 VPWR / VGND strap is nearest in x
    nv=min(met4['VPWR'],key=lambda x:abs(x-c['cx'])); ng=min(met4['VGND'],key=lambda x:abs(x-c['cx']))
    info[k]=dict(master=c['master'].replace('sky130_fd_sc_hd__',''),x=c['x'],y=c['y'],w=c['w'],cx=round(c['cx'],3),cy=round(c['cy'],3),row=ri['row'],vpwr_rail_y=ri['vpwr'],vgnd_rail_y=ri['vgnd'],nearest_tap_um=round(tdist,2),nearest_met4_vpwr_x=nv,nearest_met4_vgnd_x=ng)
def gap(a,b):  # bbox edge-to-edge gap
    dx=max(a['x']-(b['x']+b['w']),b['x']-(a['x']+a['w']),0); dy=max(a['y']-(b['y']+2.72),b['y']-(a['y']+2.72),0); return math.hypot(dx,dy)
cd=lambda a,b: math.hypot(C[a]['cx']-C[b]['cx'],C[a]['cy']-C[b]['cy'])
pair={}
for a,b in itertools.combinations(cp,2):
    pair[f'{a}-{b}']=dict(min_centre_um=round(min(cd(x,y) for x in cp[a] for y in cp[b]),2),min_bbox_gap_um=round(min(gap(C[x],C[y]) for x in cp[a] for y in cp[b]),2))
tri=[]
for combo in itertools.product(*cp.values()):
    r,cen=mec([(C[k]['cx'],C[k]['cy']) for k in combo]); tri.append((round(r,3),combo))
tri.sort(); 
allc=[C[k] for k in C if 'tapvpwr' not in C[k]['master'] and not re.search('fill|decap',C[k]['master'])]
logic=[k for k,c in C.items() if not re.search('tapvpwr|fill|decap|clkbuf',c['master'])]
xs=[C[k]['x'] for k in logic]+[C[k]['x']+C[k]['w'] for k in logic]; ys=[C[k]['y'] for k in logic]+[C[k]['y']+2.72 for k in logic]
b=lambda a,b_:b_
# bbox of one cell from each copy for the min-radius triple
best=tri[0]; bb=[min(C[k]['x'] for k in best[1]),min(C[k]['y'] for k in best[1]),max(C[k]['x']+C[k]['w'] for k in best[1]),max(C[k]['y']+2.72 for k in best[1])]
out=dict(var=V,die=D['die'],n_logic_cells=len(logic),n_rows=len(rows),n_taps=len(taps),n_met4_vpwr=len(met4['VPWR']),met4_vpwr_x=met4['VPWR'],met4_vgnd_x=met4['VGND'],met5_vpwr_y=met5['VPWR'],met5_vgnd_y=met5['VGND'],
 cells=info,pairwise_copy_distance=pair,min_pairwise_centre_um=min(p['min_centre_um'] for p in pair.values()),min_pairwise_bbox_gap_um=min(p['min_bbox_gap_um'] for p in pair.values()),
 min_triple_mec_r_um=best[0],min_triple=best[1],min_triple_bbox_w_h=[round(bb[2]-bb[0],2),round(bb[3]-bb[1],2)],
 min_triple_rows=sorted({info[k]['row'] for k in best[1]}),min_triple_vpwr=sorted({info[k]['vpwr_rail_y'] for k in best[1]}),min_triple_vgnd=sorted({info[k]['vgnd_rail_y'] for k in best[1]}),
 max_triple_mec_r_um=tri[-1][0],
 copy_rows={c:sorted({info[k]['row'] for k in v}) for c,v in cp.items()},copy_vpwr={c:sorted({info[k]['vpwr_rail_y'] for k in v}) for c,v in cp.items()},copy_vgnd={c:sorted({info[k]['vgnd_rail_y'] for k in v}) for c,v in cp.items()},
 copy_met4_vpwr={c:sorted({info[k]['nearest_met4_vpwr_x'] for k in v}) for c,v in cp.items()})
# does any single VPWR rail (y) hold cells of >=1 each of all 3 copies (a sufficient set on one rail)?
def rail_has_all(key): 
    ys=[set(info[k][key] for k in v) for v in cp.values()]; return sorted(set.intersection(*ys))
out['vpwr_rails_with_all_three_copies']=rail_has_all('vpwr_rail_y'); out['vgnd_rails_with_all_three_copies']=rail_has_all('vgnd_rail_y')
json.dump(out,open(f'/tmp/work_l2/metrics_{V}.json','w'),indent=1)
print(json.dumps({k:out[k] for k in out if k not in('cells','met4_vpwr_x','met4_vgnd_x')},indent=0))
