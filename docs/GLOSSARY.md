# Glossary of codenames

The reports under `research/` and the deeper documents in `docs/` refer to experiments, reviews and fix passes by short
codenames. This page maps each codename to a plain description and to the folder that holds its report, so that every
number in the front-door documents ([`README.md`](../README.md), [`START.md`](../START.md)) can still be traced.

Paths are relative to the repository root.

## Codenames

| Codename | What it is | Where |
|---|---|---|
| `glitchsat` / `faultbound-wt` | The installable GlitchSAT CLI in `product/`; `faultbound-wt` is its older command name, kept as an alias; the Python module is `faultbound_wt` | `product/` |
| `scripts/glitchsat.py` | The reference GlitchSAT engine behind the reproduce table (`make reproduce`) | `scripts/` |
| GlitchSAT Studio | The desktop app (local web page) that runs the engine or shows recorded results | `tools/studio/` |
| ANCHOR | Brute-force (z3-free) re-check of the V2 headline rows and rail rows | `research/c5/anchor/` |
| apt 0.33 / conda 0.38 | The two Yosys builds used: Ubuntu's apt package (0.33) and a conda package (0.38) | `research/c2/e2_variance/` |
| B1 | Fault-model pack: minimum cost under 17 alternative fault models | `research/c2/b1_faultmodels/` |
| B2 | Scope-sensitivity matrix (360 cells): goal, input sites, power-up, netlist | `research/c2/b2_scope/` |
| B3 | Rail-dip and wrong-time-capture event models | `research/c4/b3/`, inputs in `research/c4/b3_inputs/` |
| BC, BC2 | Critical reviews ("critical review", pre-mortem), rounds 1 and 2 | `research/c3/bc/`, `research/c5/bc2/` |
| BP | "Big picture" review of where the project could aim | `research/c4/bp/` |
| BUNDLE | Rehearsal of packaging the repository into zip bundles | `research/c5/bundle/`, `docs/BUNDLE.md` |
| c1 to c6 | Successive rounds of work; the folder number is the round in which an item was done | `research/c1/` to `research/c6/` |
| REVIEW PANEL (W1 to W3) | Panel-style review of whether the project is defensible | `research/c4/review_panel/` |
| CT, CT-1 to CT-15 | Claim-test review: numbered findings where a headline claim was tested against a changed assumption (CT-1: the accept flag `boot_ok` falls to 1 flip) | `docs/dossier/CRITIQUE.md` |
| D2, D3 | Dossier writing pass; consistency and integration pass | `research/c4/d2/`, `research/c4/d3/` |
| DA, DA2, DA3 | Devil's-advocate reviews, rounds 1 to 3 (DA measured the 6-of-32 counting-rule result; DA3 audited the predictor baselines) | `research/c2/devils_advocate/`, `research/c3/da2/`, `research/c5/da3/` |
| DASH, DASH2 | Dashboard data and text refreshes | `research/c4/dash/`, `research/c5/dash2/` |
| DOCS-FINAL, FINAL REVIEW | Last documentation pass and last overall review | `research/c5/docs_final/`, `research/c5/final_review/` |
| DS | Structured debate; source of the 10 hardest review questions (D1 to D10) | `research/c3/ds/` |
| E1 | Attacker input free on every cycle instead of constant | `research/c2/e1_timevarying/` |
| E2 | Synthesis-variance matrix: 864 configurations of V0/V1/V2 | `research/c2/e2_variance/` |
| EDU, EDU2 | Classroom kit and its move to the packaged CLI | `research/c4/edu/`, `research/c4/edu2/`, `docs/edu/` |
| EL1 | Circuit-level (ngspice, sky130) simulation of supply dips and clock runts | `research/c2/el1_spice/` |
| EL2 | Electronics-level view; solver run on sky130-mapped netlists | `research/c2/el2_engineering/` |
| F1, F2, FD, FIX2, FIX3 | Fix passes applying review findings to documents and code | `research/c2/f1/`, `research/c3/f2/`, `research/c4/fd/`, `research/c5/fix2/`, `research/c5/fix3/` |
| FP | First-principles rebuild and the 30 Socratic questions | `research/c3/fp/` |
| H1 to H5 | Hardening passes on the solver and CLI: H1 malformed-netlist errors, H2 and H3 the Yosys command-injection fix, H4 the `--cycles` cap, H5 Yosys >= 0.38 `$scopeinfo` cells | `research/c3/h1/`, `research/c5/h2/` to `research/c5/h5/` |
| IN, INT, INT2a, INT2b | Integration with other fault-injection tools (IN); document integration and wording passes (INT*) | `research/c2/in/`, `research/c6/int/`, `research/c6/int2a/`, `research/c6/int2b/` |
| L2 | Spreading the three V2 compare copies in a real OpenROAD placement | `research/c4/l2/`, inputs in `research/c4/l2_inputs/` |
| LAYOUT | Layout geometry of the compare copies (distances, radius) | `research/c4/layout/`, `layout/` |
| LEDGER | Redundancy-survival ledger: one table of what triplication bought under each fault rule | `research/c5/ledger/` |
| M1, M1b | Consumer-mask study (which of the 8 bits the consumer checks) and its two-engine recheck | `research/c3/m1/`, `research/c4/m1b/` |
| MT, T2 | Mutation testing of the test suites; tests added for surviving mutants | `research/c3/mt/`, `research/c3/t2/` |
| N1 to N14 (RT2-N1 ...) | Numbered findings of the second red-team pass | `research/c5/rt2/RT2_REPORT.md`, `docs/dossier/CRITIQUE.md` |
| P01 (P01a) | Why V2 needs only 2 flips on the apt 0.33 synthesis | `research/c6/p01/`, `docs/report/WHY_TWO_FLIPS.md` |
| P08 | Regression test pinning the 2-flip V2 witness | `research/c6/p08/`, `tests/test_p08.py` |
| P11 | Code distance as fault budget (19 codebooks) | `research/c6/p11/` |
| P12 | Random-flip "waterfall" curves | `research/c6/p12/` |
| P13 (P13a) | Wording of the coding-theory chapter | `research/c6/p13/`, `docs/comms/CODING_VIEW.md` |
| P14 | Burst events compared with random flips | `research/c6/p14/` |
| P18 | Error-correcting decoder variants of V2 (`rtl/v2c.v`, `rtl/v2_secded.v`), pre-registered | `research/c6/p18/`, `research/c6/comms/P18_PREREG.md` |
| P21, P24, P40 | Interactive pages: Solver Replay, the 264-configuration wall, the Verdict Dial | `research/c6/p21/`, `research/c6/p24/`, `research/c6/p40/`, `docs/explainers/` |
| PRE, TEST, VER | Structural predictor: pre-registration, held-out test, adversarial audit | `research/c4/pre/`, `research/c4/test/`, `research/c4/ver/` |
| PRES | Presentation set (slides, demo scripts) | `research/c4/pres/`, `docs/report/` |
| PS, PS2 to PS6 | Build and hardening rounds of the packaged CLI (now the `glitchsat` command; older name `faultbound-wt`); "Face B" means this tool as opposed to the study | `research/c2/ps/`, `research/c3/ps2/`, `research/c3/ps3/`, `research/c4/ps4/`, `research/c4/ps5/`, `research/c5/ps6/`, `product/` |
| R10, R23 | Prior-art survey and its refresh | `research/c2/r10_prior_art/`, `research/c3/r23/`, `docs/PRIOR_ART.md` |
| R20 | Larger benchmark designs (scaling check) | `research/c3/r20/` |
| R21 | Survey of fault-injection countermeasures in real designs | `research/c3/r21/` |
| R22 | Counting-rule literature review (one flip per net vs. per reader) | `research/c3/r22/` |
| R24 | Adoption, education and positioning notes | `research/c3/r24/` |
| R27, T3 | Faster at-most-k encoding (sequential counter): proposal (R27) and application to the solver (T3) | `research/c3/r27/`, `research/c4/t3/` |
| RA | Reproducibility audit done as an outside reviewer | `research/c3/ra/` |
| RECON to RECON6 | Passes reconciling headline numbers across documents | `research/c4/recon/`, `research/c4/recon2/`, `research/c5/recon3/` to `recon5/`, `research/c6/recon6/`, `docs/NUMBERS.md` |
| REP | Independent replication of the 6-of-32 vs 32-of-32 counting-rule result | `research/c3/rep/` |
| RT, RT2, RT3 | Red-team (security and robustness) passes on the tools; RT2 found the command-injection bug, RT3 re-attacked the fix | `research/c3/rt/`, `research/c5/rt2/`, `research/c5/rt3/` |
| RUN1, RUN2 | Runs of third-party tools on the toy designs (RUN2: uArchiFI, k-FRP, FIVER; RUN1 keeps logs only) | `research/c2/run1/`, `research/c5/run2/` |
| SE | Security, ethics and dual-use review | `research/c3/se/` |
| spike | The first exploratory prototype. Its netlists are the "stored" reference netlists | `reference/spike_netlists/` |
| SWEEP S1 | Periodic literature sweep | `research/c4/sweeps/` |
| the integration step | The coordinating work stream that integrated results and re-ran spot checks | (no single folder; see `docs/FINAL_STATUS.md`) |
| V2e, V2c, V2_SECDED | V2 variants: re-encoded armed state `0xA5`; syndrome-checking consumer; SECDED decoder | `rtl/` |
| V2m, V2s, V3 | Exploratory variants: V2m per-bit 2-of-3 vote, V2s one shared voter (both in M1), V3 a hardening attempt (in B2); not headline results | `research/c3/m1/`, `research/c2/b2_scope/` |
| V4, V4b, V5, V6 (V456) | Countermeasure example designs built and measured | `research/c3/v456/` |
| QA (QA SIM) | Simulated question round: 48 questions from four simulated reviewers | `research/c4/qa_sim/`, `docs/dossier/QA_SHEET.md` |
| W1 to W8, WP to WP7 | Rounds of building and reader-testing the explainer pages | `docs/explainers/dev/W*_REPORT.md`, `research/c3/w*/`, `research/c3/wp*/`, `research/c5/w7/`, `research/c5/w8/`, `research/c5/wp6/`, `research/c5/wp7/` |

