import klayout.db as db
ly=db.Layout(); ly.read("/home/user/project/layout/triage/out/ct_cmp.gds")
li1=ly.layer(67,20); mcon=ly.layer(67,44)
for n in ("sky130_fd_sc_hd__fill_1","sky130_fd_sc_hd__decap_3"):
    c=ly.cell(n); print(n,c.bbox())
    for L,nm in ((li1,"li1"),(mcon,"mcon")):
        for sh in c.shapes(L).each(): print(" ",nm,sh.bbox())
