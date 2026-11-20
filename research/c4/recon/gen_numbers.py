#!/usr/bin/env python3
"""One-off generator (work file, not delivered): writes docs/NUMBERS.md from ROWS and RULES."""
import json, sys
PROD = sys.argv[1] if len(sys.argv) > 1 else "PROD?"
PRODSKIP = sys.argv[2] if len(sys.argv) > 2 else ""
D = "2026-11-19"
R = []
def row(id, value, meaning, source, how, status, date=D, section="", verify=None):
    r = dict(id=id, value=value, meaning=meaning, source=source, how=how, status=status, date=date, section=section)
    if verify: r["verify"] = verify
    R.append(r)

# ---------- tests
S="1 Tests"
row("T.root.collected","98","pytest tests: tests collected (root engine suite)","tests/ (test_engine, test_hardening, test_check_reproduce, test_mt_oracle, test_mt_targeted)","`pytest tests --co -q` on a tar copy, venv with ci/requirements-ci.txt","MEASURED","2026-11-19 RECON",S,verify="pytest_root")
row("T.root.passed","98","pytest tests: passed, 0 failed (26.7 s on RECON copy). Docs saying 30 or 10 are stale","tests/","`pytest tests -q` on a tar copy (see section 8)","MEASURED","2026-11-19 RECON",S)
row("T.prod.collected","139","pytest product/tests: collected after `pip install ./product[test]`","product/tests/ (test_golden, test_hardening, test_mt_*, test_ps2..ps5)","`pytest product/tests --co -q` in venv with ./product[test] on a tar copy","MEASURED","2026-11-19 RECON",S,verify="pytest_prod")
row("T.prod.passed",PROD,"pytest product/tests: result line on RECON copy (skips: %s). Docs saying 21, 27 or 38 are stale"%(PRODSKIP or "1"),"product/tests/","`pytest product/tests -q` in venv with ./product[test] on a tar copy","MEASURED","2026-11-19 RECON",S)
row("T.hist.root","10 -> 30 -> 98","History of the root count: 10 (first writing), 30 (RA, after H1 added 20), 98 (after MT/T2 added tests). Quote only the current one","research/c3/ra/RA_REPORT.md; research/c4/qa_sim/QA_SIM_REPORT.md item 9","see T.root.passed","MEASURED","2026-11-19",S)
row("T.hist.prod","21 -> 27 -> 38 -> 139","History of product count: 21 (RA, H1), 27 (PS2, MT), 38 (lead, unmeasured), 139 collected now","research/c3/ra/RA_REPORT.md; research/c3/ps2/PS2_REPORT.md; docs/dossier/EVIDENCE_INDEX.md row 2","see T.prod.collected","MEASURED (38 = REPORTED)","2026-11-19",S)
row("T.b3","16","B3 research tests (research/c4/b3/test_b3.py) passed","research/c4/b3/B3_REPORT.md","`cd /tmp/work_b3; python3 -m pytest -q test_b3.py`","REPORTED","2026-11-19",S)
row("T.mt.new","61","MT extra tests (research/c3/mt/new_tests) passed per engine, 1.3 s","research/c3/mt/MT_REPORT.md; docs/dossier/PROJECT_DOSSIER.md l.118","`MT_ROOT=<tree> pytest research/c3/mt/new_tests`","REPORTED","2026-11-19",S)
row("T.mut.root","29/43 = 67%","Mutation score, tests/ vs glitchsat.py, completed runs (72 of 158 runs not run)","research/c3/mt/MT_REPORT.md","mutate.py + kill_check.py","REPORTED","2026-11-19",S)
row("T.mut.prod","28/43 = 65%","Mutation score, product/tests vs product source, completed runs","research/c3/mt/MT_REPORT.md","same","REPORTED","2026-11-19",S)
row("T.repro.rows","36","make reproduce writes 36 rows (V0/V1/V2 x netlists x k); check-reproduce: 36/36 match","results/reproduce_summary.json (key rows, len 36); ci/expected_reproduce.json","`python3 -c \"import json;print(len(json.load(open('results/reproduce_summary.json'))['rows']))\"`; `make check-reproduce` (copy)","MEASURED","2026-11-19 RECON / RA",S,verify="repro36")
row("T.repro.witness","11 of 36","Rows whose witness (fault list) differs between runs; verdict and min_faults identical","research/c3/ra/RA_REPORT.md s2","make reproduce vs stored summary (copy)","MEASURED","2026-11-19",S)
row("T.repro.time","about 25 s","make reproduce wall time (29.1 s on RA machine); machine dependent","README.md; RA_REPORT.md","`time make reproduce` (copy)","MEASURED (approx.)","2026-11-19",S)

