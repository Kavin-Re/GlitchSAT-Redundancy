#!/usr/bin/env python3
"""D3 integration edits. Usage: integrate.py ROOT. Idempotent via markers."""
import sys, pathlib
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "<repo>")
M1B = "recheck pending (M1b)"

def rd(f): return (root / f).read_text()
def wr(f, s): (root / f).write_text(s)
def rep(f, old, new, count=1):
    s = rd(f)
    if s.count(old) != count:
        print("MISS", s.count(old), f, old[:70]); return
    wr(f, s.replace(old, new))
def append(f, marker, block):
    s = rd(f)
    if marker in s: print("already", f); return
    wr(f, s.rstrip("\n") + "\n\n" + block.strip("\n") + "\n")
def insert_before(f, anchor, marker, block):
    s = rd(f)
    if marker in s: print("already", f); return
    if s.count(anchor) < 1: print("NOANCHOR", f, anchor[:50]); return
    i = s.index(anchor)
    wr(f, s[:i] + block.strip("\n") + "\n\n" + s[i:])

PRED = ("structural predictor (research script, not in the tool): exact on 150 of 163 fresh held-out cells (92%), "
        "58% (18 of 31) on cells that need 2 or more flips, within one flip 95.7% (fails the pre-registered 98% bar), "
        "1.4x slower than the solver on those cells; a heuristic attack search with a sound lower bound; the solver stays the reference "
        "(the earlier 928/928 pooled figure is near-duplicate cells, effective sample about 3 to 5 designs)")

