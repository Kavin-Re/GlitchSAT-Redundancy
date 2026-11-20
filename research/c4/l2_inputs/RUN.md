# l2_inputs: small inputs to regenerate L2's selectivity tables

Everything here is small (about 0.7 MB). Large artefacts (GDS, routed odb, magic .mag, spice, logs, lvs reports) are NOT shipped; they lived in `/tmp/work_l2/out_<var>/` and are regenerated only by the OpenROAD/magic/netgen flow `research/c4/l2/run_var.sh` + `pnr_l2.tcl` (needs env `eda`, not in this repo). The `out_*` directories still existed when this folder was written (2026-11-19); the DEF and post-route netlists below are byte copies of `out_<var>/v2.def` and `out_<var>/v2_pnr.v`.

| path | content | origin |
|---|---|---|
| `def/<var>.def` | placed + routed DEF of V2, var = base, v8, s8, v15, rr | copy of `/tmp/work_l2/out_<var>/v2.def` (MEASURED flow output) |
| `pnr/<var>_pnr.v` | post-route Verilog netlist (sky130 cells) | copy of `out_<var>/v2_pnr.v` |
| `lef/sky130_fd_sc_hd_sizes_only.lef` | MACRO + SIZE lines only (437 macros) | extracted from sky130A `sky130_fd_sc_hd.lef` (full LEF not shipped) |
| `coords/<var>_placement.csv` | cell name -> master, x, y, centre, size, orient, status, row, VPWR rail y, VGND rail y (all components incl. taps, fill, CTS) | `python3 extract_coords.py` from `def/` |
| `domains/<var>_domains_v2.json`, `domains/<var>_layout_geometry_v2.json` | layout-derived domain families (row, vpwr_rail, vgnd_rail, strap, tap, radius discs) and per-cell geometry | outputs of `code/layout_extract.py` on `def/` + `pnr/` (copied from `/tmp/work_l2/lay/<var>/`) |
| `code/*.py` | the L2-parametrised LAYOUT scripts (paths made relative; LEF via env `LEF`), plus unchanged copies of B3 `b3pack.py`, `faultpack.py` | copy of `/tmp/work_l2/lay/code/`; only the `sys.path` lines were edited |

The ORIGINAL (non-L2) layout inputs are already in the repo: `layout/v_designs/out_patched/{v1,v2}.def`, `{v1,v2}_pnr.v`, and `research/c4/layout/{domains_*,layout_geometry_*,nl/}`. `base` here reproduces the original V2 placement (COMPONENTS md5 equal, L2_REPORT).

## Commands (python3 + z3-solver only; no OpenROAD)
```
cd research/c4/l2_inputs
mkdir /tmp/l2_regen                          # a NEW empty directory you own
./run_l2_selectivity.sh /tmp/l2_regen        # extract -> geometry -> minimal sets (<=4 cells) -> radius sweep, 5 variants in parallel
./check_l2_table.py /tmp/l2_regen            # compares minsets_v2.json / sweep_v2.json with research/c4/l2/data/{minsets,sweep}_<var>.json
python3 extract_coords.py                    # (re)writes coords/*.csv from def/
```
`run_l2_selectivity.sh WORKDIR base` runs one variant. Per-variant steps are the same as `research/c4/l2/dom.sh` (which needs the /tmp paths); `simcheck` and the family table (`run_domains.py`, `fam_<var>.jsonl`) are not part of this script (the family run is long; `code/run_domains.py` is included, see the header of that file).

## Measured check (MEASURED, 2026-11-19, on a fresh copy of research/c4/l2 + l2_inputs under /tmp/work_anchor/fresh)
`time ./run_l2_selectivity.sh ...` = 59.5 s wall, 4 cores shared with another job (limit asked: 10 min). `check_l2_table.py`: 10 of 10 files IDENTICAL to `research/c4/l2/data` (5 minsets + 5 sweep; timing fields ignored). So the table "min MEC radius of a sufficient set" and the radius sweep (AoN/SUB cost per radius) regenerate from these files. NOT regenerated here: the flow numbers (die area, wire length, slack, DRC, LVS: need OpenROAD/magic/netgen; `data/summary_flow.json` holds them) and the rail-family table `fam_<var>.jsonl`.
