# EDA steps (need OpenSTA / iverilog and the sky130 PDK)

The virtual glitch lab runs in pure Python on the repository's existing placed outputs. Two optional
steps need real EDA tools; they are given here as exact commands for a cloud VM (or any Linux machine)
with OpenSTA and the sky130 PDK. They were **not** run on the VM that produced the stored results (no
OpenROAD / OpenSTA / iverilog installed there); until they are run, the lab uses its documented ASSUMED
linear delay model.

Both scripts find the repository as `$GLITCHSAT_ROOT` (`$GLITCHSAT_REPO` is accepted as an older alias),
else the checkout they sit in (`<repo>/ext/vlab/eda`). Temporary files go to a `mktemp -d` directory.

## 1. Real timing (recommended): `regen_sdf.sh`
Builds a true SDF (and a per-flop path-delay report) with OpenSTA and writes `v1.sdf` / `v2.sdf` next to
the netlists (`layout/v_designs/out_patched/`). `run_vlab.py` auto-detects them and the campaign JSON then
reports `delay_model.source = SOURCED(sdf)` instead of `ASSUMED`.

```
LIB=/path/to/sky130_fd_sc_hd__tt_025C_1v80.lib  ./regen_sdf.sh
cd .. && python3 run_vlab.py
```
`STA` defaults to `sta`; set `STA="openroad -exit"` to use the `sta` commands inside OpenROAD.

## 2. Second-simulator mapping check: `verilog_glitch_check.sh`
Re-runs the zero-delay cross-check with Icarus Verilog on the actual placed netlist plus the PDK cell
models (all 256 sig values, 8 cycles), confirming no wrong key boots. For a timing-annotated glitch
replay, annotate the SDF from step 1 (`iverilog -gspecify`, `$sdf_annotate`) and shorten one clock edge.

```
SKY130_V=/path/to/sky130_fd_sc_hd.v  ./verilog_glitch_check.sh v2
```