# ---------------------------------------------------------------- PROJECT_DOSSIER
DOS = """
## 7.10 Wave C4 findings (added by D3, 2026-11-19 late, each number has its source file; Labels as stated)
1. **Council W1** (`research/c4/council/COUNCIL_W1.md`). Consensus: defensible only as a scoped sensitivity table (V2 min 1, 2 or 3 depending on goal, fault sites, init, counting rule, build; E2 180/60/24 of 264) plus the consumer-mask rule labelled exact on the stored spike netlist only. Top risks: (1) (2) the front door was stale (it said the 6/32 vs 32/32 swing was not re-run although REP replicated it 64 of 64; fixed in README by D3); (3) the scope axes were not in the shipped tool (partly fixed by PS4/PS5, see 9); (4) the surviving claim is post-hoc and thin; (5) release blockers (licence undecided, `third_party_derived/` unlicensed, Dockerfile never built, red-team defects A1 and A6). Chair recount (F-chair-run): a compare-cone-only structural check misses 48 of the 252 breakable E2 V2 configs. The council uses the same model family as the work it reviews, so it is not independent evidence.
2. **BP recommendation and kill list** (`research/c4/bp/BP_REPORT.md`; INFERRED). Spine: option A, a redundancy linter that reports shared copies and per-consumer cost, with a small slice of the Hamming-distance lever (C) and E2/M1 data as the validation corpus; no leaderboard, no general rewriter. Its ONE experiment (pre-registered held-out predictive validity) was run: see 7.11. Kill list status as of this pass: (1) more critic waves: not extended by D3; (2) V3 and new V-numbers: V4-V6 exist from V456 (measured), nothing new started; (3) k>=4 or longer cycles on toy V2: not pursued; (4) layout polishing: not pursued, LAYOUT only measured geometry (7.13); (5) SPICE extensions: not pursued, B3 reuses EL1 as a labelled basis; (6) numerics/fuzzing: stay dropped; (7) more prior-art surveys: one periodic sweep (S1) ran, no new claim; (8) quoting 6/32 vs 32/32 as headline: REP now replicated it, but README keeps E2's table first and says it is one recipe; (9) adding document volume: D3 consolidated instead of adding pages. This list is guidance, not enforced.
3. **SWEEP S1** (`research/c4/sweeps/SWEEP_S1.md`; SOURCED/SNIPPET per row). Implications: weaken any wording that implies no minimum-fault verification exists (FIRMER and SYNFI do bounded minimum-fault search; k-FRP may cover unbounded single-flip proofs; only abstracts read); strengthen the claim that synthesis changes the verdict by citing SYNFI's own 3 to 2 faults after Yosys FSM optimisation (SOURCED); the counting convention (stem, branch, per gate) has no source found on its effect on a verdict: keep it open; a set-to-1 or group-flip fault mode is suggested by Moro et al. and EMMap (about 9 to 10 bits per event on one device, EMMap no numbers); rIC3 and GipSAT are possible solver routes (untested). Not novel; licences of SYNFI, FIRMER, rIC3, GipSAT unconfirmed, so no code or benchmark reuse. The ">90% single-bit clock glitch" figure is UNVERIFIED and must not be cited.

## 7.11 Structural predictor: pre-registered test and independent audit (PRE, TEST, VER). MEASURED
- TEST (`research/c4/test/TEST_REPORT.md`): all six pre-registered criteria passed on 928 pooled held-out cells (reported, no leakage found by VER). VER (`research/c4/ver/VER_REPORT.md`): the 928/928 is real but near-duplicate: 684 cells need only 1 flip, 54 are collisions, the rest come from a few designs (effective independent sample about 3 to 5 designs).
- On 163 fresh cells from 76 NEW netlists the predictor was exact on **150 (92.0%)** after correcting two cells for an x-init bug in the solver copy (`rerun_x.json`; the raw column compare `heldout.csv` still gives 144, a counting artefact: 4 cells with solver `>3` vs predictor 100, and 2 uncorrected rows), within one flip on 156 (95.7%, **fails** the 98% bar), exact on only **18 of 31 (58%)** cells needing 2 or more flips; 6 over-predictions, 7 under-predictions (the `uncovered` fallback printed a number where the solver proved none up to 3: the unsafe direction); the lower bound was never above the solver in 928+163+60 cells (sound); no false-safe, no false-weak; predictor 251 s vs solver 184 s (1.4x slower).
- Consequence: P3 is stated as a solver-backed scope reporter with a sound structural lower bound and a heuristic upper estimate as a quick pre-check; NOT a validated linter, NOT faster. Say "92% exact, 58% on multi-flip cells; heuristic; the solver is the reference". Never quote 928/928 as a headline.

## 7.12 Rail-dip and wrong-time capture (B3). SIMULATED basis (EL1), MEASURED solver verdicts, `research/c4/b3/B3_REPORT.md`
T=6, at most 3 events, 0 unknowns. Rail-wide events (rail_all, half-design by hierarchy, any union of units, fanout-cone domains) give `>3` (no attack found up to 3 events, not "secure") for V2 and V5 under both goals; V0 falls to 1 event under a fanout-cone dip. Early capture (runt clock) and hold (late capture) give `>3` everywhere. If ONE event may pick WHICH gates fall (dip_subset, an upper bound EL1 does not support), V2 and V5 fall to 1 event; smallest such set 3 gates (one per compare copy; V1: 2). So V2 and V5 vs V1 is not 3 vs 1 in general but ">3 for rail-wide events, 1 if selective": **selectivity is the open question**, EL1 only simulated one tiny rail. The 1-event `boot_ok` attack is a 0-to-1 flip a 1-to-0 dip cannot make. Validation: brute force agrees on V0/V1 at T<=4, k<=2 (0 disagreements; 16 unit tests); NOT brute-force validated for any V2, V5 or apt row, and no witness replay. Domains are netlist-derived, not layout.

## 7.13 Layout geometry for the selectivity question (LAYOUT). MEASURED geometry, SIMULATED verdict, `research/c4/layout/LAYOUT_REPORT.md`
From the V2 DEF and post-route netlist (36 logic cells in a 30.6 um die): exactly 4 minimal one-event attack sets, each 3 cells, all at cycle 1; the smallest enclosing circle has **r = 2.95 um** (centre to centre; three nand4bb cells; nand2 triple 3.29 um). Supply structure: ONE VPWR and ONE VGND met4 strap fed at one column each, no ring: electrically one supply net (INFERRED reading, no parasitic extraction or IR-drop solve). A one-event dip of a whole row, rail or strap domain does not break V2 within 3 events; a selective event on a disc of at least about 3 um does (cost 1); an all-or-nothing 3 um disc needs 3 events. So the verdict depends on selectivity exactly as B3 said, now with a number. The **4.6 um** figure comes from a HYPOTHETICAL what-if placement (three same-footprint cell swaps; routing, timing, DRC, LVS not redone) and is not a layout that exists; rail-type families stay at cost 1 under selective events even after the swap. V0 has no placed layout. L2 follow-up (`research/c4/l2/L2_REPORT.md`): in progress, no report found when D3 finished. SPICE is circuit-level simulation, never silicon.

## 7.14 Faster encoding (R27) and countermeasure patterns (V456). MEASURED, not applied to the tree
- R27 (`research/c3/r27/R27_REPORT.md`): a sequential-counter encoding with assumption-based "at most j" (`research/c3/r27/seq_counter.patch`, 63 lines, `glitchsat.py` only) gives 10x to 40x faster UNSAT cells and finishes cells (spike V2 k=2 at T=12 and T=20) where the engine's PbLe times out; same verdicts and minima on the 14 cells compared (a first wrapper wrapped a 6-bit popcount and gave a spurious FAIL, fixed by a wide counter). Times noisy (4 cores shared). **Status: the patch exists and is NOT applied** (no T3 report found); adopting it needs the root and product tests re-run and the 36 reproduce rows re-checked. The unbounded IC3 wrapper with a budget counter is an untested design.
- V456 (`research/c3/v456/V456_REPORT.md`; 360 cells, 0 unknown): only V5 (voter plus alert) beats V2, and only on the full-word goal in the apt-0.33 flow (3 vs 2); V5 equals V2 on the stored-style flow (3) and is 1 under boot_ok, input-as-sites and arbitrary power-up. V6 (sparse sequence FSM) is **refuted**: 1 flip in every measured cell, worse than V2 (R21's prediction failed). V4 (sparse 16-bit code) is 1. **No design beats V2 on the stored netlist.** Not done: free per-cycle attacker input, mask matrices for V5/V6h incomplete.

## 7.15 What the C4 wave changed in what you may say (D3)
- You may say: V2's number is 3, 2 or 1 depending on goal, input sites, init, netlist build, consumer width and counting rule; the counting-rule swing (6 of 32 vs 32 of 32) is replicated 64 of 64 with one recipe list; the structural lower bound is sound and the heuristic estimate is 92% exact on fresh cells; rail-wide events do not break V2 within 3 events and selective events do (selectivity open; geometry r = 2.95 um).
- You may not say: V2 resists 2 flips (without the five qualifiers); the predictor is validated or faster; V2 survives rail dips (without bounded, whole-rail only, selectivity unknown); 928/928 as a headline; that any rule is physical; anything about hardware or novelty.
- Consumer-mask figures (M1: 88/96/44 of 228, width curve 0,1,1,2,2,3,3,3, 255/255 on the stored netlist, 68 mismatches on apt-0.33) carry the note: """ + M1B + """ (agent M1b is rechecking the mask matrix for an x-init bug in the solver copy that VER found; PS5's width sweep through the product engine reproduces the width curve independently of that copy).
"""
insert_before("docs/dossier/PROJECT_DOSSIER.md", "## 8. Hardening and red-team", "## 7.10 Wave C4", DOS)

