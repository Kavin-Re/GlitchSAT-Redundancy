# V1/V2 patched flow rerun (flow_patched/, out_patched/) - MEASURED 2026-11-19

Patches from triage: `tapcell -distance 10` (was 14), `filler_placement` (fill_1/2/4/8, decap_3/4) after detailed_route, `define_pdn_grid -starts_with POWER` (was `-pins met5`), PDN pitch 20/offset 6 (was 50/10, core ~30um), VPWR/VGND labels on met5 stripes (pwrlabels.py from DEF), IO pin metal under labels (pinpaint.py), magic run with `-rcfile sky130A.magicrc`, flat extraction, `write_verilog -include_pwr_gnd` + SPICE reference built from PDK subckts (v2spice.py), netgen flat compare. Run: `flow_patched/all.sh` from layout/v_designs. Original files untouched.

| metric | V1 before | V1 after | V2 before | V2 after |
|---|---|---|---|---|
| yosys cells / area um^2 | 35 / 357.8 | 35 / 357.8 | 36 / 362.8 | 36 / 362.8 |
| placed components (taps, CTS, fill) | 43 | 76 | 44 | 72 |
| OpenROAD area / util | 393 / 75% | 399 / 77% | 393 / 75% | 399 / 77% |
| setup / hold slack (ns) | +6.964 / +0.509 | +7.050 / +0.519 | +7.016 / +0.479 | +7.035 / +0.476 |
| router DRC violations | 0 | 0 | 0 | 0 |
| magic DRC, TOP cell | 13 raw reported | no top-cell rule listed (`drc listall why` empty; no top-cell entry in DRC_TOTAL) | 18 raw reported | same: none listed for top cell |
| magic DRC, std-cell/filler definitions (per cell def) | listed | still reported: e.g. dfxtp_1 21, nor4bb_2 14, nand4bb_1 10, mux2_1 9, fill_1/2/4/8 1 each, decap_3 3 (PDK cell GDS vs magic deck; not design-caused, not fixed) | listed | same pattern |
| netgen devices (layout vs ref) | 38 vs 39 mismatch | 422 vs 422 | 39 vs 40 mismatch | 430 vs 430 |
| netgen nets | 54 vs 200 mismatch | 225 vs 225 | 55 vs 205 mismatch | 226 vs 226 |
| netgen verdict | do not match | "Circuits match uniquely"; pin lists equivalent | do not match | "Circuits match uniquely"; pin lists equivalent |

## Plain verdicts
- Route DRC: tool reports 0 violations (empty report) for both.
- Magic DRC: top cell lists no rule violations for either design; standard-cell and filler definitions still carry errors inside magic (PDK cells under this deck), so the tool does NOT report the whole GDS as DRC-clean. Antenna and off-grid checks, run later (`layout/verify/VERIFY.md`): 0 antenna violations, nothing off the 5 nm grid; not signoff.
- LVS: netgen reports the layout and the powered reference match uniquely for both designs (flat compare, PDK subcircuits, tap/fill ignored by the sky130A setup). Equivalence is for netlist vs extracted layout only; slack is a global-route parasitic estimate, not signoff.
- Unlike the triage design, no net merges appeared here.
- V1 zoom re-rendered: `out_patched/v1_zoom_ok.png` (instance `_20_` and2_0 drives net `ok`, same annotation). Also `v1_full.png`, `v2_full.png`, `v2_zoom_copies.png`.
