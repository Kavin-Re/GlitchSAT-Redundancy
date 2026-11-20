# DASH2 report: dashboard text/data sync
Work copy /tmp/work_dash2, applied to the tree after tests; make not run. Backups of the originals: research/c5/dash2/backup/ (build.py, template.html, index.html, plus verify_numbers_c4.py). Changed in the tree: dashboard/build.py, template.html, index.html. Look, layout and tokens unchanged (one class `.b-UNMEASURED` reuses the existing `--ill` token).

## Changes (all on the Scope tab unless noted)
1. Rail-dip card replaced by the reconciled statement (SIMULATED): under a 1-to-0-only model V1, V2, V5 survive within the bound (>3, bounded, not a proof); a rail-wide 0-to-1 event on the three copies costs 1 event on V2 and V5 (and V1, V0), so survival depends on polarity; selectivity costs 1; SPICE supports 1-to-0 for supply dips only; "domain" = netlist hierarchy, not a physical rail. Table from B3 matrix kept. Sources: research/c5/anchor/RAIL_RECONCILIATION.md, ledger.
2. E2 card: "V2: 180 / 60 / 24 of 264 solved configs; 152 distinct netlists: 94/38/20" (DA3 count; note that verdicts never differ within a distinct netlist).
3. New ledger card: stage tables from research/c5/ledger/ledger.csv, real HTML tables (caption, th scope col/row), every cell has a MEASURED/SIMULATED/UNMEASURED badge. 92 cells, 4 designs; the csv has 5 stages plus the 4b boot_ok sub-table (6 tables). ledger.png is referenced, not embedded.
4. Counting-rule line (spike V2 word: 3/3/3 under stem/fanout_pins/fanout_gates; input sites on: stem 1, fanout_pins 3) and synth-sweep line (rtl/v2.v, Yosys 0.33: 85 gates 2 flips; opt_merge 63 gates 1 flip), source research/c5/ps6/PS6_REPORT.md (MEASURED).
5. Safety notice: the page has NO "System" tab, so I added it as a small banner (existing .banner style) under the source banner at the top, on every tab. Moving it is a text decision for the owner.
6. verify_numbers.py extended (research/c5/dash2/verify_numbers.py, output verify_numbers_output.txt): 228 values checked, 0 mismatches. New: all 92 ledger cells (value + label) vs ledger.csv; E2 distinct 152/94/38/20 vs DA3_REPORT.md text; counting and synth numbers vs PS6_REPORT.md text and synth_sweep_v2.csv; presence of key page phrases and absence of the old rail text. Limit: counting numbers are regex-checked against report prose, not recomputed from a solver run (not re-run here).

## Browser test (headless google-chrome via playwright, research/c5/dash2/shot_test.py; screenshots shot_390.png, shot_1366.png)
- 390 and 1366 px, all four tabs clicked: 0 console errors (page in the tree), scrollWidth == viewport, smallest text 12.48 px. Wide ledger tables scroll inside their .tw wrapper, not the page.
- Keyboard: Enter on the Scope tab keeps focus on it; Shift+Tab reaches the previous tab; focus survives rebuilds.
## Not done
No screen-reader test. Ledger is dense on a phone (inner horizontal scroll). The first-act prose elsewhere (e.g. Result-first bullets) was not re-edited for polarity.
