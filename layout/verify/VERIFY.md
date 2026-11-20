# Layout verification - 2026-11-19 (MEASURED unless marked)

Tools: OpenROAD f12e2f47 (check_antennas), magic 8.3.464 (sky130A.magicrc, drc(full)), netgen 1.5.272, klayout 0.30.13 (PyPI). Inputs: layout/v_designs/out_patched (read only).

## 1. Antenna and manufacturing grid (V1, V2)
| check | V1 | V2 | how |
|---|---|---|---|
| OpenROAD `check_antennas` on v?_routed.odb | 0 pin viol, 0 net viol in 47 nets | 0 pin viol, 0 net viol in 48 nets | ant/v1.log, v2.log, reports ant/v?_ant.rpt |
| Manufacturing grid (tech: 5 dbu = 5 nm, 1000 dbu/um): instance origins in ODB | 0 of 76 off-grid | 0 of 72 off-grid | ant/v?.tcl |
| Off-grid, GDS: every polygon vertex of top cell (1870 / 1937 shapes) and of all cell definitions (2112 / 2049 shapes) | 0 off-grid | 0 off-grid | klayout, ant/grid.py, grid.txt |
| Off-grid, routed wire shapes in ODB | NOT run in OpenROAD: this build has no `odb::dbWireShapeItr` (error in v1.log). Covered instead by the GDS check, which is generated from the same routing. | same | |

Verdict: antenna rule check reports no violations (note: "CORE ANTENNACELL not found" warning, so no diode cells exist; the tool still found nothing to fix). No off-grid geometry found. Scope limits: antenna uses the PDK rules in the OpenROAD/LEF tech; this is not a foundry signoff.

## 2. Why magic reports errors in standard-cell definitions
Single PDK cells loaded alone from sky130_fd_sc_hd.gds and run through the same drc(full): cell/allcells.txt (29 cells used by V1/V2/triage). Every cell with logic reports ONLY three rules: nwell.4 (2 boxes), LU.3 (P-diff to N-tap < 15um) and LU.2 (N-diff to P-tap < 15um); fill_1/2/4/8 only nwell.4; the tap cell reports nothing. e.g. dfxtp_1 alone: nwell.4 x2, LU.3 x17, LU.2 x20 (box counts per rule; magic's own total for the cell is 21, difference not investigated).
Context test (cell/ctx.mag, ctx3.tcl): tap + dfxtp_1 + tap placed in a row, flattened: DRC list EMPTY. The same dfxtp_1 alone still shows its 3 rules.
Conclusion: these are NOT geometry errors in the cells. nwell.4 and the latch-up rules LU.2/LU.3 are rules that need a tap in the neighbourhood; a standard cell is designed to rely on tap cells placed by the flow, and magic checks each cell definition in isolation. They are context-dependent false positives of the deck when checking cell definitions standalone. Evidence is the one-cell-plus-taps test and that the full designs list nothing on the top cell. Scope: tested on dfxtp_1 context; other cells show the same rule set but were not each re-tested in context. The hierarchical count in `drc listall count` still lists cell names, so it is correct to say "magic does not print 'clean' for the whole hierarchy", while the top cell is empty.

## 3. Triage design a[26] short (15 min, layout/verify/a26/)
Reproduced: magic "Ports FILLER_10_68.VNB and a[26] are electrically shorted".
Root cause (found, real): the detailed router routes an li1 wire for a[26] at x=23.995-24.165, y=18.615-19.465 across the row boundary y=19.04. `filler_placement` ran AFTER routing; the LEF of fill/decap cells has only a met1 rail, but their GDS has li1 rails with mcon to VGND (fill_1 FILLER_3_34 at 23.92,16.32 and decap_3 FILLER_4_32 at 23.0,19.04). OpenROAD cannot see that li1 and placed the fillers on top of the routed li1 wire, shorting a[26] to VGND. So: a real flow bug (fill inserted over routed li1), not a magic import artifact.
Workaround tried: removed the 8 fillers whose li1 rail overlaps a routed li1 wire (conf.py, bad.txt: FILLER_0_40, 0_67, 1_13, 1_65, 2_10, 3_30, 3_34, 4_32) from a copy of routed.odb and re-ran magic extract and netgen: no "electrically shorted" warning; netgen "Circuits match uniquely", 514/514 devices, 326/326 nets, pin lists equivalent (a26/out/lvs.rpt).
Cost: top-cell magic DRC now lists li.3 x12 (unchanged residual li1 spacing), nwell.2a x3, hvi.5 x5, nwell.4 x1 (gaps where fillers were removed). So LVS matches but DRC is NOT clean; this is a workaround, not a fix. Proper fix (not done, out of my folder): keep li1 off row boundaries (route met1+ only for signals) or re-route with filler cells placed first, or swap each conflicting filler for one without li1 rail overlap. The li.3 spot remains real.

## 4. Rebuild test of scripts/setup_layout_tools.sh
The micromamba create into a fresh MAMBA_ROOT_PREFIX=/tmp/mm_root2 (litex-hub + conda-forge) finished with exit 0, 6m36s, about 11 GB. Then flow_patched for V1 (copy in rebuild/, paths sed'ed /tmp/mm_root -> /tmp/mm_root2): total 20.8 s (synth 1.4 s, pnr 14.8 s).
Results equal the original: route DRC report empty, setup/hold slack +7.050/+0.519, netgen "Circuits match uniquely" 422/422 devices, 225/225 nets, routed ODB byte-identical, GDS XOR 0 polygons. Same OpenROAD commit and magic 8.3.464 as the working env.
Problems found: (a) flow_patched scripts hard-code /tmp/mm_root, so the script's MAMBA_ROOT_PREFIX override breaks the flow (I had to sed a copy); (b) the micromamba download branch and the pip step were not exercised (binary and klayout/z3 already present); (c) no self-check; (d) the extraction of open_pdks.sky130a is single-core and takes minutes of the 6.5. Corrected copy: setup_layout_tools_fixed.sh (syntax checked; its install part is the same command that ran; the symlink and self-check lines were not executed). /tmp/mm_root2 deleted afterwards; /tmp/mm_root untouched.

## 5. Before / after
| item | before | after (this verification) |
|---|---|---|
| V1/V2 antenna | not run | check_antennas: 0 violations both |
| V1/V2 manufacturing grid | not run | 0 off-grid (ODB instances, all GDS shapes) |
| Errors in std-cell definitions | unexplained | explained: tap-dependent rules (nwell.4, LU.2, LU.3) on isolated cells; clean in tap context (one cell tested) |
| Whole-GDS DRC "clean" claim | not claimed | still not claimed: magic lists per-cell-definition rules; top cell empty |
| triage a[26] short | unresolved | cause found (filler over routed li1); LVS matches after removing 8 fillers; DRC gets nwell/hvi gaps; li.3 x12 remain |
| setup script | never re-run | re-run OK, 6m36s; fixed copy written |
| LVS/DRC of V1 flow after rebuild | - | identical to original |
