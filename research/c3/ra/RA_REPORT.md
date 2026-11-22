# RA report: reproducibility audit as an outside reviewer

Licence: UNDECIDED. Working title TBD. Labels: MEASURED = I ran it on the copy `/tmp/work_ra/proj` (tar copy; nothing run in the tree; the tree was only read). INFERRED = read from files or reasoned, not run.
Machine: Linux 6.18, Python 3.13.18, apt Yosys 0.33, Icarus 12.0, z3 5.4.1.0, pytest 9.1.1 (preinstalled system pytest) / 9.2.0 (venv). Network used: pypi.org only.

## 1. README quick-start, followed literally (MEASURED)

| Step | Result | Time | Note |
|---|---|---|---|
| `sudo apt-get install -y yosys iverilog` | NOT RUN (both already on PATH here); Yosys 0.33 and iverilog 12.0 matched the README | - | A reviewer on another distro gets a different Yosys; see section 4 |
| `python3 -m venv .venv && . .venv/bin/activate` | OK | 6.4 s with the next step | Python is 3.13 here; Makefile says >=3.9, CI uses 3.12. Neither 3.9 nor 3.12 was tried |
| `pip install -r ci/requirements-ci.txt` | OK (z3-solver 5.4.1.0 pinned, pytest unpinned `>=8`) | included above | Needs pypi.org |
| `make check-tools` | OK | 0.75 s | |
| `make test` | 30 passed | 28.7 s | README does not say how many; FINAL_STATUS and the dossier still say 10 (see section 3) |
| `make reproduce` | OK, 36 rows written | 29.1 s wall | README says ~25 s |
| `make check-reproduce` | "36/36 rows match ... engine NOT re-run" | 0.13 s | Passes, but the wording shows it is only an accident check without `--rerun` |
| `make replay` | OK, `agrees_with_solver: true` (2 witnesses) | 0.56 s | Writes into `tb/generated` |
| `make dashboard` | OK, "wrote index.html; live = True" | 0.07 s | Overwrites `dashboard/index.html` (differs from the tree copy, as H1 predicted) |
| `make validate` (not in README quickstart) | ran to the end (long net listing) | not timed | |

Unclear or unstated items for an outsider (INFERRED from the run):
1. The README does not say that every `make` target writes into `results/`, `tb/` and `dashboard/` of the tree; FINAL_STATUS says to work on a copy, README does not.
2. The product tests need `pip install "./product[test]"` first (documented only in `product/README.md` line 59, not in the README). Running `python3 -m pytest product/tests` straight after the quickstart FAILS at collection with `ModuleNotFoundError: faultbound_wt` (MEASURED, 2 errors). After the install: 21 passed.
3. README says "Licence: undecided" but the Quickstart does not mention the layout tools are separate and need about 12 GB (it does say "separate EDA install"; size is only in FINAL_STATUS).
4. The README does not say that a different Yosys build can change the verdict table; `ci/expected_reproduce.json` is therefore tool-build specific (stated in FINAL_STATUS, not in README Quickstart).
5. `README.md` quickstart line `make check-reproduce` has odd extra whitespace; cosmetic.
6. The README refers readers to `docs/FINAL_STATUS.md` as "read first", but that file still carries stale numbers (section 3, items 7 and 8).

## 2. Test and reproduce runs (MEASURED, on the copy)

| Command | Result | Runtime |
|---|---|---|
| `make test` (`pytest -q tests`) | 30 passed | 28.7 s |
| `make check-reproduce` | 36/36 rows match, 0 problems | 0.13 s |
| `python3 ci/check_reproduce.py --rerun` | 36/36 rows match (engine re-run), 0 problems | 23.6 s |
| `make reproduce` then `make check-reproduce` | 36/36 | 29.1 s + 0.1 s |
| `python3 -m pytest -q tests` inside `product/` without installing | 2 collection errors (ModuleNotFoundError) | 0.4 s |
| `PYTHONPATH=src pytest tests` inside `product/` | 21 passed | 15.9 s |
| `pip install "./product[test]"` then `pytest product/tests` from the root | 21 passed | 3.0 s install + 16.8 s |
| `make replay` | agrees_with_solver true | 0.56 s |

Comparison with the stored tree results (MEASURED): the rebuilt `reproduce_summary.json` has the same 36 rows, 0 rows differ in verdict or min_faults, 11 of 36 rows have a different witness (fault list), which matches H1_LOG's statement that the witness is not unique. Runtimes in the stored file differ from this machine (for example V2 spike k=3: 5.139 s stored, 3.76 s here). The dossier's "7.1 s in D1 re-run" is also machine-dependent.

## 3. 25 headline claims traced