rep("docs/dossier/PROJECT_DOSSIER.md",
    "The product is \"alpha for single-clock, synchronous-reset netlists\" (DA2 C5), a teaching/prototype checker, not a product to market.",
    "The product is \"alpha for single-clock, synchronous-reset netlists\" (DA2 C5), a teaching/prototype checker, not a product to market. **PS4 and PS5 (2026-11-19, MEASURED, `research/c4/ps4/PS4_REPORT.md`, `research/c4/ps5/PS5_REPORT.md`) shipped scope options in `product/`:** `--consumer-bits`, `--goal-out/--accept-value`, `--input-sites {none,all}`, `--init {known,arbitrary,free_nongoal}`, `--scope-sweep`, `--sweep-widths` (V2 spike, k<=3: widths 1..8 give 0,1,1,2,2,3,3,3, equal to M1's column), `--timeout-s` (worker process, exit 2 UNKNOWN_TIMEOUT), a scope line in every explanation. 20 of 255 sampled masks agree with M1's table (not all 255); 24 reproduce rows re-run through the product engine, 0 differences. **Still not shipped:** `--count-rule branch` (exit 3), per-cycle attacker input (TODO in `config.py`), contiguous per-copy width groups, a partial table after a timeout. Product tests today: 138 passed, 1 skipped. Education kit (EDU, `research/c4/edu/EDU_REPORT.md`, `docs/edu/`): 90-minute lab, worksheet, key and three starter designs, commands verified on a copy with Yosys 0.33 only; no student has run it. Dashboard (DASH, `research/c4/dash/DASH_REPORT.md`): a new Scope tab (scope table, flips-vs-width curve, E2 variance, rail-dip note labelled SIMULATED with selectivity as the open question); 115 embedded values equal the source files, 0 mismatches; look and layout unchanged.")
rep("docs/dossier/PROJECT_DOSSIER.md",
    "1. Owner: write section 17 and rehearse (`QA_SHEET.md`). 2. Read EL1's report; add rail-correlated 1-to-0 and capture-of-D fault classes to B1 (EL1 suggestion).",
    "1. Owner: write section 17 and rehearse (`QA_SHEET.md`). 2. Read EL1's report (the rail-dip and capture fault classes are now in B3, s7.12; the open item is selectivity, s7.13). Also (C4): decide whether to apply R27's faster encoding patch (s7.14), port or drop the branch counting rule in the product, read k-FRP, and run an IR-drop or extraction study before any layout claim.")

# ---------------------------------------------------------------- EVIDENCE_INDEX
f = "docs/dossier/EVIDENCE_INDEX.md"
rep(f, "| 1 | `make test`: **30 passed** (about 29 s). (The old \"10 passed\" is STALE: 15 hardening + 5 check_reproduce tests were added by H1.)",
    "| 1 | `make test` (root `pytest tests`): **98 passed** in 26.7 s on a copy, 2026-11-19. History: 10 at first writing, 30 (RA, after H1), 98 now (MT/T2 added tests); quote your own count, `docs/NUMBERS.md`.")
rep(f, "RA, H1, lead (RUN_LOG 151), MT (30 passed in 33 s) |", "RECON (98 passed); earlier RA, H1, lead, MT (30) |")
rep(f, "| 2 | Product tests: **38 passed** (28.7 s) after `pip install ./product[test]`; earlier counts 21 (RA, H1), 27 (PS2, MT) are superseded.",
    "| 2 | Product tests: **138 passed, 1 skipped** (98.9 s; 139 collected) after `pip install ./product[test]`, RECON on a copy; earlier counts 21 (RA, H1), 27 (PS2, MT), 38 (PS3 lead count, not re-measured) are superseded.")
