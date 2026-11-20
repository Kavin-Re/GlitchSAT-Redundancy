import klayout.db as db
ly=db.Layout(); ly.read("layout/triage/out/ct_cmp.gds")
top=ly.top_cell()
li1=ly.layer(67,20); mcon=ly.layer(67,44)
pt=db.Box(24100,18900,24200,19200)
for inst in top.each_inst():
    bb=inst.bbox()
    if bb.overlaps(db.Box(24000,16800,24300,19900)):
        print(inst.cell.name, bb, inst.trans)
# list top-level shapes (routing) li1 near
for sh in top.shapes(li1).each():
    if sh.bbox().overlaps(pt): print("TOP li1",sh.bbox())
for sh in top.shapes(mcon).each():
    if sh.bbox().overlaps(pt): print("TOP mcon",sh.bbox())
