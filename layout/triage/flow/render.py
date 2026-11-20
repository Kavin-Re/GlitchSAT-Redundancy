import klayout.lay as lay, glob, sys
lyp=sys.argv[1]
v=lay.LayoutView(); v.load_layout("out/ct_cmp.gds",True)
v.load_layer_props(lyp)
v.max_hier(); v.set_config("background-color","#101018"); v.set_config("grid-visible","false")
v.zoom_fit(); v.save_image("out/ct_cmp_full.png",2400,2400)
print("ok")