rep(f, "| `pip install \"./product[test]\" && python -m pytest product/tests` | PS3 (clean venv) |", "| `pip install \"./product[test]\" && python -m pytest product/tests` | RECON (copy, venv) |")
EV = """
## F. Wave C4 additions (D3, 2026-11-19 late; source numbers in `docs/NUMBERS.md`)
| # | Claim | Label | File | Command | Run by |
|---|---|---|---|---|---|
| 61 | Council W1: defensible only as a scoped sensitivity table; not adoptable then; compare-cone-only structure misses 48 of 252 breakable E2 V2 configs | SIMULATED judgement; chair recount MEASURED from stored data | `research/c4/council/COUNCIL_W1.md` | read; recount of `research/c2/e2_variance/raw/matrix.csv` | council chair |
| 62 | BP: option A spine, 9-item kill list, one experiment (held-out predictor); kill list is guidance, status in dossier s7.10 | INFERRED | `research/c4/bp/BP_REPORT.md` | read | BP |
| 63 | SWEEP S1: ePrint 2026/648, FIRMER journal id 11782, SYNFI 3 to 2 faults after FSM optimisation (SOURCED), counting-convention effect has no source; Moro EM about 9-10 bits/event on one device | SOURCED / SNIPPET / UNVERIFIED per row | `research/c4/sweeps/SWEEP_S1.md` | read | S1 |
| 64 | Predictor on 163 fresh cells: 150 exact (92.0%), within 1 156 (95.7%, fails 98% bar), 18 of 31 (58%) on 2+ flip cells; lb sound; 1.4x slower; raw column count 144 is an artefact | MEASURED | `research/c4/ver/VER_REPORT.md`, `heldout.csv`, `rerun_x.json` | `python3 -I heldout.py; python3 -I rerun_x.py` | VER (independent of PRE/TEST); RECON recomputed 144 and 150 |
| 65 | Predictor pooled 928/928 (all six pre-registered criteria) | MEASURED, near-duplicate cells (effective sample 3-5 designs); NOT a headline | `research/c4/test/TEST_REPORT.md` | `run_test.py` | TEST; audited by VER |
| 66 | B3 rail-dip: rail_all/half/unions/cone `>3` for V2 and V5; V0 cone 1; early/hold `>3`; dip_subset 1 (3 gates; V1 2); stem_flip control reproduces 3/2/1; brute force agrees on V0/V1 (T<=4, k<=2), not V2/V5 | SIMULATED basis (EL1), MEASURED verdicts | `research/c4/b3/B3_REPORT.md`, `matrix_T6.jsonl`, `val.log` | `python3 run_cells.py matrix_T6.jsonl ...`; `pytest test_b3.py` (16 passed) | B3 |
| 67 | Layout geometry V2: 4 minimal 3-cell sets, min enclosing r = 2.95 um, one supply net (one met4 VPWR strap, one VGND strap); radius thresholds; what-if 4.6 um is HYPOTHETICAL | MEASURED geometry; SIMULATED verdict; INFERRED domains; HYPOTHETICAL what-if | `research/c4/layout/LAYOUT_REPORT.md`, `geom_v2.json`, `minsets_v2.json` | `python3 minsets.py`, `radius_sweep.py` | LAYOUT |
| 68 | L2 follow-up to LAYOUT | in progress, no report found at D3 time | `research/c4/l2/L2_REPORT.md` (absent) | none | none |
| 69 | R27: sequential-counter encoding 10x-40x faster on UNSAT cells, same verdicts on 14 cells; patch NOT applied to the tree | MEASURED (noisy timing) | `research/c3/r27/R27_REPORT.md`, `seq_counter.patch`, `agree.jsonl` | `python3 exp.py` on a copy | R27 |
| 70 | V456: V5 beats V2 only on full word, apt-0.33 flow (3 vs 2); V6 refuted (1 flip everywhere); V4 1; none beats V2 spike; 360 cells, 0 unknown | MEASURED | `research/c3/v456/V456_REPORT.md`, `data/all_rows.json` | `python3 tools/run.py ...` | V456 |
| 71 | Product options PS4/PS5: consumer-bits, input-sites, init modes, scope-sweep, sweep-widths (0,1,1,2,2,3,3,3), timeout-s; branch rule not ported; 24 reproduce rows 0 differences; 20 of 255 masks agree with M1 | MEASURED | `research/c4/ps4/PS4_REPORT.md`, `research/c4/ps5/PS5_REPORT.md` | `faultbound-wt analyze ... --sweep-widths` | PS4, PS5 |
| 72 | EDU kit: lab, worksheet, key, 3 starter designs verified (V2 85 gates min 2; with opt_merge 63 gates min 1; masks 0xFF 3, 0x0F 2); no student run | MEASURED (Yosys 0.33 only) | `research/c4/edu/EDU_REPORT.md`, `verification.log` | `research/c4/edu/verify_edu.sh` | EDU |
| 73 | DASH Scope tab: 115 embedded values equal source files, 0 mismatches; 0 console errors at 390 and 1366 px | MEASURED | `research/c4/dash/DASH_REPORT.md`, `verify_numbers_output.txt` | `python3 research/c4/dash/verify_numbers.py` | DASH |
| 74 | QA weakest 10: unaided derivations; counting rule; predictor; 85 vs 83 gates; SPICE; DRC/LVS honesty; B3 rail-dip; "independent validation"/unbounded proof; novelty | SIMULATED | `research/c4/qa_sim/QA_SIM_REPORT.md` s5 | read | QA |
| 75 | M1 mask matrix recheck for an x-init bug | in progress: M1-derived figures are **recheck pending (M1b)** | `research/c4/m1b/` (CSV only, no report at D3 time) | none | M1b |
| 76 | Number reconciliation: `scripts/check_numbers.py` and `docs/NUMBERS.md` (83 rows, 15 stale rules) | MEASURED | `docs/NUMBERS.md`, `scripts/check_numbers.py`, `research/c4/recon/RECON_REPORT.md`; D3 result in `research/c4/d3/D3_REPORT.md` | `python3 scripts/check_numbers.py` | RECON, D3 |
"""
append(f, "## F. Wave C4 additions", EV)

