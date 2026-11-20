gds read out/ct_cmp.gds
load ct_cmp
select top cell
drc style drc(full)
drc check
drc catchup
drc listall why
quit
