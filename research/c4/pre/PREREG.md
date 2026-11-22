# PRE-REGISTRATION: structural min-flip predictor
Written 2026-11-19 BEFORE any held-out run. Frozen together with predictor.py (see FROZEN.sha256). Licence: UNDECIDED. Toy designs, modelled faults, no hardware claim.

## Definition (exact; code is predictor.py)
Input: Yosys-JSON gate-level netlist (cells $_AND_/OR/XOR/NOT/MUX/NAND/NOR/XNOR/ANDNOT/ORNOT/BUF + $_DFF_P_), top module, goal output port, mask, accept value, key, attacker input port, T (default 6). Other inputs held 0; attacker input = constant value != key, all values enumerated (<=1024, else seeded sample). Power-up = netlist init (default 0). Fault = single-cycle XOR on a gate output or flop Q; a stem is ONE fault.
Output: `lb, est, ub_direct, pred, flag, witness`. No SAT/SMT solver is called.
1. Fault-free bit-parallel simulation -> per (cycle t*, attacker value) the set D of masked bits that differ from accept. D empty somewhere -> pred 0 (`collision`).
2. `lb` = min over (t*, value) of the minimum set cover of D by STRUCTURAL cones: site (t,n) covers output bit b iff a path exists in the time-unrolled graph (gate fan-in same cycle; flop D to Q one cycle later). Covers state and next-state logic (flop D-cones) as well as compare cones. Reachability of every differing bit is necessary, so lb is a necessary-condition lower bound (not a vertex-cut; no min-cut is computed - stated limit).
3. `est` = smallest fault set (size<=6) built from sites whose single-flip event-propagated effect toggles >=1 bit of D and no masked bit outside D, whose COMBINATION is verified by a joint fault simulation to reach accept at t* (so est is a verified upper bound when not None; the search over combinations is incomplete: one site per distinct effect class, <=3000 combos per size). `ub_direct` = number of distinct output nets differing (flip them at t*).
4. `pred` = est if found else lb+1 (flag `uncovered`). Predicted ">=3" means pred>=3.
Counting rule: stem = 1. Solver reference model: glitchsat (T=6, k<=3, input nets not sites, known init, sig constant != key); solver values ">3" are compared as 4.

## Success criteria (fixed now; applied by step TEST to pooled held-out cells, solver-exact reference)
Let a "cell" = (netlist, mask) with a solver-exact min flips (cap 3, ">3" = 4).
- C1 soundness of the bounds: `lb` <= solver in 100% of cells and `est` (when not None) >= solver in 100%. ANY violation = bug in predictor or simulator assumptions (netlist semantics differ); reported as FAIL with the case.
- C2 exact match `pred == solver` on >= 90% of cells.
- C3 `|pred - solver| <= 1` on >= 98% of cells.
- C4 no "false safe": cases with pred >= 3 and solver == 1: 0 (hard); cases pred >= 3 and solver <= 2 reported (expected: over-estimation from incomplete search).
- C5 no "false weak": cases with pred == 1 and solver >= 2: 0 (cannot happen if C1 holds because est is verified; any occurrence is a C1 failure).
- C6 on the E2 breakable set (solver min <= 2 for the full word): >= 90% recall of pred <= 2 (the review panel's concern that breaks come from state/next-state logic, not only compare copies).
Overall PASS = C1 and C4 and C5 and C2 and C3 (and C6 when applicable). Report all numbers, per design and per flow, even when passing.
## Failure modes and meaning
- est > solver (over-prediction): the real attack needs an interaction the single-flip classes miss (two flips only effective together, or a non-representative site of an effect class). Conservative direction, but counts against C2/C3. Seen in training: 3/255 V2 masks (pred 4, truth 3).
- pred == lb+1 with flag `uncovered`: no verified combination found; low confidence.
- est < lb flag `est_below_lb`: must never occur; sign of a parser/semantics bug.
- Unsupported cell type -> exception, not a verdict.
- Large designs: simulation cost grows ~ sites x gates; no scale claim.
## Training evidence (MEASURED, `python3 test_training.py`, 2m40s; training data only: spike V0/V1/V2 vs m1_all_masks.csv spike columns; V4b/V5/V6h regenerated with conda yosys 0.38 plain via research/c3/v456/tools/synth_any.sh vs v456 mask data)
V0 255/255 exact, V1 255/255, V2 spike 252/255 (3 over-predictions 4 vs 3, within 1 on 255), V4b 255/255, V5 81/81, V6h 222/222; 0 bound violations; 0 cases pred>=3 with truth 1. Design was not iterated on the held-out data (not opened). The predictor was developed with these training data in view, so training agreement is optimistic.
