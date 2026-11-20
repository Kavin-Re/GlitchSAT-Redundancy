#!/usr/bin/env python3
"""Geometry facts from layout_geometry_<d>.json (MEASURED DEF coordinates, LEF cell sizes).
Writes geom_<d>.json. Cell position = cell centre; 'box' versions use the cell rectangle (disc touches the rectangle)."""
import json, math, itertools, sys
def mec(pts):
    best = None
    cands = [((a[0]+b[0])/2, (a[1]+b[1])/2) for a, b in itertools.combinations(pts, 2)]
    for a, b, c in itertools.combinations(pts, 3):
        d = 2*(a[0]*(b[1]-c[1])+b[0]*(c[1]-a[1])+c[0]*(a[1]-b[1]))
        if abs(d) < 1e-9: continue
        ux = ((a[0]**2+a[1]**2)*(b[1]-c[1])+(b[0]**2+b[1]**2)*(c[1]-a[1])+(c[0]**2+c[1]**2)*(a[1]-b[1]))/d
        uy = ((a[0]**2+a[1]**2)*(c[0]-b[0])+(b[0]**2+b[1]**2)*(a[0]-c[0])+(c[0]**2+c[1]**2)*(b[0]-a[0]))/d
        cands.append((ux, uy))
    if len(pts) == 1: cands = [pts[0]]
    for c in cands:
        r = max(math.hypot(c[0]-p[0], c[1]-p[1]) for p in pts)
        if best is None or r < best[0] - 1e-12: best = (r, c)
    return best
def box_radius(boxes):
    # min over centre p of max distance from p to rectangles (disc touches every rectangle); grid + refine
    f = lambda p: max(math.hypot(max(b[0]-p[0], 0, p[0]-b[2]), max(b[1]-p[1], 0, p[1]-b[3])) for b in boxes)
    xs = [b[0] for b in boxes]+[b[2] for b in boxes]; ys = [b[1] for b in boxes]+[b[3] for b in boxes]
    best = (1e9, None); step = 0.2
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            v = f((x, y))
            if v < best[0]: best = (v, (x, y))
            y += step
        x += step
    c = best[1]; step = 0.1
    for _ in range(40):
        imp = False
        for dx, dy in ((step,0),(-step,0),(0,step),(0,-step)):
            q = (c[0]+dx, c[1]+dy)
            if f(q) < f(c) - 1e-9: c = q; imp = True
        if not imp: step /= 2
    return f(c), c
def main(ds):
  for d in ds:
      G = json.load(open(f'layout_geometry_{d}.json')); C = G['cells']
      box = lambda k: (C[k]['x'], C[k]['y'], C[k]['x']+C[k]['w'], C[k]['y']+C[k]['h'])
      ctr = lambda k: (C[k]['cx'], C[k]['cy'])
      cp = sorted(G['copies'])
      out = dict(design=d, label='MEASURED geometry (DEF + LEF); radius results are for disc centres chosen optimally per triple', copies=G['copies'], triples=[])
      for combo in itertools.product(*[G['copies'][c] for c in cp]):
          pts = [ctr(k) for k in combo]; r, c = mec(pts); rb, cb = box_radius([box(k) for k in combo])
          bx = (min(box(k)[0] for k in combo), min(box(k)[1] for k in combo), max(box(k)[2] for k in combo), max(box(k)[3] for k in combo))
          w, h = bx[2]-bx[0], bx[3]-bx[1]
          inside_c = [k for k in C if math.hypot(C[k]['cx']-c[0], C[k]['cy']-c[1]) <= r+1e-9 and k not in combo]
          inside_b = [k for k in C if bx[0]-1e-9 <= C[k]['cx'] <= bx[2]+1e-9 and bx[1]-1e-9 <= C[k]['cy'] <= bx[3]+1e-9 and k not in combo]
          rows = sorted({C[k]['row'] for k in combo}); vp = sorted({C[k]['vpwr_y'] for k in combo}); vg = sorted({C[k]['vgnd_y'] for k in combo})
          out['triples'].append(dict(cells=list(combo), r_centres_um=round(r, 3), centre=[round(c[0], 3), round(c[1], 3)], r_boxes_um=round(rb, 3),
              bbox_um=[round(v, 3) for v in bx], bbox_w_h_um=[round(w, 3), round(h, 3)], bbox_area_um2=round(w*h, 3),
              rows=rows, vpwr_rails=vp, vgnd_rails=vg, others_in_circle=len(inside_c), others_in_circle_flops=sum(C[k]['kind'] == 'flop' for k in inside_c),
              others_in_bbox=len(inside_b), others_in_bbox_flops=sum(C[k]['kind'] == 'flop' for k in inside_b),
              nearest_tap_um=[C[k]['tap_nearest'][1] for k in combo], tap_same_row_um=[C[k]['tap_same_row'][1] for k in combo],
              tap_same_vpwr_rail_um=[C[k]['tap_same_vpwr_rail'][1] for k in combo]))
      json.dump(out, open(f'geom_{d}.json', 'w'), indent=1)
      ts = sorted(out['triples'], key=lambda t: t['r_centres_um'])
      print(d, 'min-radius triples (centres):'); [print('  ', t['cells'], t['r_centres_um'], 'box r', t['r_boxes_um'], 'bbox', t['bbox_w_h_um'], 'others', t['others_in_circle'], t['others_in_bbox'], 'rows', t['rows']) for t in ts[:4]]
      print('  max', ts[-1]['r_centres_um'])

if __name__ == '__main__': main(sys.argv[1:] or ['v1', 'v2'])
