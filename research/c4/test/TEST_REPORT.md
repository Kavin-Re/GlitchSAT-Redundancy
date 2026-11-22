# TEST_REPORT: held-out evaluation of the pre-registered structural min-flip predictor
2026-11-19. Licence: UNDECIDED. Toy designs, modelled faults (single-cycle bit flips), no hardware claim. Every number is MEASURED by the commands below unless stated.

## STEP 0: frozen files (MEASURED)
`sha256sum research/c4/pre/predictor.py research/c4/pre/PREREG.md` gave
- predictor.py a9e43ef93724352d5c04acaf420463cf9d069f9ff5cef1dc1c20aa82ea793170
- PREREG.md   f813674c7597acc912ae28ab26b5e91ed9f529297226e847d2bff70534759f1d
Both equal `FROZEN.sha256`. Nothing in research/c4/pre was edited. The predictor is imported unmodified (`from predictor import predict`, same function the CLI calls), default arguments except goal/mask/accept/key/T per cell; nothing tuned.

## Method and commands
```
cd research/c4/test
python3 -I run_test.py e2 ; python3 -I run_test.py m1 ; python3 -I run_test.py r20   # -> cells_e2.csv cells_m1.csv cells_r20.csv
python3 -I analyze_test.py                                                            # -> cells_all.csv, analysis.txt
```
Cell = (netlist, goal, mask, T). Solver reference = the stored glitchsat (z3) minimum from the held-out data; the predictor never reads it.
- (a) E2: `research/c2/e2_variance/raw/matrix.csv`; netlists = E2's own stored outputs `/tmp/work_e2/nl/<tag>/r1.json` (still present, no re-synthesis needed). Goal boot_word full mask 0xFF, accept 0x96, key 0xC3, T=6, solver min over k<=3. 864 configs: 792 SOLVED, 72 ENGINE_UNSUPPORTED (skipped, no solver verdict; the predictor was not run on them). The 792 solved configs collapse to 407 unique (canonical-sha, design) netlists; one cell per unique netlist (n_configs recorded; config-weighted totals also given). V0, V1, V2 included.
- (b) R20: 11 cells with a solver verdict at the same goal/T (ATTACK_FOUND with min_faults): crc_plain T4, crc_tmr T4, sbox_unprot T4, sbox_par T4, sbox_par2 T4/T8/T16, keymem T8, uart T6/T30, sbox_dmr T4. Netlists from `/tmp/work_r20/work/*.json` (R20's own, plain flow); sbox_dmr.json was not stored, so I re-synthesised it with `scripts/synth.sh sbox_dmr.v sbox_dmr out.json plain` (apt yosys 0.33; 2040 gates + 32 flops, same counts as R20 reports). Not included (no verdict, UNKNOWN): dmr k=3 (timeout), uart k=3 T=60 (no result). k=0 NO_ATTACK runs (sc_crc_k0, sc_par2_k0_T4, sc_uart_k0_T6) say only min>=1; they are consistent with all predictions (pred>=1) and not counted as cells.
- (c) M1: `research/c3/m1/m_v2_apt033.jsonl` (255 masks, T=6) on `research/c2/b1_faultmodels/netlists/v2_apt033.json`; also `m_v1_apt033.jsonl` (255 masks) on v1_apt033.json as an extra group. Netlist file identity with M1's `nl/v2_apt033.json` is UNVERIFIED (M1's working copy is gone; sha of the b1 copy differs from E2's apt baseline sha, probably creator field); the prediction agreed with M1 verdicts on all 255 masks, which supports it being the same design.
- Overlaps: the E2 apt-0.33 V2 baseline and the M1 V2 apt-0.33 full-mask cell are the same design; the pooled count includes both.

## Criteria verdicts (fixed in PREREG.md; applied unchanged; pooled unique cells n = 928; E2 weighted by configs n = 1313 gives identical results)
| criterion | result | verdict |
|---|---|---|
| C1 lb <= solver in 100%; est >= solver in 100% (when not None) | lb > solver: 0/928; est < solver: 0/928 | PASS |
| C2 exact pred == solver >= 90% | 928/928 = 100.0% | PASS |
| C3 \|pred - solver\| <= 1 on >= 98% | 928/928 = 100.0% | PASS |
| C4 pred>=3 with solver==1: 0 | 0 (also pred>=3 with solver<=2: 0) | PASS |
| C5 pred==1 with solver>=2: 0 | 0 | PASS |
| C6 E2 breakable set (solver<=2) recall of pred<=2 >= 90% | E2: 387/387 = 100%; all pooled cells with solver 1..2: 854/854 | PASS |
**Overall: PASS** (C1, C4, C5, C2, C3, C6).

Per group (all numbers in `analysis.txt`): E2 407/407 exact (V0 126, V1 129, V2 152 unique netlists); R20 11/11; M1 V2 apt-0.33 255/255; M1 V1 apt-0.33 255/255. Flags: ok 873, collision 54 (27 + 27 masks where solver min = 0, predictor `collision` pred 0, matched), uncovered 1 (below).

### Confusion matrix (rows solver min, columns pred; pooled unique cells; 4 = ">3" never occurred)
| solver \ pred | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| 0 | 54 | 0 | 0 | 0 |
| 1 | 0 | 684 | 0 | 0 |
| 2 | 0 | 0 | 170 | 0 |
| 3 | 0 | 0 | 0 | 20 |
Per group: E2 1/2/3 = 334/53/20 all diagonal; R20 1:10, 2:1; M1 V2 0/1/2 = 27/112/116; M1 V1 0/1 = 27/228. All diagonal.

### Failures
None (0 cells with pred != solver). Low-confidence correct result: sbox_dmr T4 (solver 2) had no verified combination (`est` None, flag `uncovered`), so pred = lb+1 = 2 was right by the fallback, not by a verified witness. This is the only uncovered cell; it is the only cell in the corpus with solver 2 on a non-toy-size netlist, so the evidence that the lb+1 fallback is reliable is one data point (UNVERIFIED beyond it).

## Runtime (MEASURED, but not a controlled benchmark)
Predictor: per-cell wall time in `cells_*.csv` (`pred_s`), pure Python, 2-4 processes in parallel on a 4-core box, so times are inflated by contention. Solver: times recorded in the original runs (E2 `solve_s`, M1 `s`, R20 `runtime_s.solve_and_minimize`), on the original steps' machines/load, z3 incl. minimisation.
| group | predictor (sum) | solver (sum) | ratio |
|---|---|---|---|
| E2 (407 netlists) | 371.5 s | 2729.5 s | ~7.3x faster |
| M1 V2 apt (255 masks) | 162.5 s | 555.9 s | ~3.4x |
| M1 V1 apt (255 masks) | 163.1 s | 463.0 s | ~2.8x |
| R20 (11 cells, 2040-gate S-box designs, T up to 30) | 161.4 s | 162.9 s (only the k giving the verdict; dmr counted k=1 plus k=2) | ~1.0x; the predictor is SLOWER on the S-box (e.g. sbox_par2 T16: 62 s vs 10.5 s; uart T30 47.7 s vs 31.8 s) and faster only on the small ones and dmr (3.2 s vs 109 s) |
Single call, V2 full mask: `predictor.py v2_apt033.json --top v2` real 0.33 s. Conclusion: a real speedup (about 3x to 7x in sum, per-call under a second to a few seconds) on the small 6-cycle designs the method was built for; no speedup at 2000 gates x longer T, where cost grows ~ sites x gates (as PREREG says). Solver times are not comparable to better than a factor ~2 because machines differ.

## What the result means
All six pre-registered criteria pass on the held-out corpus with zero disagreement. For this corpus the claim "a polynomial structural predictor (cone set-cover lower bound plus simulation-verified upper bound, no solver) reproduces the solver's minimum flip count at T<=6, k<=3" is SUPPORTED. Scope limits: toy scale; the held-out set is the same family of designs as the training set (V0/V1/V2 RTL re-synthesised under 407 flow variants; the same RTL gives structurally similar netlists, so the 407 E2 cells are far from 407 independent samples; M1 is the same two netlists with 255 masks each); most cells are min 1 (684 of 928), so the interesting tail is small (20 cells at 3, all E2 V2, 1 cell at 2 among R20). Genuinely different designs are only the 11 R20 cells (6 distinct wrappers/designs), where it was also right (10/11 with verified witness). Note the predictor only gives the solver's verdict as a number; the solver remains the reference for anything else. Not shown: designs with deep FSM state, T>6 with solver truth (only R20 sbox_par2 T8/T16 and uart T30, all min 1), min>=3 outside V2, any ">3" case, or unsupported-cell netlists (72 E2 configs).
The fallback on 'wrapper with scope reporting' is therefore NOT needed on this evidence; if the criteria had failed that is what would have remained.

## Comments (not altering verdicts)
- C2/C3 percentages on pooled cells are dominated by trivially-1 cells (74%), and the 54 collision cells (solver 0, pred 0) are easy by construction; a stratified criterion (per min-value recall) would be more informative. Reported per value in the confusion matrix: min 3 recall 20/20, min 2 170/170.
- Pooling E2 configs and M1 masks treats near-duplicate cells as independent; effective sample size is much smaller than 928.
- C6 is defined on E2 only but is also given pooled; both 100%.
- The test only exercised the one goal shape (consumer-checked word, attacker input constant). The R20 goal encodings (accept/key/mask for each wrapper) were transcribed by me from R20's logged bound text; a transcription error would have shown up as a mismatch, none did.
- I skipped the 72 ENGINE_UNSUPPORTED E2 configs although the predictor supports those gate types; running them without a solver verdict could not test anything.

## Files
`run_test.py`, `analyze_test.py`, `cells_e2.csv`, `cells_r20.csv`, `cells_m1.csv`, `cells_all.csv` (every cell: group, cell id, netlist, top, goal port, mask, T, solver_min, lb, est, pred, flag, ub_direct, pred_s, n_configs, example_cfg), `analysis.txt`, this report. Work copy: /tmp/work_test (sbox_dmr.json/.v, logs).