# ---------- B2
S="2 Scope (B2): V0/V1/V2 minimum flips"
row("B2.v2.spike.word","3","V2 stored spike netlist, goal boot_word==0x96, input nets not fault sites, known init","research/c2/b2_scope/B2_REPORT.md matrix (v2/spike, word noin known)","`python3 run_matrix.py /tmp/work_b2/nl` (360 cells, matrix.jsonl)","MEASURED","2026-11-19",S)
row("B2.v2.apt","2","V2 re-synthesised with apt Yosys 0.33 (plain and opt), same scope cell","B2_REPORT.md (v2/apt033_plain, apt033_opt)","same","MEASURED","2026-11-19",S)
row("B2.v2.conda","3 (plain) / 2 (opt)","V2 conda 0.38 plain gives 3, conda 0.38 opt gives 2","B2_REPORT.md reading item 1","same","MEASURED","2026-11-19",S)
row("B2.v2.ok","1","V2, goal boot_ok==1 (flip the boot_ok net)","B2_REPORT.md; README table; CT-1","`glitchsat check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1`","MEASURED","2026-11-19",S)
row("B2.v2.in","1","V2, input nets counted as fault sites","B2_REPORT.md (word +in known)","run_matrix.py","MEASURED","2026-11-19",S)
row("B2.v2.nongoal","1","V2, arbitrary non-accepting power-up state","B2_REPORT.md (word noin nongoal)","run_matrix.py","MEASURED","2026-11-19",S)
row("B2.free","0","Any design, arbitrary power-up state with no reset (design gap, not a tool finding)","B2_REPORT.md reading item 2","run_matrix.py","MEASURED","2026-11-19",S)
row("B2.v0v1","1","V0 and V1 in every known-init cell (0 with arbitrary init)","B2_REPORT.md reading item 3","run_matrix.py","MEASURED","2026-11-19",S)
row("B2.v3","3 (where finished)","V3 attempt: cost 3 in finished cells (capped k<=3, many cells NOT RUN)","B2_REPORT.md V3 section","run_v3.py","MEASURED (partial)","2026-11-19",S)
row("B2.cells","360","cells in the V0-V2 scope matrix","B2_REPORT.md","run_matrix.py","MEASURED","2026-11-19",S)
row("E1.free.input","3 (V2 spike, k<=2 none)","Free per-cycle attacker input, T=4,6,8; 57-row matrix","research/c2/e1_timevarying/E1_REPORT.md; matrix_bmc_z3.json","z3 + sby + PDR","REPORTED","2026-11-19",S)

