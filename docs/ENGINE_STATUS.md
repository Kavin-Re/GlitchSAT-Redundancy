# Engine status (glitchsat toolkit)

First written 2026-11-19; updated about 19:30 UTC with review-finding fixes (F1).

All numbers below were produced by the commands shown (logs in `results/logs/`, JSON in `results/`). Label: **MEASURED** unless stated. Faults are **modelled** bit flips, not physical glitches. Every verdict here is **bounded, not unbounded**, except the one narrow PDR result for the V2 spike netlist described under Limits.


**V2 scope (F1; CT-1 to CT-4):** On the stored spike netlist, with the goal being the 8-bit result word, with input nets not treated as fault sites, with a known power-up state and a constant non-key attacker input, no set of at most 2 single-cycle flips reaches the target word (formal proof for any number of cycles with that goal); the accept output `boot_ok` itself can be flipped with 1 flip (MEASURED, re-run by the lead: `glitchsat check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1` gives ATTACK_FOUND, min 1; finding CT-1, `research/c2/critics/ct/CT_FINDINGS.md`); adding input buffers as fault sites reduces the minimum to 1 (reported by the technical critic CT-2, being re-measured); the apt Yosys 0.33 RTL re-synthesis (85 gates) has a 2-flip attack; the conda 0.38 re-synthesis (83 gates) did not.

