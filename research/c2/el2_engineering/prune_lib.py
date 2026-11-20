# Make /tmp/work_el2/lib/pruned.lib for apt Yosys 0.33 (its abc has no -dont_use): drop lpflow/probe/scan/enable/latch/etc cells.
import re
t=open('/tmp/work_el2/lib/sky130_fd_sc_hd__tt_025C_1v80.lib').read()
idx=[(m.start(),m.group(1)) for m in re.finditer(r'\n\s*cell \("([^"]+)"\)',t)]
out=[t[:idx[0][0]]]
for i,(s,n) in enumerate(idx):
    e=idx[i+1][0] if i+1<len(idx) else len(t)
    if re.search(r'lpflow|probe|sdf|sedf|edf|dlx|dlr|dls|dlclk|sdlclk|ebuf|einv|diode|fill|decap|tap',n): continue
    out.append(t[s:e])
body=''.join(out)
if not body.rstrip().endswith('}'): body+='\n}\n'
open('/tmp/work_el2/lib/pruned.lib','w').write(body)
