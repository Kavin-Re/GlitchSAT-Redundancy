# NUMBERS: single source of truth for every headline number
GlitchSAT. License: Apache-2.0. Faults are modelled single-cycle bit flips in toy netlists; nothing physical; nothing established as new. Author has not reviewed this page.

Purpose: README.md, START.md, docs/FINAL_STATUS.md, docs/report, docs/dossier, docs/explainers, docs/edu, product/QUICKSTART.md and the dashboard quote the same numbers. Quote a number only as it appears here. When a measurement changes, edit THIS file first, then run `python3 scripts/check_numbers.py` to list every page that still carries the old value.

Status labels: MEASURED (a command was run, the output was seen), SIMULATED (SPICE or rail-dip model, not silicon), SOURCED (taken from a cited source, not run), REPORTED (written in an step report, not re-run by RECON), UNVERIFIED. Date = when the value was produced; RECON rows were re-run on a tar copy in /tmp/work_recon on 2026-11-19; test counts were re-measured by RECON2 (section below) on a fresh copy.

## How RECON measured today's test counts
```
tar-pipe copy of the repository root (excluding work, dl, dl_repo, venv, compare/synfi_run/venv, third_party_derived, .git, handoff/*.zip, *.odb *.vcd *.fst *.vvp) -> /tmp/work_recon/copy
python3 -m venv /tmp/work_recon/venv && pip install -r ci/requirements-ci.txt "./product[test]"
pytest tests --co -q            -> 98 tests collected
pytest tests -q                 -> 98 passed in 26.7 s
pytest product/tests --co -q    -> 139 tests collected
pytest product/tests -q         -> 138 passed, 1 skipped (98.9 s)
```

## How RECON2 re-measured the test counts (second pass, after T2, T3, PS4, PS5) (history: at 2026-11-19 21:5x; current 136 root / 324 product since RECON5, 2026-11-20; 133 / 321 at RECON4; 310 at H2/H3 time)
```
tar-pipe copy of the repository root (same exclusions) -> /tmp/work_recon2
python3 -m venv /tmp/work_recon2/venv && pip install -r ci/requirements-ci.txt "./product[test]"
pytest tests -q          -> 99 passed in 15.52 s          (history: at 2026-11-19 21:5x; now 136 passed, RECON5; 133 at RECON3/RECON4; integration step also measured 99 passed; T3 gate 2: 99 passed in 14 s)
pytest product/tests -q  -> 139 passed, 1 skipped in 33.22 s  (history: at 2026-11-19 21:5x; now 324 passed, RECON5 (321 at RECON4; 310 at H2/H3 time); T3 gate 2: 139 passed, 1 skipped, 29 s)
python3 scripts/check_numbers.py --pytest -> root 99 collected, product 140 collected (139 passed + 1 skipped)   [history: at 2026-11-19 21:5x; current 136 / 324; 133 / 321 at RECON4; 310 at H2/H3 time]
```
The RECON counts (98 and 138 + 1 skipped) were taken before T2's `test_mt_targeted.py`/T3/PS5 changes landed in the tree; they are history now. Nothing was created in the tree (`product/build` and `*.egg-info` absent).

## How RECON3 re-measured the test counts (third pass, after PS6, DASH2, FIX3, H2, H3; 2026-11-20)
```
tar-pipe copy of the repository root (same exclusions) -> /tmp/work_recon3/p ; venv /tmp/work_recon3/venv ; pip install "./p/product[test]" pytest z3-solver pyyaml
pytest tests -q                    -> 133 passed in 18.32 s            (99 + 34 new in tests/test_h3.py)
pytest product/tests -q            -> 310 passed in 80.88 s            (175 + 135 new in product/tests/test_h2.py; 0 skipped because pyyaml is installed)
python3 ci/check_reproduce.py      -> 36/36 rows match (summary + per-run files + input hashes; engine NOT re-run); 0 row(s) FAILED; exit 0
python3 ci/check_reproduce.py --rerun -> 36/36 rows match (engine re-run); 0 row(s) FAILED; 0 problem(s); exit 0; no ENGINE_MANIFEST warning printed
python3 scripts/check_numbers.py --verify --pytest -> 10/10 verify OK; collected 133 and 310 (equal to this file after RECON3 edits)
```
All five were MEASURED by RECON3 on the fresh copy; nothing was created in the tree (`product/build` and `*.egg-info` absent). The counts 98/99, 138/139+1, 174/175 are history now (PS6: 174 passed 1 skipped; H2 copy: 175 pre-existing + 135 new).

## How RECON4 re-measured the test counts (fourth pass, after H4; 2026-11-20)
```
tar-pipe copy of the repository root (same exclusions) -> /tmp/work_recon4/p ; venv /tmp/work_recon4/venv ; pip install -r ci/requirements-ci.txt "./p/product[test]" pytest z3-solver pyyaml
pytest tests -q                    -> 133 passed in 14.93 s            (unchanged)
pytest product/tests -q            -> 321 passed in 81.34 s            (310 + 11 new in product/tests/test_h4.py; 0 skipped; `[test]` now pulls pyyaml)
python3 ci/check_reproduce.py      -> 36/36 rows match (engine NOT re-run); 0 row(s) FAILED; 0 problem(s); exit 0
python3 ci/check_reproduce.py --rerun -> 36/36 rows match (engine re-run); 0 row(s) FAILED; 0 problem(s); exit 0
python3 scripts/check_numbers.py --verify --pytest -> 10/10 verify OK; collected 133 and 321 (equal to this file after RECON4 edits)
```
MEASURED by RECON4 on the fresh copy; nothing was created in the tree (`product/build` and `*.egg-info` absent). The product count 310 is history (H2/H3 time, RECON3).

## How RECON5 re-measured the test counts (fifth pass, after H5, the Action run and the Docker run; 2026-11-20)
```
tar-pipe copy of the repository root (same exclusions) -> /tmp/work_recon5/p ; venv /tmp/work_recon5/venv ; pip install -r ci/requirements-ci.txt "./p/product[test]" pytest z3-solver pyyaml
pytest tests -q                    -> 136 passed in 15.37 s            (133 + 3 new in tests/test_h5.py)
pytest product/tests -q            -> 324 passed in 81.32 s            (321 + 3 new in product/tests/test_h5.py)
python3 ci/check_reproduce.py      -> 36/36 rows match (engine NOT re-run); 0 row(s) FAILED; 0 problem(s)
python3 ci/check_reproduce.py --rerun -> 36/36 rows match (engine re-run); 0 row(s) FAILED; 0 problem(s); no ENGINE_MANIFEST warning
python3 scripts/check_numbers.py --verify --pytest -> collected 136 and 324 (see RECON5_REPORT.md for the final run after the edits)
```
MEASURED by RECON5 on the fresh copy; nothing was created in the tree. H5 itself reported 324 in a clean copy and 314 passed / 10 skipped in the tree (conda Yosys on PATH); the tree counts differ by skips and are not the headline. 133 / 321 are history (RECON4).

## Mutation scores: which figure is which
| figure | what it is | status |
|---|---|---|
| root `tests/` vs `scripts/glitchsat.py`: **72.5% = 50/69 runs** | T2 (after adding `test_mt_oracle.py` + `test_mt_targeted.py`; T2 before: 59.4%, 41/69), re-confirmed by T3 on the counter-encoding engine (50/69, no change). **Current** | REPORTED (T2, T3), not re-run by RECON2 |
| product `product/tests` vs product source: **67.6% = 50/74 runs** | T3, on the patched product engine. 74 = T2's 79 runs minus 5 mutants (`init_all_zero`, `cycles_minus1`, `kind_label`, `pf_filter_none`, `pr_kind_inv`) that no longer apply after PS4 changed the text. T2's own figure on the same 74 was 63.5%. **Current** | REPORTED (T3) |
| product 65.8% = 52/79 runs | T2's figure on the pre-T3 engine over 79 runs (10 more runs, 89 in all, were never run). **Superseded by 67.6% (different denominator, patched engine); quote only as T2's** | REPORTED (T2) |
| 67% (29/43) root, 65% (28/43) product | MT's figure over the easy FIRST 43 mutants of 158 runs (72 not run). History only | REPORTED (MT) |
Caveats: killed/run; hangs (`loop_off`, `extract_inv`, killed only by the 120 s cap) are counted separately (75.4% root / 68.4% product if counted); equivalence of survivors is by reading, not proof; T3 did not re-run T2's survivors, and 3 mutants (`temporal_off1`, `simp_always`, `timeout_off`, product) now count as killed for unexplained reasons.

## Resolution of the 144/163 versus 150/163 question
Both are real counts of the same file `research/c4/ver/heldout.csv` (163 cells), but only 150/163 (92.0%) is the audit figure. Raw `pred==solver` string comparison gives 144. Add 4 cells where the solver column says `>3` and the predictor column holds 100 (lb sentinel 99, plus 1): PREREG compares `>3` as 4 and caps the prediction at 4, so these 4 match (148). Add 2 cells (rc103_opt mask 0x18, rc117_opt mask 0xf) where the solver column still holds the pre-correction value from `gs_mask.py` (x init bit mapped to 0 clobbered an aliased flop); `rerun_x.json` holds the corrected solver values 0 and 2, which equal the predictor (150). RECON recomputed all three steps (script check `heldout` in `scripts/check_numbers.py --verify`). Quote 150/163 (92.0%), 58% on cells needing 2 or more flips, and always say the 928/928 pooled figure is near-duplicate cells.



