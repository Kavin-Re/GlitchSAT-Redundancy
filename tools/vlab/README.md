# Virtual glitch lab for GlitchSAT

## In plain language

GlitchSAT today reasons about *abstract* faults: "flip this one bit in this cycle." A real attacker does
not flip bits — they shorten a clock pulse or dip the supply so that some flip-flops are sampled **before
their input has finished settling**, and latch a stale or half-formed value. This lab reproduces that
mechanism **in software, on the real placed sky130 layout** of V1 and V2, so the abstract model can be
checked against a more physical one — with no bench, no chip, no probe.

It answers one question for each design: **in this simulation, can a single clock glitch make the boot
check accept a wrong key?** The simulated answer is **no**: for both V1 and V2, across the whole simulated
sweep of glitch timings (ASSUMED delays), **0 wrong-key accepts**. This is a result of that sweep, not a
proof for other delays or for silicon (see "Limitation: hazard captures" below).

> This is a **simulation, not a measurement.** No silicon was involved. It is a model of how glitches
> cause faults; a real device adds noise, process spread, metastability and layout effects this does not.

## What it models

1. **Parse the placed design.** `v1_pnr.v` / `v2_pnr.v` (post-route gate-level Verilog) are joined to the
   DEF placement and LEF cell sizes by instance name, and the logic graph, clock tree and 8 state flops
   are rebuilt and checked (`vlab/netlist.py`, `vlab/cells.py`).
2. **Static-timing fault model.** A timing graph over the placed netlist gives each flop the longest
   combinational delay to its D pin and a clock-tree latency; below a given period a flop is predicted to
   miss its new value (`vlab/delaymodel.py`, `vlab/timing.py`). Computed here (SIMULATED): worst D-path ≈ **1070 ps**
   (V1), **849 ps** (V2) under the ASSUMED model.
3. **Event-driven capture.** For a glitch at cycle *t* with shortened period *P*, an event-driven
   two-value-with-delays simulator settles the netlist (hazards included) and samples each flop's D at
   *P + clock-latency*; a flop latches the **old** value (or a hazard-**intermediate** one) when its path
   is slower than the glitched period (`vlab/timing.py`, `vlab/glitch.py`).
4. **Campaign.** Sweep period × offset over all 256 `sig` values, organised like a ChipWhisperer
   offset × period sweep, and label every cell SUCCESS / CRASH / NO_EFFECT (`vlab/campaign.py`). Each
   cell also counts captures with a bit that is neither old nor new (`n_nonmix_capture_sigs`).
5. **Supply droop** is modelled as a uniform delay derating at a fixed nominal period (`run_vlab.py
   --derate-sweep`).

The **spatial (laser/EM)** mechanism is built separately in `tools/shots`; this lab only defines the shared
record both feed into the comparison — see `interface/README.md`.

**Which netlist "V1"/"V2" means.** This lab simulates the placed-and-routed netlists
`layout/v_designs/out_patched/v{1,2}_pnr.v` (+ DEF). These are not the reference Yosys netlists
`reference/spike_netlists/v{1,2}.json` that `tools/surface` and `tools/unbounded` analyse (V2 there: 182
minimum triples at 6 cycles; the placed V2 has 22, all in cycle 1).

Labels: **MEASURED** = tool output on the cloud VM; **SIMULATED** = output of this physical-mechanism
model; **SOURCED** / **ASSUMED** = inputs taken from a source / chosen by us.

## Assumptions: ASSUMED vs SOURCED

| Item | Status | Source |
|---|---|---|
| Netlist, placement, cell sizes | **SOURCED** | repo `layout/` (OpenROAD/sky130 flow), `research/c4/l2_inputs/lef` |
| Cell boolean functions | **SOURCED** | sky130 PDK (open_pdks, Apache-2.0): hand-written table, compared input by input with a switch-level evaluation of the PDK transistor subcircuits in `layout/v_designs/out_patched/v2_ref.spice` (22 of 22 cell types, evaluator from `tools/shots/shotmodel/switchlevel.py`; test `test_cell_table_matches_pdk_transistor_netlists`), and cross-checked vs the engine netlist over all 256 keys |
| sky130 cell sizes (LEF) | **SOURCED** | sky130 PDK (open_pdks, Apache-2.0), sizes-only LEF in `research/c4/l2_inputs/lef/` |
| Boot semantics (KEY 0xC3, GOOD 0x96, INIT 0xF0) | **SOURCED** | `rtl/v{1,2}.v`, repo README |
| Per-cell / wire **delays** | **ASSUMED** | linear model in `delaymodel.py` (intrinsic/drive/fanout/wirelength); sky130-scale guesses, **not a .lib**. No SDF/liberty timing ships in the repo. |
| Setup time, clock-to-Q, droop derating | **ASSUMED** | `delaymodel.py` constants |

The absolute picoseconds are arbitrary; only the **relative ordering** of path delays and the **shape** of
the sweep are meaningful. `eda/regen_sdf.sh` regenerates a **true** SDF with OpenSTA on a cloud VM with
OpenSTA and the sky130 PDK (not run on the VM that produced these results); drop it next to the netlist and
the campaign flips to `delay_model.source = SOURCED(sdf)` with no code change.

## Results (SIMULATED, ASSUMED delays)