# ---------------------------------------------------------------- CRITIQUE
CR = """
| COUNCIL-1 | Council W1 | HIGH | no record of the owner re-deriving any result | research/c4/council/COUNCIL_W1.md s4 | OPEN [OWNER]: `docs/OWNER_DERIVATION_SHEET.md`, dossier s17 |
| COUNCIL-2 | Council W1 | HIGH | Front door stale: called the DA 6/32 vs 32/32 result not re-run (REP replicated 64/64); framed weighting rules beside stem=1 | COUNCIL_W1 s3 item 1, risk 2 | FIXED (D3): README, START, FINAL_STATUS, ENGINE_STATUS, report pages say replicated, one recipe list |
| COUNCIL-3 | Council W1 | HIGH | Scope axes and goal masks absent from `product/src` | COUNCIL_W1 s1 item 3 | PARTLY FIXED: PS4/PS5 shipped consumer-bits, input-sites, init, scope-sweep, sweep-widths; branch rule and per-cycle input still not shipped |
| COUNCIL-4 | Council W1 | MED | Compare-cone-only structural check misses 48 of 252 breakable E2 V2 configs | COUNCIL_W1 s2 (chair recount) | OPEN: see VER-1 (the extended predictor was tested; heuristic only) |
| COUNCIL-5 | Council W1 | MED | Release blockers: licence undecided, third_party_derived unlicensed, Dockerfile never built, red-team A1 (order-dependent multi-driver verdict) and A6 (crash exit code equals attack exit code) | COUNCIL_W1 s4 item 5 | OPEN [OWNER] for licence and third_party_derived; A1 and A6 were not re-checked by D3 |
| BP-1 | BP | INFO | Kill list (9 items) and recommended spine (linter) | research/c4/bp/BP_REPORT.md s3 | ADOPTED as guidance; D3 added no new document pages |
| S1-1 | SWEEP S1 | MED | Wording must not imply no minimum-fault verification exists (FIRMER, SYNFI bounded search; k-FRP unbounded); SYNFI 3 to 2 faults is SOURCED support | research/c4/sweeps/SWEEP_S1.md s3 | FIXED (wording): dossier s7.10; k-FRP and FIVER full texts still unread |
| VER-1 | VER | HIGH | Predictor "928/928" not validated: 150/163 (92%) on fresh cells, 18/31 (58%) on 2+ flip cells, within-1 95.7% fails the 98% bar, 7 under-predictions via `uncovered` fallback, 1.4x slower | research/c4/ver/VER_REPORT.md s3-5 | FIXED (wording): README, FINAL_STATUS, dossier s7.11, QA cards; code fix (report `uncovered` as unknown) not done |
| VER-2 | VER | MED | `heldout.csv` raw column gives 144/163; corrected 150 lives in `rerun_x.json` | RECON s3 | OPEN: VER should append a corrected column; docs quote 150 with the correction named |
| VER-3 | VER | MED | x-init clobber in solver copy `gs_mask.py` (47 cells rerun, 2 changed) may affect M1-derived tables | VER s3.3 | OPEN: M1b recheck pending; M1 figures marked 'recheck pending (M1b)' |
| B3-1 | B3 | MED | "V2 survives rail dips" reads as a security result; depends on selectivity (dip_subset 1 event, 3 gates); not brute-force validated for V2/V5; no witness replay | research/c4/b3/B3_REPORT.md | FIXED (wording): dossier s7.12; OPEN (validation) |
| LAY-1 | LAYOUT | MED | Selectivity radius 2.95 um is geometry plus simulated verdict; one supply net; no IR-drop or extraction; what-if 4.6 um hypothetical; V0 not covered | research/c4/layout/LAYOUT_REPORT.md s5-6 | FIXED (wording): dossier s7.13; L2 in progress |
| R27-1 | R27 | LOW | Faster encoding patch exists, not applied; adoption needs tests and reproduce re-run | research/c3/r27/R27_REPORT.md s4 | OPEN [decision] |
| V456-1 | V456 | INFO | V6 refuted; V5 beats V2 only in apt full-word cell; no design beats V2 on the stored netlist | research/c3/v456/V456_REPORT.md | FIXED (wording): dossier s7.14; R21-1 superseded for V4-V6 |
| PS-1 | PS4/PS5 | MED | Product `--count-rule branch` not ported; per-cycle input TODO; 20 of 255 masks spot-checked | PS4 report | OPEN |
| QA-1 | QA | HIGH | Weakest 10 answers (authorship, unaided derivations, counting rule, predictor, 85 vs 83, SPICE, DRC/LVS, B3, "independent", novelty) | research/c4/qa_sim/QA_SIM_REPORT.md s5 | FIXED (wording) where numbers are involved; the rest are [OWNER] practice items |
| RECON-1 | RECON | MED | 38 stale numbers across docs (test counts, "not re-run", 144/163) | research/c4/recon/RECON_REPORT.md s5 | FIXED in D3's files; remaining files (dashboard/build.py and index.html, research/c4/qa_sim) belong to other owners: see research/c4/d3/D3_REPORT.md |
"""
_s = rd("docs/dossier/CRITIQUE.md")
if "| COUNCIL-1 |" not in _s: wr("docs/dossier/CRITIQUE.md", _s.rstrip("\n") + "\n" + CR.strip("\n") + "\n")
rep("docs/dossier/CRITIQUE.md", "| RA-1 | RA | MED | \"10 passed\" stale (30 now)", "| RA-1 | RA | MED | \"10 passed\" stale (30 then, 98 now per RECON)")

# ---------------------------------------------------------------- QA_SHEET
VS = """
## Wave C4 additions (D3): questions the new results invite 
30. *Is the structural predictor validated, and is it faster?* No. On 163 fresh cells from 76 new netlists it was exact on 150 (92%), 58% (18 of 31) on cells needing 2 or more flips; within one flip 95.7%, which fails the 98% bar we set before the run; it was 1.4x slower than the solver. It is a heuristic attack search with a sound lower bound; the solver is the reference. The 928/928 figure is near-duplicate cells. (VER, `research/c4/ver/VER_REPORT.md`.)
31. *Does V2 survive a supply dip?* Only inside the model and only if the event hits a whole rail, a whole hierarchy unit or a fanout cone: no attack up to 3 events (bounded, T=6). If one event can choose which gates fall, 3 gates (one per copy) give a 1-event attack. Whether a real dip can choose is not established; the SPICE basis is one tiny rail. (B3.)
32. *Where would the three copies have to sit?* In the stored V2 layout the three comparator cells that suffice lie within a 2.95 um radius and there is one supply net, so a selective local event is geometrically possible; this is a measured geometry plus a simulated verdict, with no IR-drop study. A hypothetical swap raised the radius to 4.6 um. (LAYOUT; L2 in progress.)
33. *Did you try a better design?* Yes: V4 (sparse code) 1, V5 (voter plus alert) beats V2 only on the full-word goal in the apt flow (3 vs 2), V6 (sparse sequence) was worse (1) so the prediction in the literature sketch failed. No design beats V2 on the stored netlist. (V456.)
34. *Is the tool ready for others?* Partly: the product now has consumer bits, input sites, power-up modes, scope sweeps, width sweeps and a timeout; branch counting and per-cycle input are not shipped; licence undecided; Dockerfile and Action never run. (PS4, PS5, council W1.)
35. *Is it faster to solve now?* A patch exists (sequential-counter encoding, 10x to 40x on UNSAT cells, same verdicts on 14 cells); it is not applied to the tree. (R27.)
36. *Which of your mask numbers could still change?* The consumer-mask table (88/96/44, 68 mismatches on apt-0.33): recheck pending (M1b) for an x-init bug found by VER in the solver copy; the width curve 0,1,1,2,2,3,3,3 was also reproduced through the product engine.
Weakest ten (QA sim s5): (1) what did you do; (2) unaided derivations; (3) counting rule 6/32 vs 32/32; (4) predictor 92% not 928/928; (5) 85 vs 83 gates, cause unknown; (6) SPICE physics; (7) DRC/LVS wording; (8) B3 rail-dip needs "bounded, selectivity unknown"; (9) drop "independent" and "unbounded proof"; (10) novelty: nothing established as new, name SYNFI, FIRMER, k-FRP.
"""
append("docs/dossier/QA_SHEET.md", "## Wave C4 additions", VS)

