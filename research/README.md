# Research archive

This folder is the working archive of the study: one folder per experiment, review or fix pass, grouped by the round in which it was done (`c1` is the first round, `c6` the last). The claims of the project live in [`README.md`](../README.md), [`docs/FINAL_STATUS.md`](../docs/FINAL_STATUS.md) and [`docs/NUMBERS.md`](../docs/NUMBERS.md); this archive holds the reports, scripts and raw data those claims point to. Folder names are short codenames. [`docs/GLOSSARY.md`](../docs/GLOSSARY.md) gives a plain description of every codename.

The reports are working notes: some describe results that a later report corrected. When two reports disagree, the later round and `docs/FINAL_STATUS.md` win.

## Where the main results are

| Result | Folder |
|---|---|
| Scope matrix: how the goal, fault sites and power-up state move the minimum (360 cells) | [`c2/b2_scope/`](c2/b2_scope/B2_REPORT.md) |
| Synthesis-variance matrix: 864 configurations of V0, V1, V2 | [`c2/e2_variance/`](c2/e2_variance/E2_REPORT.md) |
| Which of the 8 result bits the consumer reads (consumer masks) | [`c3/m1/`](c3/m1/M1_REPORT.md) |
| Counting rule: one flip per net vs. one per reader (6 of 32 vs. 32 of 32) | [`c3/r22/`](c3/r22/R22_REPORT.md), [`c3/rep/`](c3/rep/REP_REPORT.md) |
| Why V2 needs only 2 flips on one synthesis (state encoding) | [`c6/p01/`](c6/p01/P01_REPORT.md) |
| Supply-dip event models | [`c4/b3/`](c4/b3/B3_REPORT.md) |
| Layout geometry of the compare copies | [`c4/layout/`](c4/layout/LAYOUT_REPORT.md) |
| Structural predictor: pre-registration, held-out test, audit | [`c4/pre/`](c4/pre/PRE_REPORT.md), [`c4/test/`](c4/test/TEST_REPORT.md), [`c4/ver/`](c4/ver/VER_REPORT.md) |
| Brute-force re-check without z3 | [`c5/anchor/`](c5/anchor/ANCHOR_REPORT.md) |
| Coding-theory view of the state words | [`c6/p11/`](c6/p11/P11_REPORT.md), [`c6/p13/`](c6/p13/P13_REPORT.md) |
| Runs of third-party tools (uArchiFI, k-FRP, FIVER) | [`c5/run2/`](c5/run2/RUN2_REPORT.md) |
| Prior-art survey | [`c2/r10_prior_art/`](c2/r10_prior_art/R10_PRIOR_ART_FULL.md) |

## What each round contains

- **`c1`**: first notes on users' needs and the tool landscape, and a first circuit-level (SPICE) look.
- **`c2`**: the core experiments (fault models `b1`, scope `b2_scope`, time-varying input `e1`, synthesis variance `e2`, circuit-level `el1`/`el2`), the first reviews (`reviews/`, `devils_advocate/`), the first fix pass `f1`, the first build of the installable CLI `ps`, and the prior-art survey `r10`.
- **`c3`**: deeper experiments (consumer masks `m1`, larger designs `r20`, countermeasure designs `v456`, counting rule `r22`/`rep`, faster encoding `r27`), robustness work (hardening `h1`, red team `rt`, mutation testing `mt`/`t2`), reviews (`bc`, `da2`, `ds`, `fp`, `ra`, `se`) and the first rounds of building and reader-testing the browser pages (`w2` to `w6`, `wp` to `wp5`).
- **`c4`**: supply-dip models (`b3`), layout (`layout`, `l2`), the structural predictor (`pre`, `test`, `ver`), the CLI scope options (`ps4`, `ps5`), the faster solver encoding applied (`t3`), dossier and integration passes (`d2`, `d3`, `fd`), number reconciliation (`recon`, `recon2`), the classroom kit (`edu`, `edu2`), a simulated question round (`qa_sim`), a review panel (`review_panel`) and literature sweeps (`sweeps`).
- **`c5`**: re-checks (`anchor`, `ledger`, `da3`), hardening of the CLI (`h2` to `h5`) and second red-team passes (`rt2`, `rt3`), the last CLI round (`ps6`), third-party tool runs (`run2`), bundle rehearsal (`bundle`), documentation and review passes (`docs_final`, `final_review`, `fix2`, `fix3`, `bc2`, `recon3` to `recon5`) and the last page rounds (`w7`, `w8`, `wp6`, `wp7`).
- **`c6`**: the encoding root cause (`p01`), the engine text fix (`p08`), coding-theory experiments (`p11` to `p14`, `p18`, `comms`), the interactive pages (`p21` replay, `p24` wall, `p40` dial), a fresh review and its plan (`fresh_eyes`) and the final integration and count passes (`int`, `int2a`, `int2b`, `recon6`).

Labels used in the reports (MEASURED, SIMULATED, SOURCED, UNVERIFIED and others) are defined in [`docs/EVIDENCE_LABELS.md`](../docs/EVIDENCE_LABELS.md). Paths such as `/tmp/...` inside the reports name the scratch copies the runs were made in; they are not part of this repository.
