import klayout.db as db
ly=db.Layout(); ly.read("/home/user/project/layout/triage/out/ct_cmp.gds")
top=ly.top_cell()
box=db.Box(23000,16500,25500,20300)
for name,(l,d) in {"li1":(67,20),"mcon":(67,44),"met1":(68,20),"via":(68,44)}.items():
    li=ly.layer(l,d)
    r=db.Region(top.begin_shapes_rec(li)).merged()
    sub=r & db.Region(box)
    print(name)
    for p in r.interacting(db.Region(box)).each(): 
        print("  poly bbox",p.bbox(), "area",p.area())
