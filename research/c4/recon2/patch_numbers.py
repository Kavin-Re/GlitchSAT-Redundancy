import json, re, sys
f = sys.argv[1]
t = open(f, encoding="utf-8").read()
D = "2026-11-19"
def row(i, v, m, s, h, st): return "| `%s` | %s | %s | %s | %s | %s | %s |" % (i, v, m, s, h, st, D)

# ---- section "How ... measured": add RECON2 block
blk = """## How RECON2 re-measured the test counts (second pass, after T2, T3, PS4, PS5)
```
tar-pipe copy of /home/user/project (same exclusions) -> /tmp/work_recon2
python3 -m venv /tmp/work_recon2/venv && pip install -r ci/requirements-ci.txt "./product[test]"
pytest tests -q          -> 99 passed in 15.52 s          (lead also measured 99 passed; T3 gate 2: 99 passed in 14 s)
pytest product/tests -q  -> 139 passed, 1 skipped in 33.22 s  (T3 gate 2: 139 passed, 1 skipped, 29 s)
python3 scripts/check_numbers.py --pytest -> root 99 collected, product 140 collected (139 passed + 1 skipped)
```
The RECON counts (98 and 138 + 1 skipped) were taken before T2's `test_mt_targeted.py`/T3/PS5 changes landed in the tree; they are history now. Nothing was created in the tree (`product/build` and `*.egg-info` absent).

## Mutation scores: which figure is which
| figure | what it is | status |
|---|---|---|
| root `tests/` vs `scripts/glitchsat.py`: **72.5% = 50/69 runs** | T2 (after adding `test_mt_oracle.py` + `test_mt_targeted.py`; T2 before: 59.4%, 41/69), re-confirmed by T3 on the counter-encoding engine (50/69, no change). **Current** | REPORTED (T2, T3), not re-run by RECON2 |
| product `product/tests` vs product source: **67.6% = 50/74 runs** | T3, on the patched product engine. 74 = T2's 79 runs minus 5 mutants (`init_all_zero`, `cycles_minus1`, `kind_label`, `pf_filter_none`, `pr_kind_inv`) that no longer apply after PS4 changed the text. T2's own figure on the same 74 was 63.5%. **Current** | REPORTED (T3) |
| product 65.8% = 52/79 runs | T2's figure on the pre-T3 engine over 79 runs (10 more runs, 89 in all, were never run). **Superseded by 67.6% (different denominator, patched engine); quote only as T2's** | REPORTED (T2) |
| 67% (29/43) root, 65% (28/43) product | MT's figure over the easy FIRST 43 mutants of 158 runs (72 not run). History only | REPORTED (MT) |
Caveats: killed/run; hangs (`loop_off`, `extract_inv`, killed only by the 120 s cap) are counted separately (75.4% root / 68.4% product if counted); equivalence of survivors is by reading, not proof; T3 did not re-run T2's survivors, and 3 mutants (`temporal_off1`, `simp_always`, `timeout_off`, product) now count as killed for unexplained reasons.
"""
t = t.replace("## Resolution of the 144/163", blk + "\n## Resolution of the 144/163", 1)

# ---- section 1 rows
def rep(old_start, newrow):
    global t
    m = re.search(r"^\| `%s` \|.*$" % re.escape(old_start), t, re.M)
    assert m, old_start
    t = t[:m.start()] + newrow + t[m.end():]
