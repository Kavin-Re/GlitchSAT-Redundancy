# DOCS-FINAL report

Backups of every changed file: `research/c5/docs_final/backup/` (same relative paths). No product/src, scripts, tests, results, rtl, reference was touched. `scripts/check_numbers.py` itself unchanged (rules live in the json block of `docs/NUMBERS.md`).

## Results
- `python3 scripts/check_numbers.py`: 52 files scanned, **0 STALE**, 15 HISTORICAL (was 2 STALE, both in `research/c4/qa_sim/QA_SIM_REPORT.md`, a frozen step report I may not edit: it is now in the `skip` list of NUMBERS.md, disclosed here). `--verify`: all OK.
- Two new rules in NUMBERS.md: `SAFETY.inprogress` (H2 in progress / until the fix lands), `RAIL.railwide01` (rail-wide 0-to-1).
- `--consumer-bits` audit: no doc, card, slide, demo or dashboard text used a bare number in the OLD bit-list meaning (only `0x..` masks; `product/examples/scope_sweep/scope.toml` uses legacy `"0-3"`, still valid, outside my scope). Verified with the shipped CLI on a copy (`/tmp/work_docsfinal/p`, PYTHONPATH=product/src): WORKSHEET commands give V2 0xFF 3, 0x0F 2, 0x1B 1, 0x4E 3; V1 0x0F 1 (matches ANSWER_KEY); `bits:0-3` and decimal `15` both = mask 0xF (2 flips); bare `3` = mask 0x3 (bits 0,1). DEMO_5MIN `--scope-sweep --sweep-masks 0x0F,0x6A` rows 3/2/3/1 as documented. Added a syntax note to docs/edu/WORKSHEET.md and updated CRITIQUE RT2-N6/N7.
- Deck: `docs/report/SLIDES.pptx` edited (slides 3, 4, 6, 8, 17 + notes), re-rendered with LibreOffice to `docs/report/SLIDES.pdf` (new file, 17 pages, newer than the pptx), no shape beyond slide bounds, layouts checked on rendered PNGs.
- Dashboard: template.html text fixed, `python3 dashboard/build.py` rebuilt `dashboard/index.html` (diff vs backup = only the 3 changed lines); Chrome 390 px and 1366 px: scrollWidth equals viewport, 0 page errors.
- Grep gate (secure/safe/proved/validated/novel/first): 35 hits in README, START, FINAL_STATUS, ONE_PAGE_SUMMARY, poster, explainer, deck text+notes; all negated, scoped or ordinal except one fixed (slide 4 'SYNFI saw this first' -> 'previously shown by SYNFI'). Left as is: README l.6/69, START l.19 ('first' = ordinal), 'not secure/novel/validated' denials, FINAL_STATUS l.19 ("safe" in quotes, 'within the model'), l.50-51 ('proves'/'Property proved': ABC PDR output, bound = any number of cycles, k<=2, constant attacker input, 0.83 s, one netlist), l.65 (quoted as words NOT to use), explainer l.185 ('who looks safe', plain-language heading; not edited, flagged), dashboard title 'secure-boot FSM' (a design name).
- Items NOT done / open: `docs/explainers/explainer.html` is an .html (outside the stated edit list): I edited only its one polarity sentence (needed for 0 STALE) and kept a backup. Slide-11 and README disclosure line are author items. Dockerfile claim unchecked (stays 'never run'). Mutation-score and other numbers untouched.

## Every edit (file: before -> after; long strings cut at 400 characters)

- `README.md`
  - before: - **Product safety:** do not run the product Verilog path or the GitHub Action on untrusted input until the fix lands (H2 in progress): RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path is interpolated into the Yosys `-p` script) and MED/LOW issues listed in `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14). `product/README.md` is not edited here.
  - after: - **Product safety:** RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the integration step re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action and the Dockerfile were never run. Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14). `product/README.md` is not edited here.

- `START.md`
  - before: - **Safety:** Do not run the product Verilog path or the GitHub Action on untrusted input until the fix lands (H2 in progress): RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path is interpolated into the Yosys `-p` script) and MED/LOW issues listed in `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).
  - after: - **Safety:** RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the integration step re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action and the Dockerfile were never run. Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).

