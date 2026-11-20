# R27: formal-methods upgrades (research + small experiments)

Labels: MEASURED = my command, scratch in /tmp/work_r27 (copies only; tree and envs untouched); SOURCED = web search snippets, NOT read in full (see 1). Modelled bit flips, bounded verdicts unless stated. Nothing here is claimed as new.
Machine: 4 cores, up to 4 of my jobs ran at once, so every time is noisy (a cell can differ by 2x); only order-of-magnitude gaps are reported as findings.

## 1. Literature (SOURCED; search snippets only, I did not open the PDFs)
- Tan, Gao, Song, Chen, Wu, "SAT-based Formal Verification of Fault Injection Countermeasures for Cryptographic Circuits", TCHES 2024 (FIRMER). https://tches.iacr.org/index.php/TCHES/article/view/11782 , arXiv https://arxiv.org/pdf/2307.00561 . SAT encoding of a "circuit with controllable faults" plus a gate-reduction step; the snippet says the prior approach failed on 31 tasks at 24 h. Bounded, SAT-based like glitchsat.
- Tollec et al., k-FRP ("k-fault-resistant partitioning"), TCHES 2024, artifact page https://artifacts.iacr.org/tches/2024/a27/ (search summary: an inductive solution to fault propagation, motivated by scalability limits of bounded techniques; reported on AES with 3 faults). I could not confirm title/authors/venue details beyond that summary, and found no source that combines k-FRP with IC3/PDR. UNVERIFIED beyond that.
- IC3/PDR for unbounded safety proofs; KIC3 (IC3 + k-induction), FMCAD 2017: https://cs.utexas.edu/~hunt/FMCAD/FMCAD17/preprints/s6p3.pdf . PD-KIND (property-directed k-induction for fault-tolerant distributed algorithms) appeared in the same search; not hardware faults.
- SecIC3 (DATE 2026, IC3 customised for non-interference): https://www.alphaxiv.org/abs/2601.21353 . Not fault injection.
- Sound statement of "no k-fault attack for any number of cycles" (my reasoning, standard): put the budget in the transition system. Add a state counter `used` (width >= log2(k+1)), a free per-cycle flip vector, the constraint `used + popcount(flip) <= k` as an assumption every cycle, `used' = used + popcount(flip)`, and the property "goal never observed". Soundness needs: (i) counter wide enough that popcount and the sum cannot wrap (my first wrapper had a 6-bit popcount over 2072 sites and wrapped: it gave a spurious FAIL, see 3e), (ii) the same observation point as the bounded model (flips also applied on observed nets), (iii) a non-vacuity check (honest key, k=0 must FAIL). PASS then means: no execution of any length with <= k flips total reaches the goal, for this netlist and fault model.
- Speedups from the literature/standard practice (not all tested): cone-of-influence and temporal-reach pruning (already in glitchsat `--reduce full`), gate reduction (FIRMER), incremental SAT with assumptions across k, unary counters instead of PB constraints, word-level vs bit-blasted choice, per-fault-site pruning, symmetry between duplicated copies (not tested), sequential-equivalence/invariant strengthening for PDR (not tested).

