# Real-design attempt #2: report

Saved at integration session from the second-real-design worker's hand-back (the worker could not write this file itself). Numbers are as reported by that worker and are in `door_results.json` in this folder; I have not re-run them.

## Design used
- "Digital Door Lock" (Tiny Tapeout), module `tt_um_rameshwar_door_lock`, https://github.com/Rameshwar-12/Door_lock_system
- Commit pinned: `d05eab5298e152d0a4e4838240ae7f43a49050ee` (default-branch HEAD at fetch time, 2026-11-19, obtained with `git clone`, not the blocked API or releases path).
- Licence: Apache-2.0 (LICENSE identical to `src/LICENSE.apache2`; `SHA256SUMS` matches a fresh clone's `src/project.v`, per the worker).
- Plain Verilog, one file: `src/door_lock.v`. A copy with only the top-module name changed is at `layout/second/rtl/door.v`.
- Other candidates in `dl_repo/` were not pursued (Wokwi schematics, notes-only).

## What the design actually is (important)
Purely **combinational**: the netlist (`door5.json`) has only AND, NOT and OR cells and no flip-flops. `clk`, `rst_n` and `ena` are unused. Logic: `unlock = (ui_in[3:0] == 4'b1010)`, `error = ~unlock`. There is no stored state, no debounce and no lockout. The password 1010 is also published in the repo's own `docs/info.md`.
**Consequence for this project:** a 4-bit comparator with 6 gates is too small to be an informative test of the solver. It adds little beyond the first real design.

## Synthesis (project flow)
`yosys -p "read_verilog src/door_lock.v; hierarchy -top tt_um_rameshwar_door_lock; flatten; proc; opt -full; memory; opt -full; techmap; opt -full; abc -g AND,OR,XOR,MUX; opt_clean; write_json door5.json"` (yosys 0.38, `eda` env). Result: 6 cells (2 AND, 2 OR, 2 NOT), identical to the earlier netlist.

## Security goal and model
`unlock == 1` while `ui_in[3:0] != 4'b1010`, with at most k single-net bit flips in the 6-gate netlist. `ui_in` is free per cycle. No sequential state, so the cycle bound T adds no power (kept for format consistency). Solver: `glitchsat_door.py` (z3, single core).

## Results (MEASURED, z3)
| k | T | verdict | runtime | minimal fault |
|---|---|---|---|---|
| 0 | 4, 6 | UNSAT | 0.005 s / 0.001 s | none |
| 1 | 4 | SAT | 0.002 s | one internal compare-tree gate output (`new_n10_`) |
| 1 | 6 | SAT | 0.002 s | `new_n7_` |
| 2 | 4 | SAT | 0.001 s | minimises to 1 fault (`new_n9_`) |
| 2 | 6 | SAT | 0.002 s | minimises to 1 fault (`new_n7_`) |

## Interpretation
Flipping any one of the four internal gates of the single compare tree is enough. That tree is the entire security logic, so this is the same generic single-event-upset category as the first report's decision flop, not a design-specific weakness. **Not a finding to publish or disclose**; the password is public anyway.

## Layout (flow_patched lineage, own copy in `layout/second/flow/`)
One real change beyond the inherited triage fixes: utilisation lowered from 60 to 10 because the 3-cell design is smaller than the 60% core (OpenROAD GPL-0301). A null guard was added to `pwrlabels.py` (no met5 VGND stripe exists at this core size).
| metric | value (MEASURED) |
|---|---|
| synthesized cells | 3 (`nand4bb_1`, `nor4bb_1`, `conb_1`) |
| cell area | 25.024 um^2 |
| placed area / utilisation | 29 um^2 / 17% |
| setup / hold slack | +7.739 ns / +2.027 ns |
| router DRC | 0 violations |
| magic DRC, top cell | none listed (only PDK cell-definition artifacts, same as `out_patched/RESULT.md`) |
| netgen LVS | devices and nets match (28 devices, 20 nets) ("Netlists match uniquely with port errors"), but the final line of the report is **"Top level cell failed pin matching"**: 22 output pins are tied to the same constant-0 net by the RTL, so they collapse to one pin versus 22 named pins in the reference, and VGND is missing from the layout ports (`door_lvs.rpt`) |
The match is of devices and nets only; the top-level LVS did **not** pass. The cause is the design tying many outputs to ground plus the missing VGND port, not shown to be an extraction bug.
Files: `layout/second/out/` (door.def, door.gds, door_pnr.v, door_{yosys,openroad,magic,lvs}.log, door_lvs.rpt, door_stat.txt).

## Not done
Zoomed renders, antenna and off-grid checks, Verilator, a third design, and the LVS port-collapse fix (needs a design change).
