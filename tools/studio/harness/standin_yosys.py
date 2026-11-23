#!/usr/bin/env python3
"""STAND-IN for the yosys program (plumbing tests only): copies a stored Yosys 0.33 netlist to ./netlist.json."""
import os, shutil, sys, time
REAL = os.environ.get('GS_STANDIN_REAL') or open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_standin_real')).read().strip()   # set by make_overlay
if '-V' in sys.argv: print('Yosys 0.33 (git sha1 STAND-IN, plumbing test)'); sys.exit(0)
time.sleep(float(os.environ.get('STANDIN_YOSYS_SLEEP', '0.02')))
txt = open('design.v').read() if os.path.exists('design.v') else ''
scr = open('flow.ys').read() if os.path.exists('flow.ys') else ' '.join(sys.argv)
if 'opt_merge' in scr: src = 'research/c2/e2_variance/baseline_netlists/conda-eda0.38_v2.json'   # a different circuit, so merge builds get another hash
elif 'module v2e' in txt: src = 'research/c6/p01/netlists/nl_apt_v2e.json'
else: src = 'research/c6/p01/netlists/nl_apt_v2.json'
if 'abc -dff' in scr: print('ERROR: stand-in: abc -dff failed', file=sys.stderr); sys.exit(1)
shutil.copy(os.path.join(REAL, src), 'netlist.json')
