# VER_REPORT: adversarial audit of the "structural predictor 928/928" result
2026-11-19. Licence: UNDECIDED. Toy designs, modelled bit flips, no hardware claim. All numbers MEASURED by the commands/files listed; predictor.py (sha a9e43ef9...3170 = FROZEN.sha256) was imported unmodified; nothing in research/c4/pre or test was edited. Work dir /tmp/work_ver, copies in this folder.

## 1. Leakage (read line by line)  -> NO LEAKAGE FOUND
- predictor.py: imports only json, sys, heapq, random, itertools, argparse (line 27); no z3/SAT. The only file read is the netlist, `json.load(open(path))` (line 57). No CSV/truth/M1/E2 path appears (grep for open/csv/solver/z3/truth). `random` used only if the attacker input is >12 bits (seeded), not in these cells.
- run_test.py: `predict(path, top, **kw)` (line 12) gets netlist path, top, mask/goal/accept/key/T only. The solver value is carried in the job tuple and written to the CSV after the call (lines 9-17); it is never passed in. No parameter selection uses truth. Predictor frozen before the run (hash equal).
- Residual (not leakage, but real): the predictor was developed with V0/V1/V2/V4b/V5/V6h training data in view (PRE says so), and the R20 accept/key/mask encodings were hand-transcribed by TEST.
- Semantic differences predictor vs solver (found): predictor holds all non-attacker inputs at 0, the solver leaves them free (irrelevant for the 1-input designs here); predictor skips 'x' init bits, M1's gs_mask.py copy turns 'x' into 0 and can clobber an aliased flop's real init (see 3.3). scripts/glitchsat.py itself rejects x init (lines 109-110).

## 2. Independent resample of 60 corpus cells (`resample.py`, `resample.csv`, `resample.log`)
Seed 20261119; stratified: all 20 min-3 E2 cells sampled (all 20 min-3 cells that exist), 12 of 53 min-2 E2, 6 min-1 E2, 8 min-2 + 4 min-1 M1 V2, 3 M1 V1 min-1, 3 collisions (min 0), 4 R20. Solver truth re-run fresh with a COPY of M1's gs_mask.py (z3 5.4.1, T from CSV, k<=3, minimised, timeout 300 s); predictor re-run fresh.
Result: 60/60 rows reproduce (my solver == CSV solver_min, my pred == CSV pred). Solver truth: 20x3, 20x2, 17x1, 3x0. CPU: predictor 73 s total vs solver 1625 s total on this sample (E2 min-3 cells are slow for z3; machine under load). `python3 -I resample.py`. The CSV is faithful; the 928/928 is not a transcription artefact.

## 3. Fresh held-out (`gen.py`, `heldout.py`, `heldout.csv`, `rerun_x.py`, `manifest.json`, `gen/`)
76 NEW netlists (apt yosys 0.33 via scripts/synth.sh, plain or opt flow), 163 (netlist, mask) cells (full mask + 1 random mask each; 3 random masks for V456), none seen by PRE/TEST:
- rc (28): random FSM/counter phase decode (3-6 flops) + 1-3 keep_hierarchy compare copies + and/vote combiner + registered output, random widths/keys/accept; 
- rand (14): random sequential logic, 3-8 flops, 10-60 gates, outputs from random nodes;
- crc (22): CRC / LFSR-compare / parity checkers with 1-3 redundant copies, 1/4/8-bit goals;
- V456 (12): v4, v4b, v5, v6, v6bh, v6h under apt-0.33 plain AND opt (same RTL family PRE trained on, new flows).
Truth: glitchsat model, T=6, k<=3, timeout 150 s per cell; 0 unknowns; `>3` compared as 4, pred capped at 4 (PREREG rule).
### 3.1 Results (MEASURED; 163 cells / 76 netlists)
| | n | exact | within 1 | pred>solver (over) | pred<solver (under) |
|---|---|---|---|---|---|
| all | 163 | 150 (92.0%) | 156 (95.7%) | 6 | 7 |
| solver 0 | 33 | 33 | 33 | 0 | 0 |
| solver 1 | 99 | 99 | 99 | 0 | 0 |
| solver 2 | 15 | 12 | 15 | 3 | 0 |
| solver 3 | 5 | 2 | 5 | 3 | 0 |
| solver >3 | 11 | 4 | 4 | 0 | 7 |
| solver>=2 (31) | 31 | 18 (58%) | 24 | 6 | 7 |
By family: rc 49/53, rand 19/26, crc 36/36, V456 46/48. 65 of 76 netlists have all cells exact.
Confusion (solver,pred): (0,0)33 (1,1)99 (2,2)12 (2,3)3 (3,3)2 (3,4)3 (>3,>=4)4 (>3,2)7.
Bounds: lb > solver 0 cases; est (verified witness) < solver 0 cases (after 3.3). false-safe (pred>=3, solver 1): 0. false-weak (pred 1, solver>=2): 0. So C1/C4/C5 hold; C2 92.0% (>=90%) passes narrowly but only because 124 of 163 cells are trivially 0 or 1; C3 within-1 95.7% FAILS the 98% bar.
### 3.2 Where it fails
- Over-prediction (6): est search misses a combination: rc110 full mask solver 3 pred 4; rc112, rc116, rc124 solver 2 pred 3; V456 v5 full mask under apt-0.33 plain and opt solver 3 pred 4 (the training claim was 81/81 on v5 under conda-0.38 plain). Cause: the combination search takes one site per effect class, and joint effects of flips that are individually ineffective are missed. Conservative direction.
- Under-prediction (7, all `uncovered` fallback pred=lb+1=2, solver >3): rand 202 (x2), 204, 208, 209 (x2), 212. The lb+1 fallback is not a bound; it said "2 flips" where the solver proves no attack with <=3. This is the unsafe direction (it claims an attack that does not exist at k<=3... or at least that the solver cannot find) and shows `uncovered` should be reported as "unknown", never as a number. In 4 further >3 cells the structural lb was 99 (pred 100) which is correct in meaning.
- The 1-flip predictions were never wrong in 99/99 solver-1 cells, and the 2-3 flip structure was only exact in 14/20.
### 3.3 Solver-side finding (not a predictor error)
Two cells initially disagreed (rc103_opt mask 0x18 solver 1 vs pred 0; rc117_opt mask 0xf solver 1 vs pred 2). Cause: with the opt flow yosys merges aliased output bits and writes init 'xx1001'; gs_mask.py (M1 copy, same parse as the older glitchsat) maps 'x'->0 and the later alias clobbers the real init of the shared flop. With a patched copy (gs_mask2.py, skip x, as the predictor does) the solver gives 0 and 2, i.e. the predictor was right. I used the corrected values in the table (`rerun_x.py`, 47 x-init cells rerun, 2 changed). Implication: any prior corpus netlist with x init bits under gs_mask.py could carry the same truth error; scripts/glitchsat.py rejects x init so the main engine is not affected.
### 3.4 Runtime (not controlled, machine loaded)
Predictor total 251 s vs solver 184 s on the 163 held-out cells: ratio ~1.4x SLOWER. The solver is fast on these (<1 s typical); the predictor's cost is the joint-simulation combination search. No speedup claim survives; the 3-7x in TEST_REPORT applies only to the heavy min-3 V2 cells.

