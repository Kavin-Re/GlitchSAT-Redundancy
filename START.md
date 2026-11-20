# START HERE (10-minute path)


What this is: a model-only study of whether redundant copies of a boot check really protect a decision against modelled single-cycle bit flips in a gate-level netlist. Toy 8-bit designs V0 (naive), V1 (two compare copies), V2 (three copies). No hardware, nothing physical, no novelty claim.

## Minutes 0 to 3: read two things
1. `README.md`, the top screen: the problem sentence and the one-glance table (V2 needs 3 flips for the full word on the stored netlist, 2 on an apt-0.33 re-synthesis, 1 for the accept flag `boot_ok` or if any one assumption changes).
2. `docs/OWNER_DERIVATION_SHEET.md` question 1 (one shared wire beats guards). It takes two minutes and gives the idea of the whole project.

## Minutes 3 to 8: run the three commands that work
Run them on a copy, because they rewrite `results/` and `tb/`.
```
cp -r <repo> /tmp/proj_copy && cd /tmp/proj_copy
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
```
Counts as of 2026-11-20 (re-measured by RECON6 on the unpacked bundle): root `pytest tests` 189 passed, 2 skipped (190 collected; unpacked bundle plus `pip install ./product[test]`, no numpy, no browser; with numpy and no product CLI on PATH a dev tree gives 202 passed, 1 skipped); product tests 324 passed; mutation score (REPORTED) root 72.5%, product 67.6% (quote your own counts). Expected: the first finds an attack with 1 flip on the shared net `ok`; the second says NO_ATTACK_UP_TO_BOUND (no 2-flip attack on the word, 6 cycles); the third finds an attack with 1 flip on `boot_ok`. Each prints its bound. Optional full sweep: `make reproduce && make check-reproduce` (about 25 s; needs yosys, iverilog, `pip install -r ci/requirements-ci.txt`).

## Minutes 8 to 10: know where the evidence is
| Question | File |
|---|---|
| Current status, every bound | `docs/FINAL_STATUS.md` |
| Which assumptions move the number (360-cell matrix) | `research/c2/b2_scope/B2_REPORT.md` |
| Number depends on the consumer's width | `research/c3/m1/M1_REPORT.md` |
| Number depends on synthesis (864 configs; V2 180/60/24 of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3; previously shown by SYNFI, 3->2 and 4->2; our E2 replicates it on a toy design) | `research/c2/e2_variance/E2_REPORT.md` |
| 6 of 32 vs 32 of 32 replicated (64 of 64 rows, one recipe list) | `research/c3/rep/REP_REPORT.md` |
| Predictor audit (150 of 163, 92%; baselines 62% always-1, 83% lower bound alone) | `research/c4/ver/VER_REPORT.md`, `research/c5/da3/DA3_REPORT.md` |
| Rail dips and layout geometry | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |
| Numbers in one place (run `python3 scripts/check_numbers.py`) | `docs/NUMBERS.md` |
| Which counting rule, and why | `research/c3/r22/R22_REPORT.md` |
| Bounded and unbounded checks | `formal/FORMAL.md`, `validation/VALIDATION.md` |
| Prior art | `docs/PRIOR_ART.md` |
| Problem statement versions | `docs/dossier/PROBLEM_STATEMENT_EVOLUTION.md` |
| Dashboard | `dashboard/index.html` |

## What is NOT proven
- Nothing physical: faults are modelled flips; no chip, glitch, fabrication or sign-off. Layouts are flow demos.
- Not novel: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the method (k-FRP and FIVER full texts unread). Third-party tools: uArchiFI run on 9 of 9 cells, same minimum flips as ours (one tool, three toy designs; not a validation; counting unit matters); k-FRP built but answers a different question; FIVER not built or run (RUN2, measured).
- Neither fault-counting rule (stem = 1, or cost = fanout) has been shown physical. Stem = 1 is the headline rule (R22).
- All bounds are 6 cycles, k <= 3 on toy designs; the single unbounded proof is for one netlist, k <= 2, word goal, and was not replicated by a second tool.
- The scope options (consumer bits, input sites, power-up modes, sweeps) are now in `product/` (PS4, PS5); the branch counting rule and per-cycle input are not shipped. The structural predictor is a research script: 92% exact on 150/163 fresh cells (62% for always-1, 83% for the lower bound alone), 58% on multi-flip cells, 4/6 on fresh RTLs (LEDGER), not faster; the solver is the reference. The consumer-mask rule is the minimum of Hamming distance to idle states and the number of comparator copies touched: known-style cut/Hamming reasoning, not a discovery; exact on spike V2 (255/255), 187/255 on apt (DA3).
- **Safety:** RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the lead re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action's two shell steps were run locally in a clean venv (MEASURED by the lead, 2026-11-20; the `uses:` steps and the SARIF upload cannot run off GitHub, so nothing ran on GitHub), and the Dockerfile was built and run locally only after adding the sandbox proxy's CA to a COPY of it (shipped Dockerfile unchanged; not built on a normal network). Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. RT3 (`research/c5/rt3/RT3_REPORT.md`, MEASURED, 2026-11-20 about 02:xx UTC) re-attacked the fix with about 300 payloads and found 0 canaries on the paths RT2 listed, one remaining path of the same class in a classroom script (`docs/edu/tools/synth_merge.sh`, since fixed by the lead; verified netlist identity v2 d776226e, v1 931050a5; lead canary re-test 2026-11-20 02:15) and an uncapped `--cycles` (fixed by H4: more than 200 is exit 3). Residual limits unchanged: Yosys unsandboxed, Action steps run locally only (not on GitHub), Dockerfile built and run locally only (proxy-CA copy; not on a normal network). Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).
- Rail dips (SIMULATED basis, bounded T=6, 3 events): under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication; SPICE supports 1-to-0 for supply dips, EM literature reportedly describes set-to-1 (UNVERIFIED, snippet level); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug). V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates). Brute-force anchors now exist (agent ANCHOR, z3-free simulator, `research/c5/anchor/`): V2 spike stem flips (k<=2 none at T=4; 182 attacking triples at k=3), V2 apt pairs (3 attacking pairs at k=2), B3 rail models (32 rows, T=4, k<=2, all agree with z3) and selective sets (22 sets of size 3, none of size 1 or 2). Still z3-only: T=6 rail events at k=3, and V5. B3, LAYOUT; r = 2.95 um, one supply net, no extraction; ledger `research/c5/ledger/LEDGER.md`.
- Consumer-mask figures (M1): rechecked by M1b with two engines: no cell changed (0 of 1785; research/c4/m1b/M1B_REPORT.md).
