# EL1 report: circuit-level bridge from physical disturbances to the solver's fault model
Everything below is SIMULATED (circuit-level simulation in ngspice, NOT silicon, NOT physical validation). No physical attack was performed or is claimed.

## What was run (SIMULATED)
- Simulator: `/tmp/mm_root/envs/spice/bin/ngspice -b <netlist>` (ngspice-41, batch mode, `.control` loops with `alterparam`/`reset`/`tran`/`meas`).
- Models: `.lib /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice {tt|ss|ff}` and `.include /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice`. Cells: `sky130_fd_sc_hd__dfxtp_1`, `inv_1`, `nand2_1`, `buf_1`, `clkbuf_1`. The model file provides corners tt, ss, ff (plus sf, fs, ll, hh, ...). Used: tt 27 C, ss 100 C, ff -40 C, VDD 1.8 V nominal.
- Scripts (in this folder): `expA.py` (supply dip), `expBC.py` (clock runt; setup/hold), `fix_wd1n.py` (re-run of the 1 ns column, see Caveats), `analyze.py` (JSON + plots), helper `spl.py`. Raw: `part*.json`. Machine-readable windows: `fault_windows.json`. Plots: `plot_A_supply_dip.png`, `plot_B_clock_runt.png`, `plot_C_setup_hold.png`.
- Read-out: voltage >1.44 V = 1, <0.36 V = 0, else U (undefined). Sampling points are fixed times after the disturbance (4-8 ns), so "U" would mean not yet resolved by then; none occurred in the final data.

## Experiment A: supply dip on one shared rail (SIMULATED)
Circuit: one VPWR rail (the dipping one) feeds two dfxtp_1 flops (one stored 0, one stored 1), their clkbuf/buf input drivers, an inverter and a nand2 with output high, an inverter and a nand2 with output low, loads. Two clean-rail flops sample the high outputs at the dip centre. Dip: 0.1 ns ramps to floor Vmin, width 0.3, 1, 3 ns, Vmin in {1.0, 0.7, 0.5, 0.3, 0.0} V; tt, with clock held low and held high; ss and ff clock low. D set to the opposite of the stored value during the dip.
Results (60 points, `fault_windows.json` key `A_supply_dip`):
- Flop Q: held its value in ALL 60 points, including a floor of 0 V for 3 ns, both clock phases, all three corners. No Q flip, no undefined state, no spurious clock edge from the clock buffer sagging. Only 3 ns max width was tested; storage will fail for sufficiently long dips (not mapped here: the earlier partial retention script `e1_retention.py` was not completed).
- Gate outputs that are HIGH sag with the rail (output follows VDD down). Their minimum is below 0.9 V (mid-rail) for floors <= 0.7 V at every width tested (0.3 ns: 0.56 V at the 0 V floor, still read as 1 by the sampler because the dip is short). Gate outputs that are LOW stay low (max 0.16 V, ss, 0 V floor).
- A clean-rail flop clocked at the dip centre captured WRONG (0 instead of 1) from a high gate output at: tt 3 ns with Vmin <= 0.5; tt/ss/ff 1 ns only at Vmin = 0 V; ss 3 ns Vmin <= 0.5; ff 3 ns Vmin <= 0.3; none at 0.3 ns. Both inverter and nand2 behave the same.
- Simultaneity: in every wrong-sampling point, ALL high-output gates on the rail drooped together (inv and nand2 identical within ~0.01 V); flops on that rail did not flip.

