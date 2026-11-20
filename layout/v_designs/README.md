# v_designs: V1 and V2 through a real open-source RTL-to-GDS flow (sky130_fd_sc_hd)

Reproduce (from this directory): `flow/all.sh` (needs micromamba env `eda`: openroad, magic, netgen, yosys 0.38, open_pdks.sky130a; `pip install klayout pillow`).
Steps per design D in {v1,v2}: `flow/run.sh D` (yosys synth without flatten, so `(* keep_hierarchy *) cmp8` copies stay; abc/dfflibmap to sky130_fd_sc_hd; OpenROAD floorplan util 60%, place density 0.9, CTS, repair_timing, global+detailed route, STA), then magic (`flow/gds.tcl`: DEF->GDS, DRC, extract), netgen (`flow/lvs.sh`), `flow/render.py D` (klayout PNGs + ANNOTATION overlays). RTL in `rtl/` is a copy of /home/user/project/rtl.

## MEASURED (this run, 2026-11-19)
| | v1 | v2 |
|---|---|---|
| yosys cells (stat, incl. 2 resp. 3 cmp8 instances) | 35 | 36 |
| yosys chip area um^2 | 357.8 | 362.8 |
| cmp8 copies survived synthesis | yes (2, 3 cells each) | yes (3, 3 cells each) |
| net `ok` survived | yes, driven by `and2_0` instance `_20_` | n/a |
| placed components (incl. 5 taps, 3 clkbuf from CTS) | 43 | 44 |
| OpenROAD design area / utilisation | 393 um^2 / 75% | 393 um^2 / 75% |
| die | 30.42 x 30.42 um | 30.59 x 30.59 um |
| setup slack @10 ns clk (post-route est.) | +6.964 ns | +7.016 ns |
| hold slack | +0.509 ns | +0.479 ns |
| runtime synth / P&R | 1.0 s / 8.2 s | 1.2 s / 12.7 s |
| OpenROAD route DRC (DRT violations; report file size) | 0; empty file | 0; empty file |
| magic DRC (`drc(full)`), top-cell count | 13 raw errors reported | 18 raw errors reported |
| netgen LVS | "Netlists do not match" | "Netlists do not match" |

Honest status: NOT DRC-verified and NOT LVS-verified. The router reports 0 violations, but magic reports raw DRC errors (counts in `out/*_magic.log`; many are listed against the standard cells themselves, not diagnosed, so some may be rule-deck/import artefacts, unconfirmed). LVS fails: the reference Verilog from OpenROAD has no power pins, so cell pin lists differ, and device counts differ by 1 (38 vs 39, 39 vs 40); not diagnosed. Slack is a placement/global-route parasitic estimate, not signoff. Cells have no reset; `initial st` values were not carried into the netlist (dfxtp flops). No physical glitch behaviour is claimed or tested.

## ANNOTATION (derived from the post-synthesis netlist; the solver fault model ran on a different, generic gate netlist)
- `out/v1_zoom_ok.png`: red box on instance `_20_` (`and2_0`), found by net name: it is the cell whose output pin is net `ok` in `out/v1_pnr.v` (name survived via `keep`). High confidence that it is the AND of m1,m2 as written in RTL; the correspondence with the solver's generic gate `ok` is by name only.
- `out/v2_zoom_copies.png`: boxes on each placed cell with hierarchical instance prefix c0/ (red), c1/ (green), c2/ (blue), from `out/v2.def`. Copies are not placed contiguously; this says nothing about independence of faults.
Other: `out/v1_full.png`, `out/v2_full.png` full layouts; `out/*.gds`, `*.def`, `*_routed.odb`, logs, `*_stat.txt`, `*_lvs.rpt`.