| Design | GlitchSAT min flips, all sites (reference netlist, `results/reproduce`) | its attack sites (reference netlist) | min flips, flops only, 1 cycle (placed netlist) | GOOD reachable under the hazard-free old/new check (offsets 1..7, all 255 wrong sigs, 20-cycle continuation) | wrong-key accepts in the simulated sweep |
|---|---|---|---|---|---|
| V1 | **1** | the merge AND `ok` (`ok = m1 & m2`), cycle 1 | **4** | no | **0** |
| V2 | **3** | one internal compare gate net per copy (`c0/c1/c2 new_n15_/new_n16_`), cycle 1 | **4** | no | **0** |

The "all sites" column is read from the reference-netlist runs in `results/reproduce/*_spike_given-netlist_k*.json`;
it is not recomputed on the placed netlist this lab simulates. On the placed netlists the single-cell flip
minimum is the same (V1 1, V2 3: `tools/shots` at r = 0, and an independent review enumeration).

Across **7 offsets × 96 periods × 256 sigs** per design the simulated campaign finds **0 wrong-key accepts**
(ASSUMED delays). It is not inert: it records **11,267** (V1) / **12,288** (V2) crash cells (ASSUMED delays)
where the glitch corrupts state but boot does not wrongly accept. Supply-droop derating (ASSUMED uniform
slow-down) reaches crashes only at ≥ 2× slow-down (ASSUMED delays), still **0** accepts.

**Old/new mix check (hazard-free model, diagnostic only).** Under a hazard-free capture model, a glitch at
offset t can set each state bit only to its old value S[t] or its new value S[t+1]. For V1 and V2 every
wrong key gives the same trajectory 0xF0, 0xCC, 0x69, 0x69, ...; 0x96 is no per-bit old/new mix at any
campaign offset (e.g. old 0xCC, new 0x69: bit 1 is 0 in both but 1 in 0x96), and no mix leads to 0x96 in
the fault-free continuation within 20 cycles (`comparison.json`, `oldnew_mix_check`). This explains the
sweep result under that model; it is **not** a proof that no clock glitch works, because the premise does
not hold in this lab's own simulator (next paragraph).

**Limitation: hazard captures (neither old nor new).** The event-driven simulator models hazards, so a flop
can capture a value that is neither old nor new:
* ASSUMED default delays, V1, offset 2, period 815.99 ps (a point of the campaign grid): old = new = 0x69,
  captured **0x6d** (bit 2 neither old nor new), for all 255 wrong sigs. That is 1 of 672 offset × period
  cells for wrong keys (4 cells including the honest key; `v1_campaign.json`, `nonmix_captures`). V2: 0.
* Under 200 random per-cell delay scalings (ASSUMED, ×0.3 to ×3, seed 1; `run_vlab.py --hazard-trials 200`,
  `vlab/hazard.py`, `results/hazard_probe.json`), checking every distinct sample instant: V1 **2,071**
  non-old/non-new captures, V2 0. None of them led to a wrong-key accept (fault-free continuation checked).

So the statement this lab supports is the simulated one: **0 wrong-key accepts in the sweep** under the
ASSUMED delays and under those 200 perturbations. Other delays (a true SDF, process spread) could capture
other non-mix values; whether one of them reaches 0x96 is not shown. The abstract attacks GlitchSAT finds
flip internal gate nets (V1: 1, V2: 3), which this clock-glitch model does not act on directly; the
cheapest flop-only abstract attack needs **4** flops set at once.

## Run it

```
cd tools/vlab                          # inside the repository checkout, or set GLITCHSAT_ROOT
python3 run_vlab.py                 # ~15 s; writes results/*.json and plots/*.png
python3 run_vlab.py --derate-sweep --hazard-trials 200   # as stored: + supply-droop sweep + hazard probe (~80 s)
python3 -m pytest -q tests          # about 30 s (machine dependent)
```

Key validations in the suite: the **infinite-clock property** (a very long period reproduces the
zero-delay functional behaviour exactly, for all 256 keys and every offset) and the **exhaustive
cross-check** of the placed-netlist mapping against the engine's own Yosys-JSON netlist.

## Outputs
- `results/<d>_campaign.json` — schema `vlab-glitch-campaign/1` (full sweep; for a Studio "virtual glitch
  campaign" view). `inputs` holds the repo-relative input paths and their SHA-256; `generated` is a
  timestamp and is not a compared field.
- `results/<d>_shared.json` — schema `physical-fault-campaign/1` (shared with `tools/shots`).
- `results/comparison.json` — abstract vs clock-glitch, both designs.
- `results/hazard_probe.json` — non-old/non-new captures under ASSUMED delays and 200 random scalings.
- `plots/<d>_sweep.png`, `plots/<d>_slack.png`, `plots/comparison.png`.

## Limits
Still a model. ASSUMED delays until `eda/regen_sdf.sh` is run. Two-value logic with a simple hazard
model — no analog metastability, no process/voltage/temperature spread, no multi-edge glitch trains, no
clock-tree glitch propagation detail. Single-edge glitches only (one shortened period); multi-cycle fault
campaigns are a different regime. The capture is not limited to old/new mixes (V1, above), so the 0-accept
result holds for the simulated grid and delays only. **Nothing here is evidence about physical silicon: it is
a second, timing-based fault model to compare with the abstract one, not a measurement of a chip.**