# ---------------------------------------------------------------- ONE_PAGE_FOR_THE_OWNER
f = "docs/dossier/ONE_PAGE_FOR_THE_OWNER.md"
rep(f, "The tests pass (30 main tests, 38 product tests, on copies).", "The tests pass (98 main tests, 138 product tests with 1 skipped, on a copy, 2026-11-19; run `make test` and quote your own count).")
rep(f, "## What is NOT proven\n",
"""## What changed in the last wave (C4)
- The check "does a predictor tell you the answer without the solver" was run: on fresh netlists it was exact 92% of the time (58% when 2 or more flips are needed) and not faster; so it is a rough pre-check, the solver stays the judge.
- A supply dip over a whole rail, a whole block or a cone does not break V2 within 3 events (model, bounded); if one dip could pick its gates it takes 1 event (3 gates). The layout puts the three sufficient cells within 2.95 um of each other on one supply net. Whether a real dip can choose is the open question.
- Other designs: only V5 beats V2, and only on one setting; V6 was worse. The command-line tool now offers consumer bits, input sites, power-up modes and scope sweeps; a classroom kit and a dashboard Scope tab exist.
- Consumer-mask numbers: recheck pending (M1b).

## What is NOT proven
""")
rep(f, "- Nothing is new: SYNFI and FIRMER already do this kind of analysis; one closer paper (k-FRP) was never read.",
"- Nothing is new: SYNFI and FIRMER already do this kind of analysis; one closer paper (k-FRP) was never read.\n- The predictor is not validated and not faster (92% exact, 58% on multi-flip cells); the 928/928 figure is near-duplicate cells.\n- Not shown: that a real supply dip can choose which gates fall (B3, LAYOUT), or any layout-based security claim (no IR-drop or extraction).")
rep(f, "(30 s) How it was checked (other tools, same model; 30 tests; re-run on a copy)", "(30 s) How it was checked (other tools, same model; 98 tests; re-run on a copy)")

# ---------------------------------------------------------------- EVIDENCE_MAP
f = "docs/dossier/EVIDENCE_MAP.md"
RB = """
**C4 additions (D3):** row 5 Verification also: VER audit (60/60 resample, 150/163 fresh-cell predictor, bounds sound), B3 brute-force check on V0/V1 only. Row 6 Results also: B3 rail/capture matrix (T=6, 3 events), LAYOUT geometry (r = 2.95 um), V456 (V6 refuted), SWEEP S1 prior-art update (SOURCED/SNIPPET). Row 12 Electronics: geometry and supply-net facts from the DEF (MEASURED), verdicts SIMULATED, no extraction: estimate stays 4. Row 15 Product: scope options shipped by PS4/PS5, 138 tests; branch rule and per-cycle input missing: estimate 4 to 5. EDU kit supports rows 9 and 15 (no student run). Estimates unchanged otherwise; the mean is not recomputed. Consumer-mask evidence (M1): recheck pending (M1b).
"""
append(f, "**C4 additions (D3):**", RB)

# ---------------------------------------------------------------- AI_USE (nothing more), PROBLEM_STATEMENT (P3 stays)
# ---------------------------------------------------------------- FINAL_STATUS
f = "docs/FINAL_STATUS.md"
rep(f, "- **Not in the shipped tool (checked by grep of `product/src` by the council chair):** the scope options (input nets as fault sites, power-up modes, free per-cycle input) and the goal-mask option exist only as research scripts (`research/c2/b2_scope/gs.py`, `research/c3/m1/gs_mask.py`); per-cycle attacker input is a TODO in `product/src/faultbound_wt/config.py` (line 76). The product reports only the constant-input, word-goal baseline.",
    "- **Shipped tool vs research scripts (updated by D3 after PS4 and PS5, 2026-11-19):** `product/` now has `--consumer-bits`, `--goal-out/--accept-value`, `--input-sites`, `--init {known,arbitrary,free_nongoal}`, `--scope-sweep`, `--sweep-widths` (0,1,1,2,2,3,3,3 on the stored V2) and `--timeout-s` (`research/c4/ps4/PS4_REPORT.md`, `research/c4/ps5/PS5_REPORT.md`). NOT shipped: `--count-rule branch` (exit 3), per-cycle attacker input (TODO in `config.py`), per-copy width groups. The council chair's earlier grep (no scope flags in `product/src`) was true when written and is superseded.")
