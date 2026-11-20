#!/usr/bin/env python3
"""cell -> (master, x, y lower-left um, centre, size, orient, status, row, VPWR rail y, VGND rail y) CSV from a stored DEF.
usage: extract_coords.py   (writes coords/<var>_placement.csv for every def/<var>.def). Needs only python3."""
import os, sys, csv, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'code'))
os.environ.setdefault('LEF', os.path.join(HERE, 'lef', 'sky130_fd_sc_hd_sizes_only.lef'))
import layout_extract as le
sz = le.lef_sizes()
for p in sorted(glob.glob(os.path.join(HERE, 'def', '*.def'))):
    v = os.path.basename(p)[:-4]; D = le.parse_def(p)
    rows = {round(y, 3): (int(n.split('_')[1]), o) for n, x, y, o in D['rows']}
    with open(os.path.join(HERE, 'coords', f'{v}_placement.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['cell', 'master', 'x_um', 'y_um', 'cx_um', 'cy_um', 'w_um', 'h_um', 'orient', 'status', 'row', 'vpwr_rail_y_um', 'vgnd_rail_y_um'])
        for k, c in sorted(D['comps'].items()):
            W, H = sz[c['master']]; r = rows.get(round(c['y'], 3), (None, 'N')); top, bot = c['y'] + 2.72, c['y']
            w.writerow([k, c['master'], c['x'], c['y'], round(c['x'] + W / 2, 3), round(c['y'] + H / 2, 3), W, H, c['orient'], c['status'], r[0],
                        round(top if r[1] == 'N' else bot, 3), round(bot if r[1] == 'N' else top, 3)])
    print(v, len(D['comps']), 'components')