Source key: README = README.md, FS = docs/FINAL_STATUS.md, PD = docs/dossier/PROJECT_DOSSIER.md, OP = docs/report/ONE_PAGE_SUMMARY.md, EX = docs/explainers/explainer.html.

| # | Claim (where) | Verdict | Where / actual value |
|---|---|---|---|
| 1 | V0 breaks with 1 flip, 6 cycles (README, OP, PD, EX) | TRACED | `results/reproduce_summary.json` rows v0/k=1..3 min_faults 1, all three netlists; re-measured |
| 2 | V1 breaks with 1 flip on shared net `ok` (README, OP) | TRACED | same file, v1 rows min_faults 1; shared net `ok`, cycle 1: `validation/VALIDATION.md` line 16 |
| 3 | V2 spike: no attack k<=2, attack at k=3, min 3 (FS, OP, PD) | TRACED | summary rows v2 spike k=2 NO_ATTACK_UP_TO_BOUND (1.178 s), k=3 ATTACK_FOUND min 3 (5.139 s) |
| 4 | V2 re-synthesized with apt Yosys 0.33 has a 2-flip attack (README, FS, OP) | TRACED | summary rows v2 rtl/plain and rtl/opt k=2: ATTACK_FOUND min 2; re-measured via `make reproduce` |
| 5 | 36 rows in the sweep; `check-reproduce` "36/36" (PD) | TRACED | 36 rows in summary; re-measured 36/36 |
| 6 | `make reproduce` about 25 s (README, FS) | TRACED (approx.) | 29.1 s wall here; the sum of solver runtimes is lower; "about" is acceptable, but machine dependent |
| 7 | `make test` 10 passed (FS Results; PD table "10 passed in 18.56 s"; OP "10 tests pass") | MISMATCH | 30 passed in 28.7 s now (`tests/` holds test_engine plus H1's test_hardening 15 and test_check_reproduce 5). FS, PD and OP not updated after H1 |
| 8 | Product tests (not stated as a number anywhere I found) | NOT TRACED | no document states the count; measured 21 passed |
| 9 | V2 apt netlist is 85 gates (40 AND, 25 OR, 20 NOT, 8 DFF) (README, FS, PD, OP) | TRACED | `formal/FORMAL.md` line 20 and 35; `results/work/v2.json` counts 40/25/20/8 (85 combinational gates plus 8 flops, 93 cells in total; the text uses "85 gates" for the combinational count only, which is unlabelled) |
| 10 | opt flow gives 81 gates and also a 2-flip attack (EX, `docs/ENGINE_STATUS.md` line 34) | TRACED | `results/work/v2_opt.json`: 38 AND, 23 OR, 18 NOT, 2 MUX = 81 combinational; summary row v2 rtl/opt k=2 min 2 |
| 11 | conda Yosys 0.38+92 gives 83 gates (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF) and no 2-flip attack (README, FS, OP) | TRACED but not re-run | `formal/FORMAL.md` lines 20, 35; I cannot rerun it (no conda env here): INFERRED as to current truth |
| 12 | 32-netlist matrix: V2 needs 2 flips on 26, 3 on 6; "held against 2 flips on 6 of 32"; 19 percent (README, FS, OP, EX) | TRACED | `research/c2/devils_advocate/DA_CYCLE1.md` line 11 (26/32 and 6/32; 6/32 = 18.75 percent, rounds to 19); replicated 64/64 by `research/c3/rep/REP_REPORT.md` line 4 (not re-run by me) |
| 13 | With stem flip costing its fanout, V2 needs 3 on all 32, V1 needs 2 on all 32 (README, FS, EX) | TRACED | DA_CYCLE1.md line 13 (E3) |
| 14 | Flow B netlist: V2 falls to 1 flip, 4 of 378 single-flip sites (FS, OP) | TRACED | `validation/VALIDATION.md` line 28 |
| 15 | ~2.1M simulated fault sets x 255 inputs, 0 disagreements; 13/13 replays; 5 boolector queries (PD) | TRACED | `validation/VALIDATION.md` line 24 and 21 |
| 16 | V2 spike all 2-flip sets: 46,056 (T=4), 103,740 (T=6), none succeed (PD) | TRACED | `validation/VALIDATION.md` line 18 |
| 17 | 3 flips all in cycle 1: 70,300 sets, 182 attacks (PD) | TRACED | `validation/VALIDATION.md` line 19 |
| 18 | PDR unbounded proof for V2 spike k=2 PASS in 0.83 s (FS, PD) | TRACED to a report, NOT re-run by me | claim text in `formal/FORMAL.md`; conda env `formal` is not available here, so MEASURED by others only |
| 19 | sby BMC depth 6 matches the solver on 40 netlist/k pairs (FS, PD) | TRACED | `formal/FORMAL.md` line 25 (`formal/runs/bmc_matrix*.json`) |
| 20 | Deep sweep: V2 spike k=2 at 20 cycles 294.3 s, k=3 474.9 s, never broken at 2 up to 20 cycles (PD) | TRACED | `docs/DEEP_RESULTS.md` lines 36, 37, 62, 63; data in `results/deep/sweep_main.json` |
| 21 | Layout: 35 vs 36 cells, 357.8 vs 362.8 um^2, setup slack +7.050 / +7.035 ns (PD) | TRACED | `layout/v_designs/out_patched/RESULT.md` lines 7 and 10 (patched columns; the two other columns have +6.964 and +7.016 ns, so the claim is only correct for the patched flow) |
| 22 | State code {F0, CC, 96, 69} minimum Hamming distance 4 (PD) | TRACED | computed by me: pairwise distances 4,4,4,4,4,8 |
| 23 | Mutation check: netlist level 2/2 caught; RTL level 2 of 3 not caught (PD) | TRACED | `results/mutation_summary.json`: netlist_share_c1_with_c0 caught true, netlist_share_c2_with_c1 true; RTL share_c1_with_c0 false, share_c2_with_c1 false, single_decision_net true |
| 24 | sqrt_q15 worst case 7.15 LSB at input 31797, 25 inputs above 6 LSB, CBMC bound 8 (FS) | TRACED | `numerics_audit/AUDIT.md` lines 12 and 13 (value 7.1509; CBMC counterexample at bound 6 is in=30868, not 31797; the two are different results and consistent) |
| 25 | Fuzzing "0 mismatches in about 6,700 programs" (FS) | NOT TRACED | FS itself labels it UNVERIFIED and says the data is not in the repo; the figure appears only in `handoff/CONTINUATION/earlier_research/gasp/GASP_DECISION.md` line 27 (a decision doc, not data) |
| 26 | E1: free per-cycle input, 57-row matrix, V2 k<=2 none at T=4,6,8 (FS, PD) | TRACED | `research/c2/e1_timevarying/matrix_bmc_z3.json` has 57 rows; I did not read each row |
| 27 | CMSIS_5 #1386 / CMSIS-DSP #9 already tracked upstream (FS) | NOT TRACED | external issue numbers; FS says UNVERIFIED |
| 28 | "CI workflows exist but never ran on GitHub" (OP) | TRACED | `ci/README.md`, `.github/workflows/ci.yml` and `nightly.yml` present; "never ran" cannot be checked from the tree (INFERRED) |

Additional mismatch found while tracing (not in the 25 count): FS "Reproduce" block says `cd dashboard && python3 build.py`, while the Makefile runs `python3 dashboard/build.py` from the root; both work, but the FS command path style differs. FS "Results" also still says `make reproduce` "about 25 s" while the Makefile help also says ~25 s.

Totals for items 1-28 above: TRACED 22 (of which 2 are "TRACED to a report, not re-run by me" and 1 is approximate), MISMATCH 1 (item 7), NOT TRACED 3 (items 8, 25, 27), plus the quantity "93 versus 85 gates" counting-convention note under item 9.

## 4. What would differ on another machine (INFERRED unless marked)

| Item | Why | Effect |
|---|---|---|
| Yosys build | Verdict table depends on the build: apt 0.33 gives 85 gates and a 2-flip attack on V2, conda 0.38+92 gives 83 gates and none (README, FORMAL.md) | `make reproduce` + `make check-reproduce` can FAIL on a newer apt Yosys (Debian 12 ships 0.27, Ubuntu 24.04 ships 0.33 or later; neither tested). Only 0.33 was run by me (MEASURED) |
| Debian vs Ubuntu apt versions | README says "tested with yosys 0.33, iverilog 12.0" and nothing else | other versions untested |
| z3 version | pinned `z3-solver==5.4.1.0`; witnesses change run to run (11 of 36 rows differ here, MEASURED) | verdicts stable, witnesses not; do not diff `faults` |
| Python version | 3.13 here, 3.12 in CI, >=3.9 claimed | 3.9 to 3.11 untested |
| Conda envs | `formal`, `spice`, `eda` live in `/tmp/mm_root`, not in the bundle (`handoff/CONTINUATION/ENV_REBUILD.md`) | PDR proof, sby cross-check, SPICE and layout cannot be reproduced from the README quickstart alone; I could not re-run any of them |
| Layout flow | needs a separate EDA install (about 12 GB), `scripts/setup_layout_tools.sh` "NOT re-run end to end" (FS) | UNVERIFIED reproducibility |
| Runtimes | stored runtimes differ from mine (V2 spike k=3: 5.139 s stored versus 3.76 s here) | only the verdicts are portable |
| Network | pip needs pypi.org | none otherwise for the core path |
| Nested venv | `compare/synfi_run/venv` (391 MB, Python 3.11 site-packages) is inside the tree; my copy excluded only the top-level `venv/`, so it was copied | wasted 391 MB, would break on another Python/OS |

## 5. Bundle hygiene (MEASURED, read-only on the tree)

| Check | Result |
|---|---|
| Tree size, whole (incl. work/dl/dl_repo/venv present in tree) | 730 MB (`du -sh`; the copy without work/dl/dl_repo/venv/third_party_derived/.git/big binaries is 713 MB, because the nested venv was copied) |
| Tree size without any venv and without `*.zip` | 181 MB |
| `compare/synfi_run/venv` | 391 MB (nested venv, not this project's code; LICENSE_CHOICE.md says it must be excluded) |
| `handoff/*.zip` (5 earlier bundles, 29 to 33 MB each) | 156 MB in total: bundles inside the bundle |
| `handoff`, `research`, `layout`, `results` | 162 MB, 60 MB, 34 MB, 1.7 MB |
| Screenshots | `dashboard/screens` 13 MB, `docs/report/review/shots` 32 MB |
| Files total | 12,928 (including nested venv) |
| `.md` files | 241 (excluding top-level work/dl/venv trees; 253 counting everything) |
| Files over 3 MB | 20: 9 are in `compare/synfi_run/venv` (ray, numpy, pysolvers; up to 44 MB); 5 are bundle zips in `handoff/` (29 to 33 MB); one UI design-pack zip in `handoff/` (3.8 MB); `dashboard/screens/desktop2.png` 6.8 MB; 4 PNGs in `docs/report/review/shots/` 6.5 to 6.6 MB each. After excluding venv and zips, 5 PNGs remain over 3 MB, which breaks the "files over 3 MB are excluded" rule in CHECKPOINT.md step 5 unless PNGs are also dropped |
| `__pycache__` / `*.egg-info` dirs outside venvs | 7 (CHECKPOINT item 4 wanted `product/` clean; I did not check which ones are in `product/`) |
| Secret patterns (AWS key, private key header, ghp_, github_pat_, xox, sk-, AIza) | 1 file matched, `handoff/CONTINUATION/audit/A3_rules_safety_privacy.md`, and the match is the audit text that lists the patterns, not a secret. `key=value` regex for api_key/secret/password/token with 12+ chars: 0 hits. No `.env`, `id_rsa`, `.pem` files found |
| Email addresses in the tree (excluding venvs) | `claire@yosyshq.com` 150 hits in Yosys-generated logs under `formal/runs/*/model/*.log` (tool banner, a third-party maintainer, not the author); `security@opentitan.org` 4 (public contact in an audit text and a SYNFI file); `random@developer.example.org` 2 (placeholder). No author email found; I did not search for the author's name because I was not given it |
| Licence statements | No `LICENSE` file at the root, by design (`LICENSE_CHOICE.md`, `NOTICE.md`: "all rights reserved by default"; licence UNDECIDED). Third-party licence files present: `compare/synfi_run/src/LICENSE` (Apache-2.0), `real_designs/second/src/LICENSE.apache2`, `real_designs/second/dl_repo/{door,lock2,padlock}/LICENSE`, `third_party_derived/uarchifi_kfrp_fiver/uarchifi_plugin/LICENSE-LGPL-2.1.txt`. `NOTICE.md` lists copied Apache-2.0 designs; `real_designs/second/dl_repo` holds cloned repos (3 LICENSE files) that `NOTICE.md` does not mention by that path |
| Repos with unclear licence | `third_party_derived/` (excluded from my copy per instructions; 120 KB) is the area flagged as an open author decision in CHECKPOINT.md |

## 6. Recommendations (for the integration step; I changed nothing outside `research/c3/ra/`)

1. Update the test count (10 to 30) in `docs/FINAL_STATUS.md`, `docs/dossier/PROJECT_DOSSIER.md` and `docs/report/ONE_PAGE_SUMMARY.md`, and add the product-test count (21) with the `pip install "./product[test]"` step to the README quickstart.
2. README should say that make targets write into the tree and that verdicts are tied to Yosys 0.33.
3. When building the final bundle exclude nested `*/venv/`, `handoff/*.zip` and the 5 large PNGs; the CHECKPOINT rule only names the top-level venv. A clean bundle should come to about 20 to 25 MB (INFERRED from 181 MB minus the 156 MB of zips, a rough figure; not measured).
4. Gate counts are given as "85 gates" (combinational) but the JSON has 93 cells; one sentence defining the counting convention would stop a reviewer from calling it a mismatch.
5. Not done by me: conda-env items (PDR, sby, SPICE, layout), the 32-netlist matrix, SYNFI, numerics audit; those remain "reported, not re-run" in this audit.