## 4. What the predictor really is
A fault-free simulation + structural cone set-cover lower bound (necessary, sound in every cell here) + a verified attack search: `est` is found by enumerating combinations of single-flip effect classes (<=3000 per size) and checking each by joint fault simulation. `pred = est`, so pred equals the cost of a witness attack found by a heuristic, incomplete, solver-free attack search (an explicit-state search guided by single-flip effect sets), not a closed-form structural count. When it finds a witness it is an upper bound by construction; it equals the solver minimum whenever the heuristic search finds the optimum, and lb/est tie. It is NOT a lower-bound proof: when lb<est, nothing certifies minimality, and the fallback lb+1 is unverified.
Why 928/928 was too clean: 684 cells are min-1 (single-flip witness is found by the first search level), 54 are collisions (D empty), leaving 190 cells of min 2-3, which come from ~3 designs (V0/V1/V2 re-synthesised, M1 masks of one V2 netlist, 6 R20 wrappers). Effective independent sample size for "min>=2": roughly 3-5 distinct designs plus 1 distinct non-toy cell (sbox_dmr, the only `uncovered`-fallback hit, correct by luck of lb+1). 
## 5. Verdict
"The structural predictor is validated": NOT supportable as stated. PARTLY: supportable for (a) soundness of the lb bound (0 violations in 928+163+60 cells), (b) correct classification of "single-flip breakable (1)" vs not on the tested families (99/99 + 684/684, zero false-safe, zero false-weak), (c) exact count on the V0/V1/V2 family. Not supported: exact min-flip count for 2-3 flip attacks outside that family (18/31, within-1 24/31; my own fresh circuits fail the 98% within-1 criterion), runtime advantage, and any use of `uncovered` as a number.
Suggested wording for the author: "On held-out toy netlists the solver-free predictor never underestimated the attacker's effort when it found a witness, and matched the solver exactly on the V0/V1/V2 family (928/928, but these are near-duplicate cells, effective sample of a few designs). On 76 fresh random/CRC/FSM netlists it matched the solver on 92% of cells (58% of cells needing 2 or more flips) and was off by more than one flip in 7 cells. It is a heuristic attack search with a structural lower bound, not a validated estimator; the SAT solver remains the reference."
## Limits
T=6, k<=3, one goal shape (consumer word with constant attacker input), single attacker input; my circuits are random toys (rand family mostly min 0/1/>3); truth from a copy of the solver (patched for x init in 47 cells); 76 netlists, ~25 cells with min>=2 outside the V2 family; cells per netlist not independent; runtimes contended.
## Commands
`python3 -I gen.py` ; `for d in v4 v4b v5 v6 v6bh v6h; for f in plain opt: sh scripts/synth.sh research/c3/v456/rtl/$d.v $d gen/V456_${d}_$f.json $f` ; `python3 -I heldout.py` ; `python3 -I rerun_x.py` ; `python3 -I resample.py`. Analysis snippets were inline python over heldout.csv (confusion matrix above).