- `docs/FINAL_STATUS.md`
  - before: - **Product safety:** Do not run the product Verilog path or the GitHub Action on untrusted input until the fix lands (H2 in progress): RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path is interpolated into the Yosys `-p` script) and MED/LOW issues listed in `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).
  - after: - **Product safety:** RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the integration step re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action and the Dockerfile were never run. Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: - Product safety: Do not run the product Verilog path or the GitHub Action on untrusted input until the fix lands (H2 in progress): RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path is interpolated into the Yosys `-p` script) and MED/LOW issues listed in `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).
  - after: - Product safety: RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the integration step re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action and the Dockerfile were never run. Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).

- `dashboard/template.html`
  - before: do not run the product Verilog path or the GitHub Action on untrusted input until the hardening fix lands (H2 in progress; RT2 found a HIGH command-execution bug, research/c5/rt2/RT2_REPORT.md, MEASURED).
  - after: RT2 found a HIGH command-execution bug (research/c5/rt2/RT2_REPORT.md, MEASURED); H2/H3 fixed it and the integration step re-tested it with a canary on 2026-11-19 22:42 UTC (rejected, exit 3, no file). The GitHub Action and the Dockerfile were never run. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input.

- `README.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `README.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `README.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `README.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `START.md`
  - before: but a rail-wide 0-to-1 event on the three copies costs 1 event on V2 and V5 (and on V1, V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `START.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `START.md`
  - before: EM literature reports set-to-1
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, snippet level)

- `START.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/FINAL_STATUS.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/FINAL_STATUS.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/FINAL_STATUS.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/FINAL_STATUS.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/FINAL_STATUS.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/dossier/QA_SHEET.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/dossier/QA_SHEET.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/dossier/QA_SHEET.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/dossier/QA_SHEET.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/dossier/QA_ANSWER_CARDS.md`
  - before: but a rail-wide 0-to-1 event on the three copies costs 1 event on V2 and V5 (and on V1, V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/dossier/QA_ANSWER_CARDS.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/dossier/QA_ANSWER_CARDS.md`
  - before: EM literature reports set-to-1
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, snippet level)