rep("T.root.collected", row("T.root.collected", "99", "pytest tests: tests collected (root engine suite)", "tests/ (test_engine, test_hardening, test_check_reproduce, test_mt_oracle, test_mt_targeted)", "`pytest tests --co -q` (check_numbers.py --pytest) on the tar copy, venv with ci/requirements-ci.txt", "MEASURED"))
rep("T.root.passed", row("T.root.passed", "99", "pytest tests: passed, 0 failed (15.5 s on the RECON2 copy; lead also saw 99). Docs saying 30, 10 or 98 are stale", "tests/", "`pytest tests -q` on a tar copy (RECON2); lead RUN_LOG: pytest tests 99 passed", "MEASURED (RECON2 and lead)"))
rep("T.prod.collected", row("T.prod.collected", "140", "pytest product/tests: collected (139 passed + 1 skipped) after `pip install ./product[test]`", "product/tests/ (test_golden, test_hardening, test_mt_*, test_ps2..ps5)", "`pytest product/tests --co -q` in venv with ./product[test] on a tar copy", "MEASURED"))
rep("T.prod.passed", row("T.prod.passed", "139 passed, 1 skipped (33.2 s)", "pytest product/tests: result line on the RECON2 copy (1 skipped). Docs saying 21, 27, 38 or 138 are stale", "product/tests/", "`pytest product/tests -q` in venv with ./product[test] on a tar copy; T3 saw the same (139 passed, 1 skipped, 29 s)", "MEASURED"))
rep("T.hist.root", row("T.hist.root", "10 -> 30 -> 98 -> 99", "History of the root count: 10 (first writing), 30 (RA, after H1 added 20), 98 (RECON, after MT/T2 oracle tests), 99 (RECON2/T3, after test_mt_targeted). Quote only the current one", "research/c3/ra/RA_REPORT.md; research/c3/t2/T2_REPORT.md; research/c4/viva/VIVA_SIM_REPORT.md item 9", "see T.root.passed", "MEASURED"))
rep("T.hist.prod", row("T.hist.prod", "21 -> 27 -> 38 -> 138+1 -> 139+1", "History of product count: 21 (RA, H1), 27 (PS2, MT), 38 (lead, unmeasured), 138 passed + 1 skipped (RECON), 139 passed + 1 skipped now (T2 targeted tests, PS5)", "research/c3/ra/RA_REPORT.md; research/c3/ps2/PS2_REPORT.md; docs/dossier/EVIDENCE_INDEX.md row 2", "see T.prod.passed", "MEASURED (38 = REPORTED)"))
rep("T.mut.root", row("T.mut.root", "72.5% = 50/69 runs (after T2's new tests; T3 re-run same)", "Mutation score, tests/ vs glitchsat.py; before T2's tests 59.4% (41/69). 75.4% if the 2 hang mutants count as killed. See 'Mutation scores: which figure is which'", "research/c3/t2/T2_REPORT.md (score_out.txt); research/c4/t3/T3_REPORT.md gate 3", "`python research/c3/t2/mutate_t2.py` then `score.py`; T3: mutate_t3.py, score_merge.py", "REPORTED (T2, T3)"))
rep("T.mut.prod", row("T.mut.prod", "67.6% = 50/74 runs (T3); T2 had 65.8% = 52/79 on the pre-T3 engine", "Mutation score, product/tests vs product source on the patched engine; 74 runs because 5 mutants no longer apply (PS4 changed their text); 10 product runs never run. Before T2's tests 53.2%", "research/c4/t3/T3_REPORT.md gate 3; research/c3/t2/T2_REPORT.md", "same harness", "REPORTED (T2, T3)"))
# history row for MT
m = re.search(r"^\| `T.mut.prod` \|.*$", t, re.M)
t = t[:m.end()] + "\n" + row("T.mut.hist", "29/43 = 67% root, 28/43 = 65% product", "MT's first figures, over the first 43 mutants only (72 of 158 runs not run). History; not the current score", "research/c3/mt/MT_REPORT.md", "mutate.py + kill_check.py", "REPORTED (history)") + t[m.end():]
# also add T3/lead verified rows after T.repro.time
m = re.search(r"^\| `T.repro.time` \|.*$", t, re.M)
extra = [
 row("T.t3.gates", "check_reproduce --rerun 36/36 match (lead: 12.9 s); summed row runtime 14.4 s -> 4.2 s (T3); witness set differs 11/36, witness size equal 36/36", "R27 counter encoding applied: reproduce rows unchanged in verdict, min_faults, cycles", "research/c4/t3/T3_REPORT.md gate 1; handoff RUN_LOG 214", "`python3 ci/check_reproduce.py --rerun` (lead, on a copy)", "MEASURED (lead 36/36 in 12.9 s); runtimes REPORTED (T3)"),
 row("T.t3.speed", "dmr k=1 T=4: 1.6 s vs legacy timeout at 150 s (>= 43x); dmr k=1 T=8 34.7 s vs timeout (>= 3.9x); V2 k=2 T=12 0.35 s vs 56.6 s (80x); T=20 0.64 s vs timeout (>= 107x); V2 k=3 T=6 0.05 s vs 4.7 s (28x)", "Counter vs legacy PbLe encoding, solve time, reduce full; wall-clock speedups are LOWER BOUNDS where legacy timed out; single runs on a loaded 4-core machine (factor ~2 noise)", "research/c4/t3/T3_REPORT.md gate 5; speed_cases.jsonl", "`gate5.py speed` on /tmp/work_t3", "REPORTED (T3)"),
 row("T.t3.xcheck", "0 disagreements: seeds 1,2,3 = 40+150+150 = 340 netlists x 2 engines x 3 reduce modes (counter mode)", "Brute-force cross-check after the encoding change", "research/c4/t3/xcheck_t3.log", "xcheck_t3.py", "REPORTED (T3)"),
 row("R27.speed", "UNSAT cells 10x to 40x faster (s2 k=2 T=6 2.7 -> 0.26 s; dmr k=1 T=4 149 -> 3.5 s); uart k=3 T=60 SAT 4.5 -> 32.6 s (slower); same verdicts on 14 cells", "R27's own experiment (the estimate T3 then measured on the tree)", "research/c3/r27/R27_REPORT.md s2-s3; results.jsonl", "`python3 exp.py` on a copy", "REPORTED (R27)"),
 row("LEAD.verified", "check_reproduce --rerun 36/36 in 12.9 s; pytest tests 99 passed; product CLI V2 k=2 none, k=3 min 3, boot_ok 1; m1b CSV byte-identical to M1 CSV; predictor hashes unchanged", "What the lead re-ran after the T3/PRES/M1b hand-backs", "handoff/CONTINUATION/RUN_LOG.md entries 212-219 (lead verification as written there)", "lead, on copies", "MEASURED (lead; RECON2 re-ran the pytest counts and the CSV cmp)"),
]
t = t[:m.end()] + "\n" + "\n".join(extra) + t[m.end():]