## Experiment B: clock runt/extra pulse (SIMULATED; clean rail, D = opposite of stored)
`fault_windows.json` key `B_clock_runt`. Amplitude {0.5, 0.9, 1.3, 1.8} V x width {0.1, 0.4, 2} ns (48 points).
- tt: no capture at 0.5 V; 0.9 V needs 2 ns width; >=1.3 V flips for all widths tested (0.1 ns at 1.3 V flips). ss needs more (1.3 V / 0.1 ns holds; 0.9 V / 2 ns flips); ff most sensitive (0.9 V / 0.4 ns flips). Flip = Q captures D, i.e. the stored bit is overwritten by D, so the "fault" value is whatever D holds; a clock glitch is a wrong-time capture, not an arbitrary bit flip. Stored 1 behaves like stored 0 (tt).
## Experiment C: data near the clock edge (SIMULATED; dt = data change time relative to the edge; 25 ps grid)
`fault_windows.json` key `C_setup_hold`. Latest dt that still captures the new value: tt 1.8 V: dt <= -50 ps (stored 0), dt <= -75 ps (stored 1); tt at static VDD 1.2 V: dt <= -100 ps; ss: -75 ps; ff: -25 ps. After the edge (dt >= 0) the old value is held (no hold violation seen at dt >= 0 in this cell, 25 ps grid). No undefined/metastable output at the 25 ps grid: the metastable window, if any, is narrower than 25 ps. Setup requirement therefore scales with corner and supply (about 2x between 1.8 V and 1.2 V).

## Which solver fault sites are circuit-plausible (SIMULATED indications only)
1. Flop Q single-cycle flip from a supply dip alone: NOT shown (0 of 60 dip points). Do not claim it from this.
2. Gate output wrong for a cycle: SHOWN in the sense that a high gate output sags below mid-rail and a downstream capture at that instant sees the wrong value. Only high-to-low sag; low outputs did not rise. So a supply dip is a one-directional (1 to 0) fault on the captured value, not a symmetric flip.
3. Flop captures a wrong value via a clock-edge glitch or early/late data: SHOWN. A runt clock pulse of >= 1.3 V (tt) overwrites the flop with its current D (both polarities). A data change within ~25-100 ps before the edge (corner, VDD dependent) is the setup window where the old value is captured instead of the new: this is the "late data" fault, again a wrong-capture, not a free flip.
4. Simultaneous multi-net faults on one rail: SHOWN. Every high-output gate on the dipping rail sagged together and the same samplers failed together. A supply dip is therefore a correlated, rail-wide, one-directional disturbance.

## Suggested constraints for the solver (modelling suggestions, not results about silicon)
- Weight multi-flip attacks as one correlated event: all gates on the same rail (or clock-tree branch) are hit together; independent single-flip sites are the less supported model for supply dips. A rail-correlated fault class (set of nets driven 1 to 0 at one cycle) is the physically motivated alternative.
- Directionality: supply-dip faults pull high nets low; fault classes should allow 1-to-0 only (or capture-of-D) rather than free flips.
- Clock and data faults act on flop captures (Q takes the value of D at a wrong time), so model them as 'flop captures D_early/D_late' rather than 'Q flipped'.
- Flop Q flips should be the least plausible solver site for supply dips (not seen), and are only reachable here via clock runt (which is capture of D).
- Do not read a numeric window (volts, ps) as an attack parameter: it only ranks sensitivity across corners.

## What the SPICE result does NOT show
- Not silicon, no layout, no extracted parasitics, no power-grid RC/inductance: a real dip does not have this clean shape or locality, and VDD droop does not alter ground in this model (VNB tied to VGND).
- One cell type each, 1 fF-5 fF loads, no process mismatch (no Monte Carlo), 1 temperature per corner, VDD 1.8 V nominal only; dip width max 3 ns, so retention loss for longer dips is unmapped; the earlier `e1_retention.py` was not completed.
- No radiation/laser/EM injection models; no claim that a physical attacker can produce these waveforms.
- Metastability window not resolved (25 ps grid, sampling at a fixed time); undefined states are not excluded.
- Grids are coarse (5 floors x 3 widths; 4 x 3 clock-runt points; 21 setup points per case). Windows are bracketed, not exact.
- Does not validate any redundancy verdict from the solver; it only supplies plausibility and correlation hints.

## Caveats and provenance
- A first run of the 1 ns column was invalid (a `meas at=` equal to tran stop time failed and shifted echo columns, giving spurious 'U'); it was discarded and re-run with `fix_wd1n.py` after making the tran run 1 ns past the sample time. `analyze.py` drops the old 1 ns rows. Two earlier full-size runs were killed for time (heavy machine load); grids were reduced to finish within the cap.
- Over the 45-minute cap by a few minutes because of machine load.
