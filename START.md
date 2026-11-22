# Start here (10 minutes)

**GlitchSAT: How Many Glitches Does Redundancy Stop?** Bounded SAT-based fault analysis of redundant boot checks. Author: Kavin.K.K. Licence: Apache-2.0.

GlitchSAT is a model-only study: does doing a boot check two or three times protect the decision against modelled single-cycle bit flips in a gate-level netlist? Three toy 8-bit designs: V0 (one check), V1 (two checks joined by one wire), V2 (three checks with separate output bits). No hardware, nothing physical, no novelty claim.

## Minutes 0 to 3: read two things

1. [`README.md`](README.md), "In plain words" and "Results at a glance": V2 needs 3 flips for the full word on the stored netlist, 2 on an apt Yosys 0.33 re-synthesis, and 1 for the accept flag `boot_ok` or when one of the scope assumptions changes.
2. [`docs/DERIVATION_SHEET.md`](docs/DERIVATION_SHEET.md), question 1 (why one shared wire beats several checks). It takes two minutes and gives the idea of the whole project.

## Minutes 3 to 8: see it run

Either open the app (from the repository root):

```
bash tools/studio/glitchsat-studio.sh
```

or run three commands. They need Python 3 and z3 (`pip install z3-solver`, inside a venv on Linux Mint or Ubuntu) and use the stored netlists, so no Yosys is needed:

```
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
```

Expected: the first finds an attack with 1 flip on the shared net `ok`; the second says `NO_ATTACK_UP_TO_BOUND` (no 2-flip attack on the word, 6 cycles); the third finds an attack with 1 flip on `boot_ok`. Each prints its bound.

Optional full sweep: `make reproduce && make check-reproduce` (about 25 s; needs `sudo apt-get install -y yosys iverilog` and `pip install -r ci/requirements-ci.txt`). These rewrite files under `results/` and `tb/`. Test counts as last recorded: root `pytest tests` 189 passed, 2 skipped; product tests 324 passed (`tests/test_cli_help.py` was added afterwards). Quote your own counts.

## Minutes 8 to 10: know where the evidence is

Reports under `research/` use short names; [`docs/GLOSSARY.md`](docs/GLOSSARY.md) explains each one and [`research/README.md`](research/README.md) explains the folders.

| Question | File |
|---|---|
| Current status, every bound | [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md) |
| Full written report | [`docs/report/PROJECT_REPORT.md`](docs/report/PROJECT_REPORT.md) |
| Which assumptions move the number (scope matrix, 360 cells) | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) |
| Number depends on how many bits the consumer reads | [`research/c3/m1/M1_REPORT.md`](research/c3/m1/M1_REPORT.md) |
| Number depends on synthesis (864 configs; V2 180/60/24 of 264 solved; 152 distinct netlists: 94/38/20); previously shown by SYNFI, replicated here on a toy design | [`research/c2/e2_variance/E2_REPORT.md`](research/c2/e2_variance/E2_REPORT.md) |
| Why V2 falls to 2 flips on one synthesis | [`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md) |
| Counting rule: 6 of 32 vs 32 of 32 | [`research/c3/r22/R22_REPORT.md`](research/c3/r22/R22_REPORT.md), [`research/c3/rep/REP_REPORT.md`](research/c3/rep/REP_REPORT.md) |
| Numbers in one place (check with `python3 scripts/check_numbers.py`) | [`docs/NUMBERS.md`](docs/NUMBERS.md) |
| Bounded and unbounded checks; independent simulator | [`formal/FORMAL.md`](formal/FORMAL.md), [`validation/VALIDATION.md`](validation/VALIDATION.md) |
| Prior art | [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) |
| Known weaknesses and review findings | [`docs/dossier/CRITIQUE.md`](docs/dossier/CRITIQUE.md) |
| Hard questions | [`docs/dossier/QA_SHEET.md`](docs/dossier/QA_SHEET.md), [`docs/dossier/ONE_PAGE_KEY_POINTS.md`](docs/dossier/ONE_PAGE_KEY_POINTS.md) |
| Browser pages and dashboard | [`docs/explainers/index.html`](docs/explainers/index.html), [`dashboard/index.html`](dashboard/index.html) |

## What is NOT shown

- **Nothing physical.** Faults are modelled flips; no chip, glitch, fabrication or sign-off. Layouts are flow demos.
- **Not novel.** SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the method (k-FRP and FIVER full texts unread). uArchiFI was run on 9 of 9 cells and gave the same minimum flips (one tool, three toy designs; not a validation); k-FRP was built but answers a different question; FIVER was not run (`research/c5/run2/RUN2_REPORT.md`).
- **Bounds.** 6 cycles, at most 3 flips, toy designs: the baseline netlists have under 100 gates; some synthesis-sweep variants reach 141 gates (`research/c2/e2_variance/raw/matrix.csv`). The single unbounded result is for one netlist, k <= 2, word goal, tool-reported and not replicated.
- **Counting rule.** Neither rule (a flipped net counts once, or once per reader) has been shown physical; counting once per net is the headline rule.
- **Consumer-mask rule.** The minimum of the Hamming distance to idle states and the number of copies touched: known-style reasoning, not a discovery; exact on the stored V2 netlist (255/255), 187/255 on the apt re-synthesis.
- **Untrusted input.** The Verilog path calls Yosys, which is not sandboxed: see [`SECURITY.md`](SECURITY.md).
