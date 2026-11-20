import json, sys
exec(open('research/c6/int/apply_edits.py').read().split('# ---------- README')[0])
E[:] = json.load(open(ROOT/'research/c6/int/edits_log.json'))
NEWT = "So the answer depends on the exact netlist the tool produces. It is not a version effect (the spike netlist is also Yosys 0.33): the armed word 0xCC touches only 2 of the 3 copies, so encoding sets the floor at 2 and the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md). Always name the netlist hash and flow."
# revert template anchor (build.py TEXT_FIXES needs the original sentence), move the change into build.py's replacement text
p = ROOT/'dashboard/template.html'; t = p.read_text()
assert t.count(NEWT) == 1
p.write_text(t.replace(NEWT, "So the answer depends on the exact netlist the tool produces: always name the tool build."))
E[:] = [e for e in E if not (e['file'] == 'dashboard/template.html' and e['after'] == NEWT)]
rep('dashboard/build.py',
 "research/c3/rep/REP_REPORT.md): always name the tool build.'),",
 "research/c3/rep/REP_REPORT.md). It is not a version effect (the spike netlist is also Yosys 0.33): the armed word 0xCC touches only 2 of the 3 copies, so encoding sets the floor at 2 and the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md). Always name the netlist hash and flow.'),")
json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1); print(len(E))