# ---- new section 9
s9 = """
## 9 C4 additions (RECON2): layout, L2, B3, product options, EDU2, DASH, VIVA, M1b
Status here: REPORTED = taken from the agent's report; no solver, flow or SPICE was re-run by RECON2. "RECOUNTED" = RECON2 recomputed the number from the agent's stored data files with `python3 scripts/check_numbers.py --verify` (no tool re-run). MEASURED only where RECON2 or the lead re-ran the command.
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
""" + "\n".join([
 row("LAY.radius", "2.95 um", "Smallest enclosing-circle radius (cell centres) of the cheapest sufficient one-event set of V2 (three nand4bb cells c0/c1/c2 `_2_`); cells are 1.4 to 5 um wide so the real disc is somewhat larger. Geometry MEASURED from DEF; verdict SIMULATED and only under the selective-event model", "research/c4/layout/LAYOUT_REPORT.md s2, s5; minsets_v2.json", "`minsets.py` (z3, B3 engine) on DEF placement; RECOUNTED by check_numbers --verify", "MEASURED geometry / SIMULATED verdict; REPORTED, RECOUNTED"),
 row("LAY.minsets", "4 minimal one-event sets, all 3 cells, all cycle 1: r 2.95 / 3.06 / 3.29 / 4.58 um (word and ok)", "Enumeration limited to <= 4 cells and 400 sets, so radii are upper bounds", "LAYOUT_REPORT.md s2; layout/minsets_v2.json", "minsets.py; RECOUNTED", "SIMULATED; RECOUNTED"),
 row("LAY.supply", "one VPWR net: ONE met4 VPWR strap (x=9.22), ONE met4 VGND strap (x=19.22), no ring; 4 VPWR rails join the strap at one column; 36 logic cells in a 30.6 um die, 77% utilisation", "Electrically one supply net fed at one column. This is an INFERRED reading of the DEF; no extraction, no IR-drop solve", "LAYOUT_REPORT.md s2 (DEF SPECIALNETS)", "layout_extract.py (plain Python)", "MEASURED (DEF read) / INFERRED (reading); REPORTED"),
 row("LAY.whatif", "4.58 um (nand4bb triple) and 6.13 um (nand2 triple) after 3 same-footprint swaps; rail families still 1", "HYPOTHETICAL placement; routing, timing, DRC, LVS not redone. Not a layout that exists", "LAYOUT_REPORT.md s6; whatif.py", "whatif.py -> minsets.py", "HYPOTHETICAL; REPORTED"),
 row("L2.spacing", "min copy-to-copy centre distance: base 1.84 um, v8 9.2, rr 16.3, s8 17.9, v15 23.5 (bbox gap 0, 5.98, 13.6, 14.7, 20.2)", "Real OpenROAD runs with the 9 cells of c0/c1/c2 pinned (`pnr_l2.tcl`); same netlist as the original V2 (byte-identical `v2_net.v`)", "research/c4/l2/L2_REPORT.md results table; data/metrics_<var>.json pairwise_copy_distance", "`run_var.sh` then `metrics.py` (agent); RECOUNTED from metrics_*.json", "MEASURED placement; REPORTED, RECOUNTED"),
 row("L2.radius", "smallest sufficient one-event set radius: base 2.95, v8 11.15, s8 17.91, v15 15.16, rr 15.30 um (x3 to > x5); v8's true threshold lies in (8, 10] um", "Upper bounds from a <= 4-cell enumeration; the sweep (primitive-level, any size) is authoritative. Thresholds depend on where the placer put `_16_` (output inverter), which was not pinned", "L2_REPORT.md security-model table; data/minsets_<var>.json, sweep_<var>.json", "`dom.sh <var>` (z3, T=6, <= 3 events); RECOUNTED", "SIMULATED on MEASURED placement; RECOUNTED"),
 row("L2.selectivity", "selectivity threshold (SUB cost 1 first at r): base between 2.5 and 3.0 um; v8 between 8 and 10; s8 > 15 (SUB 2 at 15); v15 15 (SUB 2 at 10); rr 15 (SUB 2 at 8, 10)", "Radius sweep r = 3, 5, 10, 15 um; AoN = all cells of the disc fall, SUB = one event picks which fall", "L2_REPORT.md radius sweep table; data/sweep_<var>.json", "dom.sh", "SIMULATED; REPORTED"),
 row("L2.rail_all", "rail_all (whole die, one selective event): still 1 / 1 (word / ok) in ALL five variants", "Hardening by distance does not remove a die-wide selective dip: the three copies stay on the same two supply nets (one PDN)", "L2_REPORT.md rail-level paragraph; data/fam_<var>.jsonl", "dom.sh; RECOUNTED (family rail_all, mode subset)", "SIMULATED; RECOUNTED"),
 row("L2.rail.perrail", "VPWR rail family SUB cost: base 1/1, v8 2/2, s8 2/2, v15 2/2, rr 3/2 (word/ok); VGND rail 2/2 everywhere; strap-branch base 1/1, v8 2/2, s8 and v15 3/3, rr 3/2", "Per-rail events: 1 -> 2 (v8, s8, v15) and 3 (rr, word goal) once the copies sit on different rails; row 2/2 (rr 3/2). Rail families are only 1 to 2 rows wide here", "L2_REPORT.md rail-level paragraph; data/fam_<var>.jsonl", "dom.sh; RECOUNTED for rail_all and VPWR rail", "SIMULATED; RECOUNTED (VPWR rail), REPORTED (strap, VGND, row)"),
 row("L2.cost", "die area x1.26 (v8: 936 -> 1183 um^2) to x2.5 (v15: 2362); cell area +0.3% to +7%; detailed wire length +29% (v8), +31% (s8), +36% (rr), +50% (v15: 1418.7 vs 949 um, 49.5%); slack change <= 0.02 ns (estimate, no extraction)", "Cost of spreading", "L2_REPORT.md results table and cost paragraph; data/summary_flow.json", "run_var.sh; RECOUNTED wire percentages", "MEASURED flow output (agent); RECOUNTED wire length"),
 row("L2.drc", "router DRC 0 violations in 5 of 5 variants; antenna 0 pin / 0 net in 5 of 5; magic top-cell DRC 15 / 20 / 24 / 18 rules in the 4 spread variants (none listed for base); LVS match uniquely for base (430/430 devices, 226/226 nets) and **FAILS in 4 of 4 spread variants** (pin matching: 428/430, 427/430, 425/430, 427/430)", "Cause: li1 wire crossing a row boundary touches a filler VGND in magic's view (the same flow bug as VERIFY.md s3). NOT fixed, not suppressed; the spread layouts are an experiment, not a fix", "L2_REPORT.md DRC/LVS paragraph; data/summary_flow.json", "run_var.sh, magic, netgen; RECOUNTED LVS pass/fail, router DRC, antenna", "MEASURED flow output (agent); RECOUNTED"),
 row("L2.sim", "decomposed layout netlists equal the original on all 256 sig values over 5 cycles (0 of 256 differ)", "Function unchanged at netlist level", "L2_REPORT.md limits; lay/<var>/sim.log", "simcheck.py", "MEASURED (agent)"),
 row("EL1.simul", "all high gates on a dipping rail droop together (inv and nand2 within ~0.01 V); clean-rail flop mis-samples at tt 3 ns with Vmin <= 0.5 V, tt/ss/ff 1 ns only at 0 V; none at 0.3 ns; 60 dip points + 48 runt points", "Basis for the rail-dip model: correlated 1 -> 0 sag, flop Q not flipped. One tiny rail with a handful of gates, so it cannot show a real dip cannot be selective", "research/c2/el1_spice/EL1_REPORT.md A, B; fault_windows.json", "ngspice-41, sky130 tt/ss/ff", "SIMULATED"),
 row("B3.matrix", "T=6, <= 3 events, 0 unknown: rail_all / rail_half / rail_unions `>3` for V0, V1, V2, V2 apt, V5 apt (word and ok); rail_cone V0 1 (V0 apt 1), V1/V2/V5 `>3`; dip_subset (one event picks which gates fall) 1 for every design; early_*/hold_* `>3`; baseline stem_flip V2 spike 3 / apt 2 / boot_ok 1", "`>3` = UNSAT for cost <= 3, NOT 'secure'. Verdict depends on selectivity", "research/c4/b3/B3_REPORT.md matrix; matrix_T6.jsonl (182 rows)", "`python3 run_cells.py` (agent); RECOUNTED from matrix_T6.jsonl", "SIMULATED (fault model) / MEASURED solver output (agent); RECOUNTED"),
 row("B3.valid", "brute force vs z3: 0 disagreements on V0 (T=4, k<=2, 9 models) and V1 (T=3, k<=2, 9 models); dip_subset V0 T=4 k=1: 1,048,579 sets, z3 1 = brute 1; NOT validated: V2, V5, apt rows, T=6", "Independent checker bf_b3.py, no z3", "B3_REPORT.md Validation; val.log", "bf_b3.py", "MEASURED (agent); small scope"),
 row("PS4.opts", "shipped in `faultbound-wt`: `--consumer-bits`, `--goal-out/--accept-value`, `--input-sites {none,all}`, `--init {known,arbitrary}`, `--scope-sweep` (+ `--sweep-masks`, `--cell-timeout-ms`, `--sweep-out`); NOT shipped: `--count-rule branch` (exit 3), per-cycle attacker input", "Exit codes 0/1/2/3/4 and schema `faultbound-wt-report/1` unchanged", "research/c4/ps4/PS4_REPORT.md", "CLI runs on spike V2 (agent); lead: product CLI V2 k=2 none / k=3 min 3 / boot_ok 1", "MEASURED (agent; lead re-ran the three default cells)"),
 row("PS4.sweep", "scope sweep V2 (columns none+known, all+known, none+arbitrary, all+arbitrary): word 3,1,0,0; bits 0xF 2,1,0,0; bits 0x6A 3,1,0,0; boot_ok 1,1,0,0 (33 s)", "Same numbers as B2 scope table (word 3, input sites 1, arbitrary power-up 0) and as PRES / EDU2 re-runs (PRES: 17.9 s for masks 0x0F, 0x6A)", "PS4_REPORT.md; research/c4/ps4/data/sweep_v2.json; PRES_REPORT.md; EDU2_REPORT.md", "`faultbound-wt analyze ... --max-flips 3 --scope-sweep --sweep-masks 0x0F,0x6A`; RECOUNTED from sweep_v2.json", "MEASURED (PS4, PRES, EDU2 agents); RECOUNTED"),
 row("PS4.masks", "consumer masks vs m1_all_masks.csv: 10 of 10 popcount-4 masks agree (seed 7), plus 10 of 10 mixed masks incl. one colliding (seed 4): 20 of 255 masks; --input-sites all gives 1 (`c0.a[1]@1`); --init arbitrary gives 0", "Not the full table", "PS4_REPORT.md verification", "data/masks.py", "MEASURED (agent)"),
 row("PS4.tests", "test_ps4.py: 25 tests; clean venv (copy lacking T2 files): 62 passed, 1 skipped in 81 s", "Superseded as a total by T.prod.passed (139 + 1 skipped today)", "PS4_REPORT.md", "pytest in a copy", "REPORTED"),
 row("PS5.width", "width curve n=1..8: 0,1,1,2,2,3,3,3 (18 s, `--sweep-widths --max-flips 3`) equal to m1_all_masks.csv column v2_spike_min_flips for masks 0x01,0x03,0x07,0x0F,0x1F,0x3F,0x7F,0xFF", "Same as M1.width, now through the shipped CLI; EDU2: V1 0,1,1,1,1,1,1,1; mini_v2 n=1..4 0,1,2,2", "research/c4/ps5/PS5_REPORT.md item 5; research/c4/edu2/EDU2_REPORT.md; test_sweep_widths_matches_m1_csv", "`faultbound-wt analyze examples/v2.json --config threat.toml --sweep-widths --max-flips 3`", "MEASURED (PS5, PRES, EDU2 agents; check_numbers --verify recomputes the curve from the CSV)"),
 row("PS5.scope", "scope sweep rows 3,1,0,0 (word) / 2,1,0,0 (0x0F) / 3,1,0,0 (0x6A) / 1,1,0,0 (boot_ok)", "The 'scope sweep 3,1,0,0' headline = V2 word goal across none+known, all+known, none+arbitrary, all+arbitrary", "see PS4.sweep", "see PS4.sweep", "MEASURED (agents); RECOUNTED"),
 row("PS5.opts", "`--timeout-s 3` on a cell needing ~8 s: exit 2, UNKNOWN_TIMEOUT, `timed_out: true` (PRES: `--timeout-s 2` exit 2 after 2.1 s; 0.05 s returns in 0.17 s); `--init free_nongoal` V2 k<=2: ATTACK_FOUND 1 flip (boot_word[4]@0); 8 tests in test_ps5.py", "Timeout gives no partial sweep table; Linux only", "PS5_REPORT.md items 2-3, 6; PRES_REPORT.md", "faultbound-wt CLI on spike V2", "MEASURED (agents)"),
 row("EDU2.rerun", "40 commands of the answer key re-run (exit codes in verification.log); no minimum-flip number changed: Ex1 V0 1 / V1 1 / V2 3; Ex3 plain 85 gates min 2 (hash f954078f), merge 63 gates min 1 (d776226e); V2 k=3 about 8 s (was 'about 12 s'); run sheet about 100 min (86 without Ex 7-8), ESTIMATE, UNPILOTED", "Lab kit moved to the shipped CLI; Yosys 0.33 only (counts and hashes differ on other builds)", "research/c4/edu2/EDU2_REPORT.md; verification.log; verify_edu2.sh", "`sh verify_edu2.sh` in a copy (agent)", "MEASURED (agent); schedule ESTIMATED"),
 row("DASH.values", "115 values compared (scope table 20, widths 16, E2 3 rows, rail table 25, engine summary, curve runtimes): 115 match, 0 mismatches; 0 console errors at 390 and 1366 px; smallest text 12.48 px; text/background contrast >= 4.5:1", "Numbers page vs source data files; does not check prose", "research/c4/dash/DASH_REPORT.md; verify_numbers_output.txt", "`python3 research/c4/dash/verify_numbers.py` (agent); headless Chrome", "MEASURED (agent); not re-run by RECON2"),
 row("VIVA.falsify", "19 repo claims listed with a one-command falsifier (section 7); 11 re-run by the VIVA agent (rows 1-9, 11, 19), 5 UNVERIFIED (10, 12, 13, 14, 16), 3 not rebuildable from the bundle (15, 17, 18); 48 questions, weakest 10", "Rows 9 (test count) and 11 (144 vs 150) were found stale/unreconciled and are fixed in the docs by RECON/D3/RECON2 (VIVA's own report still shows them)", "research/c4/viva/VIVA_SIM_REPORT.md s7", "commands in the report", "REPORTED"),
 row("M1b.cells", "0 of 1785 cells changed (7 designs x 255 masks, two independent engines); `m1b_all_masks.csv` byte-identical to `m1_all_masks.csv`; no x init in any of the 7 netlists; rule 255/255 on spike V2, 68 mismatches on apt-0.33 V2 unchanged; B2 headline: 30 cells, 0 differences", "No published M1 claim changes. Only the 7 M1 netlists were checked (opt-flow held-out netlists with 'xx1001' init were not)", "research/c4/m1b/M1B_REPORT.md", "`sh runall.sh mat2.py`, `diff.py`; CSV cmp", "MEASURED (agent); CSV identity MEASURED by lead and RECON2 (`cmp`, check_numbers --verify)"),
 row("E2.unique", "24 configs at min 3 = 20 unique netlists (TEST's '20 cells at min 3')", "Say which one you mean: configs 24 or unique netlists 20", "research/c4/recon/RECON_REPORT.md s4; TEST_REPORT.md", "see E2.v2.min", "MEASURED (RECON)"),
 row("REP.pct", "6/32 = 18.75%, quoted as 19%", "Stem rule: V2 survives 2 flips on 6 of 32 netlists", "see REP.unit", "see REP.unit", "MEASURED"),
 row("PRE.train", "V2 spike 252/255 exact, 255/255 within 1; 0 bound violations, 0 false-safe; optimistic (designed with the data in view)", "Companion to PRE.train row in section 7; held-out audit figure is VER.heldout.exact (150/163)", "research/c4/pre/PRE_REPORT.md; test_training.py", "pytest research/c4/pre/test_training.py", "MEASURED (agent); predictor hashes verified by lead"),
]) + "\n"
t = t.replace("\n## Machine-readable block", s9 + "\n## Machine-readable block", 1)