rep(f, "- Engine (`docs/ENGINE_STATUS.md`): `make test` 30 passed (MEASURED by agent RA, 2026-11-19, `research/c3/ra/RA_REPORT.md`; `tests/` may have gained tests from agent T2 since, not re-counted here; product tests: 38 (count given by the lead; 27 were MEASURED by agent PS2, `research/c3/ps2/PS2_REPORT.md`, before later additions) after `pip install ./product[test]`), `make reproduce` about 25 s.",
    "- Engine (`docs/ENGINE_STATUS.md`): root tests **98 passed**; product tests **138 passed, 1 skipped** after `pip install ./product[test]` (MEASURED by RECON on a copy, 2026-11-19, `research/c4/recon/RECON_REPORT.md`; history 10, 30 (RA), 98 and 21, 27 (PS2), 38 (lead count, unmeasured); counts move when tests are added: run `make test` and quote your own, `docs/NUMBERS.md`), `make reproduce` about 25 s.")
rep(f, "Under stem = 1, V2 holds against 2 flips on 6 of 32 netlists.", "Under stem = 1, V2 holds against 2 flips on 6 of 32 netlists (one recipe list, so one recipe, not independent designs).")
rep(f, "E1", "E1")
FS = """
## Update C4 (D3 integration pass, 2026-11-19 late; numbers in `docs/NUMBERS.md`)
- **Predictor** (`research/c4/pre/`, TEST, VER): exact on 150 of 163 fresh cells (92%), 58% (18 of 31) on cells needing 2 or more flips, within one flip 95.7% (fails the 98% bar set beforehand), 1.4x slower than the solver; heuristic attack search with a sound lower bound; the solver stays the reference. The pooled 928/928 is near-duplicate cells (effective sample 3 to 5 designs) and is not a headline. Research script only, not in the tool.
- **Rail dip and wrong-time capture** (B3, SIMULATED basis, bounded T=6, 3 events): whole-rail, half-hierarchy, union and fanout-cone dips give no attack for V2 and V5; early and hold capture none; if one event may choose which gates fall, 1 event (3 gates, one per copy). **Selectivity is the open question.**
- **Layout geometry** (LAYOUT, MEASURED geometry, SIMULATED verdict): the cheapest sufficient set sits within r = 2.95 um, one supply net, no extraction. The 4.6 um placement is a hypothetical what-if. L2 follow-up: in progress.
- **Other designs** (V456): only V5 beats V2 and only for the full word in the apt-0.33 flow (3 vs 2); V6 refuted (1 flip); none beats V2 on the stored netlist.
- **Faster encoding** (R27): a sequential-counter patch exists (10x to 40x on UNSAT cells); not applied to the tree.
- **Council W1, BP, SWEEP S1, QA sim, EDU, DASH:** see dossier s7.10 to 7.15 (`docs/dossier/PROJECT_DOSSIER.md`). Council: defensible only as a scoped sensitivity table; owner defence is the largest risk. QA weakest 10: `research/c4/qa_sim/QA_SIM_REPORT.md` s5.
- **Consumer-mask figures (M1):** recheck pending (M1b).
- What is NOT proven (unchanged): nothing physical, nothing novel, no security of any design, no validation of the predictor, no physical basis for any counting rule, the unbounded proof is one netlist and unreplicated.
"""
insert_before(f, "## Known weak points", "## Update C4", FS)

# ---------------------------------------------------------------- ENGINE_STATUS extra
append("docs/ENGINE_STATUS.md", "R27 faster encoding (D3 note)", "R27 faster encoding (D3 note): a sequential-counter patch (`research/c3/r27/seq_counter.patch`, 10x to 40x on UNSAT cells, same verdicts on 14 cells) exists and is NOT applied to `scripts/glitchsat.py`; adopting it needs `make test`, product tests and the 36 reproduce rows re-run on a copy.")

