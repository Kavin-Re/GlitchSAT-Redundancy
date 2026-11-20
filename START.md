# GlitchSAT: How Many Glitches Does Redundancy Stop?

Bounded SAT-Based Fault Analysis of Redundant Boot Checks. Start here (10-minute path); repository name: GlitchSAT-Redundancy.

GlitchSAT-Redundancy is a model-only study of whether redundant copies of a boot check really protect a decision
against modelled single-cycle bit flips in a gate-level netlist. Toy 8-bit designs: V0 (naive), V1 (two compare
copies), V2 (three copies). No hardware, nothing physical, no novelty claim.

## Minutes 0 to 3: read two things
1. [`README.md`](README.md), sections "What this is" and "Results at a glance": V2 needs 3 flips for the full word on
   the stored netlist, 2 on an apt Yosys 0.33 re-synthesis, and 1 for the accept flag `boot_ok` or when one of the
   scope assumptions changes.
2. [`docs/OWNER_DERIVATION_SHEET.md`](docs/OWNER_DERIVATION_SHEET.md), question 1 (one shared wire beats the guards).
   It takes two minutes and gives the idea of the whole project.

## Minutes 3 to 8: run three commands
They need Python 3 and `pip install z3-solver`, and use the stored netlists (no Yosys needed). Run from the repository root.
```
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
```
Expected: the first finds an attack with 1 flip on the shared net `ok`; the second says `NO_ATTACK_UP_TO_BOUND` (no
2-flip attack on the word, 6 cycles); the third finds an attack with 1 flip on `boot_ok`. Each prints its bound.

Optional full sweep: `make reproduce && make check-reproduce` (about 25 s; needs yosys, iverilog and
`pip install -r ci/requirements-ci.txt`). These rewrite files under `results/` and `tb/`.

Test counts as last recorded (2026-11-20): root `pytest tests` 189 passed, 2 skipped (190 collected on the unpacked
bundle with `pip install ./product[test]`, no numpy, no browser; a development tree with numpy and without the product
CLI on PATH gives 202 passed, 1 skipped); product tests 324 passed; mutation score (REPORTED, not re-run) root 72.5%,
product 67.6%. Quote your own counts.

## Minutes 8 to 10: know where the evidence is
Reports under `research/` use short codenames; [`docs/GLOSSARY.md`](docs/GLOSSARY.md) explains each one.

| Question | File |
|---|---|
| Current status, every bound | `docs/FINAL_STATUS.md` |
| Full written report | `docs/report/PROJECT_REPORT.md` |
| Which assumptions move the number (scope matrix, 360 cells) | `research/c2/b2_scope/B2_REPORT.md` |
| Number depends on the consumer's width | `research/c3/m1/M1_REPORT.md` |
| Number depends on synthesis (864 configs; V2 180/60/24 of 264 solved configs; 152 distinct netlists: 94/38/20). Previously shown by SYNFI (3->2 and 4->2); this study replicates it on a toy design | `research/c2/e2_variance/E2_REPORT.md` |
| Why V2 falls to 2 flips on one synthesis | `docs/report/WHY_TWO_FLIPS.md` |
| Counting rule: 6 of 32 vs 32 of 32, replicated (64 of 64 rows, one recipe list) | `research/c3/r22/R22_REPORT.md`, `research/c3/rep/REP_REPORT.md` |
| Structural predictor audit (150 of 163, 92%; baselines 62% always-1, 83% lower bound alone) | `research/c4/ver/VER_REPORT.md`, `research/c5/da3/DA3_REPORT.md` |
| Rail-dip event models and layout geometry | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |
| Numbers in one place (run `python3 scripts/check_numbers.py`) | `docs/NUMBERS.md` |
| Bounded and unbounded checks; independent simulator | `formal/FORMAL.md`, `validation/VALIDATION.md` |
| Prior art | `docs/PRIOR_ART.md` |
| Known weaknesses and review findings | `docs/dossier/CRITIQUE.md` |
| Hard questions | `docs/dossier/QA_SHEET.md` |
| Problem statement versions | `docs/dossier/PROBLEM_STATEMENT_EVOLUTION.md` |
| Dashboard | `dashboard/index.html` |

## What is NOT proven
- **Nothing physical.** Faults are modelled flips; no chip, glitch, fabrication or sign-off. Layouts are flow demos.
- **Not novel.** SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the method (k-FRP and FIVER full texts
  unread). Third-party tools: uArchiFI was run on 9 of 9 cells and gave the same minimum flips (one tool, three toy
  designs; not a validation; the counting unit matters); k-FRP was built but answers a different question; FIVER was
  not built or run (`research/c5/run2/RUN2_REPORT.md`, MEASURED).
- **Counting rule.** Neither rule (a flipped net counts once, or once per reader) has been shown physical. Counting
  once per net is the headline rule (`research/c3/r22/R22_REPORT.md`).
- **Bounds.** All bounds are 6 cycles, k <= 3, on toy designs. The single unbounded proof is for one netlist, k <= 2,
  word goal, and was not replicated by a second tool.
- **Tool vs research scripts.** The scope options (consumer bits, input sites, power-up modes, sweeps) are in
  `product/`; the per-reader counting rule and per-cycle attacker input are not. The structural predictor is a research
  script: 92% exact on 150/163 fresh cells (62% for always-1, 83% for the lower bound alone), 58% on multi-flip cells,
  4/6 on fresh RTLs, not faster; the solver is the reference.
- **Consumer-mask rule.** The minimum of the Hamming distance to idle states and the number of comparator copies
  touched: known-style cut/Hamming reasoning, not a discovery; exact on the stored V2 netlist (255/255), 187/255 on the
  apt re-synthesis. The mask figures were rechecked with two engines: no cell changed (0 of 1785;
  `research/c4/m1b/M1B_REPORT.md`).
- **Rail-dip rows (SIMULATED basis, bounded T=6, 3 events).** Under the 1-to-0-only rail model V1, V2 and V5 survive
  within the bound (V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with
  one event (V1 and V0 too): survival depends on polarity, not on triplication. The "rail" is the netlist hierarchy,
  not a physical rail; no extraction was done (`research/c4/b3/B3_REPORT.md`, `research/c5/ledger/LEDGER.md`,
  `research/c5/anchor/ANCHOR_REPORT.md`).
- **Running on untrusted input.** An earlier red-team pass found that a module name or Verilog path could be pasted
  into a Yosys command (command execution). The names are now validated and written to a Yosys script file instead
  (`scripts/synth.sh`, `scripts/glitchsat.py check`, `product/`, `docs/edu/tools/synth_merge.sh`), and `--cycles` is
  capped at 200 in the product. Yosys itself is not sandboxed, the GitHub Action was only run locally and the
  Dockerfile was only built locally, so do not run the Verilog path or the Action on untrusted input. History and
  remaining findings: `research/c5/rt2/RT2_REPORT.md`, `research/c5/rt3/RT3_REPORT.md`, `docs/dossier/CRITIQUE.md`.