## Terms

| Term | Meaning |
|---|---|
| flip, fault | A modelled one-cycle inversion of one gate output or one flip-flop output (Q). Not a physical glitch. |
| k | The fault budget: the maximum number of flips allowed in one run. |
| T, N, cycles | The number of clock cycles the netlist is unrolled for (6 in the headline rows). |
| stem, branch | A net's driver output is the stem; each gate input it feeds is a branch. The headline rule counts one flip of a stem as one fault ("stem = 1"). The "fanout" rule counts it once per branch. |
| word goal, `boot_ok` goal | Attack goal: the 8-bit `boot_word` equals the accept value `0x96`, or the 1-bit accept flag `boot_ok` is 1. |
| consumer, mask | The logic that reads the result word. A mask says which of the 8 bits it actually checks. |
| stored netlist, spike netlist | The gate-level netlists in `reference/spike_netlists/`. |
| plain, opt | The two synthesis flows in `scripts/synth.sh`. |
| scope cell | One combination of goal, fault sites, power-up assumption and netlist in the scope matrix (B2). |
| NO_ATTACK_UP_TO_BOUND | No attack exists with at most k flips within the given cycles. Not a proof beyond the bound. |
| MEASURED, SIMULATED, ESTIMATED, ILLUSTRATIVE, UNVERIFIED | Evidence labels, defined in [`EVIDENCE_LABELS.md`](EVIDENCE_LABELS.md). |
| SOURCED, REPORTED | Used in some reports: taken from a cited paper (SOURCED), or reported by one work stream and not re-run (REPORTED). |
| PDR, BMC | Property-directed reachability (unbounded proof engine in ABC); bounded model checking. |