# ---------------------------------------------------------------- README (rewrite, <= 70 lines)
README = """# Project (working title TBD)



## The problem (working statement P3; owner decides wording: `docs/dossier/PROBLEM_STATEMENT_EVOLUTION.md`)
Given a gate-level netlist and the bits a consumer actually checks, report how many single-cycle flips defeat a redundant boot decision, which nets the supposed copies share, and how that answer changes with synthesis build, counting rule and scope.

## One glance (MEASURED; modelled single-cycle bit flips, 6 cycles, k <= 3, toy 8-bit designs; nothing physical)
Minimum flips the solver needs to make V2 (triplicated check) accept a wrong input. V1 is duplicated, V0 naive.

| Goal / consumer (V2) | Flips | Source |
|---|---|---|
| Full 8-bit word, stored netlist | **3** | `research/c2/b2_scope/B2_REPORT.md`, `research/c3/m1/M1_REPORT.md` |
| Full 8-bit word, re-synthesized with apt Yosys 0.33 | **2** | same |
| Consumer that checks only 4 bits (stored netlist) | 1 to 3 (28 / 36 / 4 of 68 masks need 1 / 2 / 3); M1 figures: recheck pending (M1b) | `research/c3/m1/m1_all_masks.csv` |
| Accept flag `boot_ok`; or input nets as fault sites; or arbitrary non-accepting power-up | **1** | B2 matrix (360 cells) |
| V1 and V0, every scope cell tried | **1** (V1 needs 2 in 31 of 264 re-synthesis configs) | B2, E2 |
| V2 over 264 solved synthesis configurations | 1 in 180, 2 in 60, 3 in 24 | `research/c2/e2_variance/E2_REPORT.md` |
| V2 under rail-wide, half-design or cone supply dips (SIMULATED basis) | no attack up to 3 events; **1 event if one dip may choose its gates** (3 gates; selectivity open) | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |

So: copies that share one wire do not help (V1 breaks with one flip on `ok`), and "V2 resists 2 flips" is true only in one narrow cell (full word, input nets not fault sites, known power-up, stored netlist). Never quote it without those qualifiers.

## Counting rule
Headline rule: a flip of a net (stem) is one fault, however many gates read it (matches FIRMER's per-gate counting; `research/c3/r22/R22_REPORT.md`). Counting a fanout-f net as f faults is a stress test. Neither rule is shown physical. Under stem = 1, V2 holds against 2 flips on 6 of 32 re-synthesized netlists; under fanout counting on 32 of 32. Measured by agent DA, replicated by agent REP on 64 of 64 rows with one reused recipe list (one recipe, not independent designs; `research/c3/rep/REP_REPORT.md`).

## What this is, and what it is not
- A reproducible fault-injection analysis toolkit (solver, dashboard, flow-demo layouts, a small CLI in `product/`) and a specimen showing how a redundancy verdict moves with scope, consumer width, synthesis and counting rule.
- **No novelty claim**: nothing established as new. Prior art: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI (`docs/PRIOR_ART.md`; k-FRP and FIVER full texts unread).
- Model only: no chip, hardware, physical glitch, fabrication, sign-off or deployed-product finding.
- **Not proven:** that any design is secure (bounds are 6 cycles, k <= 3; `>3` is not "secure"); the one unbounded proof (ABC PDR, V2 spike, k <= 2) is one netlist and not replicated; no counting rule is physical; whether a real supply dip can choose which gates fall; the predictor (below) is not validated.
- Structural predictor (`research/c4/pre/`, research script): exact on 150 of 163 fresh cells (92%), 58% on cells needing 2+ flips, 1.4x slower than the solver. A heuristic with a sound lower bound; the solver stays the reference. The old 928/928 is near-duplicate cells.

## Shipped tool vs research (status)
- In `product/`: consumer bits, goal output, input sites, power-up modes, scope sweep, width sweep, timeout (PS4, PS5). **Not shipped:** branch counting rule, per-cycle attacker input (TODO `config.py`), predictor.
- Layout (`layout/`) needs a separate EDA install; not in CI. Dockerfile never built, GitHub Action never run.
- Open: layout-based selectivity study (L2 in progress); faster encoding patch exists but is not applied (`research/c3/r27/`).

## Quick start (Linux; verified by agent RA, counts by RECON on a copy, 2026-11-19)
```
sudo apt-get install -y yosys iverilog          # tested with yosys 0.33, iverilog 12.0
python3 -m venv .venv && . .venv/bin/activate
pip install -r ci/requirements-ci.txt           # z3-solver, pytest
make check-tools && make test                   # 98 passed (quote your own count)
make reproduce && make check-reproduce          # V0/V1/V2 sweeps (~25 s), 36/36 rows
```
`make reproduce` and `make test` rewrite `results/` and `tb/`: run them on a copy. Product tests (`pip install ./product[test]`): 138 passed, 1 skipped. The apt 0.33 and conda 0.38 builds give different V2 netlists (85 vs 83 combinational gates), so CI on another Yosys may not reproduce `ci/expected_reproduce.json`. `make help` lists targets.

## Where things are
- `START.md` first path; `docs/OWNER_DERIVATION_SHEET.md` pencil derivations; `docs/dossier/` dossier, Q&A sheet, evidence index, critique; `docs/edu/` classroom kit; `docs/wow/` explainer and game.
- `rtl/` designs, `reference/spike_netlists/`, `scripts/glitchsat.py` solver, `formal/`, `results/`, `dashboard/` (now with a Scope tab), `layout/`, `product/`, `research/` agent reports. Run log: `handoff/RUN_LOG.md`.
- Every number carries one label (MEASURED, SIMULATED, ESTIMATED, ILLUSTRATIVE, UNVERIFIED): `docs/EVIDENCE_LABELS.md`. Licence: undecided (`LICENSE_CHOICE.md`).
"""
wr("README.md", README)

# ---------------------------------------------------------------- START.md
f = "START.md"
rep(f, "- The scope and goal-mask options are research scripts, not in `product/`; per-cycle input is a TODO there.",
"- The scope options (consumer bits, input sites, power-up modes, sweeps) are now in `product/` (PS4, PS5); the branch counting rule and per-cycle input are not shipped. The structural predictor is a research script: 92% exact on fresh cells, 58% on multi-flip cells, not faster; the solver is the reference.\n- A supply dip over a whole rail or cone does not break V2 within 3 modelled events, but one dip that could choose its gates would (3 gates); whether a real dip can is open (B3, LAYOUT; r = 2.95 um, one supply net, no extraction).\n- Consumer-mask figures (M1): recheck pending (M1b).")
rep(f, "| 6 of 32 vs 32 of 32 replicated | `research/c3/rep/REP_REPORT.md` |", "| 6 of 32 vs 32 of 32 replicated (64 of 64 rows, one recipe list) | `research/c3/rep/REP_REPORT.md` |\n| Predictor audit (150 of 163, 92%) | `research/c4/ver/VER_REPORT.md` |\n| Rail dips and layout geometry | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |\n| Numbers in one place (run `python3 scripts/check_numbers.py`) | `docs/NUMBERS.md` |")
rep(f, "Expected: the first finds an attack with 1 flip", "Counts as of 2026-11-19: `make test` 98 passed (quote your own). Expected: the first finds an attack with 1 flip")
print("integrate done")