## Commands
```
make reproduce     # scripts/reproduce.py  -> results/reproduce/*.json, results/reproduce_summary.json (~25 s)
make replay        # scripts/replay.py     -> tb/generated/*.v, *.vcd, *_replay.json (iverilog)
make bench         # scripts/bench_reduce.py -> results/reduction_benchmark.json (~100 s)
make mutate        # scripts/mutate.py --all -> results/mutation_summary.json
make test          # pytest tests/ (189 passed, 2 skipped (190 collected; 22 s; clean venv with `./product[test]`, no numpy, no browser; history: 196 passed, 1 skipped at INT2a before test_wow_checks existed) and product tests 324 passed in 81.3 s after `pip install ./product[test]`: MEASURED on a copy, 2026-11-20 (re-measured by RECON6 on the unpacked bundle); history: 10 tests at first writing, then a 30-test suite after H1, 27 product tests per PS2; run it and quote your own count, `docs/NUMBERS.md`)
python scripts/glitchsat.py check rtl/v1.v --top v1 --k 3 --cycles 6 --out results/x.json [--reduce none|coi|full] [--flow plain|opt]
python scripts/replay.py results/x.json
```
`check` accepts a `.v` file (synthesized by `scripts/synth.sh`: Yosys, AND/OR/XOR/NOT/MUX + DFF, per-module mapping then flatten, no opt_merge so redundant copies stay independent) or a pre-synthesized Yosys `.json` (`reference/spike_netlists/`, the spike's original netlists).

## Model (what is and is not covered)
- Faults: single-cycle bit flip of any gate output net or flop Q net, at any cycle 0..N-1, at most K total.
- Attacker input `sig`: free, constant for the whole run, must differ from key 0xC3. (A free per-cycle input was tested separately by E1, below; the engine itself still uses a constant input.) Goal: `boot_word == 0x96` at some cycle < N.
- Output JSON: verdict (`ATTACK_FOUND` / `NO_ATTACK_UP_TO_BOUND`), minimized fault list (net, cycle), attacker input, runtime, bound block, BOUNDED note, plain-language explanation + fix pattern, fault-free "legitimate key boots" sanity bit.
- Reductions (`--reduce`): `coi` = only fault sites in the backward cone of the goal output; `full` = coi + drop fault sites that cannot reach a goal bit before the horizon, plus z3 constant-folding.

## Results (N=6 cycles, k = max faults; "min" = minimized fault count)
| design | netlist | k=1 | k=2 | k=3 |
|---|---|---|---|---|
| V0 naive | any of 3 | ATTACK, min 1 | ATTACK, min 1 | ATTACK, min 1 |
| V1 dup compare + sparse FSM | any of 3 | ATTACK, min 1, net `ok` @ cycle 1 | min 1 | min 1 |
| V2 triplicated, split word | spike netlist | NO_ATTACK | NO_ATTACK (about 1 to 2.5 s; machine and load dependent, 1.18 s in the stored run) | ATTACK, min 3 (3 compare-internal nets @ cycle 1) |
| V2 triplicated, split word | re-synthesized from `rtl/v2.v` with **apt Yosys 0.33** (plain flow 85 gates, opt flow 81 gates; both give a 2-flip attack with apt 0.33) | NO_ATTACK | **ATTACK, min 2** | ATTACK, min 2 |
| V2 triplicated, split word | re-synthesized from `rtl/v2.v` with conda Yosys 0.38+92 (83 gates, 1 MUX; MEASURED in the `formal` env, see `formal/FORMAL.md`; plain flow only, conda 0.38 not run for the opt flow) | NO_ATTACK | NO_ATTACK | ATTACK, min 3 |
| V2 triplicated, split word | validation flow B netlist (hierarchy stripped, `synth -flatten`; `validation/VALIDATION.md`, `make validate`, 6 cycles) | ATTACK, min 1 (4 of 378 single-flip sites) | min 1 | min 1 |

Minimum flips for V2 therefore range 1, 2 or 3 by netlist. Synthesis-recipe and counting-rule caveat (experiment `research/c2/devils_advocate/DA_CYCLE1.md`, MEASURED by that agent and replicated by agent REP on 64 of 64 rows with one recipe list (`research/c3/rep/REP_REPORT.md`)): over 32 re-synthesized V2 netlists the unit-weight minimum was 2 in 26 and 3 in 6; if a flip of a net with fanout f costs f faults, V2 needs 3 on all 32 and V1 needs 2 on all 32. The 2-flip attacks use ABC-introduced shared stems (fanout 2 or 3), so the "V2 holds" outcome depends on both the netlist and on counting a stem flip as one fault.

All k=0 runs: UNSAT (wrong key never boots) and the legitimate key boots fault-free. Full table: `results/reproduce_summary.json`.

**Important, honest finding:** the spike's V2 claim ("no attack with <=2 faults") reproduces exactly on the spike's netlist (`reference/spike_netlists/v2.json`), but when `rtl/v2.v` is re-synthesized by this repo's flow with apt Yosys 0.33, ABC shares logic between result-word bits and the solver finds a 2-fault attack (two gates feeding several word bits, at cycle 0). The same script with conda Yosys 0.38+92 gives a different netlist (83 gates) with no 2-fault attack. The countermeasure's strength therefore depends on the synthesized netlist, not just the RTL. Root cause (CORRECTED 2026-11-20, P01a, `docs/report/WHY_TWO_FLIPS.md`; earlier wording blamed the Yosys version, an error: the stored netlist is also Yosys 0.33): the armed word 0xCC differs from 0x96 only in bits of two of the three copies; `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over the 8 flows versus 2 1 1 2 2 2 2 2. Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, not the underlying weakness. `ci/expected_reproduce.json` was recorded with apt Yosys 0.33: `make check-reproduce` will mismatch with another Yosys build. Fixing this (e.g. hierarchy/keep boundaries per word bit) is not done. Do not cite "V2 resists 2 faults" for the re-synthesized design. Build differences (H5, 2026-11-20, MEASURED): on the plain flow at <=2 flips apt 0.33 (85 gates) gives an attack, conda 0.38 and Docker/Debian 0.52 (83 gates each) do not; conda 0.38 gives 2 on three other flows (P01a). Verdicts belong to a netlist hash and flow.

Weak-point explanations are generated automatically; V1 reads: single AND gate `ok` combines 8 bits of `sig`, drives 8/8 `boot_word` bits; fix = split the decision across independent bits.

## Replay (iverilog)
`replay.py` regenerates a faulted gate-level netlist and testbench from the solver JSON (no hand-written bench), runs faulted and fault-free controls, dumps VCDs in `tb/generated/`. V0 and V1 attacks: faulted run reaches 0x96, fault-free run with the same input stays 0x69 (tests assert this). Verilator replay: NOT done. The replay netlist is emitted from the same Yosys JSON, so it checks the solver's semantics, not Yosys-vs-RTL equivalence.

## Reduction benchmark (V2 spike netlist, k=2, UNSAT; `results/reduction_benchmark.json`)
| cycles | none | coi | full | fault vars none/full |
|---|---|---|---|---|
| 4 | 0.46 s | 0.42 | 0.34 | 304 / 215 |
| 6 | 1.57 | 1.35 | 1.28 | 456 / 353 |
| 8 | 7.53 | 6.08 | 8.05 | 608 / 491 |
| 10 | 28.47 | 23.73 | 21.66 | 760 / 629 |
Gain is modest (about 17 to 29 percent fewer fault variables; up to about 26 percent faster (0.46 s to 0.34 s); N=8 `full` was slower, i.e. noise-level). Runtime grows about 4x per 2 extra cycles from 6 to 10 cycles (this table); in the depth sweep it grows about 2x to 3x per 4 extra cycles between 12 and 20 (`docs/DEEP_RESULTS.md` section 4). These toy designs are almost entirely in the goal cone, so COI cannot help much. Verdicts were identical across modes (pytest checks this).

## Mutation check (`results/mutation_summary.json`, k=3, N=6)
- Netlist level on the spike V2 (baseline min cost 3): sharing copy 1's result with copy 0, or copy 2 with copy 1, drops min cost to 2: both CAUGHT.
- RTL level (baseline from this repo's synthesis is already 2): single AND deciding all bits drops to 1: CAUGHT. Sharing `m1=m0` or `m2=m1` stays at 2: NOT caught (baseline already weak). Reported as is.

## Limits
Toy 8-bit compare FSMs; modelled flips only (no stuck-at, multi-bit/spatial, clock/voltage); input held constant in the engine (see the E1 note below); bounded cycles/faults; runtime exponential-ish in cycles; SymbiYosys is available only in a separate conda env (`formal`), not in the CI path; an unbounded proof exists for the V2 spike netlist, k<=2, this fault model only (`formal/FORMAL.md`), none for anything else; no Verilator replay; the `keep` attributes in `rtl/` mimic a dont_touch flow.


## Free per-cycle attacker input (E1; MEASURED by that agent, not re-run here)
`research/c2/e1_timevarying/E1_REPORT.md`: the V2 spike claim "no attack with k<=2" also holds when the attacker input is free on every cycle, under the spec rule "the key 0xC3 is never presented at any cycle" (T=4, 6, 8 bounded z3 with minimum still 3; sby BMC depth 16; ABC PDR PASS for k<=2 for any number of cycles; explicit-state fixpoint agrees). V0 and V1 stay at 1. It applies to the spike V2 netlist only (not run on re-synthesized netlists; no exported PDR certificate; same netlist reader and flip semantics). The reason is structural: the design samples `sig` once and then latches. Under the weaker spec "accept at cycle t counts if the input at t is not the key" every design breaks with zero flips.

> Tool-build labels: apt Yosys is 0.33. The conda package is `yosys-0.38_93_g84116c9a3` (litex-hub, 2024-02-23); its binary banner prints 'Yosys 0.38+92 (git sha1 84116c9a3)': same source. Where this repo writes 'conda 0.38+92' it means that package. Always record the Yosys build and the netlist gate count next to any V2 verdict.

R27's sequential-counter 'at most j' encoding was APPLIED by T3 to `scripts/glitchsat.py` and `product/src/faultbound_wt/_engine.py` (default `--amk counter`; `--amk legacy` keeps the old code; product: env `FAULTBOUND_AMK`; `research/c4/t3/T3_REPORT.md`, reported, lead re-ran `check_reproduce --rerun` 36/36 in 12.9 s and `pytest tests` 99 passed at that time): 36/36 reproduce rows match (witness set differs in 11/36, as before), tests 99 and 139 + 1 skipped pass at T3 time (now 150 and 324 (INT); 136 at RECON5; 133 and 321 at RECON4/H4 time; 310 at H2/H3 time), UNSAT cells at least 43x faster (dmr k=1 T=4: 1.6 s vs legacy timeout at 150 s), 80x (V2 k=2 T=12), at least 107x (T=20); summed reproduce row time 14.4 s -> 4.2 s; slower on some SAT cells (R27: uart k=3 T=60 4.5 s -> 33 s). `make reproduce` outputs in `results/` predate the patch.