# ---------- E2
S="3 Synthesis variance (E2)"
row("E2.configs","864 (792 solved + 72 ENGINE_UNSUPPORTED)","configurations: 3 builds x 3 designs x 96","research/c2/e2_variance/E2_REPORT.md; raw/matrix.csv","`python3 scripts/matrix.py out`","MEASURED","2026-11-19",S,verify="e2")
row("E2.v2.min","180 / 60 / 24","V2 solved configs with min 1 / 2 / 3 (264 solved)","E2_REPORT.md s3; raw/matrix.csv (status SOLVED, design v2, min_flips)","count rows of raw/matrix.csv","MEASURED","2026-11-19",S,verify="e2")
row("E2.v1.min","233 / 31 / 0","V1 solved configs with min 1 / 2 / 3 (264 solved)","E2_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("E2.v0.min","264 / 0 / 0","V0 solved configs with min 1 / 2 / 3","E2_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("E2.v2.build","apt 60/24/4; formal 60/18/10; eda 60/18/10","V2 by build, min1/min2/min3","E2_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("E2.gates.apt","V0 25, V1 72, V2 85","Baseline gate counts (combinational; plus 8 DFF for V1/V2), apt Yosys 0.33, `synth.sh` plain","E2_REPORT.md s2; formal/FORMAL.md","`scripts/synth.sh rtl/vN.v vN out.json plain`","MEASURED","2026-11-19",S)
row("E2.gates.conda","V0 23, V1 70, V2 83","Baseline gate counts, conda Yosys 0.38+92","E2_REPORT.md s2","same with conda env","MEASURED","2026-11-19",S)
row("E2.baseline.min","apt V2 2; conda V2 3; V0, V1 1","Baseline min flips by build","E2_REPORT.md s2","same","MEASURED","2026-11-19",S)
row("G.v2.85","85 (40 AND, 25 OR, 20 NOT, 8 DFF)","V2 apt-0.33 netlist; 85 counts combinational gates only (93 cells in total)","formal/FORMAL.md l.20,35; results/work/v2.json","`python3 -c` count of cells","MEASURED","2026-11-19",S)
row("G.v2.83","83 (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF)","V2 conda 0.38+92 netlist","formal/FORMAL.md","same","MEASURED (not re-run by RA/RECON)","2026-11-19",S)
row("G.v2.81","81 (38 AND, 23 OR, 18 NOT, 2 MUX)","V2 apt-0.33 opt flow, also a 2-flip attack","results/work/v2_opt.json; docs/ENGINE_STATUS.md l.34","same","MEASURED","2026-11-19",S)
row("G.v2.spike","V0 18, V1 58, V2 68","Stored spike netlists, gate counts (edu answer key)","docs/edu/ANSWER_KEY.md Exercise 1, 3","`glitchsat check` prints gate count","MEASURED","2026-11-19",S)
row("G.v2.merge","63","V2 apt-0.33 plus opt_merge (edu exercise 3): min 1 flip (hash d776226e); plain 85 hash f954078f","docs/edu/ANSWER_KEY.md; INSTRUCTOR_NOTES.md; WORKSHEET.md","edu_work/synth_merge.sh","MEASURED (edu agent)","2026-11-19",S)
row("V.flowB","1 (4 of 378 single-flip sites)","V2 on validation flow B (flatten, hierarchy stripped)","validation/VALIDATION.md l.28","`make validate`","MEASURED","2026-11-19",S)

# ---------- M1
S="4 Consumer width (M1)"
row("M1.masks","255 (228 non-colliding, 27 colliding)","Masks tested; colliding ones accept with 0 flips (F0/CC states)","research/c3/m1/M1_REPORT.md s1; m1_all_masks.csv","`python3 mat.py <netlist> <top> 6 out.jsonl 90000`","MEASURED","2026-11-19",S,verify="m1")
row("M1.split","88 / 96 / 44 (+27 at 0)","V2 spike masks needing 1 / 2 / 3 flips (of 228 non-colliding)","M1_REPORT.md; m1_all_masks.csv column v2_spike_min_flips","count column","MEASURED","2026-11-19",S,verify="m1")
row("M1.width","0,1,1,2,2,3,3,3","V2 spike min flips for lowest n bits, n=1..8 (masks 0x01,0x03,0x07,0x0F,0x1F,0x3F,0x7F,0xFF)","m1_all_masks.csv; product `--sweep-widths`; research/c4/dash/verify_numbers.py","`faultbound-wt analyze examples/v2.json --config threat.toml --sweep-widths --max-flips 3`","MEASURED","2026-11-19",S,verify="m1")
row("M1.four","28 / 36 / 4 of 68","V2 spike four-bit masks needing 1 / 2 / 3","M1_REPORT.md table row popcount 4","m1_all_masks.csv","MEASURED","2026-11-19",S,verify="m1")
row("M1.apt","68 mismatches of 255","Mask rule vs solver on apt-0.33 V2 re-synthesis (rule exact only on stored netlist, 255/255)","M1_REPORT.md s3; docs/FINAL_STATUS.md","pred.py vs m_v2_apt033.jsonl","MEASURED","2026-11-19",S)
row("M1.val","255 of 255 agree (T=4, k<=2 brute force)","Independent brute force vs z3, V2 spike","M1_REPORT.md s1","`python3 bf.py v2 4 2 ...; python3 val.py`","MEASURED","2026-11-19",S)
row("M1.cells","1785 cells, 0 unknown","7 designs x 255 masks","M1_REPORT.md s2","mat.py","MEASURED","2026-11-19",S)

# ---------- counting
S="5 Counting rule (DA, REP, R22)"
row("REP.unit","26 x 2 flips, 6 x 3 flips (of 32 V2)","Stem=1 rule: V2 holds against 2 flips on only 6/32 (18.75%, quoted 19%)","research/c3/rep/REP_REPORT.md; research/c3/rep/rep_results.csv rep_unit_cli","count column rep_unit_cli; DA_CYCLE1.md E1","MEASURED (DA) + REPLICATED (REP)","2026-11-19",S,verify="rep")
row("REP.fanout","32 of 32 at 3 flips (V1: 2 on 32/32)","Fanout-pin counting; stress test only, not shown physical","rep_results.csv column rep_fanout_pins; DA_CYCLE1.md E3","same","MEASURED","2026-11-19",S,verify="rep")
row("REP.rows","64 of 64 agree","REP vs DA, 32 V2 + 32 V1 netlists; one shared recipe list so not independent","REP_REPORT.md verdict","`scripts/cli_check.sh`, `rep_measure.py`","MEASURED","2026-11-19",S,verify="rep")
row("REP.recipe","2 builds x 2 flows x 8 ABC = 32","Netlist recipe grid","REP_REPORT.md s2","gen_rep.sh","MEASURED","2026-11-19",S)

# ---------- R20
S="6 Real designs (R20)"
row("R20.dmr","2040 gates / 32 flops; k=1 NO_ATTACK (62 s); k=2 min 2 (46 s)","DMR AES S-box, T=4: the only R20 design not at 1 flip","research/c3/r20/R20_REPORT.md s3","`glitchsat check --reduce full`","MEASURED","2026-11-19",S)
row("R20.sbox","unprot 1012/16 -> 1; par 2040/17 -> 1; par2 2040/25 -> 1","S-box variants, T=4, min flips","R20_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("R20.crc","crc_plain 40/9 -> 1; crc_tmr 44/11 -> 1","CRC-8 boot compare","R20_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("R20.uart","368 gates / 34 flops; k=0 none, k=1,2 -> 1 (T=6); T=30 k=2 -> 1 (31.8 s)","UART tx; no legit frame","R20_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("R20.keymem","32 gates / 7 flops -> 1","aes_key_mem control, T=8","R20_REPORT.md s3","same","MEASURED","2026-11-19",S)
row("R20.designs","six wrappers/designs","sbox, crc, uart, keymem, dmr, par variants","R20_REPORT.md","","MEASURED","2026-11-19",S)

# ---------- predictor
S="7 Predictor (PRE, TEST, VER)"
row("PRE.train","V0 255/255, V1 255/255, V2 252/255 (255/255 within 1), V4b 255/255, V5 81/81, V6h 222/222","Training agreement of the structural predictor (optimistic: designed with it in view)","research/c4/pre/PRE_REPORT.md; test_training.py","`pytest research/c4/pre/test_training.py`","MEASURED","2026-11-19",S)
row("TEST.pooled","928/928 exact (100%)","Pre-registered held-out test, 928 unique cells (E2 407, R20 11, M1 V2 255, M1 V1 255); effective sample 3-5 designs; 684 cells are min 1, 54 collisions","research/c4/test/TEST_REPORT.md; analysis.txt","`python3 -I run_test.py e2|m1|r20; python3 -I analyze_test.py`","MEASURED","2026-11-19",S)
row("TEST.confusion","0:54, 1:684, 2:170, 3:20","Solver minimum counts in the 928 cells","TEST_REPORT.md","same","MEASURED","2026-11-19",S)
row("TEST.speed","7.3x E2, 3.4x/2.8x M1, 1.0x R20","Predictor vs solver runtime, uncontrolled; VER found 1.4x SLOWER on held-out. No speedup claim","TEST_REPORT.md; VER_REPORT.md s3.4","per-cell times","MEASURED (not controlled)","2026-11-19",S)
row("VER.heldout.exact","150/163 = 92.0%","FRESH held-out, 76 netlists/163 cells: exact matches AFTER the x-init corrections (rerun_x.json) and with '>3' compared as 4 and pred capped at 4 (PREREG rule). THIS IS THE CORRECTED FIGURE","research/c4/ver/VER_REPORT.md s3.1; heldout.csv + rerun_x.json","`python3 -I heldout.py; python3 -I rerun_x.py` then count pred==solver with the rules above (RECON recomputed: 150)","MEASURED","2026-11-19 RECON",S,verify="heldout")
row("VER.heldout.raw","144/163","Naive string compare of columns pred==solver in heldout.csv. Differs from 150 by: +4 cells where solver '>3' vs pred 100 (lb sentinel 99+1, equals '>=4' under the PREREG cap) and +2 cells (rc103_opt 0x18, rc117_opt 0xf) whose solver column still holds the pre-correction gs_mask.py x-init value. NOT a headline number","research/c4/ver/heldout.csv","`python3 -c \"import csv;h=list(csv.DictReader(open('research/c4/ver/heldout.csv')));print(sum(x['pred']==x['solver'] for x in h))\"`","MEASURED (a raw column count, not the audit figure)","2026-11-19 RECON",S,verify="heldout")
row("VER.heldout.split","within 1: 156/163 (95.7%); over 6; under 7; solver>=2: 18/31 (58%)","FAILS the 98% within-1 bar; 7 under-predictions are the unsafe `uncovered` fallback lb+1","VER_REPORT.md s3.1-3.2","confusion matrix in the report","MEASURED","2026-11-19",S)
row("VER.heldout.safe","false-safe 0, false-weak 0, lb>solver 0 in 928+163+60 cells","Bound soundness","VER_REPORT.md s3.1, s5","same","MEASURED","2026-11-19",S)
row("VER.resample","60/60","Independent resample of corpus cells reproduces the CSV","VER_REPORT.md s2","`python3 -I resample.py`","MEASURED","2026-11-19",S)
row("VER.runtime","predictor 251 s vs solver 184 s on 163 cells (1.4x slower)","Not a controlled benchmark","VER_REPORT.md s3.4","","MEASURED (contended machine)","2026-11-19",S)
row("VER.xinit","47 x-init cells rerun, 2 changed","gs_mask.py maps x->0 and can clobber an aliased flop init; scripts/glitchsat.py rejects x init","VER_REPORT.md s3.3; rerun_x.json","`python3 -I rerun_x.py`","MEASURED","2026-11-19",S,verify="heldout")
row("VER.percent","92% overall; 58% when 2+ flips needed","Headline wording for the predictor (heuristic search, not validated estimator)","VER_REPORT.md s5","","MEASURED","2026-11-19",S)

# ---------- EL1/B3/formal/layout/misc
S="8 SPICE, rail-dip, formal, layout, misc"
row("EL1.dip","0 of 60 dip points flipped a stored flop (0 V for 3 ns)","SPICE (ngspice, sky130 cells): supply dip alone never flipped Q","research/c2/el1_spice/EL1_REPORT.md A; fault_windows.json key A_supply_dip","expA.py","SIMULATED","2026-11-19",S)
row("EL1.runt","tt: 1.3 V runt (0.1 ns) captures D; 0.9 V needs 2 ns; 0.5 V none","Clock runt makes flop capture D (wrong-time capture)","EL1_REPORT.md B","expBC.py","SIMULATED","2026-11-19",S)
row("EL1.setup","about 50 to 75 ps (tt, 1.8 V); about 100 ps (1.2 V); 25 ps grid","Latest data change still captured before the edge. Do not quote as attack parameters","EL1_REPORT.md C","expBC.py","SIMULATED","2026-11-19",S)
row("B3.model","V2 and V5: no attack up to 3 events under rail_all / half / unions / cone; V0 cone 1 event","Rail-dip model, T=6, <=3 events, 0 unknown","research/c4/b3/B3_REPORT.md Plain answers; matrix_T6.jsonl","`python3 run_cells.py`","SIMULATED","2026-11-19",S)
row("B3.subset","1 event; smallest domain 3 gates (V2, V5), 2 (V1)","dip_subset upper bound: one event may choose which gates fall (selectivity open)","B3_REPORT.md; minsubset.py","`python3 minsubset.py v2,v2_apt033,v5_apt033,v1`","SIMULATED","2026-11-19",S)
row("F.pdr","V2 spike k=2 PASS in 0.83 s (unbounded, ABC PDR)","Needs conda env `formal`; not re-run by RA or RECON","docs/FINAL_STATUS.md; formal/FORMAL.md","`sby` / abc pdr in env formal","MEASURED by lead (not re-run by RECON)","2026-11-19",S)
row("F.sby","40 netlist/k pairs match","sby BMC depth 6 vs solver","formal/FORMAL.md l.25","formal/runs/bmc_matrix*.json","REPORTED","2026-11-19",S)
row("F.valid","~2.1M fault sets x 255 inputs, 0 disagreements; 13/13 replays; 5 boolector queries","Independent simulator vs solver","validation/VALIDATION.md l.21,24","`make validate`","MEASURED","2026-11-19",S)
row("F.sets","46,056 (T=4) and 103,740 (T=6) 2-flip sets, none succeed on V2 spike; 70,300 3-flip sets all cycle 1, 182 attacks","Exhaustive fault-set enumeration","validation/VALIDATION.md l.18-19","`make validate`","MEASURED","2026-11-19",S)
row("F.deep","V2 spike k=2 at 20 cycles 294.3 s; k=3 474.9 s","Deep sweep","docs/DEEP_RESULTS.md l.36-37; results/deep/sweep_main.json","","MEASURED","2026-11-19",S)
row("L.cells","V0 10 cells 89 um2; V1 35 / 358 (357.8); V2 36 / 363 (362.8)","Layout flow demo cell count/area, patched flow; slack +7.050 / +7.035 ns (estimate, not signoff)","layout/v_designs/out_patched/RESULT.md l.7,10; docs/dossier/PROJECT_DOSSIER.md 7.9","flow_patched/all.sh","ESTIMATED / MEASURED flow output","2026-11-19",S)
row("L.lvs","V1 422 vs 422 devices, 225 nets; match uniquely (V1, V2)","netgen LVS","layout/v_designs/out_patched/RESULT.md","","MEASURED","2026-11-19",S)
row("L.antenna","0 pin / 0 net violations; 0 off-grid","OpenROAD check_antennas, klayout grid","layout/verify/VERIFY.md","","MEASURED","2026-11-19",S)
row("H.hamming","4 (code F0,CC,96,69; 96/69 complement distance 8)","Minimum pairwise Hamming distance of the state code","docs/dossier/test_hamming.py; RA item 22","`python3 docs/dossier/test_hamming.py`","MEASURED","2026-11-19",S)
row("N.sqrt","7.15 LSB at input 31797; 25 inputs above 6 LSB; CBMC bound 8","sqrt_q15 numerics spike","numerics_audit/AUDIT.md l.12-13","not re-run","UNVERIFIED (spike result)","2026-11-19",S)
row("N.fuzz","0 mismatches in about 6,700 programs","Fuzzing spike; data not in repo","handoff/CONTINUATION/earlier_research/gasp/GASP_DECISION.md l.27","none","UNVERIFIED / REPORTED","2026-11-19",S)

# ---------- rules for check_numbers.py
HIST = r"(?i)\b(stale|superseded|first writing|at that time|at review time|earlier counts?|used to|before later|were 10|was 10|10 at first|old )"
OWN = {
 "README.md":"LEAD", "START.md":"LEAD", "docs/FINAL_STATUS.md":"LEAD", "docs/ENGINE_STATUS.md":"LEAD (F2/docs)",
 "docs/dossier/":"DOSSIER agent (D2)", "docs/report/":"REPORT agent (F2)", "docs/wow/":"WOW agents (W1-W6)",
 "docs/edu/":"EDU agent", "product/QUICKSTART.md":"PS agent (product)", "product/README.md":"PS agent (product)",
 "dashboard/":"DASH agent", "research/c4/qa_sim/":"QA agent", "docs/HANDOFF.md":"LEAD", "docs/PRIOR_ART.md":"LEAD",
 "docs/DEEP_RESULTS.md":"LEAD", "docs/OWNER_DERIVATION_SHEET.md":"DOSSIER agent (D2)",
}
SCAN = ["README.md","START.md","docs/*.md","docs/report/*.md","docs/dossier/*.md","docs/wow/*.md","docs/wow/*.html",
        "docs/edu/*.md","product/QUICKSTART.md","product/README.md","dashboard/template.html","dashboard/build.py",
        "dashboard/index.html","research/c4/qa_sim/QA_SIM_REPORT.md"]
# skip tables of history / critique logs that legitimately quote old values
SKIP = ["docs/dossier/CRITIQUE.md","docs/dossier/EVIDENCE_INDEX.md","docs/NUMBERS.md","docs/report/FIX_LOG.md","docs/report/WORDING_FLAGS.md"]
RULES = [
 dict(id="T.root.passed", hist=False, re=r"\b30\s+(?:tests?\b|passed\b|pass\b)|\bpass(?:ed)? (?:in )?30\b|\b30 per RA", should="98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count'", label="stale root test count (30 quoted as current)"),
 dict(id="T.root.passed", hist=True, re=r"\b10\s+(?:tests?\b|passed\b)", should="98 passed (10 only as history with a marker such as 'first writing')", label="old root test count 10"),
 dict(id="T.prod.passed", hist=False, re=r"(?i)product tests?[^|\n]{0,60}?\b38\b|\b38 (?:passed|tests|pass)\b", should="%s (product/tests after pip install ./product[test]; 139 collected)"%PROD, label="stale product test count (38 was never measured)"),
 dict(id="T.prod.passed", hist=True, re=r"(?i)product tests?[^|\n]{0,60}?\b(?:27|21)\b|\b(?:27|21) (?:after|passed|tests|pass)\b", should="%s (27 and 21 only as history with a marker)"%PROD, label="old product test count 27/21"),
 dict(id="REP.rows", hist=False, re=r"DA_CYCLE1[^\n]{0,250}not re-run|not re-run[^\n]{0,60}6/32", should="REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted", label="32-netlist result flagged not re-run, but REP replicated it"),
 dict(id="VER.heldout.exact", hist=False, re=r"\b144\s*(?:/|of)\s*163\b", should="150/163 (corrected; 144 is the raw column count, see NUMBERS.md VER.heldout.raw)", label="uncorrected held-out figure"),
 dict(id="TEST.pooled", hist=False, re=r"(?i)\b928\s*/\s*928\b(?![^\n]{0,200}(near-duplicate|effective|VER|easy|too clean|trap|not validated|heuristic))", should="928/928 only with its caveat (near-duplicate cells, effective sample 3-5 designs; VER 150/163 on fresh cells)", label="bare 928/928"),
 dict(id="VER.runtime", hist=False, re=r"(?i)\b[37](?:\.[0-9])?x faster", should="no speedup claim survives (VER: 1.4x slower on held-out)", label="predictor speedup claim"),
 dict(id="M1.apt", hist=False, re=r"\b(66|67|69|70)\s+(?:mask )?mismatch", should="68 mismatches", label="apt mask mismatch count"),
 dict(id="E2.v2.min", hist=False, re=r"\b1\s+in\s+(?!180\b)\d+,\s*2\s+in\s+\d+,\s*3\s+in\s+\d+", should="1 in 180, 2 in 60, 3 in 24", label="E2 split"),
 dict(id="REP.unit", hist=False, re=r"\b2 (?:flips )?(?:in|on) (?!26\b)\d+ and 3 (?:flips )?(?:in|on) \d+", should="2 on 26, 3 on 6 (of 32)", label="REP split"),
 dict(id="T.repro.rows", hist=False, re=r"\b3[0-5]/3[0-9] rows match|\b(?!36/)\d+/36 rows match", should="36/36", label="reproduce row count"),
 dict(id="G.v2.85", hist=False, re=r"\b(?:84|86|87)\s+gates", should="85 gates (apt 0.33 V2)", label="V2 apt gate count"),
 dict(id="M1.split", hist=False, re=r"\b(?:87|89|90)/(?:95|97|98)/(?:43|45)\b", should="88/96/44", label="M1 split"),
 dict(id="T.mut.root", hist=False, re=r"\b6[0-6]%\s*/\s*6[0-4]%|\b6[89]%\s+(?:of|and)\s+6[0-9]%", should="67% / 65%", label="mutation score"),
]
BLOCK = dict(version=1, generated=D,
  note="Machine-readable block for scripts/check_numbers.py. 'rules' are stale-value regexes (scan_globs); lines also matching hist_re are reported as HISTORICAL (the old value is quoted as history).",
  scan_globs=SCAN, skip=SKIP, hist_re=HIST, owners=OWN,
  current={"T.root.passed":"98","T.prod.passed":PROD,"T.prod.collected":"139","T.root.collected":"98"},
  rules=RULES,
  verify=[r["id"] for r in R if "verify" in r])
if __name__=="__main__":
    out=[]
    out.append("""# NUMBERS: single source of truth for every headline number
Working title TBD. License: UNDECIDED. Faults are modelled single-cycle bit flips in toy netlists; nothing physical; nothing established as new. Owner has not reviewed this page.

Purpose: README.md, START.md, docs/FINAL_STATUS.md, docs/report, docs/dossier, docs/wow, docs/edu, product/QUICKSTART.md and the dashboard quote the same numbers. Quote a number only as it appears here. When a measurement changes, edit THIS file first, then run `python3 scripts/check_numbers.py` to list every page that still carries the old value.

Status labels: MEASURED (a command was run, the output was seen), SIMULATED (SPICE or rail-dip model, not silicon), SOURCED (taken from a cited source, not run), REPORTED (written in an agent report, not re-run by RECON), UNVERIFIED. Date = when the value was produced; RECON rows were re-run on a tar copy in /tmp/work_recon on 2026-11-19.

## How RECON measured today's test counts
```
tar-pipe copy of <repo> (excluding work, dl, dl_repo, venv, compare/synfi_run/venv, third_party_derived, .git, handoff/*.zip, *.odb *.vcd *.fst *.vvp) -> /tmp/work_recon/copy
python3 -m venv /tmp/work_recon/venv && pip install -r ci/requirements-ci.txt "./product[test]"
pytest tests --co -q            -> 98 tests collected
pytest tests -q                 -> 98 passed in 26.7 s
pytest product/tests --co -q    -> 139 tests collected
pytest product/tests -q         -> @@PROD@@
```

## Resolution of the 144/163 versus 150/163 question
Both are real counts of the same file `research/c4/ver/heldout.csv` (163 cells), but only 150/163 (92.0%) is the audit figure. Raw `pred==solver` string comparison gives 144. Add 4 cells where the solver column says `>3` and the predictor column holds 100 (lb sentinel 99, plus 1): PREREG compares `>3` as 4 and caps the prediction at 4, so these 4 match (148). Add 2 cells (rc103_opt mask 0x18, rc117_opt mask 0xf) where the solver column still holds the pre-correction value from `gs_mask.py` (x init bit mapped to 0 clobbered an aliased flop); `rerun_x.json` holds the corrected solver values 0 and 2, which equal the predictor (150). RECON recomputed all three steps (script check `heldout` in `scripts/check_numbers.py --verify`). Quote 150/163 (92.0%), 58% on cells needing 2 or more flips, and always say the 928/928 pooled figure is near-duplicate cells.

""".replace("@@PROD@@",PROD))
    cur=None
    for r in R:
        if r["section"]!=cur:
            cur=r["section"]; out.append("\n## %s\n| id | value | meaning | source (file, key/line) | how measured | status | date |\n|---|---|---|---|---|---|---|"%cur)
        esc=lambda s:str(s).replace("|","\\|")
        out.append("| `%s` | %s | %s | %s | %s | %s | %s |"%(r["id"],esc(r["value"]),esc(r["meaning"]),esc(r["source"]),esc(r["how"]),r["status"],r["date"]))
    out.append("""
## Machine-readable block (read by `scripts/check_numbers.py`)
Edit rules here when a number changes. `scan_globs` are searched line by line; a `rules[].re` match is a stale value; `rules[].should` is what to write instead. `verify` lists the row ids that `check_numbers.py --verify` recomputes from the stored data files.

```json
@@J@@
```
""".replace("@@J@@", json.dumps(dict(BLOCK, rows=[{k:v for k,v in r.items() if k in("id","value","status","source","date")} for r in R]),indent=1)))
    open("docs/NUMBERS.md","w").write("\n".join(out))
    print(len(R),"rows")