## 1 Tests
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `T.root.collected` | 190 | pytest tests --co -q: tests collected (root suite) in the CANONICAL setup: unpacked bundle (or dev tree minus compare/third_party_derived, identical) + clean venv with `pip install ./product[test]` and pytest, no numpy, no Chrome/playwright. Per file: test_mt_oracle 61, test_h3 34, test_burst_sweep 18, test_decoder_variants 16, test_hardening 15, test_distance_sweep 12, test_engine 10, test_mt_targeted 8, test_explainer_checks 6, test_check_reproduce 5, test_h5 3, test_p08 2 (= 190; test_waterfall.py is skipped as a module without numpy, 13 more tests with numpy). History: 197 at INT2a (2026-11-20, system python with numpy, before test_explainer_checks existed: 190 - 6 + 13 = 197); 150 at INT | tests/ | `pytest tests --co -q` in /tmp/work_recon6/bundle (RECON6; bundle project_full_tree_20261120T054144Z.zip) | MEASURED (RECON6) | 2026-11-20 |
| `T.root.passed` | 189 passed, 2 skipped | CANONICAL (what a user gets: unpack the bundle, `pip install ./product[test]` in a clean venv, `pytest tests`; 22 s; RECON6 and the integration step's verify run agree). The 2 skips: `test_waterfall.py` (module skipped, `could not import 'numpy'`) and `test_explainer_checks.py::test_hub_browser` (`google-chrome or playwright missing`). Dev-tree numbers differ only by environment, not by tree content (RECON6: dev tree minus compare/ and third_party_derived/ gives the same 189 + 2, same per-file counts): with numpy installed in the venv test_waterfall adds 13 passing tests (202 passed, 1 skipped, 203 collected); on system python3 with numpy and no product CLI on PATH, `test_distance_sweep.py::test_remeasure_stored` skips instead (202 passed, 1 skipped, 203 collected). History: INT2a measured 196 passed, 1 skipped (197 collected) on 2026-11-20 on system python before test_explainer_checks.py (6 tests, 1 browser skip) was added: 197 - 13 (no numpy) + 6 = 190. Docs saying 196/197 as the current root count are stale; 30, 10, 98, 99, 133, 136 or 150 are history | tests/ | `python -m pytest -q -rs tests` in a clean venv on the unpacked bundle | MEASURED (RECON6) | 2026-11-20 |
| `T.prod.collected` | 324 | pytest product/tests: collected after `pip install ./product[test]` (pyyaml installed, so the YAML test runs; since H4 `[test]` pulls pyyaml itself, 0 skipped; 310 at H2/H3 time) | product/tests/ (test_golden, test_hardening, test_mt_*, test_ps2..ps6, test_h2) | `pytest product/tests --co -q` in venv with ./product[test] on a tar copy | MEASURED (RECON4) | 2026-11-20 |
| `T.prod.passed` | 324 passed (81.3 s) | pytest product/tests: result line on the RECON4 copy (310 passed, 80.9 s at H2/H3 time, RECON3). 321 = 175 pre-existing (PS6: 174 passed + 1 skipped) + 135 in `product/tests/test_h2.py` (H2) + 11 in `product/tests/test_h4.py` (H4). Docs saying 21, 27, 38, 138, 139, 174, 175 or 310 are stale or history | product/tests/ | `pytest product/tests -q` in venv with ./product[test] on a tar copy; H2 saw 310 passed on its copy | MEASURED (RECON4; H2, H4) | 2026-11-20 |
| `T.hist.root` | 10 -> 30 -> 98 -> 99 -> 133 | History of the root count: 10 (first writing), 30 (RA, after H1 added 20), 98 (RECON, after MT/T2 oracle tests), 99 (RECON2/T3, after test_mt_targeted), 133 (RECON3/H3, +34 in test_h3.py). Quote only the current one | research/c3/ra/RA_REPORT.md; research/c3/t2/T2_REPORT.md; research/c4/qa_sim/QA_SIM_REPORT.md item 9 | see T.root.passed | MEASURED | 2026-11-19 |
| `T.hist.prod` | 21 -> 27 -> 38 -> 138+1 -> 139+1 -> 174+1 -> 310 -> 321 | History of product count: 21 (RA, H1), 27 (PS2, MT), 38 (unmeasured), 138 passed + 1 skipped (RECON), 139 passed + 1 skipped (T2 targeted tests, PS5), 174 passed + 1 skipped (PS6, +35 in test_ps6.py), 310 passed at H2/H3 time (H2, +135 in test_h2.py; the skip became a pass because pyyaml was installed), 321 passed now (H4, +11 in test_h4.py) | research/c3/ra/RA_REPORT.md; research/c3/ps2/PS2_REPORT.md; docs/dossier/EVIDENCE_INDEX.md row 2 | see T.prod.passed | MEASURED (38 = REPORTED) | 2026-11-19 |
| `T.b3` | 16 | B3 research tests (research/c4/b3/test_b3.py) passed | research/c4/b3/B3_REPORT.md | `cd /tmp/work_b3; python3 -m pytest -q test_b3.py` | REPORTED | 2026-11-19 |
| `T.mt.new` | 61 | MT extra tests (research/c3/mt/new_tests) passed per engine, 1.3 s | research/c3/mt/MT_REPORT.md; docs/dossier/PROJECT_DOSSIER.md l.118 | `MT_ROOT=<tree> pytest research/c3/mt/new_tests` | REPORTED | 2026-11-19 |
| `T.mut.root` | 72.5% = 50/69 runs (after T2's new tests; T3 re-run same) | Mutation score, tests/ vs glitchsat.py; before T2's tests 59.4% (41/69). 75.4% if the 2 hang mutants count as killed. See 'Mutation scores: which figure is which' | research/c3/t2/T2_REPORT.md (score_out.txt); research/c4/t3/T3_REPORT.md gate 3 | `python research/c3/t2/mutate_t2.py` then `score.py`; T3: mutate_t3.py, score_merge.py | REPORTED (T2, T3) | 2026-11-19 |
| `T.mut.prod` | 67.6% = 50/74 runs (T3); T2 had 65.8% = 52/79 on the pre-T3 engine | Mutation score, product/tests vs product source on the patched engine; 74 runs because 5 mutants no longer apply (PS4 changed their text); 10 product runs never run. Before T2's tests 53.2% | research/c4/t3/T3_REPORT.md gate 3; research/c3/t2/T2_REPORT.md | same harness | REPORTED (T2, T3) | 2026-11-19 |
| `T.mut.hist` | 29/43 = 67% root, 28/43 = 65% product | MT's first figures, over the first 43 mutants only (72 of 158 runs not run). History; not the current score | research/c3/mt/MT_REPORT.md | mutate.py + kill_check.py | REPORTED (history) | 2026-11-19 |
| `T.repro.rows` | 36 | make reproduce writes 36 rows (V0/V1/V2 x netlists x k); check-reproduce: 36/36 match | results/reproduce_summary.json (key rows, len 36); ci/expected_reproduce.json | `python3 -c "import json;print(len(json.load(open('results/reproduce_summary.json'))['rows']))"`; `make check-reproduce` (copy) | MEASURED | 2026-11-19 RECON / RA |
| `T.repro.witness` | 11 of 36 | Rows whose witness (fault list) differs between runs; verdict and min_faults identical | research/c3/ra/RA_REPORT.md s2 | make reproduce vs stored summary (copy) | MEASURED | 2026-11-19 |
| `T.repro.time` | about 25 s | make reproduce wall time (29.1 s on RA machine); machine dependent | README.md; RA_REPORT.md | `time make reproduce` (copy) | MEASURED (approx.) | 2026-11-19 |
| `T.t3.gates` | check_reproduce --rerun 36/36 match (integration step: 12.9 s); summed row runtime 14.4 s -> 4.2 s (T3); witness set differs 11/36, witness size equal 36/36 | R27 counter encoding applied: reproduce rows unchanged in verdict, min_faults, cycles | research/c4/t3/T3_REPORT.md gate 1; handoff RUN_LOG 214 | `python3 ci/check_reproduce.py --rerun` (on a copy) | MEASURED (integration step 36/36 in 12.9 s); runtimes REPORTED (T3) | 2026-11-19 |
| `T.t3.speed` | dmr k=1 T=4: 1.6 s vs legacy timeout at 150 s (>= 43x); dmr k=1 T=8 34.7 s vs timeout (>= 3.9x); V2 k=2 T=12 0.35 s vs 56.6 s (80x); T=20 0.64 s vs timeout (>= 107x); V2 k=3 T=6 0.05 s vs 4.7 s (28x) | Counter vs legacy PbLe encoding, solve time, reduce full; wall-clock speedups are LOWER BOUNDS where legacy timed out; single runs on a loaded 4-core machine (factor ~2 noise) | research/c4/t3/T3_REPORT.md gate 5; speed_cases.jsonl | `gate5.py speed` on /tmp/work_t3 | REPORTED (T3) | 2026-11-19 |
| `T.t3.xcheck` | 0 disagreements: seeds 1,2,3 = 40+150+150 = 340 netlists x 2 engines x 3 reduce modes (counter mode) | Brute-force cross-check after the encoding change | research/c4/t3/xcheck_t3.log | xcheck_t3.py | REPORTED (T3) | 2026-11-19 |
| `R27.speed` | UNSAT cells 10x to 40x faster (s2 k=2 T=6 2.7 -> 0.26 s; dmr k=1 T=4 149 -> 3.5 s); uart k=3 T=60 SAT 4.5 -> 32.6 s (slower); same verdicts on 14 cells | R27's own experiment (the estimate T3 then measured on the tree) | research/c3/r27/R27_REPORT.md s2-s3; results.jsonl | `python3 exp.py` on a copy | REPORTED (R27) | 2026-11-19 |
| `author.verified` | history: at 2026-11-19 21:5x (current: 133 root / 321 product passed, RECON4, 2026-11-20; 310 at H2/H3 time; 36/36 reproduce rows, H2 report 2026-11-19): check_reproduce --rerun 36/36 in 12.9 s; pytest tests 99 passed; product CLI V2 k=2 none, k=3 min 3, boot_ok 1; m1b CSV byte-identical to M1 CSV; predictor hashes unchanged | What the integration step re-ran after the T3/PRES/M1b hand-backs | handoff/CONTINUATION/RUN_LOG.md entries 212-219 (integration step verification as written there) | integration step, on copies | MEASURED (integration step; RECON2 re-ran the pytest counts and the CSV cmp) | 2026-11-19 |
| `H4.cycles` | `--cycles` or TOML `cycles` above 200 is exit 3 (`MAX_CYCLES = 200`); RT3 reproducer `--cycles 1000000000` exits 3 at once; all 36 reproduce rows use cycles = 6, no verdict affected | H4 fix of RT3 F2 (`product/src/faultbound_wt/config.py`) | research/c5/h4/H4_REPORT.md | `pytest product/tests/test_h4.py`; check_reproduce --rerun 36/36 | MEASURED (H4; RECON4 re-ran 36/36 and 321 tests) | 2026-11-20 |
| `H4.pyyaml` | `pip install ./product[test]` now installs pyyaml: 0 skipped, 321 passed (321 = 310 + 11 in test_h4.py) | `product/pyproject.toml` `[test]` extra | H4_REPORT.md (F3) | RECON4 fresh copy | MEASURED (RECON4) | 2026-11-20 |
| `H4.reportdir` | `--report`, `--badge`, `--sweep-out` into a missing directory: exit 3 before the solve (checked first, no analysis run) | `product/src/faultbound_wt/cli.py` | H4_REPORT.md (F5) | `pytest product/tests/test_h4.py` | MEASURED (H4) | 2026-11-20 |
| `RT3.summary` | about 300 payload runs on the RT2 paths, 0 canaries; F1 (HIGH class, classroom script `docs/edu/tools/synth_merge.sh`) found open and FIXED at integration (verified netlist identity v2 d776226e, v1 931050a5; integration step canary re-test 2026-11-20 02:15); F2 uncapped `--cycles` fixed by H4. Yosys unsandboxed; Action shell steps run locally only and Dockerfile built/run locally only (see ACT.run, DOCKER.run) | RT3 final-gates red team | research/c5/rt3/RT3_REPORT.md | `inj*.sh`, `conc.py` on a copy | MEASURED (RT3); integration step canary MEASURED (integration step) | 2026-11-20 |

## 2 Scope (B2): V0/V1/V2 minimum flips
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `B2.v2.spike.word` | 3 | V2 stored spike netlist, goal boot_word==0x96, input nets not fault sites, known init | research/c2/b2_scope/B2_REPORT.md matrix (v2/spike, word noin known) | `python3 run_matrix.py /tmp/work_b2/nl` (360 cells, matrix.jsonl) | MEASURED | 2026-11-19 |
| `B2.v2.apt` | 2 | V2 re-synthesised with apt Yosys 0.33 (plain and opt), same scope cell | B2_REPORT.md (v2/apt033_plain, apt033_opt) | same | MEASURED | 2026-11-19 |
| `B2.v2.conda` | 3 (plain) / 2 (opt) | V2 conda 0.38 plain gives 3, conda 0.38 opt gives 2 | B2_REPORT.md reading item 1 | same | MEASURED | 2026-11-19 |
| `B2.v2.ok` | 1 | V2, goal boot_ok==1 (flip the boot_ok net) | B2_REPORT.md; README table; CT-1 | `glitchsat check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1` | MEASURED | 2026-11-19 |
| `B2.v2.in` | 1 | V2, input nets counted as fault sites | B2_REPORT.md (word +in known) | run_matrix.py | MEASURED | 2026-11-19 |
| `B2.v2.nongoal` | 1 | V2, arbitrary non-accepting power-up state | B2_REPORT.md (word noin nongoal) | run_matrix.py | MEASURED | 2026-11-19 |
| `B2.free` | 0 | Any design, arbitrary power-up state with no reset (design gap, not a tool finding) | B2_REPORT.md reading item 2 | run_matrix.py | MEASURED | 2026-11-19 |
| `B2.v0v1` | 1 | V0 and V1 in every known-init cell (0 with arbitrary init) | B2_REPORT.md reading item 3 | run_matrix.py | MEASURED | 2026-11-19 |
| `B2.v3` | 3 (where finished) | V3 attempt: cost 3 in finished cells (capped k<=3, many cells NOT RUN) | B2_REPORT.md V3 section | run_v3.py | MEASURED (partial) | 2026-11-19 |
| `B2.cells` | 360 | cells in the V0-V2 scope matrix | B2_REPORT.md | run_matrix.py | MEASURED | 2026-11-19 |
| `E1.free.input` | 3 (V2 spike, k<=2 none) | Free per-cycle attacker input, T=4,6,8; 57-row matrix | research/c2/e1_timevarying/E1_REPORT.md; matrix_bmc_z3.json | z3 + sby + PDR | REPORTED | 2026-11-19 |

## 3 Synthesis variance (E2)
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `E2.configs` | 864 (792 solved + 72 ENGINE_UNSUPPORTED) | configurations: 3 builds x 3 designs x 96 | research/c2/e2_variance/E2_REPORT.md; raw/matrix.csv | `python3 scripts/matrix.py out` | MEASURED | 2026-11-19 |
| `E2.v2.min` | 180 / 60 / 24 | V2 solved configs with min 1 / 2 / 3 (264 solved) | E2_REPORT.md s3; raw/matrix.csv (status SOLVED, design v2, min_flips) | count rows of raw/matrix.csv | MEASURED | 2026-11-19 |
| `E2.v1.min` | 233 / 31 / 0 | V1 solved configs with min 1 / 2 / 3 (264 solved) | E2_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `E2.v0.min` | 264 / 0 / 0 | V0 solved configs with min 1 / 2 / 3 | E2_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `E2.v2.build` | apt 60/24/4; formal 60/18/10; eda 60/18/10 | V2 by build, min1/min2/min3 | E2_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `E2.gates.apt` | V0 25, V1 72, V2 85 | Baseline gate counts (combinational; plus 8 DFF for V1/V2), apt Yosys 0.33, `synth.sh` plain | E2_REPORT.md s2; formal/FORMAL.md | `scripts/synth.sh rtl/vN.v vN out.json plain` | MEASURED | 2026-11-19 |
| `E2.gates.conda` | V0 23, V1 70, V2 83 | Baseline gate counts, conda Yosys 0.38+92 | E2_REPORT.md s2 | same with conda env | MEASURED | 2026-11-19 |
| `E2.baseline.min` | apt V2 2; conda V2 3; V0, V1 1 | Baseline min flips by build | E2_REPORT.md s2 | same | MEASURED | 2026-11-19 |
| `G.v2.85` | 85 (40 AND, 25 OR, 20 NOT, 8 DFF) | V2 apt-0.33 netlist; 85 counts combinational gates only (93 cells in total) | formal/FORMAL.md l.20,35; results/work/v2.json | `python3 -c` count of cells | MEASURED | 2026-11-19 |
| `G.v2.83` | 83 (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF) | V2 conda 0.38+92 netlist | formal/FORMAL.md | same | MEASURED (not re-run by RA/RECON) | 2026-11-19 |
| `G.v2.81` | 81 (38 AND, 23 OR, 18 NOT, 2 MUX) | V2 apt-0.33 opt flow, also a 2-flip attack | results/work/v2_opt.json; docs/ENGINE_STATUS.md l.34 | same | MEASURED | 2026-11-19 |
| `G.v2.spike` | V0 18, V1 58, V2 68 | Stored spike netlists, gate counts (edu answer key) | docs/edu/ANSWER_KEY.md Exercise 1, 3 | `glitchsat check` prints gate count | MEASURED | 2026-11-19 |
| `G.v2.merge` | 63 | V2 apt-0.33 plus opt_merge (edu exercise 3): min 1 flip (hash d776226e); plain 85 hash f954078f | docs/edu/ANSWER_KEY.md; INSTRUCTOR_NOTES.md; WORKSHEET.md | edu_work/synth_merge.sh | MEASURED (edu step) | 2026-11-19 |
| `V.flowB` | 1 (4 of 378 single-flip sites) | V2 on validation flow B (flatten, hierarchy stripped) | validation/VALIDATION.md l.28 | `make validate` | MEASURED | 2026-11-19 |

## 4 Consumer width (M1)
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `M1.masks` | 255 (228 non-colliding, 27 colliding) | Masks tested; colliding ones accept with 0 flips (F0/CC states) | research/c3/m1/M1_REPORT.md s1; m1_all_masks.csv | `python3 mat.py <netlist> <top> 6 out.jsonl 90000` | MEASURED | 2026-11-19 |
| `M1.split` | 88 / 96 / 44 (+27 at 0) | V2 spike masks needing 1 / 2 / 3 flips (of 228 non-colliding) | M1_REPORT.md; m1_all_masks.csv column v2_spike_min_flips | count column | MEASURED | 2026-11-19 |
| `M1.width` | 0,1,1,2,2,3,3,3 | V2 spike min flips for lowest n bits, n=1..8 (masks 0x01,0x03,0x07,0x0F,0x1F,0x3F,0x7F,0xFF) | m1_all_masks.csv; product `--sweep-widths`; research/c4/dash/verify_numbers.py | `faultbound-wt analyze examples/v2.json --config threat.toml --sweep-widths --max-flips 3` | MEASURED | 2026-11-19 |
| `M1.four` | 28 / 36 / 4 of 68 | V2 spike four-bit masks needing 1 / 2 / 3 | M1_REPORT.md table row popcount 4 | m1_all_masks.csv | MEASURED | 2026-11-19 |
| `M1.apt` | 68 mismatches of 255 | Mask rule vs solver on apt-0.33 V2 re-synthesis (rule exact only on stored netlist, 255/255) | M1_REPORT.md s3; docs/FINAL_STATUS.md | pred.py vs m_v2_apt033.jsonl | MEASURED | 2026-11-19 |
| `M1.val` | 255 of 255 agree (T=4, k<=2 brute force) | Independent brute force vs z3, V2 spike | M1_REPORT.md s1 | `python3 bf.py v2 4 2 ...; python3 val.py` | MEASURED | 2026-11-19 |
| `M1.cells` | 1785 cells, 0 unknown | 7 designs x 255 masks | M1_REPORT.md s2 | mat.py | MEASURED | 2026-11-19 |

## 5 Counting rule (DA, REP, R22)
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `REP.unit` | 26 x 2 flips, 6 x 3 flips (of 32 V2) | Stem=1 rule: V2 holds against 2 flips on only 6/32 (18.75%, quoted 19%) | research/c3/rep/REP_REPORT.md; research/c3/rep/rep_results.csv rep_unit_cli | count column rep_unit_cli; DA_CYCLE1.md E1 | MEASURED (DA) + REPLICATED (REP) | 2026-11-19 |
| `REP.fanout` | 32 of 32 at 3 flips (V1: 2 on 32/32) | Fanout-pin counting; stress test only, not shown physical | rep_results.csv column rep_fanout_pins; DA_CYCLE1.md E3 | same | MEASURED | 2026-11-19 |
| `REP.rows` | 64 of 64 agree | REP vs DA, 32 V2 + 32 V1 netlists; one shared recipe list so not independent | REP_REPORT.md verdict | `research/c3/rep/scripts/cli_check.sh`, `research/c3/rep/scripts/rep_measure.py` | MEASURED | 2026-11-19 |
| `REP.recipe` | 2 builds x 2 flows x 8 ABC = 32 | Netlist recipe grid | REP_REPORT.md s2 | gen_rep.sh | MEASURED | 2026-11-19 |

## 6 Real designs (R20)
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `R20.dmr` | 2040 gates / 32 flops; k=1 NO_ATTACK (62 s); k=2 min 2 (46 s) | DMR AES S-box, T=4: the only R20 design not at 1 flip | research/c3/r20/R20_REPORT.md s3 | `glitchsat check --reduce full` | MEASURED | 2026-11-19 |
| `R20.sbox` | unprot 1012/16 -> 1; par 2040/17 -> 1; par2 2040/25 -> 1 | S-box variants, T=4, min flips | R20_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `R20.crc` | crc_plain 40/9 -> 1; crc_tmr 44/11 -> 1 | CRC-8 boot compare | R20_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `R20.uart` | 368 gates / 34 flops; k=0 none, k=1,2 -> 1 (T=6); T=30 k=2 -> 1 (31.8 s) | UART tx; no legit frame | R20_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `R20.keymem` | 32 gates / 7 flops -> 1 | aes_key_mem control, T=8 | R20_REPORT.md s3 | same | MEASURED | 2026-11-19 |
| `R20.designs` | six wrappers/designs | sbox, crc, uart, keymem, dmr, par variants | R20_REPORT.md |  | MEASURED | 2026-11-19 |

## 7 Predictor (PRE, TEST, VER)
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `PRE.train` | V0 255/255, V1 255/255, V2 252/255 (255/255 within 1), V4b 255/255, V5 81/81, V6h 222/222 | Training agreement of the structural predictor (optimistic: designed with it in view) | research/c4/pre/PRE_REPORT.md; test_training.py | `pytest research/c4/pre/test_training.py` | MEASURED | 2026-11-19 |
| `TEST.pooled` | 928/928 exact (100%) | Pre-registered held-out test, 928 unique cells (E2 407, R20 11, M1 V2 255, M1 V1 255); effective sample 3-5 designs; 684 cells are min 1, 54 collisions | research/c4/test/TEST_REPORT.md; analysis.txt | `python3 -I run_test.py e2\|m1\|r20; python3 -I analyze_test.py` | MEASURED | 2026-11-19 |
| `TEST.confusion` | 0:54, 1:684, 2:170, 3:20 | Solver minimum counts in the 928 cells | TEST_REPORT.md | same | MEASURED | 2026-11-19 |
| `TEST.speed` | 7.3x E2, 3.4x/2.8x M1, 1.0x R20 | Predictor vs solver runtime, uncontrolled; VER found 1.4x SLOWER on held-out. No speedup claim | TEST_REPORT.md; VER_REPORT.md s3.4 | per-cell times | MEASURED (not controlled) | 2026-11-19 |
| `VER.heldout.exact` | 150/163 = 92.0% | FRESH held-out, 76 netlists/163 cells: exact matches AFTER the x-init corrections (rerun_x.json) and with '>3' compared as 4 and pred capped at 4 (PREREG rule). THIS IS THE CORRECTED FIGURE | research/c4/ver/VER_REPORT.md s3.1; heldout.csv + rerun_x.json | `python3 -I heldout.py; python3 -I rerun_x.py` then count pred==solver with the rules above (RECON recomputed: 150) | MEASURED | 2026-11-19 RECON |
| `VER.heldout.raw` | 144/163 | Naive string compare of columns pred==solver in heldout.csv. Differs from 150 by: +4 cells where solver '>3' vs pred 100 (lb sentinel 99+1, equals '>=4' under the PREREG cap) and +2 cells (rc103_opt 0x18, rc117_opt 0xf) whose solver column still holds the pre-correction gs_mask.py x-init value. NOT a headline number | research/c4/ver/heldout.csv | `python3 -c "import csv;h=list(csv.DictReader(open('research/c4/ver/heldout.csv')));print(sum(x['pred']==x['solver'] for x in h))"` | MEASURED (a raw column count, not the audit figure) | 2026-11-19 RECON |
| `VER.heldout.split` | within 1: 156/163 (95.7%); over 6; under 7; solver>=2: 18/31 (58%) | FAILS the 98% within-1 bar; 7 under-predictions are the unsafe `uncovered` fallback lb+1 | VER_REPORT.md s3.1-3.2 | confusion matrix in the report | MEASURED | 2026-11-19 |
| `VER.heldout.safe` | false-safe 0, false-weak 0, lb>solver 0 in 928+163+60 cells | Bound soundness | VER_REPORT.md s3.1, s5 | same | MEASURED | 2026-11-19 |
| `VER.resample` | 60/60 | Independent resample of corpus cells reproduces the CSV | VER_REPORT.md s2 | `python3 -I resample.py` | MEASURED | 2026-11-19 |
| `VER.runtime` | predictor 251 s vs solver 184 s on 163 cells (1.4x slower) | Not a controlled benchmark | VER_REPORT.md s3.4 |  | MEASURED (contended machine) | 2026-11-19 |
| `VER.xinit` | 47 x-init cells rerun, 2 changed | gs_mask.py maps x->0 and can clobber an aliased flop init; scripts/glitchsat.py rejects x init | VER_REPORT.md s3.3; rerun_x.json | `python3 -I rerun_x.py` | MEASURED | 2026-11-19 |
| `VER.percent` | 92% overall; 58% when 2+ flips needed | Headline wording for the predictor (heuristic search, not validated estimator) | VER_REPORT.md s5 |  | MEASURED | 2026-11-19 |

## 8 SPICE, rail-dip, formal, layout, misc
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `EL1.dip` | 0 of 60 dip points flipped a stored flop (0 V for 3 ns) | SPICE (ngspice, sky130 cells): supply dip alone never flipped Q | research/c2/el1_spice/EL1_REPORT.md A; fault_windows.json key A_supply_dip | expA.py | SIMULATED | 2026-11-19 |
| `EL1.runt` | tt: 1.3 V runt (0.1 ns) captures D; 0.9 V needs 2 ns; 0.5 V none | Clock runt makes flop capture D (wrong-time capture) | EL1_REPORT.md B | expBC.py | SIMULATED | 2026-11-19 |
| `EL1.setup` | about 50 to 75 ps (tt, 1.8 V); about 100 ps (1.2 V); 25 ps grid | Latest data change still captured before the edge. Do not quote as attack parameters | EL1_REPORT.md C | expBC.py | SIMULATED | 2026-11-19 |
| `B3.model` | V2 and V5: no attack up to 3 events under rail_all / half / unions / cone; V0 cone 1 event | Rail-dip model, T=6, <=3 events, 0 unknown | research/c4/b3/B3_REPORT.md Plain answers; matrix_T6.jsonl | `python3 run_cells.py` | SIMULATED | 2026-11-19 |
| `B3.subset` | 1 event; smallest domain 3 gates (V2, V5), 2 (V1) | dip_subset upper bound: one event may choose which gates fall (selectivity open) | B3_REPORT.md; minsubset.py | `python3 minsubset.py v2,v2_apt033,v5_apt033,v1` | SIMULATED | 2026-11-19 |
| `F.pdr` | V2 spike k=2 PASS in 0.83 s (unbounded, ABC PDR); replicated by a second, independent implementation (ext/unbounded: k=0,1,2 proved for all time, k=3 attack, same netlist) | Needs conda env `formal`; not re-run by RA or RECON | docs/FINAL_STATUS.md; formal/FORMAL.md | `sby` / abc pdr in env formal | MEASURED by the integration step (not re-run by RECON) | 2026-11-19 |
| `F.sby` | 40 netlist/k pairs match | sby BMC depth 6 vs solver | formal/FORMAL.md l.25 | formal/runs/bmc_matrix*.json | REPORTED | 2026-11-19 |
| `F.valid` | ~2.1M fault sets x 255 inputs, 0 disagreements; 13/13 replays; 5 boolector queries | Independent simulator vs solver | validation/VALIDATION.md l.21,24 | `make validate` | MEASURED | 2026-11-19 |
| `F.sets` | 46,056 (T=4) and 103,740 (T=6) 2-flip sets, none succeed on V2 spike; 70,300 3-flip sets all cycle 1, 182 attacks; all 15,699,320 triples at T=6 enumerated (--reduce none): 182 attacks, all cycle 1 (reference netlist; placed V2 has 22) | Exhaustive fault-set enumeration | validation/VALIDATION.md l.18-19 | `make validate` | MEASURED | 2026-11-19 |
| `F.deep` | V2 spike k=2 at 20 cycles 294.3 s; k=3 474.9 s | Deep sweep | docs/DEEP_RESULTS.md l.36-37; results/deep/sweep_main.json |  | MEASURED | 2026-11-19 |
| `L.cells` | V0 10 cells 89 um2; V1 35 / 358 (357.8); V2 36 / 363 (362.8) | Layout flow demo cell count/area, patched flow; slack +7.050 / +7.035 ns (estimate, not signoff) | layout/v_designs/out_patched/RESULT.md l.7,10; docs/dossier/PROJECT_DOSSIER.md 7.9 | flow_patched/all.sh | ESTIMATED / MEASURED flow output | 2026-11-19 |
| `L.lvs` | V1 422 vs 422 devices, 225 nets; match uniquely (V1, V2) | netgen LVS | layout/v_designs/out_patched/RESULT.md |  | MEASURED | 2026-11-19 |
| `L.antenna` | 0 pin / 0 net violations; 0 off-grid | OpenROAD check_antennas, klayout grid | layout/verify/VERIFY.md |  | MEASURED | 2026-11-19 |
| `H.hamming` | 4 (code F0,CC,96,69; 96/69 complement distance 8) | Minimum pairwise Hamming distance of the state code | docs/dossier/test_hamming.py; RA item 22 | `python3 docs/dossier/test_hamming.py` | MEASURED | 2026-11-19 |
| `N.sqrt` | 7.15 LSB at input 31797; 25 inputs above 6 LSB; CBMC bound 8 | sqrt_q15 numerics spike | numerics_audit/AUDIT.md l.12-13 | not re-run | UNVERIFIED (spike result) | 2026-11-19 |
| `N.fuzz` | 0 mismatches in about 6,700 programs | Fuzzing spike; data not in repo | handoff/CONTINUATION/earlier_research/gasp/GASP_DECISION.md l.27 | none | UNVERIFIED / REPORTED | 2026-11-19 |

## 9 C4 additions (RECON2): layout, L2, B3, product options, EDU2, DASH, QA, M1b
Status here: REPORTED = taken from the step's report; no solver, flow or SPICE was re-run by RECON2. "RECOUNTED" = RECON2 recomputed the number from the step's stored data files with `python3 scripts/check_numbers.py --verify` (no tool re-run). MEASURED only where RECON2 or the integration step re-ran the command.
| id | value | meaning | source (file, key/line) | how measured | status | date |
|---|---|---|---|---|---|---|
| `LAY.radius` | 2.95 um | Smallest enclosing-circle radius (cell centres) of the cheapest sufficient one-event set of V2 (three nand4bb cells c0/c1/c2 `_2_`); cells are 1.4 to 5 um wide so the real disc is somewhat larger. Geometry MEASURED from DEF; verdict SIMULATED and only under the selective force-to-0 (supply-dip) model. Under the bit-flip model a sufficient triple {c0/_2_, c1/_4_, c2/_4_} lies within 1.665 um; placed V2 has 22 flip triples, all in cycle 1; one shot opens V2 from 1.75 um (centre rule) or 0.25 um (overlap rule, ASSUMED); with set0 and no selection no single shot works | research/c4/layout/LAYOUT_REPORT.md s2, s5; minsets_v2.json | `minsets.py` (z3, B3 engine) on DEF placement; RECOUNTED by check_numbers --verify | MEASURED geometry / SIMULATED verdict; REPORTED, RECOUNTED | 2026-11-19 |
| `LAY.minsets` | 4 minimal one-event sets, all 3 cells, all cycle 1: r 2.95 / 3.06 / 3.29 / 4.58 um (word and ok) | Enumeration limited to <= 4 cells and 400 sets, so radii are upper bounds | LAYOUT_REPORT.md s2; layout/minsets_v2.json | minsets.py; RECOUNTED | SIMULATED; RECOUNTED | 2026-11-19 |
| `LAY.supply` | one VPWR net: ONE met4 VPWR strap (x=9.22), ONE met4 VGND strap (x=19.22), no ring; 4 VPWR rails join the strap at one column; 36 logic cells in a 30.6 um die, 77% utilisation | Electrically one supply net fed at one column. This is an INFERRED reading of the DEF; no extraction, no IR-drop solve | LAYOUT_REPORT.md s2 (DEF SPECIALNETS) | layout_extract.py (plain Python) | MEASURED (DEF read) / INFERRED (reading); REPORTED | 2026-11-19 |
| `LAY.whatif` | 4.58 um (nand4bb triple) and 6.13 um (nand2 triple) after 3 same-footprint swaps; rail families still 1 | HYPOTHETICAL placement; routing, timing, DRC, LVS not redone. Not a layout that exists | LAYOUT_REPORT.md s6; whatif.py | whatif.py -> minsets.py | HYPOTHETICAL; REPORTED | 2026-11-19 |
| `L2.spacing` | min copy-to-copy centre distance: base 1.84 um, v8 9.2, rr 16.3, s8 17.9, v15 23.5 (bbox gap 0, 5.98, 13.6, 14.7, 20.2) | Real OpenROAD runs with the 9 cells of c0/c1/c2 pinned (`pnr_l2.tcl`); same netlist as the original V2 (byte-identical `v2_net.v`) | research/c4/l2/L2_REPORT.md results table; data/metrics_<var>.json pairwise_copy_distance | `run_var.sh` then `metrics.py` (step); RECOUNTED from metrics_*.json | MEASURED placement; REPORTED, RECOUNTED | 2026-11-19 |
| `L2.radius` | smallest sufficient one-event set radius: base 2.95, v8 11.15, s8 17.91, v15 15.16, rr 15.30 um (x3 to > x5); v8's true threshold lies in (8, 10] um | Upper bounds from a <= 4-cell enumeration; the sweep (primitive-level, any size) is authoritative. Thresholds depend on where the placer put `_16_` (output inverter), which was not pinned. All radii are for the selective force-to-0 (supply-dip) model; under the bit-flip model the base triple lies within 1.665 um | L2_REPORT.md security-model table; data/minsets_<var>.json, sweep_<var>.json | `dom.sh <var>` (z3, T=6, <= 3 events); RECOUNTED | SIMULATED on MEASURED placement; RECOUNTED | 2026-11-19 |
| `L2.selectivity` | selectivity threshold (SUB cost 1 first at r): base between 2.5 and 3.0 um; v8 between 8 and 10; s8 > 15 (SUB 2 at 15); v15 15 (SUB 2 at 10); rr 15 (SUB 2 at 8, 10) | Radius sweep r = 3, 5, 10, 15 um; AoN = all cells of the disc fall, SUB = one event picks which fall (selective force-to-0 model; with set0 and no selection no single shot works; under a bit flip one shot opens V2 from 1.75 um centre rule / 0.25 um overlap rule, ASSUMED) | L2_REPORT.md radius sweep table; data/sweep_<var>.json | dom.sh | SIMULATED; REPORTED | 2026-11-19 |
| `L2.rail_all` | rail_all (whole die, one selective event): still 1 / 1 (word / ok) in ALL five variants | Hardening by distance does not remove a die-wide selective dip: the three copies stay on the same two supply nets (one PDN) | L2_REPORT.md rail-level paragraph; data/fam_<var>.jsonl | dom.sh; RECOUNTED (family rail_all, mode subset) | SIMULATED; RECOUNTED | 2026-11-19 |
| `L2.rail.perrail` | VPWR rail family SUB cost: base 1/1, v8 2/2, s8 2/2, v15 2/2, rr 3/2 (word/ok); VGND rail 2/2 everywhere; strap-branch base 1/1, v8 2/2, s8 and v15 3/3, rr 3/2 | Per-rail events: 1 -> 2 (v8, s8, v15) and 3 (rr, word goal) once the copies sit on different rails; row 2/2 (rr 3/2). Rail families are only 1 to 2 rows wide here | L2_REPORT.md rail-level paragraph; data/fam_<var>.jsonl | dom.sh; RECOUNTED for rail_all and VPWR rail | SIMULATED; RECOUNTED (VPWR rail), REPORTED (strap, VGND, row) | 2026-11-19 |
| `L2.cost` | die area x1.26 (v8: 936 -> 1183 um^2) to x2.5 (v15: 2362); cell area +0.3% to +7%; detailed wire length +29% (v8), +31% (s8), +36% (rr), +50% (v15: 1418.7 vs 949 um, 49.5%); slack change <= 0.02 ns (estimate, no extraction) | Cost of spreading | L2_REPORT.md results table and cost paragraph; data/summary_flow.json | run_var.sh; RECOUNTED wire percentages | MEASURED flow output (step); RECOUNTED wire length | 2026-11-19 |
| `L2.drc` | router DRC 0 violations in 5 of 5 variants; antenna 0 pin / 0 net in 5 of 5; magic top-cell DRC 15 / 20 / 24 / 18 rules in the 4 spread variants (none listed for base); LVS match uniquely for base (430/430 devices, 226/226 nets) and **FAILS in 4 of 4 spread variants** (pin matching: 428/430, 427/430, 425/430, 427/430) | Cause: li1 wire crossing a row boundary touches a filler VGND in magic's view (the same flow bug as VERIFY.md s3). NOT fixed, not suppressed; the spread layouts are an experiment, not a fix | L2_REPORT.md DRC/LVS paragraph; data/summary_flow.json | run_var.sh, magic, netgen; RECOUNTED LVS pass/fail, router DRC, antenna | MEASURED flow output (step); RECOUNTED | 2026-11-19 |
| `L2.sim` | decomposed layout netlists equal the original on all 256 sig values over 5 cycles (0 of 256 differ) | Function unchanged at netlist level | L2_REPORT.md limits; lay/<var>/sim.log | simcheck.py | MEASURED (step) | 2026-11-19 |
| `EL1.simul` | all high gates on a dipping rail droop together (inv and nand2 within ~0.01 V); clean-rail flop mis-samples at tt 3 ns with Vmin <= 0.5 V, tt/ss/ff 1 ns only at 0 V; none at 0.3 ns; 60 dip points + 48 runt points | Basis for the rail-dip model: correlated 1 -> 0 sag, flop Q not flipped. One tiny rail with a handful of gates, so it cannot show a real dip cannot be selective | research/c2/el1_spice/EL1_REPORT.md A, B; fault_windows.json | ngspice-41, sky130 tt/ss/ff | SIMULATED | 2026-11-19 |
| `B3.matrix` | T=6, <= 3 events, 0 unknown: rail_all / rail_half / rail_unions `>3` for V0, V1, V2, V2 apt, V5 apt (word and ok); rail_cone V0 1 (V0 apt 1), V1/V2/V5 `>3`; dip_subset (one event picks which gates fall) 1 for every design; early_*/hold_* `>3`; baseline stem_flip V2 spike 3 / apt 2 / boot_ok 1 | `>3` = UNSAT for cost <= 3, NOT 'secure'. Verdict depends on selectivity | research/c4/b3/B3_REPORT.md matrix; matrix_T6.jsonl (182 rows) | `python3 run_cells.py` (step); RECOUNTED from matrix_T6.jsonl | SIMULATED (fault model) / MEASURED solver output (step); RECOUNTED | 2026-11-19 |
| `B3.valid` | brute force vs z3: 0 disagreements on V0 (T=4, k<=2, 9 models) and V1 (T=3, k<=2, 9 models); dip_subset V0 T=4 k=1: 1,048,579 sets, z3 1 = brute 1; NOT validated: V2, V5, apt rows, T=6 | Independent checker bf_b3.py, no z3 | B3_REPORT.md Validation; val.log | bf_b3.py | MEASURED (step); small scope | 2026-11-19 |
| `FIX2.rail.v1` | V1 also >3 events under whole-rail and half-design 1-to-0 events (T=6, 3 events); V2 and V5 >3 | Polarity result, not a benefit of triplication; selective event costs 1 on V2; 0-to-1 control done by LEDGER (rise_unions/rise_half cost 1 on V0, V1, V2, V5) | research/c4/b3/B3_REPORT.md matrix | `python3 run_cells.py matrix_T6.jsonl ...` | SIMULATED basis, MEASURED verdict (z3 alone for V2/V5) | 2026-11-19 |
| `FIX2.synfi` | SYNFI: faults needed 3->2 (FSM recoding), 4->2 (register merging), restored 4 by set_dont_touch | Previously shown; our E2 replicates on a toy design | research/c4/sweeps/SWEEP_S2.md s1, 2b | none (paper text read) | SOURCED | 2026-11-19 |
| `PS4.opts` | shipped in `faultbound-wt`: `--consumer-bits`, `--goal-out/--accept-value`, `--input-sites {none,all}`, `--init {known,arbitrary}`, `--scope-sweep` (+ `--sweep-masks`, `--cell-timeout-ms`, `--sweep-out`); NOT shipped: `--count-rule branch` (exit 3), per-cycle attacker input | Exit codes 0/1/2/3/4 and schema `faultbound-wt-report/1` unchanged | research/c4/ps4/PS4_REPORT.md | CLI runs on spike V2 (step); integration step: product CLI V2 k=2 none / k=3 min 3 / boot_ok 1 | MEASURED (step; integration step re-ran the three default cells) | 2026-11-19 |
| `PS4.sweep` | scope sweep V2 (columns none+known, all+known, none+arbitrary, all+arbitrary): word 3,1,0,0; bits 0xF 2,1,0,0; bits 0x6A 3,1,0,0; boot_ok 1,1,0,0 (33 s) | Same numbers as B2 scope table (word 3, input sites 1, arbitrary power-up 0) and as PRES / EDU2 re-runs (PRES: 17.9 s for masks 0x0F, 0x6A) | PS4_REPORT.md; research/c4/ps4/data/sweep_v2.json; PRES_REPORT.md; EDU2_REPORT.md | `faultbound-wt analyze ... --max-flips 3 --scope-sweep --sweep-masks 0x0F,0x6A`; RECOUNTED from sweep_v2.json | MEASURED (PS4, PRES, EDU2 steps); RECOUNTED | 2026-11-19 |
| `PS4.masks` | consumer masks vs m1_all_masks.csv: 10 of 10 popcount-4 masks agree (seed 7), plus 10 of 10 mixed masks incl. one colliding (seed 4): 20 of 255 masks; --input-sites all gives 1 (`c0.a[1]@1`); --init arbitrary gives 0 | Not the full table | PS4_REPORT.md verification | data/masks.py | MEASURED (step) | 2026-11-19 |
| `PS4.tests` | test_ps4.py: 25 tests; clean venv (copy lacking T2 files): 62 passed, 1 skipped in 81 s | Superseded as a total by T.prod.passed (321 passed after RECON4; 310 at H2/H3 time; 139 + 1 skipped was the count then) | PS4_REPORT.md | pytest in a copy | REPORTED | 2026-11-19 |
| `PS5.width` | width curve n=1..8: 0,1,1,2,2,3,3,3 (18 s, `--sweep-widths --max-flips 3`) equal to m1_all_masks.csv column v2_spike_min_flips for masks 0x01,0x03,0x07,0x0F,0x1F,0x3F,0x7F,0xFF | Same as M1.width, now through the shipped CLI; EDU2: V1 0,1,1,1,1,1,1,1; mini_v2 n=1..4 0,1,2,2 | research/c4/ps5/PS5_REPORT.md item 5; research/c4/edu2/EDU2_REPORT.md; test_sweep_widths_matches_m1_csv | `faultbound-wt analyze examples/v2.json --config threat.toml --sweep-widths --max-flips 3` | MEASURED (PS5, PRES, EDU2 steps; check_numbers --verify recomputes the curve from the CSV) | 2026-11-19 |
| `PS5.scope` | scope sweep rows 3,1,0,0 (word) / 2,1,0,0 (0x0F) / 3,1,0,0 (0x6A) / 1,1,0,0 (boot_ok) | The 'scope sweep 3,1,0,0' headline = V2 word goal across none+known, all+known, none+arbitrary, all+arbitrary | see PS4.sweep | see PS4.sweep | MEASURED (steps); RECOUNTED | 2026-11-19 |
| `PS5.opts` | `--timeout-s 3` on a cell needing ~8 s: exit 2, UNKNOWN_TIMEOUT, `timed_out: true` (PRES: `--timeout-s 2` exit 2 after 2.1 s; 0.05 s returns in 0.17 s); `--init free_nongoal` V2 k<=2: ATTACK_FOUND 1 flip (boot_word[4]@0); 8 tests in test_ps5.py | Timeout gives no partial sweep table; Linux only | PS5_REPORT.md items 2-3, 6; PRES_REPORT.md | faultbound-wt CLI on spike V2 | MEASURED (steps) | 2026-11-19 |
| `EDU2.rerun` | 40 commands of the answer key re-run (exit codes in verification.log); no minimum-flip number changed: Ex1 V0 1 / V1 1 / V2 3; Ex3 plain 85 gates min 2 (hash f954078f), merge 63 gates min 1 (d776226e); V2 k=3 about 8 s (was 'about 12 s'); run sheet about 100 min (86 without Ex 7-8), ESTIMATE, UNPILOTED | Lab kit moved to the shipped CLI; Yosys 0.33 only (counts and hashes differ on other builds) | research/c4/edu2/EDU2_REPORT.md; verification.log; verify_edu2.sh | `sh verify_edu2.sh` in a copy (step) | MEASURED (step); schedule ESTIMATED | 2026-11-19 |
| `DASH.values` | 115 values compared (scope table 20, widths 16, E2 3 rows, rail table 25, engine summary, curve runtimes): 115 match, 0 mismatches; 0 console errors at 390 and 1366 px; smallest text 12.48 px; text/background contrast >= 4.5:1 | Numbers page vs source data files; does not check prose | research/c4/dash/DASH_REPORT.md; verify_numbers_output.txt | `python3 research/c4/dash/verify_numbers.py` (step); headless Chrome | MEASURED (step); not re-run by RECON2 | 2026-11-19 |
| `QA.falsify` | 19 repo claims listed with a one-command falsifier (section 7); 11 re-run by the QA step (rows 1-9, 11, 19), 5 UNVERIFIED (10, 12, 13, 14, 16), 3 not rebuildable from the bundle (15, 17, 18); 48 questions, weakest 10 | Rows 9 (test count) and 11 (144 vs 150) were found stale/unreconciled and are fixed in the docs by RECON/D3/RECON2 (QA's own report still shows them) | research/c4/qa_sim/QA_SIM_REPORT.md s7 | commands in the report | REPORTED | 2026-11-19 |
| `M1b.cells` | 0 of 1785 cells changed (7 designs x 255 masks, two independent engines); `m1b_all_masks.csv` byte-identical to `m1_all_masks.csv`; no x init in any of the 7 netlists; rule 255/255 on spike V2, 68 mismatches on apt-0.33 V2 unchanged; B2 headline: 30 cells, 0 differences | No published M1 claim changes. Only the 7 M1 netlists were checked (opt-flow held-out netlists with 'xx1001' init were not) | research/c4/m1b/M1B_REPORT.md | `sh runall.sh mat2.py`, `diff.py`; CSV cmp | MEASURED (step); CSV identity MEASURED by the integration step and RECON2 (`cmp`, check_numbers --verify) | 2026-11-19 |
| `E2.unique` | 24 configs at min 3 = 20 unique netlists (TEST's '20 cells at min 3') | Say which one you mean: configs 24 or unique netlists 20 | research/c4/recon/RECON_REPORT.md s4; TEST_REPORT.md | see E2.v2.min | MEASURED (RECON) | 2026-11-19 |
| `REP.pct` | 6/32 = 18.75%, quoted as 19% | Stem rule: V2 survives 2 flips on 6 of 32 netlists | see REP.unit | see REP.unit | MEASURED | 2026-11-19 |
| `PRE.train` | V2 spike 252/255 exact, 255/255 within 1; 0 bound violations, 0 false-safe; optimistic (designed with the data in view) | Companion to PRE.train row in section 7; held-out audit figure is VER.heldout.exact (150/163) | research/c4/pre/PRE_REPORT.md; test_training.py | pytest research/c4/pre/test_training.py | MEASURED (step); predictor hashes verified by the integration step | 2026-11-19 |

## 10 Wave-2 figures (FIX3, read from the named reports, not re-run by FIX3 unless marked)
| id | value | meaning | source | how measured | status | date |
|---|---|---|---|---|---|---|
| `DA3.E2.distinct` | 152 distinct netlists among 264 solved V2 configs; min 1/2/3 = 94/38/20 | E2 split per distinct canonical netlist (180/60/24 is per config) | research/c5/da3/DA3_REPORT.md A2 | `python3 -I c.py` on raw/matrix.csv (DA3) | MEASURED (verified by DA3) | 2026-11-19 |
| `DA3.pred.baseline` | always-1 101/163 = 62%; sound lower bound alone 136/163 = 83% | trivial baselines next to the predictor's 150/163 = 92% | DA3_REPORT.md A7; research/c4/ver/heldout.csv | recount of the `lb` column, '>3' as 4 (FIX3 recount: lb 136) | MEASURED | 2026-11-19 |
| `LEDGER.pred.sample` | 71/71 exact (stratified E2 sample); 4/6 on fresh RTLs (wrong on V2m, V5) | predictor on the same family vs fresh designs | research/c5/ledger/LEDGER_REPORT.md s4 | frozen predictor sha a9e43ef9 | MEASURED | 2026-11-19 |
| `DA3.rule.apt` | one-liner min(Hamming, copies touched) = 255/255 spike, 187/255 apt | consumer-mask rule is cut/Hamming reasoning | DA3_REPORT.md A1 | a.py on m1_all_masks.csv | MEASURED | 2026-11-19 |
| `LEDGER.rise` | rise_unions / rise_half = 1 for V0, V1, V2, V5 (T=6, k<=3); rise_all and rise_cone >3 for word goal | rail 0-to-1 control | LEDGER_REPORT.md s2; data/pol.jsonl (196 cells) | b3pol.py (copy of B3 engine; no independent checker) | SIMULATED | 2026-11-19 |
| `ANCHOR.bf` | V2 spike k=3 T=3/4: 182 attacking triples, none smaller; V2 apt k=2: 3 pairs; 32 rail rows agree (T=4, k<=2); selective sets: 22 of size 3, none of size 1 or 2 | z3-free brute-force anchors | research/c5/anchor/ANCHOR_REPORT.md s1 | anchor_sim.py, dip_subset_bf.py | MEASURED | 2026-11-19 |
| `ANCHOR.grid` | 24 REP/E2 netlist pairs agree 24/24 on min flips; REP 6/32 and E2 180/60/24 not comparable | grid reconciliation | ANCHOR_REPORT.md s4 | grid_reconcile.py | MEASURED | 2026-11-19 |
| `RT2.findings` | N1 HIGH (command execution via `top`/path in yosys -p); N2-N5 MED; N6-N14 LOW to LOW-MED | product red-team wave 2 | research/c5/rt2/RT2_REPORT.md | run on copies by RT2 | MEASURED | 2026-11-19 |
| `FIX3.155` | DA3's 155 not reproduced; heldout.csv: raw 144, est column 144, pred column 148 ('>3' as 4), 150 after x-init corrections | reconciliation of 150 vs 155 | FIX3 recount of research/c4/ver/heldout.csv | python3 recount | MEASURED | 2026-11-19 |

## 11 Wave-2b/3 additions (RECON3, 2026-11-20): H2, H3, PS6, RT2, ANCHOR, LEDGER, DASH2
Labels: MEASURED (RECON3) = RECON3 re-ran it on the fresh copy (see "How RECON3 re-measured"). MEASURED (RUN_LOG n) = the integration step's own re-run, as logged in handoff/CONTINUATION/RUN_LOG.md entry n (195 PS4, 214 T3, 235 H2, 236 H3). REPORTED = taken from the step report, not re-run by RECON3. RECOUNTED = recomputed from stored data.
| id | value | meaning | source | how measured | status | date |
|---|---|---|---|---|---|---|
| `H2.tests` | product/tests 310 passed = 175 pre-existing + 135 new in `product/tests/test_h2.py` (H2 copy, 101 s); in the tree after applying: `test_h2.py` 135 passed. RECON3 fresh copy: 310 passed in 80.9 s (310 at H2/H3 time; 321 after H4, RECON4) | Hardening of the product after RT2 findings N1..N14 | research/c5/h2/H2_REPORT.md | `pytest -q product/tests` (H2 copy; RECON3 copy) | MEASURED (RECON3 and H2) | 2026-11-20 |
| `H2.canary` | pre-H2 source: `faultbound-wt analyze m.v --top 'm; exec -- touch X; hierarchy -top m'` created the canary file; after H2: `error: top ... is not a plain module identifier`, exit 3, no canary; same for a Verilog file name with `; exec`; integration step re-ran on a fresh venv: top payload exit 3 and file-arg payload exit 3, canary not created | N1 HIGH (command execution through the Yosys script) fixed in the product: names validated, `yosys -q -s flow.ys` script file, no shell, no `-p` | H2_REPORT.md s1; RUN_LOG 235 | canary file check before/after | MEASURED (H2; integration step, RUN_LOG 235) | 2026-11-19 |
| `H2.newtests.onold` | the new tests fail on the pre-H2 source: 68 of 114 finished cases failed (run hung at N7 CPU burn; N8/N9/N10 not run on old) | The new tests detect the bugs | RUN_LOG 235; H2_REPORT.md | new tests against /tmp/work_h2/orig | REPORTED (H2) | 2026-11-19 |
| `H2.chk_repro` | `ci/check_reproduce.py --rerun`: a mismatching engine row now counts as FAILED (35/36 + 1 row(s) FAILED, exit 1, test with a fake engine); ENGINE_MANIFEST (SHA-256 of `scripts/glitchsat.py`, `scripts/synth.sh`) warns when they differ; RECON3 fresh copy: `check_reproduce.py` 36/36 and `--rerun` 36/36, 0 FAILED, no manifest warning (the integration step updated ENGINE_MANIFEST at 22:46) | N2/N13 | H2_REPORT.md s3; RUN_LOG 236 | `python3 ci/check_reproduce.py [--rerun]` | MEASURED (RECON3; H2) | 2026-11-20 |
| `H3.tests` | root tests 133 passed = 99 + 34 new in `tests/test_h3.py` (H3 copy; RECON3 fresh copy 133 passed in 18.3 s); in the tree after applying: `test_h3.py` 34 passed | H3 closed the N1 residue in `scripts/synth.sh` and `glitchsat.py check` | research/c5/h3/H3_REPORT.md | `pytest -q tests` | MEASURED (RECON3 and H3) | 2026-11-20 |
| `H3.canary` | old `synth.sh` with `--top 'v0; exec -- touch CANARY'`: canary created; new `synth.sh` and `glitchsat.py check`: 9 bad-top payloads and 6 bad file/out payloads (both args) all exit non-zero, no canary; integration step re-ran on a fresh venv: top and file payload refused, no canary. Behaviour change: Verilog paths containing `;`, quotes, backslash or `#` now fail | N1 residue closed | H3_REPORT.md; RUN_LOG 236 | canary check | MEASURED (H3; integration step, RUN_LOG 236) | 2026-11-19 |
| `H3.sha` | netlist sha256 old vs new `synth.sh`, Yosys 0.33, rtl/v0, v1, v2 x flows plain and opt (relative paths): 6/6 identical | The validation does not change any netlist | H3_REPORT.md | sha256 of yosys output | MEASURED (H3) | 2026-11-19 |
| `H23.notfixed` | not fixed: Yosys reading a hostile `.v` file's own contents (`include`); coordinated edits of several files in one tree are not detectable by `check_reproduce.py`; SIGKILL of the parent leaves a worker temp dir `fbwt_w_*`; Action and `yosys_flow.sh` changes not run on GitHub; bare `3` in `--consumer-bits` was bit 3 and is now mask 3 (behaviour change) | Open items after H2 and H3 | H2_REPORT.md; H3_REPORT.md; RUN_LOG 235, 236 | read | REPORTED | 2026-11-19 |
| `PS6.tests` | product tests 174 passed, 1 skipped on the PS6 copy (clean venv, 86 s) incl. `test_ps6.py` 35 tests (18 passed, 17 skipped when Yosys is off PATH). Superseded as a total by T.prod.passed (321; 310 at H2/H3 time) | PS6 added counting rules and the synthesis-flow sweep to the product | research/c5/ps6/PS6_REPORT.md | pytest in a copy | REPORTED (PS6) | 2026-11-19 |
| `PS6.count` | `--count-rule stem/fanout/fanout_pins/fanout_gates`: spike V2 boot_word min flips 3 / 3 / 3 (stem / fanout / fanout_gates); with `--input-sites all`: stem 1, fanout_pins 3. REP comparison: 32 regenerated apt-0.33 netlists, 32 agree on sha16 and all three costs, 0 differ (not compared: REP's 32 Yosys-0.38 netlists). Counting rule `branch` not implemented (exit 3) | The rule changes the answer on only some cells; that a rule is physically meaningful is not claimed | PS6_REPORT.md Verification; research/c5/ps6/rep_compare.csv | `faultbound-wt analyze ... --count-rule ...`; `python3 -I research/c5/ps6/rep_compare.py` | REPORTED (PS6) | 2026-11-19 |
| `PS6.synth` | `--synth-sweep` on rtl/v2.v, apt Yosys 0.33, 8 built-in variants (~5 s): plain 85 gates 2 flips; plain_opt_merge 63 gates 1 flip; flatten_before_abc 71 gates 1; abc_fast 88 gates 2; abc_no_mux byte-identical to plain; opt_flow 81 gates 2; plain_keep_off 83 gates 2; opt_flow_keep_off 81 gates 2; summary: min flips ranged 1..2. Not the E2 matrix (864 configs); the 0.33 vs 0.38 difference is not reproduced here | The build flow changes the answer | PS6_REPORT.md; research/c5/ps6/synth_sweep_v2.csv; product/examples/synth_sweep/expected_output.txt | `faultbound-wt analyze rtl/v2.v --top v2 --synth-sweep --max-flips 4` | REPORTED (PS6); gate counts 85/63 agree with EDU2 and DA | 2026-11-19 |
| `PS4.PS5.status` | PS4 (consumer bits, goal/accept, input sites, init, scope sweep) and PS5 (width sweep, timeout, `--init free_nongoal`) are listed in rows PS4.opts, PS4.sweep, PS4.masks, PS4.tests, PS5.width, PS5.scope, PS5.opts; integration step re-ran PS4 on a fresh venv: V2 spike k=2 NO_ATTACK_UP_TO_BOUND (1.8 s), k=3 ATTACK_FOUND minimum 3 flips (11.2 s), boot_ok k=1 ATTACK_FOUND (0.3 s) | Pointer row so that PS4/PS5 are not missing from this section | RUN_LOG 195, 200 | `faultbound-wt analyze reference/spike_netlists/v2.json ...` | MEASURED (RUN_LOG 195) | 2026-11-19 |
| `RT2.fuzz` | T3 counter encoding vs a brute-force oracle: 1120 random netlists (seeds 1-4 x 80, 11-14 x 200), 8406 solver runs, oracle on 1076 netlists, 0 verdict/min-fault disagreements, 0 crashes, 0 bad witnesses; about 76% attack, 24% no-attack; netlists tiny (<= ~14 sites), the oracle shares the fault-model reading | Validates the encoding, not the model | research/c5/rt2/RT2_REPORT.md (line 40); fuzz_amk.py; mk_netlists.py | `python3 fuzz_amk.py` (RT2 copy) | MEASURED (RT2); not re-run by RECON3 | 2026-11-19 |
| `LEDGER.cells` | ledger of 92 cells (designs V0, V1, V2, V5 x flow, consumer bits, counting rule, fault model, placement), each labelled MEASURED, SIMULATED or UNMEASURED; pol.jsonl 196 cells; see also LEDGER.rise and LEDGER.pred.sample in section 10 | Polarity: 1-to-0 rail model V1, V2, V5 survive within the bound; a rail-wide 0-to-1 event on the three copies costs 1 on V2 and V5 (and V1, V0) | research/c5/ledger/LEDGER_REPORT.md; ledger.csv | b3pol.py (copy of the B3 engine, no independent checker) | SIMULATED / MEASURED per cell | 2026-11-19 |
| `ANCHOR.pointer` | brute-force anchors: see ANCHOR.bf and ANCHOR.grid in section 10 (V2 spike k=3 T=3/4: 182 attacking triples, none smaller; V2 apt k=2: 3 pairs; 32 rail rows agree; 24/24 REP/E2 netlist pairs agree) | z3-free anchors for the z3 results | research/c5/anchor/ANCHOR_REPORT.md | anchor_sim.py, dip_subset_bf.py, grid_reconcile.py | MEASURED (ANCHOR) | 2026-11-19 |
| `DASH2.values` | dashboard: 228 values checked against sources, 0 mismatches (incl. all 92 ledger cells vs ledger.csv, E2 152/94/38/20 against DA3 text, counting and synth numbers against PS6 text); earlier DASH.values was 115/115. Counting and synth numbers are regex-checked against report prose, not recomputed from a solver | Dashboard numbers equal the reports | research/c5/dash2/DASH2_REPORT.md; verify_numbers_output.txt | `python3 research/c5/dash2/verify_numbers.py` | REPORTED (DASH2) | 2026-11-19 |
| `FIX3.status` | FIX3 integrated wave-2 results (polarity statement, E2 94/38/20, predictor baselines 62%/83%, 71/71 and 4/6, ledger slide 17) into README, START, report and dossier files; `check_numbers` on its copy 0 STALE | Docs sync | research/c5/fix3/FIX3_REPORT.md; RUN_LOG 233 | check_numbers.py | REPORTED (FIX3); 0 STALE re-measured by RECON3 before its edits | 2026-11-19 |

## 12 Action, Docker, Yosys version, third-party tools (RECON5, 2026-11-20)
| id | value | meaning | source | how measured | status | date |
|---|---|---|---|---|---|---|
| `ACT.run` | the composite action's two shell steps run locally in a clean venv; bug found and fixed (default `package-path` `product` made pip install an unrelated PyPI package named `product`: dependency-confusion risk; fixed: bare names get `./`, needs pyproject.toml); after the fix install OK, analysis on spike V2 with scope.toml (consumer_bits 0-3) -> ATTACK_FOUND exit 1, min 2 flips, SARIF 2.1.0 with 1 result, badge JSON `attack found: 2 flips @ 6 cycles (scoped)`; bad inputs (metacharacters in max-flips, leading-dash netlist, metacharacters in top, cycles above the cap of 200) all exit 3, no canary. NOT run on GitHub: `uses:` steps (actions/setup-python) and the code-scanning SARIF upload untested | product/action/action.yml (backup research/c5/final_review/action.yml.orig) | RUN_LOG 261 | integration step ran the shell steps locally | MEASURED (integration step) | 2026-11-20 |
| `DOCKER.run` | image built only after adding the sandbox proxy's CA to a COPY of the Dockerfile (container did not trust the proxy's TLS CA; TLS checking NOT disabled; shipped Dockerfile unchanged; on a normal network it should build, not tested); image runs as uid 1000 (non-root); V2 JSON k=2 no attack, k=3 min 3; malicious `--top` rejected, no canary; Verilog path failed on Debian Yosys 0.52 ($scopeinfo cells) until H5 | product/Dockerfile | RUN_LOG 261, 262 | integration step ran dockerd locally | MEASURED (integration step) | 2026-11-20 |
| `H5.scopeinfo` | loader skips `$scopeinfo` cells with no non-input port in `product/src/faultbound_wt/_engine.py` and `scripts/glitchsat.py` (5 added lines each; integration step verified the diff); ENGINE_MANIFEST glitchsat.py sha256 78ecea08...fe40; check_reproduce --rerun 36/36, no warning; Docker after H5: v2 k<=2 -> NO_ATTACK_UP_TO_BOUND 83 gates, v1 k=1 -> ATTACK_FOUND 70 gates | research/c5/h5/H5_REPORT.md | H5; integration step | MEASURED (H5 step; integration step verified diff and --rerun) | 2026-11-20 |
| `YOSYS.version` | V2 (`rtl/v2.v`, plain flow) at <=2 flips: apt Yosys 0.33 attack found (85 gates); conda 0.38 and Docker/Debian 0.52 no attack (83 gates each). Netlist-dependent, not a version effect (CORRECTED 2026-11-20 by P01a: stored netlist also Yosys 0.33; conda 0.38 gives 2 on three other flows; cause = encoding, see `P01.*`); state the netlist hash and flow with every V2 result | research/c5/h5/H5_REPORT.md; E2 | same command, three Yosys builds | MEASURED (H5) | 2026-11-20 |
| `RUN2.uarchifi` | uArchiFI (CEA-LIST/uArchiFI @8a2d792f, LGPL-2.1; plugin built against conda Yosys 0.38, it targets 0.61) matched OUR minimum-flip numbers in 9 of 9 cells: V0 1, V1 1, V2 stored 3 (K=1, K=2 PASS, K=3 FAIL), V2 apt-0.33 2, boot_ok 1 everywhere; with its counting unit set to one RTL wire V0, V1, V2 all give 1; its bundled example BMC reached depth 7 in the 600 s cap (no verdict); counts per Yosys wire; only flip run. Independent agreement of one third-party tool on 9 cells of three toy designs through an step-written adapter: does NOT validate either tool | research/c5/run2/RUN2_REPORT.md | author-authorised run | MEASURED (step; not re-run at integration) | 2026-11-20 |
| `RUN2.kfrp` | k-FRP (@75929f60, Apache-2.0) built; Skinny64 example ran in 13.5 s; on our netlists it asks a different question (any output corruption with no alert, no goal value; alert port a constant-1 stand-in) and reports exploitable single faults on V0, V1, V2 alike: no comparable minimum | research/c5/run2/RUN2_REPORT.md | as above | MEASURED (step) | 2026-11-20 |
| `RUN2.fiver` | FIVER (@176a1db7, custom NON-COMMERCIAL licence): NOT built, NOT run (needs CUDD, not on PyPI or conda). Deviations in RUN2: Yosys 0.38 not 0.61; z3 not yices; k-FRP submodules fetched. Derived code only in `third_party_derived/uarchifi_kfrp_fiver/` (local only, never in a bundle) | research/c5/run2/RUN2_REPORT.md | | REPORTED | 2026-11-20 |

## 13 Encoding root cause, coding view, P08 (step INT, 2026-11-20)
Toy designs, modelled single-cycle bit flips, nothing physical, nothing established as new. Flow order of `--synth-sweep`: plain, plain_opt_merge, flatten_before_abc, abc_fast, abc_no_mux, opt_flow, plain_keep_off, opt_flow_keep_off.
| id | value | meaning | source | how measured | status | date |
|---|---|---|---|---|---|---|
| `P01.v2.apt.sweep` | 2 1 1 2 2 2 2 2 (8 flows) | V2 min flips per flow, apt Yosys 0.33, goal boot_word==0x96, stem rule, T=6, k<=3, known init | research/c6/p01/P01_REPORT.md; sweeps/sweep_apt_v2.json | `faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --cycles 6 --synth-sweep` | MEASURED (P01a; re-run at integration 2026-11-20 05:06 UTC, identical) | 2026-11-20 |
| `P01.v2e.apt.sweep` | 3 1 1 3 3 3 3 3 | `rtl/v2e.v` (armed 0xA5, touches 3 copies), same command; conda 0.38 identical | P01_REPORT.md; sweeps/sweep_apt_v2e.json, sweep_conda_v2e.json | same with `rtl/v2e.v --top v2e` | MEASURED (P01a; integration step re-run identical) | 2026-11-20 |
| `P01.v2.conda.sweep` | 3 1 1 2 3 2 3 2 | V2 with conda Yosys 0.38+92: 3 only on plain (and abc_no_mux, plain_keep_off), 2 on abc_fast, opt_flow, opt_flow_keep_off | P01_REPORT.md; sweeps/sweep_conda_v2.json | conda yosys first in PATH | MEASURED (P01a) | 2026-11-20 |
| `P01.stored.creator` | stored V2 netlist creator `Yosys 0.33 (git sha1 2584903a060)`, 68 gates | stored vs apt is a flow/source difference, not a version difference | P01_REPORT.md; nl_info.log | `nl_info.py` | MEASURED (P01a) | 2026-11-20 |
| `P01.cause` | 0xCC xor 0x96 = 0x5A = bits {1,3,4,6}, copies m1 and m0 only; apt witness `new_n58_` (bits 1,4) and `new_n74_` (bits 3,6) at cycle 0 | encoding sets the floor; the flow decides whether it is reached; the 1s are copy-merging flows | WHY_TWO_FLIPS.md; witness_apt_v2.txt | arithmetic + solver witness | MEASURED (P01a) | 2026-11-20 |
| `P01.controls` | 3 copies (5A, 3C): 3 1 1 3 3 3 3 3 on both versions; 2 copies (BB, 4D, 0F): 2 or 3; 1 copy (04): 1 everywhere, B2 1 or 2; brute force T=4 k<=2: apt v2 3 pairs, apt v2e 0 of 75,467, conda v2 0, conda v2e 0; 9 designs boot only for key 0xC3 | controls for the encoding hypothesis | P01_REPORT.md; bf/*.json; tb_all.log | anchor_sim.py; iverilog 256 keys | MEASURED (P01a) | 2026-11-20 |
| `P11.codebooks` | 19 codebooks measured (+2 negative controls rejected before any solver run) | code distance as fault budget | research/c6/p11/P11_REPORT.md; results/comms/distance_sweep.csv | `python3 scripts/comms/distance_sweep.py --out results/comms/distance_sweep.csv --cli faultbound-wt` | MEASURED (P11a) | 2026-11-20 |
| `P11.flops` | flops-only min = nearest non-accept distance d_min in 15 of 15 codebooks with d_min <= 6; 4 of 4 with d_min > 6 no attack up to 6 (bounded) | prediction (a) held | same | same | MEASURED (P11a) | 2026-11-20 |
| `P11.allnets` | all nets <= flops-only in 19 of 19 (both flows); no-ABC structural netlist equals the copy rule 19 of 19 | prediction (b) held | same | same | MEASURED (P11a) | 2026-11-20 |
| `P11.failed` | FAILED: flops-only = d(I,W) (2 B-variant codebooks: 3 and 6 vs 8); 3 of 16 three-copy codebooks at 2 on the apt plain flow; complement pairs give 3, not 2; word order: F0 then CC 2, CC then F0 3 (mechanism not dissected) | failed predictions, kept | same | same | MEASURED (P11a) | 2026-11-20 |
| `P13.rm13` | RM(1,3) [8,4,4], d=4, weight enumerator 1 + 14z^4 + z^8; F0, CC, 96, 69, C3 all members (LSB- and MSB-first) | coding view | docs/comms/test_rm13.py; research/c6/p13/test_output.txt | `pytest -q docs/comms/test_rm13.py`: 16 passed (INT fresh copy, 2026-11-20) | FACT (test); integration step re-ran membership | 2026-11-20 |
| `P13.hamming` | flops-only min 4 on V1 spike, V2 spike, V1 apt, V2 apt; all nets 1 / 3 / 1 / 2 | distance = flops-only budget; decoder = ceiling | research/c6/p13/hamming_runs.txt | `python3 docs/dossier/test_hamming.py` (z3, T=6) | MEASURED (P13a) | 2026-11-20 |
| `P08.glitchsat` | `scripts/glitchsat.py` sha256 1ad037ef07e23c2aabcea75b87a99616591957bd61ed8e0b80abae6b737a9f3c (old 78ecea08...); synth.sh run via `sh`; 'add another independent copy' advice removed; ENGINE_MANIFEST updated at integration | engine change | research/c6/p08/P08_REPORT.md; tests/test_p08.py (2 tests) | sha256sum | MEASURED (P08; integration step) | 2026-11-20 |
| `ENG.pin` | `scripts/glitchsat.py` sha256 b38bbe735a055a750c08471b2336dcaa63dd747b2a0831a0431f21d9eef3387d (current pin in `ci/check_reproduce.py` ENGINE_MANIFEST; replaces 3a66dcac... , 1ad037ef... above and the untracked 91ba5309... of the published tree) | `Netlist.__init__` flop-init merge only: an `x` at one alias of a flop bit yields to a known 0/1 at another alias, so 14 netlists (28 cells) that were falsely rejected now parse; x-only flops are still rejected; every other parsed netlist in the repo is identical before and after (147 netlist/top pairs compared). Earlier change: CLI-only (z3 imported lazily, help text, `--version`) | `ci/check_reproduce.py`; `tests/test_netlist_init_alias.py`; `tests/test_cli_help.py` | sha256sum; before/after comparison of parsed objects | MEASURED (hash, parse comparison); `--rerun` 36/36 not yet repeated on a machine with z3 and yosys | 2026-11-21 |
| `INT.tests` | root `pytest tests` 150 passed (19.9 s; incl. test_distance_sweep 12, test_p08 2, test_h5 3); product `pytest product/tests` 324 passed (82.4 s); `docs/comms/test_rm13.py` 16 passed (not under tests/, not counted in 150) | current test counts | /tmp/work_int/m1 (fresh tar copy, venv with ci/requirements-ci.txt and ./product[test]) | `pytest -q tests`; `pytest -q product/tests` | MEASURED (INT, 2026-11-20 05:13 UTC) | 2026-11-20 |
| `INT.repro` | `ci/check_reproduce.py` 36/36 rows match; `--rerun` 36/36 (engine re-run), 0 FAILED, no manifest warning | reproduce gate after P08 | same copy | `python3 ci/check_reproduce.py [--rerun]` | MEASURED (INT) | 2026-11-20 |

## 14 Comms experiments, WOW pages, re-measured counts (step INT2a, 2026-11-20)
Toy designs, modelled bit flips, nothing physical, nothing established as new. Row numbers count the CSV header as row 1. Facts copied from the files named; counts in the last rows MEASURED by INT2a on a fresh tar copy (/tmp/work_int2a/copy).
| id | value | meaning | source (file, line/row) | how measured | status | date |
|---|---|---|---|---|---|---|
| `P12.slopes` | low-p slopes V0 0.984, V1 0.881, V2-stored 3.003, V2-apt 2.137, V2e 2.971 (min flips 1, 1, 3, 2, 3) | random-flip waterfall: slope = minimum flips (prediction P1 held) | research/c6/p12/analysis.out lines 1, 11, 21, 31, 41; P12_REPORT.md table "Predictions" row P1 | `scripts/comms/bsc_channel.py all` (P12) | SIMULATED (P12) | 2026-11-20 |
| `P12.mult` | A_dmin at the plotted key: V0 11, V1 1, V2-stored 80, V2-apt 3, V2e 734; any wrong key 15, 1, 182, 3, 1065 | multiplicity: V2e about 9x V2-stored at low p (6.27e-7 vs 6.88e-8 at p=1e-3) | results/comms/waterfall.csv rows 2, 11, 20, 29, 38 (columns A_dmin, A_dmin_anykey, estimate) | same | SIMULATED (P12) | 2026-11-20 |
| `P12.P2.failed` | FAILED: truncated series (K=3) inside the MC 95% interval at 9 of 31 eligible points (never for V2e) | the series is a lower bound | research/c6/p12/P12_REPORT.md "FAILED prediction first" | same | SIMULATED (P12) | 2026-11-20 |
| `P12.p01` | p = 0.1: V1 9.6e-3, V2-stored 6.0e-3, V2-apt 8.0e-3, V2e 8.6e-3 | V2 within a factor 1.6 of V1 at high noise | results/comms/waterfall.csv rows 19, 28, 37, 46 | same | SIMULATED (P12) | 2026-11-20 |
| `P14.complement` | 69/96, C3/3C, A5/5A: random flops-only >6, all nets 3; one all-flop burst 1 event; one-group burst 3 events | complement pairs: random-robust, burst-fragile | results/comms/burst.csv rows 2, 4, 6 | `scripts/comms/burst_sweep.py` (P14) | SIMULATED (P14) | 2026-11-20 |
| `P14.stored` | stored F0/96 (fail 0x69): random 4 / 2, one all-flop burst 1; fail word 0x3C: no all-flop burst attack within 6 cycles, random 4 / 3 | fail word complement of accept | results/comms/burst.csv rows 8, 22 | same | SIMULATED (P14) | 2026-11-20 |
| `P14.pred` | 0 mismatches in 32 rows x 4 burst kinds; 2B_95_BEB struct row flagged ENGINE_CHECK_FAILED (control timeout; re-run gave 3 = CLI) | pre-registered predictions | research/c6/p14/P14_REPORT.md; recheck_control.log | same | SIMULATED (P14) | 2026-11-20 |
| `P18.secded` | v2_secded flops-only 3 (v2: 4); all nets 2 (v2: 2); plain gates 143 (v2: 85) | SECDED corrector lowers flops-only cost by t=1 | results/comms/decoder_variants.csv rows 2, 11, 74, 83 | `scripts/comms/decoder_variants.py` (P18) | MEASURED (P18) | 2026-11-20 |
| `P18.allflows` | all-nets min over 9 flows: v2, v2_secded, v2c all 2,1,1,2,2,2,2,2,3; v2e 3,1,1,3,3,3,3,3,3 | no all-nets change from the decoder | results/comms/decoder_variants.csv (goal boot_word, sites all) | same | MEASURED (P18; INT2a re-read the CSV: v2c equals v2 in every cell) | 2026-11-20 |
| `P21.witness` | V1 1 flip (`ok`, tick 1, key 0xC7); V2 none at k<=1, k<=2 (456 sites, 353 modelled); V2 3 flips (`c2.m`, `word[0]`, `c1.m`, tick 1); V2 accept flag 1 flip (`boot_ok`, tick 3) | Solver Replay frames | docs/explainers/witness.json; research/c6/p21/P21_REPORT.md table "What was replayed" | `scripts/glitchsat.py check` on stored netlists + `scripts/replay.py` | MEASURED + SIMULATED (P21) | 2026-11-20 |
| `P24.wall` | 288 V2 rows: 264 solved = 180 / 60 / 24; 152 distinct netlists = 94 / 38 / 20; opt_merge on: 120 / 12 / 0 | 264-builders wall | research/c6/p24/P24_REPORT.md "Numbers"; research/c2/e2_variance/raw/matrix.csv | `python3 scripts/export_e2_wall.py && python3 docs/explainers/dev/check_wall.py` | MEASURED (row counts, P24) | 2026-11-20 |
| `P40.dial` | 432 cells, 94 measured, 338 not measured; stage path 3 (matrix.jsonl line 241) -> 2 (265) -> 1 (277) -> 0 (281); merging 1, V2e 3 (sweep_rows.csv lines 3, 10) | Verdict Dial | research/c6/p40/P40_REPORT.md "What the dial shows" | `python3 docs/explainers/dev/build_dial.py` | MEASURED (copied rows, P40) | 2026-11-20 |
| `INT2a.tests` | root `pytest tests`: 197 collected, 196 passed, 1 skipped (18.4 s; system python3); product `pytest product/tests` (venv, `./product[test]`): 324 passed (82.0 s) | test counts at INT2a time (history; root superseded by T.root.passed / T.root.collected: 189 passed, 2 skipped, 190 collected, RECON6; product 324 unchanged) | /tmp/work_int2a/copy (tar copy excluding work, dl, venv, third_party_derived, .git, zips, waveform files) | `python3 -m pytest -q tests`; `pytest -q product/tests` | MEASURED (INT2a) | 2026-11-20 |
| `INT2a.repro` | `ci/check_reproduce.py` 36/36 rows match, 0 FAILED, 0 problems; `--rerun` 36/36 (engine re-run), 0 FAILED | reproduce gate | same copy | `python3 ci/check_reproduce.py [--rerun]` | MEASURED (INT2a) | 2026-11-20 |
| `INT2a.wow` | `docs/explainers/dev/check_dial.py --browser` 467 passed, 0 failed; `docs/explainers/dev/check_wall.py` 42 PASS, 0 failed; `docs/explainers/dev/check_theatre.py --browser` 149 passed, 0 failed | WOW page checkers (headless Chrome) | same copy | commands as named | MEASURED (INT2a) | 2026-11-20 |

## Machine-readable block (read by `scripts/check_numbers.py`)
Edit rules here when a number changes. `scan_globs` are searched line by line; a `rules[].re` match is a stale value; `rules[].should` is what to write instead. `verify` lists the row ids that `check_numbers.py --verify` recomputes from the stored data files.

```json
{
 "version": 1,
 "generated": "2026-11-19 (RECON2 extended); RECON6 2026-11-20 (root 190 collected / 189 passed / 2 skipped, canonical bundle setup; INT2a had 197 / 196 / 1)",
 "note": "Machine-readable block for scripts/check_numbers.py. 'rules' are stale-value regexes (scan_globs); lines also matching hist_re are reported as HISTORICAL (the old value is quoted as history).",
 "scan_globs": [
  "README.md",
  "START.md",
  "docs/*.md",
  "docs/report/*.md",
  "docs/dossier/*.md",
  "docs/explainers/*.md",
  "docs/explainers/*.html",
  "docs/edu/*.md",
  "product/QUICKSTART.md",
  "product/README.md",
  "dashboard/template.html",
  "dashboard/build.py",
  "dashboard/index.html",
  "research/c4/qa_sim/QA_SIM_REPORT.md"
 ],
 "skip": [
  "docs/dossier/CRITIQUE.md",
  "docs/dossier/EVIDENCE_INDEX.md",
  "docs/NUMBERS.md",
  "docs/report/FIX_LOG.md",
  "docs/report/WORDING_FLAGS.md",
  "research/c4/qa_sim/QA_SIM_REPORT.md"
 ],
 "hist_re": "(?i)\\b(at T3 time|then; now|was the count then|after H2|H2/H3 time|after H4|PS6 copy|H2 copy|stale|superseded|first writing|at that time|at review time|earlier counts?|used to|before later|were 10|was 10|10 at first|old |first 43|\\bhistory\\b|before T[23]|T2 had|T2's own|earlier MT|earlier 67)",
 "owners": {
  "README.md": "author",
  "START.md": "author",
  "docs/FINAL_STATUS.md": "author",
  "docs/ENGINE_STATUS.md": "author (F2/docs)",
  "docs/dossier/": "DOSSIER step (D2)",
  "docs/report/": "REPORT step (F2)",
  "docs/explainers/": "WOW steps (W1-W6)",
  "docs/edu/": "EDU step",
  "product/QUICKSTART.md": "PS step (product)",
  "product/README.md": "PS step (product)",
  "dashboard/": "DASH step",
  "research/c4/qa_sim/": "QA step",
  "docs/HANDOFF.md": "author",
  "docs/PRIOR_ART.md": "author",
  "docs/DEEP_RESULTS.md": "author",
  "docs/DERIVATION_SHEET.md": "DOSSIER step (D2)"
 },
 "current": {
  "T.root.passed": "189",
  "T.prod.passed": "324 passed (81.3 s)",
  "T.prod.collected": "324",
  "T.root.collected": "190"
 },
 "rules": [
  {
   "id": "T.root.196",
   "hist": true,
   "re": "\\b19[67]\\s+(?:passed|collected|root|main tests|tests)|\\*\\*196 passed|\\b196\\b[^|\\n]{0,25}\\(1 skipped\\)|\\b196,? 1 skipped|197 collected",
   "should": "189 passed, 2 skipped (190 collected) root, canonical = unpacked bundle + `pip install ./product[test]` + `pytest tests` (RECON6, 2026-11-20); 196 / 197 only as history (INT2a, before test_explainer_checks)",
   "label": "stale root test count 196/197 (INT2a dev-environment count)"
  },
  {
   "id": "T.root.136",
   "hist": true,
   "re": "\\b136\\s+(?:passed|root|main tests|tests?\\b)|\\*\\*136 passed|now 136\\b",
   "should": "189 passed (2 skipped) root (RECON6, 2026-11-20; 196 was INT2a history); 136 only as history (RECON5)",
   "label": "stale root test count 136 (before P08/P11 tests)"
  },
  {
   "id": "YOSYS.version.cause",
   "hist": true,
   "re": "(?i)verdict depends on the Yosys version|Yosys version dependence|depends on the Yosys version",
   "should": "not a version effect: encoding sets the floor (0xCC touches 2 of 3 copies), the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md, P01a)",
   "label": "misattribution corrected 2026-11-20 (fresh-eyes review, P01a)"
  },
  {
   "id": "T.root.133",
   "hist": true,
   "re": "\\b133\\s+(?:passed|tests?\\b|root|main tests)|\\b321\\s+(?:passed|collected|product)|tests 321 passed|root tests \\*\\*133",
   "should": "189 passed (2 skipped) root, 324 product passed (RECON6 root / INT2a product, 2026-11-20); 133 / 321 only as history (RECON4)",
   "label": "stale test count (133 root / 321 product, before H5 tests)"
  },
  {
   "id": "ACT.run",
   "hist": false,
   "re": "Dockerfile (?:never built|NEVER BUILT|written, NEVER BUILT)|Docker ?file (?:was|were) never (?:built|run)|(?:Action|Dockerfile) (?:and|,) (?:the )?(?:Dockerfile|Docker file|Action) (?:were |was )?never (?:built|run)|GitHub Action NEVER RUN(?! on GitHub)|Docker, Action, pre-commit never run|Dockerfile and Action never run",
   "should": "Action shell steps run locally only (integration step 2026-11-20; not on GitHub); Dockerfile built and run locally with a proxy-CA copy (not on a normal network)",
   "label": "stale Docker/Action status ('never built/run' was true before 2026-11-20 04:xx UTC)"
  },
  {
   "id": "RUN2.never",
   "hist": false,
   "re": "(?i)(?:uArchiFI|FIVER)(?: and (?:uArchiFI|FIVER))? renderers[^|\\n]{0,60}never run(?!; RUN2)",
   "should": "RUN2 (2026-11-20) ran uArchiFI (9 of 9 cells agree) and built k-FRP; FIVER not built",
   "label": "stale third-party-tool status"
  },
  {
   "id": "T.root.passed",
   "hist": false,
   "re": "\\b30\\s+(?:tests?\\b|passed\\b|pass\\b)|\\bpass(?:ed)? (?:in )?30\\b|\\b30 per RA",
   "should": "189 passed (2 skipped) root (root `pytest tests`, 2026-11-20, INT); or 'run `make test` and quote your own count'",
   "label": "stale root test count (30 quoted as current)"
  },
  {
   "id": "T.root.passed",
   "hist": true,
   "re": "\\b10\\s+(?:tests?\\b|passed\\b)",
   "should": "189 passed (2 skipped) root (10 only as history with a marker such as 'first writing')",
   "label": "old root test count 10"
  },
  {
   "id": "T.prod.passed",
   "hist": false,
   "re": "(?i)product tests?[^|\\n]{0,60}?\\b38\\b|\\b38 (?:passed|tests|pass)\\b",
   "should": "324 passed (81.3 s) (product/tests after pip install ./product[test]; 324 collected)",
   "label": "stale product test count (38 was never measured)"
  },
  {
   "id": "T.prod.passed",
   "hist": true,
   "re": "(?i)product tests?[^|\\n]{0,60}?\\b(?:27|21)\\b|\\b(?:27|21) (?:after|passed|tests|pass)\\b",
   "should": "324 passed (81.3 s) (27 and 21 only as history with a marker)",
   "label": "old product test count 27/21"
  },
  {
   "id": "REP.rows",
   "hist": false,
   "re": "DA_CYCLE1[^\\n]{0,250}not re-run|not re-run[^\\n]{0,60}6/32",
   "should": "REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted",
   "label": "32-netlist result flagged not re-run, but REP replicated it"
  },
  {
   "id": "VER.heldout.exact",
   "hist": false,
   "re": "\\b144\\s*(?:/|of)\\s*163\\b",
   "should": "150/163 (corrected; 144 is the raw column count, see NUMBERS.md VER.heldout.raw)",
   "label": "uncorrected held-out figure"
  },
  {
   "id": "RAIL.pending",
   "hist": false,
   "re": "(?i)0-to-1 control[^\\n]{0,40}pending|control pending|0-to-1 control: \\*\\*pending",
   "should": "0-to-1 control is done (LEDGER, research/c5/ledger/): rise_unions/rise_half cost 1 on V0, V1, V2, V5; survival depends on polarity",
   "label": "rail 0-to-1 control still called pending"
  },
  {
   "id": "E2.v2.baseline",
   "hist": false,
   "re": "^(?!.*(?:distinct|152|94/38/20|94, 38|94 / 38|94, 38 and 20)).*\\b1 in 180,\\s*2 in 60,\\s*3 in 24",
   "should": "1 in 180, 2 in 60, 3 in 24 of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3)",
   "label": "E2 split without per-netlist baseline"
  },
  {
   "id": "PRE.baseline",
   "hist": false,
   "re": "^(?!.*(?:62%|always.?1|always predict|lower bound alone|83%|sound lower bound)).*\\b(?:exact on 150|150 of 163[^\\n]{0,10}92|92% exact|92% (?:overall|exact))",
   "should": "92% (150/163) quoted with baselines: always-1 62%, lower bound alone 83% (DA3); LEDGER 71/71 same family, 4/6 fresh RTLs",
   "label": "predictor 92% without baselines"
  },
  {
   "id": "Z3.anchors.stale",
   "hist": false,
   "re": "(?i)brute-force anchors (?:for these )?(?:are being added|in progress)|ANCHOR is adding|anchors in progress|brute force covered only V0 and V1",
   "should": "brute-force anchors exist (ANCHOR): V2 spike/apt stem flips, B3 rails T=4 k<=2 (32 rows), selective sets; still z3-only: T=6 k=3 rail events, V5",
   "label": "stale 'z3 alone / anchors in progress'"
  },
  {
   "id": "RULE.discovery",
   "hist": false,
   "re": "(?i)\\b(?:novel|new|discovered|our) (?:consumer-)?mask rule\\b",
   "should": "mask rule = min(Hamming distance to idle states, comparator copies touched); known-style cut/Hamming reasoning, not a discovery; 255/255 spike, 187/255 apt",
   "label": "mask rule presented as a discovery"
  },
  {
   "id": "TEST.pooled",
   "hist": false,
   "re": "(?i)\\b928\\s*/\\s*928\\b(?![^\\n]{0,200}(near-duplicate|effective|VER|easy|too clean|trap|not validated|heuristic))",
   "should": "928/928 only with its caveat (near-duplicate cells, effective sample 3-5 designs; VER 150/163 on fresh cells)",
   "label": "bare 928/928"
  },
  {
   "id": "VER.runtime",
   "hist": false,
   "re": "(?i)\\b[37](?:\\.[0-9])?x faster",
   "should": "no speedup claim survives (VER: 1.4x slower on held-out)",
   "label": "predictor speedup claim"
  },
  {
   "id": "M1.apt",
   "hist": false,
   "re": "\\b(66|67|69|70)\\s+(?:mask )?mismatch",
   "should": "68 mismatches",
   "label": "apt mask mismatch count"
  },
  {
   "id": "E2.v2.min",
   "hist": false,
   "re": "\\b1\\s+in\\s+(?!180\\b)\\d+,\\s*2\\s+in\\s+\\d+,\\s*3\\s+in\\s+\\d+",
   "should": "1 in 180, 2 in 60, 3 in 24",
   "label": "E2 split"
  },
  {
   "id": "REP.unit",
   "hist": false,
   "re": "\\b2 (?:flips )?(?:in|on) (?!26\\b)\\d+ and 3 (?:flips )?(?:in|on) \\d+",
   "should": "2 on 26, 3 on 6 (of 32)",
   "label": "REP split"
  },
  {
   "id": "T.repro.rows",
   "hist": false,
   "re": "\\b3[0-5]/3[0-9] rows match|\\b(?!36/)\\d+/36 rows match",
   "should": "36/36",
   "label": "reproduce row count"
  },
  {
   "id": "G.v2.85",
   "hist": false,
   "re": "\\b(?:84|86|87)\\s+gates",
   "should": "85 gates (apt 0.33 V2)",
   "label": "V2 apt gate count"
  },
  {
   "id": "M1.split",
   "hist": false,
   "re": "\\b(?:87|89|90)/(?:95|97|98)/(?:43|45)\\b",
   "should": "88/96/44",
   "label": "M1 split"
  },
  {
   "id": "T.mut.root",
   "hist": true,
   "re": "(?<![\\d.])(?:29|28)\\s*(?:/|of)\\s*43\\b",
   "should": "root 72.5% (50/69), product 67.6% (50/74) (T2/T3); 29/43 and 28/43 only as history ('first 43')",
   "label": "stale mutation score (first-43 figure as current)"
  },
  {
   "id": "T.mut.pct",
   "hist": true,
   "re": "(?i)mutation[^\\n]{0,140}(?<![\\d.])(?:67|65)\\s?%|(?<![\\d.])67\\s?%\\s*/\\s*65\\s?%|\\b65-67\\s?%|(?<![\\d.])67/65\\s?%",
   "should": "root 72.5% (50/69), product 67.6% (50/74); 67%/65% only as history",
   "label": "stale mutation percentage"
  },
  {
   "id": "T.root.133",
   "hist": true,
   "re": "(?<![\\d.])99\\s+(?:passed|root|main tests|tests in the main)\\b|\\(99 (?:passed|tests)|\\bnow 99\\b|\\btoday 99\\b|tests 99 and",
   "should": "189 passed (2 skipped) root (root, INT; 99 + 34 in test_h3.py + 3 in test_h5.py); 99 only as history",
   "label": "stale root test count (99, before H3)"
  },
  {
   "id": "T.prod.310",
   "hist": true,
   "re": "\\b(?:139|140|174|175|310)\\s+(?:passed|collected|product)\\b|\\b(?:138|139)\\s*\\+\\s*1\\b|\\b139 and 1 skipped|(?i:product tests?)[^|\\n]{0,60}?\\b310\\b|\\b133 and 310\\b|133 root / 310|\\b310 product\\b",
   "should": "324 passed, 324 collected (product, RECON5; 175 + 135 in test_h2.py + 11 in test_h4.py + 3 in test_h5.py); 139/174/175/310 only as history",
   "label": "stale product test count (139, 174 or 175, before H2)"
  },
  {
   "id": "T.root.99",
   "hist": true,
   "re": "\\b98 (?:passed|tests|root|main tests)\\b|\\bnow 98\\b|\\btoday 98\\b",
   "should": "189 passed (2 skipped) root (root, INT); 98 only as history",
   "label": "stale root test count (98)"
  },
  {
   "id": "T.prod.139",
   "hist": true,
   "re": "\\b138 (?:passed|product)\\b|\\b139 collected\\b|\\b98\\.9 s\\b|\\b26\\.7 s\\b",
   "should": "324 passed, 324 collected, 81.3 s (RECON5); 138+1 only as history",
   "label": "stale product test count or timing (138, 139 collected, 98.9 s, 26.7 s)"
  },
  {
   "id": "L2.status",
   "hist": false,
   "re": "(?i)\\bL2\\b[^\\n|]{0,60}\\b(?:in progress|absent|not yet run)\\b|\\bL2 follow-up[^\\n]{0,40}in progress|no report found (?:at|when) D3",
   "should": "L2 is done: research/c4/l2/L2_REPORT.md (spread r 11 to 18 um, rail_all still 1, LVS FAILS 4 of 4)",
   "label": "L2 shown as unfinished"
  },
  {
   "id": "R27.applied",
   "hist": false,
   "re": "(?i)(?:R27|sequential-counter|faster (?:at-most-k )?encoding)[^\\n]{0,200}\\b(?:NOT applied|not applied|patch exists)|no T3 report",
   "should": "applied by T3 (counter encoding default, `--amk legacy` keeps the old code; research/c4/t3/T3_REPORT.md)",
   "label": "R27 patch shown as not applied"
  },
  {
   "id": "M1b.pending",
   "hist": false,
   "re": "(?i)recheck pending|M1b[^\\n]{0,40}(?:is rechecking|pending|in progress)",
   "should": "M1b done: 0 of 1785 cells changed (research/c4/m1b/M1B_REPORT.md)",
   "label": "M1b shown as pending"
  },
  {
   "id": "L2.lvs",
   "hist": false,
   "re": "(?i)\\bspread[^\\n]{0,100}(?:LVS (?:clean|passes|match(?:es)?)|passes? LVS)",
   "should": "LVS FAILS in 4 of 4 spread variants (research/c4/l2/L2_REPORT.md)",
   "label": "spread layouts shown as LVS clean"
  },
  {
   "id": "L2.hardening",
   "hist": false,
   "re": "(?i)\\b(?:spread(?:ing)?|distance)[^\\n]{0,80}\\b(?:removes|eliminates|solves|fixes)\\b[^\\n]{0,40}\\b(?:selective|dip|event)",
   "should": "spreading raises the radius threshold to 11 to 18 um but a die-wide selective dip (rail_all) still costs 1 event",
   "label": "hardening by distance overclaimed"
  },
  {
   "id": "L2.wire",
   "hist": false,
   "re": "(?i)\\bwire[ -]?length[^\\n]{0,30}\\+(?:1\\d|2[0-7]|5[2-9]|[6-9]\\d)\\s?%",
   "should": "wire length +29% to +50%",
   "label": "L2 wire-length cost misquoted"
  },
  {
   "id": "L2.area",
   "hist": false,
   "re": "(?i)\\bdie (?:area )?(?:cost )?x(?:1\\.[0-1]\\d?|2\\.[6-9]|[3-9])\\b",
   "should": "die area x1.26 to x2.5",
   "label": "L2 die-area cost misquoted"
  },
  {
   "id": "LAY.radius",
   "hist": true,
   "re": "(?i)\\b(?:enclosing|selectivity|minimal)\\b[^\\n]{0,40}\\bradius[^\\n]{0,30}\\b(?:3\\.5|2\\.5)\\s*um",
   "should": "2.95 um (centre to centre); 3.5 um was an assumed disc (EL2), 4.6 um a hypothetical what-if",
   "label": "layout radius misquoted"
  },
  {
   "id": "B3.overclaim",
   "hist": false,
   "re": "(?i)^(?!.*(?:may not say|do not say|never say|not say|trap)).*?\\bV2\\b[^\\n]{0,40}\\b(?:resists|survives|is (?:secure|safe) against)\\b[^\\n]{0,30}\\b(?:rail|dip)",
   "should": "no attack found up to 3 events (bounded, T=6) under rail_all/half/unions/cone; 1 event if a dip may choose which gates fall",
   "label": "rail-dip result overclaimed"
  },
  {
   "id": "SAFETY.inprogress",
   "hist": false,
   "re": "H2 in progress|until the fix lands|until the hardening fix",
   "should": "H2/H3 fixed the RT2-N1 command-execution bug; RT3 (2026-11-20) found one more path (classroom script, fixed) and an uncapped --cycles (fixed by H4); integration step canary re-test 2026-11-19 22:42 UTC and 2026-11-20 02:15 (rejected, exit 3, no file); Action steps run locally only (not on GitHub), Dockerfile built/run locally with a proxy-CA copy only; do not run the Verilog path or the Action on untrusted input until a human reviews the fix",
   "label": "stale safety wording (fix 'in progress')"
  },
  {
   "id": "RAIL.railwide01",
   "hist": false,
   "re": "rail-wide 0-to-1|rail-wide <b>0-to-1</b>",
   "should": "a 0->1 event on the three compare copies breaks V2/V5 with one event; the domain is the netlist hierarchy, not a physical rail",
   "label": "contradictory rail 0-to-1 wording"
  },
  {
   "id": "T.root.150",
   "hist": true,
   "re": "\\b150\\s+(?:passed|root\\b|main tests)|#\\s*150 passed|\\b150 tests in the main",
   "should": "189 passed, 2 skipped (root pytest tests, canonical bundle setup, RECON6 2026-11-20; 190 collected); 150 only as history (INT)",
   "label": "stale root test count 150 (before P12/P14/P18 tests)"
  }
 ],
 "verify": [
  "T.root.collected",
  "T.prod.collected",
  "T.repro.rows",
  "E2.configs",
  "E2.v2.min",
  "M1.masks",
  "M1.split",
  "M1.width",
  "M1.four",
  "REP.unit",
  "REP.fanout",
  "REP.rows",
  "VER.heldout.exact",
  "VER.heldout.raw",
  "VER.xinit"
 ],
 "rows": [
  {
   "id": "T.root.collected",
   "value": "190",
   "source": "tests/ (test_engine, test_hardening, test_check_reproduce, test_mt_oracle, test_mt_targeted, test_h3, test_h5, test_distance_sweep, test_p08, test_burst_sweep, test_decoder_variants, test_explainer_checks; test_waterfall skipped without numpy)",
   "status": "MEASURED",
   "date": "2026-11-20 RECON6"
  },
  {
   "id": "T.root.passed",
   "value": "189 passed, 2 skipped",
   "source": "tests/",
   "status": "MEASURED",
   "date": "2026-11-20 RECON6"
  },
  {
   "id": "T.prod.collected",
   "value": "324",
   "source": "product/tests/ (test_golden, test_hardening, test_mt_*, test_ps2..ps6, test_h2, test_h4)",
   "status": "MEASURED",
   "date": "2026-11-20 RECON5"
  },
  {
   "id": "T.prod.passed",
   "value": "324 passed (81.3 s)",
   "source": "product/tests/",
   "status": "MEASURED",
   "date": "2026-11-20 RECON5"
  },
  {
   "id": "T.hist.root",
   "value": "10 -> 30 -> 98",
   "source": "research/c3/ra/RA_REPORT.md; research/c4/qa_sim/QA_SIM_REPORT.md item 9",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "T.hist.prod",
   "value": "21 -> 27 -> 38 -> 139",
   "source": "research/c3/ra/RA_REPORT.md; research/c3/ps2/PS2_REPORT.md; docs/dossier/EVIDENCE_INDEX.md row 2",
   "status": "MEASURED (38 = REPORTED)",
   "date": "2026-11-19"
  },
  {
   "id": "T.b3",
   "value": "16",
   "source": "research/c4/b3/B3_REPORT.md",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "T.mt.new",
   "value": "61",
   "source": "research/c3/mt/MT_REPORT.md; docs/dossier/PROJECT_DOSSIER.md l.118",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "T.mut.root",
   "value": "29/43 = 67%",
   "source": "research/c3/mt/MT_REPORT.md",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "T.mut.prod",
   "value": "28/43 = 65%",
   "source": "research/c3/mt/MT_REPORT.md",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "T.repro.rows",
   "value": "36",
   "source": "results/reproduce_summary.json (key rows, len 36); ci/expected_reproduce.json",
   "status": "MEASURED",
   "date": "2026-11-19 RECON / RA"
  },
  {
   "id": "T.repro.witness",
   "value": "11 of 36",
   "source": "research/c3/ra/RA_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "T.repro.time",
   "value": "about 25 s",
   "source": "README.md; RA_REPORT.md",
   "status": "MEASURED (approx.)",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.spike.word",
   "value": "3",
   "source": "research/c2/b2_scope/B2_REPORT.md matrix (v2/spike, word noin known)",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.apt",
   "value": "2",
   "source": "B2_REPORT.md (v2/apt033_plain, apt033_opt)",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.conda",
   "value": "3 (plain) / 2 (opt)",
   "source": "B2_REPORT.md reading item 1",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.ok",
   "value": "1",
   "source": "B2_REPORT.md; README table; CT-1",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.in",
   "value": "1",
   "source": "B2_REPORT.md (word +in known)",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v2.nongoal",
   "value": "1",
   "source": "B2_REPORT.md (word noin nongoal)",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.free",
   "value": "0",
   "source": "B2_REPORT.md reading item 2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v0v1",
   "value": "1",
   "source": "B2_REPORT.md reading item 3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "B2.v3",
   "value": "3 (where finished)",
   "source": "B2_REPORT.md V3 section",
   "status": "MEASURED (partial)",
   "date": "2026-11-19"
  },
  {
   "id": "B2.cells",
   "value": "360",
   "source": "B2_REPORT.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E1.free.input",
   "value": "3 (V2 spike, k<=2 none)",
   "source": "research/c2/e1_timevarying/E1_REPORT.md; matrix_bmc_z3.json",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.configs",
   "value": "864 (792 solved + 72 ENGINE_UNSUPPORTED)",
   "source": "research/c2/e2_variance/E2_REPORT.md; raw/matrix.csv",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.v2.min",
   "value": "180 / 60 / 24",
   "source": "E2_REPORT.md s3; raw/matrix.csv (status SOLVED, design v2, min_flips)",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.v1.min",
   "value": "233 / 31 / 0",
   "source": "E2_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.v0.min",
   "value": "264 / 0 / 0",
   "source": "E2_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.v2.build",
   "value": "apt 60/24/4; formal 60/18/10; eda 60/18/10",
   "source": "E2_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.gates.apt",
   "value": "V0 25, V1 72, V2 85",
   "source": "E2_REPORT.md s2; formal/FORMAL.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.gates.conda",
   "value": "V0 23, V1 70, V2 83",
   "source": "E2_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "E2.baseline.min",
   "value": "apt V2 2; conda V2 3; V0, V1 1",
   "source": "E2_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "G.v2.85",
   "value": "85 (40 AND, 25 OR, 20 NOT, 8 DFF)",
   "source": "formal/FORMAL.md l.20,35; results/work/v2.json",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "G.v2.83",
   "value": "83 (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF)",
   "source": "formal/FORMAL.md",
   "status": "MEASURED (not re-run by RA/RECON)",
   "date": "2026-11-19"
  },
  {
   "id": "G.v2.81",
   "value": "81 (38 AND, 23 OR, 18 NOT, 2 MUX)",
   "source": "results/work/v2_opt.json; docs/ENGINE_STATUS.md l.34",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "G.v2.spike",
   "value": "V0 18, V1 58, V2 68",
   "source": "docs/edu/ANSWER_KEY.md Exercise 1, 3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "G.v2.merge",
   "value": "63",
   "source": "docs/edu/ANSWER_KEY.md; INSTRUCTOR_NOTES.md; WORKSHEET.md",
   "status": "MEASURED (edu step)",
   "date": "2026-11-19"
  },
  {
   "id": "V.flowB",
   "value": "1 (4 of 378 single-flip sites)",
   "source": "validation/VALIDATION.md l.28",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.masks",
   "value": "255 (228 non-colliding, 27 colliding)",
   "source": "research/c3/m1/M1_REPORT.md s1; m1_all_masks.csv",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.split",
   "value": "88 / 96 / 44 (+27 at 0)",
   "source": "M1_REPORT.md; m1_all_masks.csv column v2_spike_min_flips",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.width",
   "value": "0,1,1,2,2,3,3,3",
   "source": "m1_all_masks.csv; product `--sweep-widths`; research/c4/dash/verify_numbers.py",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.four",
   "value": "28 / 36 / 4 of 68",
   "source": "M1_REPORT.md table row popcount 4",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.apt",
   "value": "68 mismatches of 255",
   "source": "M1_REPORT.md s3; docs/FINAL_STATUS.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.val",
   "value": "255 of 255 agree (T=4, k<=2 brute force)",
   "source": "M1_REPORT.md s1",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "M1.cells",
   "value": "1785 cells, 0 unknown",
   "source": "M1_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "REP.unit",
   "value": "26 x 2 flips, 6 x 3 flips (of 32 V2)",
   "source": "research/c3/rep/REP_REPORT.md; research/c3/rep/rep_results.csv rep_unit_cli",
   "status": "MEASURED (DA) + REPLICATED (REP)",
   "date": "2026-11-19"
  },
  {
   "id": "REP.fanout",
   "value": "32 of 32 at 3 flips (V1: 2 on 32/32)",
   "source": "rep_results.csv column rep_fanout_pins; DA_CYCLE1.md E3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "REP.rows",
   "value": "64 of 64 agree",
   "source": "REP_REPORT.md verdict",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "REP.recipe",
   "value": "2 builds x 2 flows x 8 ABC = 32",
   "source": "REP_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.dmr",
   "value": "2040 gates / 32 flops; k=1 NO_ATTACK (62 s); k=2 min 2 (46 s)",
   "source": "research/c3/r20/R20_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.sbox",
   "value": "unprot 1012/16 -> 1; par 2040/17 -> 1; par2 2040/25 -> 1",
   "source": "R20_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.crc",
   "value": "crc_plain 40/9 -> 1; crc_tmr 44/11 -> 1",
   "source": "R20_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.uart",
   "value": "368 gates / 34 flops; k=0 none, k=1,2 -> 1 (T=6); T=30 k=2 -> 1 (31.8 s)",
   "source": "R20_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.keymem",
   "value": "32 gates / 7 flops -> 1",
   "source": "R20_REPORT.md s3",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "R20.designs",
   "value": "six wrappers/designs",
   "source": "R20_REPORT.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "PRE.train",
   "value": "V0 255/255, V1 255/255, V2 252/255 (255/255 within 1), V4b 255/255, V5 81/81, V6h 222/222",
   "source": "research/c4/pre/PRE_REPORT.md; test_training.py",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "TEST.pooled",
   "value": "928/928 exact (100%)",
   "source": "research/c4/test/TEST_REPORT.md; analysis.txt",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "TEST.confusion",
   "value": "0:54, 1:684, 2:170, 3:20",
   "source": "TEST_REPORT.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "TEST.speed",
   "value": "7.3x E2, 3.4x/2.8x M1, 1.0x R20",
   "source": "TEST_REPORT.md; VER_REPORT.md s3.4",
   "status": "MEASURED (not controlled)",
   "date": "2026-11-19"
  },
  {
   "id": "VER.heldout.exact",
   "value": "150/163 = 92.0%",
   "source": "research/c4/ver/VER_REPORT.md s3.1; heldout.csv + rerun_x.json",
   "status": "MEASURED",
   "date": "2026-11-20 RECON5"
  },
  {
   "id": "VER.heldout.raw",
   "value": "144/163",
   "source": "research/c4/ver/heldout.csv",
   "status": "MEASURED (a raw column count, not the audit figure)",
   "date": "2026-11-20 RECON5"
  },
  {
   "id": "VER.heldout.split",
   "value": "within 1: 156/163 (95.7%); over 6; under 7; solver>=2: 18/31 (58%)",
   "source": "VER_REPORT.md s3.1-3.2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "VER.heldout.safe",
   "value": "false-safe 0, false-weak 0, lb>solver 0 in 928+163+60 cells",
   "source": "VER_REPORT.md s3.1, s5",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "VER.resample",
   "value": "60/60",
   "source": "VER_REPORT.md s2",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "VER.runtime",
   "value": "predictor 251 s vs solver 184 s on 163 cells (1.4x slower)",
   "source": "VER_REPORT.md s3.4",
   "status": "MEASURED (contended machine)",
   "date": "2026-11-19"
  },
  {
   "id": "VER.xinit",
   "value": "47 x-init cells rerun, 2 changed",
   "source": "VER_REPORT.md s3.3; rerun_x.json",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "VER.percent",
   "value": "92% overall; 58% when 2+ flips needed",
   "source": "VER_REPORT.md s5",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "EL1.dip",
   "value": "0 of 60 dip points flipped a stored flop (0 V for 3 ns)",
   "source": "research/c2/el1_spice/EL1_REPORT.md A; fault_windows.json key A_supply_dip",
   "status": "SIMULATED",
   "date": "2026-11-19"
  },
  {
   "id": "EL1.runt",
   "value": "tt: 1.3 V runt (0.1 ns) captures D; 0.9 V needs 2 ns; 0.5 V none",
   "source": "EL1_REPORT.md B",
   "status": "SIMULATED",
   "date": "2026-11-19"
  },
  {
   "id": "EL1.setup",
   "value": "about 50 to 75 ps (tt, 1.8 V); about 100 ps (1.2 V); 25 ps grid",
   "source": "EL1_REPORT.md C",
   "status": "SIMULATED",
   "date": "2026-11-19"
  },
  {
   "id": "B3.model",
   "value": "V2 and V5: no attack up to 3 events under rail_all / half / unions / cone; V0 cone 1 event",
   "source": "research/c4/b3/B3_REPORT.md Plain answers; matrix_T6.jsonl",
   "status": "SIMULATED",
   "date": "2026-11-19"
  },
  {
   "id": "B3.subset",
   "value": "1 event; smallest domain 3 gates (V2, V5), 2 (V1)",
   "source": "B3_REPORT.md; minsubset.py",
   "status": "SIMULATED",
   "date": "2026-11-19"
  },
  {
   "id": "F.pdr",
   "value": "V2 spike k=2 PASS in 0.83 s (unbounded, ABC PDR); replicated by a second, independent implementation (ext/unbounded: k=0,1,2 proved for all time, k=3 attack, same netlist)",
   "source": "docs/FINAL_STATUS.md; formal/FORMAL.md",
   "status": "MEASURED by the integration step (not re-run by RECON)",
   "date": "2026-11-19"
  },
  {
   "id": "F.sby",
   "value": "40 netlist/k pairs match",
   "source": "formal/FORMAL.md l.25",
   "status": "REPORTED",
   "date": "2026-11-19"
  },
  {
   "id": "F.valid",
   "value": "~2.1M fault sets x 255 inputs, 0 disagreements; 13/13 replays; 5 boolector queries",
   "source": "validation/VALIDATION.md l.21,24",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "F.sets",
   "value": "46,056 (T=4) and 103,740 (T=6) 2-flip sets, none succeed on V2 spike; 70,300 3-flip sets all cycle 1, 182 attacks; all 15,699,320 triples at T=6 enumerated (--reduce none): 182 attacks, all cycle 1 (reference netlist; placed V2 has 22)",
   "source": "validation/VALIDATION.md l.18-19",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "F.deep",
   "value": "V2 spike k=2 at 20 cycles 294.3 s; k=3 474.9 s",
   "source": "docs/DEEP_RESULTS.md l.36-37; results/deep/sweep_main.json",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "L.cells",
   "value": "V0 10 cells 89 um2; V1 35 / 358 (357.8); V2 36 / 363 (362.8)",
   "source": "layout/v_designs/out_patched/RESULT.md l.7,10; docs/dossier/PROJECT_DOSSIER.md 7.9",
   "status": "ESTIMATED / MEASURED flow output",
   "date": "2026-11-19"
  },
  {
   "id": "L.lvs",
   "value": "V1 422 vs 422 devices, 225 nets; match uniquely (V1, V2)",
   "source": "layout/v_designs/out_patched/RESULT.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "L.antenna",
   "value": "0 pin / 0 net violations; 0 off-grid",
   "source": "layout/verify/VERIFY.md",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "H.hamming",
   "value": "4 (code F0,CC,96,69; 96/69 complement distance 8)",
   "source": "docs/dossier/test_hamming.py; RA item 22",
   "status": "MEASURED",
   "date": "2026-11-19"
  },
  {
   "id": "N.sqrt",
   "value": "7.15 LSB at input 31797; 25 inputs above 6 LSB; CBMC bound 8",
   "source": "numerics_audit/AUDIT.md l.12-13",
   "status": "UNVERIFIED (spike result)",
   "date": "2026-11-19"
  },
  {
   "id": "N.fuzz",
   "value": "0 mismatches in about 6,700 programs",
   "source": "handoff/CONTINUATION/earlier_research/gasp/GASP_DECISION.md l.27",
   "status": "UNVERIFIED / REPORTED",
   "date": "2026-11-19"
  }
 ]
}
```