# ---- JSON block
m = re.search(r"```json\s*\n(.*?)\n```", t, re.S)
d = json.loads(m.group(1))
d["current"] = {"T.root.passed": "99", "T.prod.passed": "139 passed, 1 skipped (33.2 s)", "T.prod.collected": "140", "T.root.collected": "99"}
d["hist_re"] = d["hist_re"][:-2] + "|first 43|history|earlier (?:MT|figure|counts?)|superseded|before T[23])\""[:0] + d["hist_re"][-2:] if False else d["hist_re"]
if "first 43" not in d["hist_re"]:
    d["hist_re"] = d["hist_re"].replace("|old )", "|old |first 43|\\bhistory\\b|before T[23]|T2 had|T2's own|earlier MT|earlier 67)")
for r in d["rules"]:
    if r["id"] == "T.root.passed":
        r["should"] = r["should"].replace("98 passed (root `pytest tests`, 2026-11-19, RECON)", "99 passed (root `pytest tests`, 2026-11-19, RECON2)").replace("98 passed", "99 passed")
    if r["id"] == "T.prod.passed":
        r["should"] = r["should"].replace("138 passed, 1 skipped (98.9 s)", "139 passed, 1 skipped (33.2 s)").replace("(product/tests after pip install ./product[test]; 139 collected)", "(product/tests after pip install ./product[test]; 140 collected)")
    if r["id"] == "T.mut.root":
        r["re"] = r"(?<![\d.])(?:29|28)\s*(?:/|of)\s*43\b"
        r["hist"] = True
        r["should"] = "root 72.5% (50/69), product 67.6% (50/74) (T2/T3); 29/43 and 28/43 only as history ('first 43')"
        r["label"] = "stale mutation score (first-43 figure as current)"
