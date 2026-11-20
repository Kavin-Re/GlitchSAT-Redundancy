# DRC/LVS triage (ct_cmp, sky130_fd_sc_hd, 70 cells) - run 2026-11-19

Spike inputs were copied; the spike was not modified. Everything is in this directory (flow/, out/).

## Results

| check | tool | before | after | reason |
|---|---|---|---|---|
| Route DRC | OpenROAD detailed_route | 0 (empty rpt) | 0 (empty rpt) | tool says clean |
| Magic DRC, top cell | magic 8.3 drc(full) | 30 | 2 rule types, 12 boxes (li.3, li.c2, one spot near (24um,20um)) | see below |
| Magic DRC, std-cell definitions | magic | 3-24 per cell (inv_1 3 ... dfrtp_1 24) | unchanged | checking PDK cell GDS itself; not caused by this design; known deck/cell mismatch; NOT fixable here |
| LVS device count | netgen | 73 vs 74 | 514 vs 514 (flat transistors; N 249, P 257, special N 8) | tap cells and filler now ignored by the sky130A setup; flat compare |
| LVS net count | netgen | 154 vs 434 | 320 vs 326 MISMATCH | layout has 6 nets merged (below) |
| LVS result | netgen | no match | NO MATCH ("Top level cell failed pin matching") | residual short in layout/extraction |

## Magic DRC classification (before: 30 on top cell)
Rules fired and where (drc_why.tcl on the spike GDS: out/drc_spike.log):
- nwell.2a (19 boxes), n-well spacing < 1.27um: FALSE POSITIVE of the flow. Gaps between abutting cells in rows with no filler cells. Fixed by `filler_placement` (fill_1/2/4/8, decap_3/4).
- hvi.5 (28 boxes), HVI/nwell spacing: same cause (unfilled gaps), cleared by filler.
- nwell.4 (7) "nwell must contain metal-connected N+ taps" and LU.3 (13) "P-diff to N-tap < 15um": tap/PDN connectivity. Cleared by tapcell -distance 10 (19 taps instead of 13) and filler/decap plus connected PDN.
- After the fix only li.3 (0.17um) and li.c2 (0.14um) remain, 6 boxes each, one location around (24um, 20um): this is the li1 detour of net a[26] (li1 jog at x=24.08/24.15, y~19.5), i.e. a small real li1 spacing/notch issue that OpenROAD's router does not flag. Treat as REAL until the router is fixed or the li1 jog is removed.
- Per-cell counts (inv_1 3, dfrtp_1 24, ...) come from the PDK cell GDS under the magic deck. They are cell-library issues and do not count against the design.
Antenna and off-grid were not run here (not in drc(full) output); they were run later for V1 and V2, see `layout/verify/VERIFY.md`.

## Fixes
- pnr.tcl: `define_pdn_grid -name grid -starts_with POWER` (the old `-pins met5` gave "No shapes on layer met4" and left met4 PDN unbuilt); stripes pitch 20 / offset 6 for the 40um core; tapcell distance 10; filler_placement after detailed_route; `write_verilog -include_pwr_gnd`.
- gds.tcl: must run with `-rcfile .../sky130A.magicrc` (the spike's plain magic run without the rcfile is why `drc(full)` was not a known style in my first attempt). Adds VPWR/VGND labels on the met5 stripes (DEF special nets carry no labels), paints metal under each IO pin label (pinpaint.py), flatten + `extract all` + `ext2spice lvs`.
- LVS reference: v2spice.py converts the OpenROAD powered verilog into SPICE calling the PDK `sky130_fd_sc_hd.spice` subckts; netgen compares flat layout SPICE (ct_cmp_flat) with it using sky130A_setup.tcl.

## Commands (from layout/triage, PATH includes /tmp/mm_root/envs/eda/bin, PDK_ROOT=/tmp/mm_root/envs/eda/share/pdk)
    openroad -exit flow/pnr.tcl > out/pnr.log
    magic -dnull -noconsole -rcfile $PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc flow/gds.tcl > out/magic.log
    python3 flow/pinpaint.py out/ct_cmp.def > flow/pinpaint.tcl   # before magic
    python3 flow/v2spice.py out/ct_cmp_pnr.v out/ct_cmp_top.spice $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice
    cat <lib spice> out/ct_cmp_top.spice > out/ct_cmp_ref.spice
    bash flow/lvs.sh > out/lvs.log      # report out/lvs.rpt

## What remains
(Update: the a[26] short was later traced to filler cells placed over a routed li1 wire; see `layout/verify/VERIFY.md` section 3. The text below is the state when this file was written.)
1. LVS NOT matching. Devices match (514/514) but magic reports `FILLER_10_68.VNB`, `VGND`, `a[26]`, `b[0]` as electrically shorted; netgen shows nets a[26], b[0], _026_, _053_, _055_ and VGND merged in the layout (6 fewer nets). With the met2/met3 PDN via pads removed, only a[26] stayed shorted to substrate, so a[26] (and b[0]) touching the ground/substrate net looks like a real or DEF-import artifact, not yet located. Next step: in magic `select`/`what` on the a[26] net around its li1/met1 route (li1 at x=24.08..24.15, y 16.8..19.9 crosses the VGND met1 rail at y=19.04) and check DEF-to-magic via/licon import; also try `extract unique` or reading the std cells from the PDK .mag (libs.ref/.../mag) instead of GDS.
2. VPWR/VGND top-level pins were also not matched (layout lacks them as ports because of the merge).
3. Remaining DRC li.3/li.c2 at one spot (above).
Not claimed: DRC clean, LVS clean.
