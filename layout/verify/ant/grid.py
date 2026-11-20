import sys, klayout.db as db
for d in ("v1","v2"):
    ly=db.Layout(); ly.read(f"/home/user/project/layout/v_designs/out_patched/{d}.gds")
    top=ly.top_cell(); dbu=ly.dbu
    step=round(0.005/dbu)  # 5nm mfg grid in dbu
    res={}
    for name,cells in (("flat-all-shapes",None),):
        pass
    # per-cell: top cell own shapes vs library cells
    def check(cell):
        tot=bad=0
        for li in ly.layer_indexes():
            for sh in cell.shapes(li).each():
                pts=[]
                if sh.is_polygon() or sh.is_box() or sh.is_path():
                    p=sh.polygon if not sh.is_path() else sh.path.polygon()
                    pts=[(pt.x,pt.y) for pt in p.each_point_hull()]
                    for h in range(p.holes()): pts+=[(pt.x,pt.y) for pt in p.each_point_hole(h)]
                tot+=1
                if any(x%step or y%step for x,y in pts): bad+=1
        return tot,bad
    tt,tb=check(top)
    ct=cb=0; badcells={}
    for c in ly.each_cell():
        if c.cell_index()==top.cell_index(): continue
        t,b=check(c); ct+=t; cb+=b
        if b: badcells[c.name]=b
    # instance placement offgrid in top
    ib=sum(1 for i in top.each_inst() if (i.trans.disp.x%step or i.trans.disp.y%step))
    print(f"{d}: dbu={dbu} grid_step_dbu={step} top shapes={tt} offgrid={tb}; cell-def shapes={ct} offgrid={cb} cells_with_offgrid={len(badcells)} {list(badcells.items())[:5]}; top insts offgrid={ib}/{top.child_instances()}")