## 2. Experiments (all MEASURED; script `exp.py`; raw rows `results.jsonl`, `results2.jsonl`)
Netlists: `sbox_dmr` (R20 DMR S-box, 2040 gates 32 flops, goal gout==0x17c, key 1), `uartw` (368 gates), `s2` (V2 spike netlist, goal 0x96), `w2` (V2 repo results/work). Unmodified engine = `scripts/glitchsat.py` (PbLe).
Encodings (all use the engine's own `build`, only the cardinality constraint changes): pb = PbLe (engine), atmost = z3 `AtMost`, seq = Sinz-style unary sequential counter (one-directional), incr = one seq counter, one solver, assumptions k=0..kmax, bb = seq + bit-blast tactic (simplify, solve-eqs, bit-blast, tseitin-cnf, sat).
Solve times in seconds (build excluded); TO = timeout (150 s unless noted).

| cell | pb (engine) | atmost | seq | incr (all k up to it) | bb |
|---|---|---|---|---|---|
| s2 k=2 T=6 (UNSAT) | 2.7 | 4.3 | 0.26 | 0.08 | 0.30 |
| s2 k=2 T=12 (UNSAT) | TO | - | 0.45 | - | - |
| s2 k=2 T=20 (UNSAT) | TO | - | 1.6 | - | - |
| s2 k=3 T=6 (SAT) | 8.7 | 13.6 | 0.45 | 0.49 total | - |
| w2 k=1 T=6 (UNSAT) | - | - | - | - | 0.16 |
| w2 k=2 T=6 (SAT) | 0.6 | 0.9 | 0.18 | 0.07 | - |
| dmr k=1 T=4 (UNSAT) | 149 (R20: 62) | TO | 3.5 | 3.5 (k=0,1) | 5.5 |
| dmr k=1 T=4, reduce none | - | - | 13.3 | - | - |
| dmr k=1 T=8 (UNSAT) | TO (200 s) | - | 97 | - | - |
| dmr k=2 T=4 (SAT) | 4.0 | 7.4 | 7.6 | 4.4 total (k=0,1,2) | - |
| dmr k=3 T=4 (SAT; min is 2) | 25.7 | 35.9 | 7.3 | - | - |
| uart k=0 T=60 reduce none (UNSAT) | 0.8 | - | 0.9 | - | - |
| uart k=3 T=60 reduce none (SAT; min 1) | 4.5 | - | 32.6 | - | - |
| uart k=3 T=6 / T=30 (SAT) | 0.8 / 2.9 | 1.1 / 2.5 | 0.6 / 8.4 | 1.96 / 42 incl. k=0 | - |

Findings:
1. The two R20 "unfinished" cells are not hard in the sense expected. dmr k=3 T=4: not "no attack", it is SAT (an attack exists; minimum is 2 flips, same as k=2). uart k=3 T=60: SAT (min 1 flip), 4.5 s with `--reduce none`. The real hard cell is UNSAT: dmr k=1 (T=4: 149 s -> 3.5 s with seq; T=8: engine TO at 200 s, seq 97 s).
2. The sequential counter is the best encoding for proofs of absence: 10x to 40x faster on UNSAT cells (s2 k=2 T=10: 26 s -> 0.5 s in the agreement run), and it makes s2 k=2 T=12 and T=20 finish where PbLe times out. `AtMost` is no better than PbLe. It is slightly slower than PbLe on some SAT cells (uart k=3 T=60 4.5 -> 33 s), which does not matter for the "no attack" question.
3. Incremental k with assumptions gives the whole k=0..k answer for about the cost of the last UNSAT step, and the existing minimisation loop (push/pop with a fresh PbLe each time) can reuse it. The patch does this.
4. Build time, not solve time, dominates uart at T>=30: 92-140 s build (per-node `simplify` in `reduce full/coi`) against 5.7 s with `--reduce none`, where solving was still fast. For small T `full` is fine. Cone-of-influence pruning per cycle is already in the engine (`full`); `none` and `coi` were not slower on dmr k=3 (25.3, 27.6 vs 25.7 s), so pruning buys little solve time there.
5. Bit-blast: the hand-built bit-level pipeline works with `bit-blast` (my first attempt without it returned unknown immediately; those cells are not reported) and is in the same range as word-level seq (5.5 vs 3.5 s on dmr), no clear gain. PbLe cannot go through it.
6. Not tested: symmetry breaking between the two S-box copies, sequential-equivalence, k-induction with lemmas.

## 3. Verdict agreement, unmodified engine vs patched engine (`agree.py`, `agree.jsonl`, same netlists, same goal)
Same verdict and same minimum fault count on every cell where both finished: s2 k=0..3 (T=6), w2 k=0..3 (T=6), s2 k=2 T=10, dmr k=0 and k=2 (T=4), uart k=0 and k=1 (T=6): all agree. dmr k=1 T=4: old engine timed out at 120 s under load (UNKNOWN_TIMEOUT), new said NO_ATTACK_UP_TO_BOUND in 6.3 s, consistent with the earlier 149 s UNSAT from pb. A few later rows of the file (uart k=1 and k=2 T=12) may be missing: I stopped the job at the time cap. Cells are few; this is agreement on 14 cells, not a proof of equivalence.

## 3e. ABC PDR with the flip budget as a state counter (`gen2.py`, `runpdr.sh`, sby `abc pdr`, formal env)
| netlist, k | counter style | result | wall |
|---|---|---|---|
| s2 k=2 | project (16-bit adder `used`) | PASS | 2.6 s |
| s2 k=2 | saturating-width binary counter (`sat`) | PASS | 1.4 s |
| s2 k=2 | unary thermometer counter | PASS | 2.9 s |
| s2 k=3 | `sat` | FAIL (cex exists, trace not rebuilt, no yices) | 1.5 s |
| w2 k=1 / k=2 | `sat` | PASS / FAIL | 1.5 s each |
| dmr k=1 | `sat` (16-bit popcount) | TIMEOUT at 400 s, no verdict | 400 s |
| dmr k=2, k=3, uart k=1..3 | `sat` | not finished (run cut at the time cap); uart k=1 had FAIL earlier with the wrapper bug only, so not reported | - |
These reproduce the earlier PDR result (s2 k<=2 PASS, k=3 FAIL; w2 k=1 PASS, k=2 FAIL), with the counter width chosen per design; the counter style changes time by about 2x only. PDR does not scale to the 2040-gate DMR S-box (no verdict in 400 s), so the unbounded claim stays limited to the small V2 netlists; at that size the bounded engine with seq is also sub-second to seconds.
Wrapper bug found and fixed in my copy: an earlier wrapper of mine used a popcount width of 6 bits for 2072 flip inputs; the sum wrapped and PDR returned a spurious FAIL for dmr k=1 (47 s). The project's own wrapper uses 16 bits, so is fine for designs under 65k sites; there is no assert on this, worth adding.

## 4. Recommendation
Adopt the sequential counter plus assumption-based "at most j" (patch `seq_counter.patch`, 63 lines, glitchsat.py only, NOT applied to the tree). Expected effect (MEASURED above): 10-40x on UNSAT cells, same verdicts and minima on the 14 cells compared. Also add: `--reduce none` as the fast-build choice when T*gates is large (uart T>=30); an assert/width check in `formal/src/gen_wrapper.py` that `used` can hold sites+K. Re-run the full `make check` (not done, and the patch changes which witness the solver returns, so any test that pins a specific fault list may need updating; I did not check the test suite).
Files here: `seq_counter.patch`, `exp.py`, `results.jsonl`, `results2.jsonl`, `agree.jsonl`, `gen2.py`, `runpdr.sh`.

## 5. Not done / limits
- Literature not read in full; k-FRP details UNVERIFIED. No third-party fault tool run.
- Timings under 3-4 parallel jobs; no repeats.
- PDR on dmr/uart did not finish; no unbounded claim beyond the earlier s2/w2 results.
- Symmetry, sequential equivalence, per-site pruning beyond the engine's own, boolector word-level were not tried.