new_rules = [
 ("T.mut.pct", True, r"(?i)mutation[^\n]{0,140}(?<![\d.])(?:67|65)\s?%|(?<![\d.])67\s?%\s*/\s*65\s?%|\b65-67\s?%|(?<![\d.])67/65\s?%", "root 72.5% (50/69), product 67.6% (50/74); 67%/65% only as history", "stale mutation percentage"),
 ("T.root.99", True, r"\b98 (?:passed|tests|root|main tests)\b|\bnow 98\b|\btoday 98\b", "99 passed (root, RECON2); 98 only as history", "stale root test count (98)"),
 ("T.prod.139", True, r"\b138 (?:passed|product)\b|\b139 collected\b|\b98\.9 s\b|\b26\.7 s\b", "139 passed, 1 skipped, 140 collected, 33.2 s; 138+1 only as history", "stale product test count or timing (138, 139 collected, 98.9 s, 26.7 s)"),
 ("L2.status", False, r"(?i)\bL2\b[^\n|]{0,60}\b(?:in progress|absent|not yet run)\b|\bL2 follow-up[^\n]{0,40}in progress|no report found (?:at|when) D3", "L2 is done: research/c4/l2/L2_REPORT.md (spread r 11 to 18 um, rail_all still 1, LVS FAILS 4 of 4)", "L2 shown as unfinished"),
 ("R27.applied", False, r"(?i)(?:R27|sequential-counter|faster (?:at-most-k )?encoding)[^\n]{0,200}\b(?:NOT applied|not applied|patch exists)|no T3 report", "applied by T3 (counter encoding default, `--amk legacy` keeps the old code; research/c4/t3/T3_REPORT.md)", "R27 patch shown as not applied"),
 ("M1b.pending", False, r"(?i)recheck pending|M1b[^\n]{0,40}(?:is rechecking|pending|in progress)", "M1b done: 0 of 1785 cells changed (research/c4/m1b/M1B_REPORT.md)", "M1b shown as pending"),
 ("L2.lvs", False, r"(?i)\bspread[^\n]{0,100}(?:LVS (?:clean|passes|match(?:es)?)|passes? LVS)", "LVS FAILS in 4 of 4 spread variants (research/c4/l2/L2_REPORT.md)", "spread layouts shown as LVS clean"),
 ("L2.hardening", False, r"(?i)\b(?:spread(?:ing)?|distance)[^\n]{0,80}\b(?:removes|eliminates|solves|fixes)\b[^\n]{0,40}\b(?:selective|dip|event)", "spreading raises the radius threshold to 11 to 18 um but a die-wide selective dip (rail_all) still costs 1 event", "hardening by distance overclaimed"),
 ("L2.wire", False, r"(?i)\bwire[ -]?length[^\n]{0,30}\+(?:1\d|2[0-7]|5[2-9]|[6-9]\d)\s?%", "wire length +29% to +50%", "L2 wire-length cost misquoted"),
 ("L2.area", False, r"(?i)\bdie (?:area )?(?:cost )?x(?:1\.[0-1]\d?|2\.[6-9]|[3-9])\b", "die area x1.26 to x2.5", "L2 die-area cost misquoted"),
 ("LAY.radius", True, r"(?i)\b(?:enclosing|selectivity|minimal)\b[^\n]{0,40}\bradius[^\n]{0,30}\b(?:3\.5|2\.5)\s*um", "2.95 um (centre to centre); 3.5 um was an assumed disc (EL2), 4.6 um a hypothetical what-if", "layout radius misquoted"),
 ("B3.overclaim", False, r"(?i)\bV2\b[^\n]{0,40}\b(?:resists|survives|is (?:secure|safe) against)\b[^\n]{0,30}\b(?:rail|dip)", "no attack found up to 3 events (bounded, T=6) under rail_all/half/unions/cone; 1 event if a dip may choose which gates fall", "rail-dip result overclaimed"),
]
for i, h, rx, sh, lb in new_rules:
    d["rules"].append({"id": i, "hist": h, "re": rx, "should": sh, "label": lb})
d["generated"] = "2026-11-19 (RECON2 extended)"
newj = json.dumps(d, indent=1, ensure_ascii=False)
t = t[:m.start(1)] + newj + t[m.end(1):]
t = t.replace("RECON rows were re-run on a tar copy in /tmp/work_recon on 2026-11-19.", "RECON rows were re-run on a tar copy in /tmp/work_recon on 2026-11-19; test counts were re-measured by RECON2 (section below) on a fresh copy.")
open(f, "w", encoding="utf-8").write(t)