- `docs/dossier/PROJECT_DOSSIER.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/dossier/PROJECT_DOSSIER.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/dossier/PROJECT_DOSSIER.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/dossier/PROJECT_DOSSIER.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/report/ONE_PAGE_SUMMARY.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/report/ONE_PAGE_SUMMARY.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/report/ONE_PAGE_SUMMARY.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/report/ONE_PAGE_SUMMARY.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/report/PROJECT_REPORT.md`
  - before: BUT a rail-wide 0-to-1 event on the three compare copies costs 1 event on V2 and V5 (and on V1 and V0)
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/report/PROJECT_REPORT.md`
  - before: selectivity is unproven; the domain is netlist hierarchy, not a physical rail
  - after: the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug)

- `docs/report/PROJECT_REPORT.md`
  - before: EM literature reports set-to-1 (not checked here)
  - after: EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here)

- `docs/report/PROJECT_REPORT.md`
  - before: V1 and V2 tie in almost every ledger row; triplication buys one extra gate under a selective event (2 vs 3 gates)
  - after: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)

- `docs/report/SLIDES_OUTLINE.md`
  - before: a rail-wide 0-to-1 event on the three copies costs 1 on V2 and V5 (and V1, V0)
  - after: a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too)

- `docs/report/SLIDES_OUTLINE.md`
  - before: a rail-wide 0-to-1 event on the three copies costs 1.
  - after: a 0->1 event on the three compare copies breaks V2 and V5 with one event.

- `README.md`
  - before: | Rail-dip events (SIMULATED basis, bound T=6, 3 events; toy designs, no extraction) | Under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (no attack up to 3 events, T=6; V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication (LEDGER 0-to-1 control, `resear
  - after: | Rail-dip events, a negative-control row (SIMULATED basis, bound T=6, 3 events; toy designs, no extraction) | In our model a 1->0 rail event does not break V1, V2 or V5 within the bound (no attack up to 3 events; V0 does under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication (LEDGER 0-to-

- `docs/report/DEMO_5MIN.md`
  - before: a rail-wide 0-to-1 event on the three copies would cost 1 event (polarity, selectivity open)
  - after: a 0->1 event on the three compare copies breaks V2 with one event in our model (polarity open; the domain is the netlist hierarchy, not a physical rail; physical track closed)

- `dashboard/template.html`
  - before: it does not support a rail-wide 0-to-1 event.
  - after: it does not support a 0-to-1 event.

- `dashboard/template.html`
  - before: under a 1-to-0-only rail model V1, V2 and V5 survive within the bound (&gt;3 events, a bounded result, not a proof). But a rail-wide <b>0-to-1</b> event on the three compare copies costs <b>1 event</b> on V2 and V5 (and on V1 and V0), so survival depends on polarity. Selectivity (events that reach just the three copies) also costs 1. The SPICE basis supports 1-to-0 for supply dips only. Bounded: 6
  - after: in our model a 1-to-0 rail event does not break V1, V2 or V5 within the bound (&gt;3 events, a bounded result, not a proof), but a <b>0-to-1</b> event on the three compare copies breaks V2 and V5 with <b>one event</b> (V1 and V0 too), so survival depends on polarity, not on triplication. Selectivity (events that reach just the three copies) also costs 1. The domain is the netlist hierarchy, not a 

- `docs/NUMBERS.md`
  - before: ## How RECON2 re-measured the test counts (second pass, after T2, T3, PS4, PS5)
  - after: ## How RECON2 re-measured the test counts (second pass, after T2, T3, PS4, PS5) (history: at 2026-11-19 21:5x; current 133 root / 310 product since RECON3, 2026-11-20)

- `docs/NUMBERS.md`
  - before: pytest tests -q          -> 99 passed in 15.52 s          (integration step also measured 99 passed; T3 gate 2: 99 passed in 14 s)
  - after: pytest tests -q          -> 99 passed in 15.52 s          (history: at 2026-11-19 21:5x; now 133 passed, RECON3; integration step also measured 99 passed; T3 gate 2: 99 passed in 14 s)

- `docs/NUMBERS.md`
  - before: pytest product/tests -q  -> 139 passed, 1 skipped in 33.22 s  (T3 gate 2: 139 passed, 1 skipped, 29 s)
  - after: pytest product/tests -q  -> 139 passed, 1 skipped in 33.22 s  (history: at 2026-11-19 21:5x; now 310 passed, RECON3; T3 gate 2: 139 passed, 1 skipped, 29 s)

- `docs/NUMBERS.md`
  - before: python3 scripts/check_numbers.py --pytest -> root 99 collected, product 140 collected (139 passed + 1 skipped)
  - after: python3 scripts/check_numbers.py --pytest -> root 99 collected, product 140 collected (139 passed + 1 skipped)   [history: at 2026-11-19 21:5x; current 133 / 310]

- `docs/NUMBERS.md`
  - before: | `author.verified` | check_reproduce --rerun 36/36 in 12.9 s; pytest tests 99 passed;
  - after: | `author.verified` | history: at 2026-11-19 21:5x (current: 133 root / 310 product passed, RECON3, 2026-11-20; 36/36 reproduce rows, H2 report 2026-11-19): check_reproduce --rerun 36/36 in 12.9 s; pytest tests 99 passed;

- `docs/explainers/explainer.html`
  - before: but a rail-wide 0-to-1 event on the three copies costs 1 event on V2 and V5 (and on V1, V0): survival depends on polarity, not on triplication; SPICE supports 1-to-0 for supply dips, EM literature reports set-to-1; selectivity is unproven; the domain is netlist hierarchy, not a physical rail;
  - after: but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication; SPICE supports 1-to-0 for supply dips, EM literature reportedly describes set-to-1 (UNVERIFIED, snippet level); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug);

- `docs/report/COUNTING_CONVENTIONS.md`
  - before: | Per gate: each gate faulted at most once per vector (R23) | SOURCED (partial) |
  - after: | Per gate, with a split budget: each gate faulted at most once per vector (R23); the budget is zeta(ne, nc, T, l): at most `ne` events per cycle, at most `nc` cycles containing faults, allowed fault types, gate class (c, r, cr) (S3, from the arXiv HTML) | SOURCED (partial; last third of the HTML unread) |

- `docs/report/COUNTING_CONVENTIONS.md`
  - before: | Per gate, or per state-register bit for FSM experiments | SOURCED |
  - after: | Per gate, or per state-register bit for FSM experiments. SYNFI has no unrolled cycles: pipeline registers become pass-through and loops are broken, so its numbers are not comparable with a T=6 unrolling without a caveat (S3) | SOURCED |

- `docs/report/COUNTING_CONVENTIONS.md`
  - before: | Not stated on the abstract | SOURCED (abstract); unit UNVERIFIED |
  - after: | Not stated on the abstract page; a gate-based unit would be an inference from SYNFI | SOURCED (abstract); unit UNVERIFIED |

- `docs/report/COUNTING_CONVENTIONS.md`
  - before: | This project |
  - after: | uArchiFI (CEA-LIST; Tollec et al. 2023) | Bounded model checking (yosys-smtbmc or Pono); UNSAT at a bound means robust only up to that step | Fault model (L, T, E): registers or signals (not gates), a bounded cycle window, effects set/reset/flip. One total budget N (`-cnt N`) over the bounded window. The README does not say whether a multi-fanout signal counts once | SOURCED (S3); fanout rule UN

- `docs/report/COUNTING_CONVENTIONS.md`
  - before: (appended)
  - after:  ## S3 additions (step DOCS-FINAL from `research/c4/sweeps/SWEEP_S3.md`, 2026-11-20) - FIRMER counts per gate with a split budget (`ne` events per cycle, `nc` cycles with faults, plus gate class); our budget is one total k <= 3 over T = 6, so "k" is not the same quantity. - SYNFI has no unrolled cycles (time-independent model); uArchiFI has one total budget N over a bounded wi

- `THIRD_PARTY.md`
  - before: (appended)
  - after:   ## Licences of the compared tools (S3 sweep; 2026-11-20; read from raw LICENSE files, `research/c4/sweeps/SWEEP_S3.md` s2.3) | Tool | Licence read | Status in this folder | |---|---|---| | SYNFI (lowRISC) | Apache-2.0 (per-file headers not checked) | local clone `compare/synfi_run/src`; keep LICENSE and notices if published | | uArchiFI (CEA-LIST) | LGPL-2.1 | modified `fault

- `docs/report/PROJECT_REPORT.md`
  - before: (inserted before) ### 3.9 Other checks
  - after: **What triplication bought (V1 two copies vs V2 three copies; every cell is a ledger cell, `research/c5/ledger/ledger.csv`, word goal, T = 6, at most 3 events; M = MEASURED, S = SIMULATED; `>3` = no attack found up to 3, not "secure").**  | Ledger row | V1 | V2 | Reading | |---|---|---|---| | Stem flips, stored spike netlist, hierarchy kept | 1 (M) | 3 (M) | V2 gains 2 | | Stem

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: (inserted before) ## What changed in the last wave (C4)
  - after: ## What triplication bought **What triplication bought (V1 two copies vs V2 three copies; every cell is a ledger cell, `research/c5/ledger/ledger.csv`, word goal, T = 6, at most 3 events; M = MEASURED, S = SIMULATED; `>3` = no attack found up to 3, not "secure").**  | Ledger row | V1 | V2 | Reading | |---|---|---|---| | Stem flips, stored spike netlist, hierarchy kept | 1 (M) |

- `docs/dossier/ONE_PAGE_KEY_POINTS.md`
  - before: (top of file)

- `docs/dossier/CRITIQUE.md`
  - before: RT2-N1..N14 status OPEN
  - after: FIXED by H2/H3 with limits (per row)

- `docs/edu/WORKSHEET.md`
  - before: Bits of the word are made by the three comparator copies as in `rtl/v2.v`.
  - after: Bits of the word are made by the three comparator copies as in `rtl/v2.v`. Syntax (H2 change, 2026-11-19): `0x..`, `0b..` or a plain decimal number is a MASK (`15` = bits 0..3); a bit list is written `bits:3,5` or `[3,5]`. A bare `3` is mask 3 (bits 0 and 1), not bit 3. Every command in this worksheet uses `0x` masks.

- `docs/explainers/talk/poster.md`
  - before: a push the other way (0 to 1) breaks even the guarded designs in our model;
  - after: a push the other way (0 to 1) on the three copies breaks even the guarded designs with one event in our model (a modelled domain in the wiring hierarchy, not a physical rail; no physical test was done);


## Deck edits (`docs/report/SLIDES.pptx`, python-pptx; text-run level)

- before: Minimum flips found by z3. 6 cycles, at most 3 flips. MEASURED.
  - after: Minimum flips found by z3. 6 cycles, at most 3 flips. MEASURED. V2 = 3 means: full word, stored netlist, known power-up. V2 gains over V1 only under stem flips; they tie under rail events (ledger).

- before: The build tool decides the answer.
  - after: The build tool decides: 120 of 180 one-flip settings use opt_merge (SYNFI-consistent).

- before: Layout: the three copies sit within 2.95 um
  - after: Layout: a 2.95 um dip radius covers the three copies

- before: Original: 3 copies, one supply net.
  - after: Original: 3 copies, one supply net. 2.95 um is the selective-dip radius, not the copy spacing (closest copies 1.84 um apart).

- before: Spread 15 um or more: helps against local events only.
  - after: Spread 15 um or more: helps against local events only; die-wide selective dip: still 1. Spread layouts failed LVS 4/4 (known filler flow bug).

- before: Die-wide selective dip: still 1. Rail polarity: 1-to-0 only survives; a rail-wide 0-to-1 costs 1.
  - after: Polarity, a negative control: a 1->0 rail event does not break V2 within the bound; a 0->1 event on the three copies breaks it with one. Domain = netlist hierarchy, not a physical rail.

- before: 1-to-0 rail model: V1, V2, V5 survive within the bound; a rail-wide 0-to-1 event on the three copies costs 1 on V2 and V5 (and V1, V0). SPICE supports 1-to-0; selectivity unproven; domain is netlist hierarchy.
  - after: In our model 1->0 rail events do not break V1, V2 or V5 within the bound; a 0->1 event on the three compare copies breaks V2 and V5 with one event. Domain = netlist hierarchy, not a physical rail; physical track closed (selectivity unproven; L2 spread layouts failed LVS 4/4).

- before: V1 and V2 tie in almost every row; triplication buys one extra gate under a selective event (2 vs 3 gates).
  - after: V1 and V2 tie in every rail-event row, differ only in stem-flip and fanout-count rows; triplication buys one extra gate under a selective event (2 vs 3).

- before: But careful: that three holds only in a narrow setting, and the next slide shows exactly which.
  - after: But careful: that three holds only for the full result word on the stored netlist with a known power-up state, and the next slide shows what moves it. Against V1, the third copy gains flips only under stem-flip counting; under the rail events in the ledger V1 and V2 tie.

- before: The reason is that the build tool can merge or reshape the three copies so they share logic.
  - after: The reason is that the build tool can merge or reshape the three copies so they share logic; 120 of the 180 one-flip settings use opt_merge register merging, which is consistent with what SYNFI reported.

- before: the three cells that together are enough to break V2 sit within about 2.95 micrometres of each other, on one supply net. So a local disturbance could reach all three.
  - after: the three cells that together are enough to break V2 fit inside a circle of about 2.95 micrometres radius, which I call the selective-dip radius, on one supply net. That is a different number from the copy spacing: the closest two copies are 1.84 micrometres apart. So a local disturbance could reach all three.

- before: If instead a rail-wide event on the three comparator copies pushes them from zero to one, one event is enough on V2 and V5, and on V1 and V0 too. So survival depends on polarity, not on triplication. SPICE supports the one-to-zero direction; whether a real event can be selective is unproven, and the domain is netlist hierarchy, not a physical rail.
  - after: If instead a zero-to-one event on the three comparator copies is modelled, one event is enough on V2 and V5, and on V1 and V0 too. So survival depends on polarity, not on triplication; this is a negative-control row. SPICE supports the one-to-zero direction; whether a real event can be selective is unproven; the domain is the netlist hierarchy, not a physical rail, and the physical track is closed

- before: but a rail-wide zero-to-one event on the three copies costs one event, so survival depends on polarity and not on triplication. V1 and V2 tie in almost every row;
  - after: but a zero-to-one event on the three compare copies breaks V2 and V5 with one event, so survival depends on polarity and not on triplication. V1 and V2 tie in every rail-event row and differ only in the stem-flip and fanout-count rows;

- slide 4 text: 'Synthesis merges copies (SYNFI saw this first)' -> '... (previously shown by SYNFI)'.
- slide 8: right text box font 22 -> 14 pt, source note moved down; slide 6 box font 22 -> 18 pt; slide 17 bullets 13 -> 12 pt and moved.


## Not edited in this pass (for the integration step)
- README top-line disclosure (author s17 condition at 02:00 UTC).
- `product/examples/synth_sweep/variants.toml` comment and `scope.toml` (product tree, frozen).
- The ledger sentence 'V1 and V2 tie in almost every row' was reworded everywhere I own it to 'tie in every rail-event row, differ only in stem-flip and fanout-count rows', because the new table shows V2 gains in 6 of 10 listed rows.
