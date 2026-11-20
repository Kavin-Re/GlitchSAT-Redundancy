# FIX2 report: front-door honesty pass

Backups of every changed file: `research/c5/fix2/backup/` (path separators replaced by `__`). Checks ran on a copy (/tmp/work_fix2/copy2), not in the tree; no make was run.

Inputs absent at writing: `research/c5/anchor/RAIL_RECONCILIATION.md` (dir empty) and `research/c5/ledger/LEDGER_REPORT.md` (dir empty). So the rail statement is my own from B3 (V1/V2/V5 >3 under whole-rail/half-design; dip_subset 1, 3 gates) and the 0->1 control is marked pending. If either file appears, update the rail row.

## Results
- README.md: 61 lines (cap 70); plain 'What this is' + explainer link now above every table; rail row reworded (polarity, V1 too, selective = 1, control pending); SYNFI-first framing; 'which numbers rest on what' section.
- New file docs/report/COUNTING_CONVENTIONS.md (VerFI, VERICA, FIRMER, SYNFI, FIVER, ours; sampled vs bound, per-gate vs stem; UNVERIFIED where the sweeps do not say). Copy in research/c5/fix2/.
- FINAL_STATUS: first-person 'I re-ran'/'I ran it' replaced by 'the lead re-ran (RUN_LOG entry 72)'; 6/10 panel score removed from line 13 (labelled not evidence); z3-alone vs independent-anchor section added.
- Slides: slides 4, 6, 13 edited and re-rendered with LibreOffice (checked images: no overflow; slide 9 unchanged and renders fine; its numbers 99/139/72.5% are current). Speaker-notes 'I re-synthesise' / 'I ran' reworded.
- explainer.html had no rail-dip or SYNFI evidence line; I added ONE `<li>` in the 'Sources and caveats' list (no layout change). 'What this project is' text left unchanged (README copies it).
- NUMBERS.md: rows FIX2.rail.v1 and FIX2.synfi. check_numbers on copy: 6 STALE, all in research/c4/viva/VIVA_SIM_REPORT.md (pre-existing, not mine); none introduced.
- Not edited / residual: other first-person 'I' in owner-voice scripts (VIVA_SHEET, VIVA_ANSWER_CARDS, AI_USE_DISCLOSURE fill-in slots) are owner placeholders and left; VIVA_ANSWER_CARDS E1-8/E2-6 opt_merge cards not SYNFI-reframed; slides 7/8 rail text not reworded (no rail-attack claim there); a dedicated slide for the counting table was not added (table lives in the docs file, linked from slide 13).

## Every edit (file, before, after)

### README.md
- before: `# Project (working title TBD) / `
- after: `# Project (working title TBD) /  / ## What this is (plain words; same text as the explainer, `docs/wow/explainer.html`) / - **Built:** a computer check that finds the fewest modelled glitches (bit flips) that fool a toy lock design with redundant guard copies. / - **Found:** how many it takes depends on exactly how the lock is wired, how it is built by synthesis, and how you count (1, 2 or 3 flips for the same design). / - **Not done:** nothing physical was tested; no novelty claim. Open `docs/wow/explainer.html` first (5 minutes, no jargon). / `

### README.md
- before: `| V2 under rail-wide, half-design or cone supply dips (SIMULATED basis) | no attack up to 3 events; **1 event if one dip may choose its gates** (3 gates; selectivity open) | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |`
- after: `| 1-to-0 supply-dip events (SIMULATED basis; a dip only pulls high gates low), bound T=6, 3 events | No rail attack (>3) under whole-rail or half-design events for **V1, V2 and V5 alike**: a polarity result, not a benefit of triplication. A SELECTIVE event reaching just the three copies costs **1** on V2 (3 gates; selectivity open). 0-to-1 control: **pending** (LEDGER, `research/c5/ledger/`) | `research/c4/b3/B3_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md` |`

### README.md
- before: `- **No novelty claim**: nothing established as new.`
- after: `- **Synthesis dependence is not new:** Previously shown by SYNFI (arXiv 2205.04775, SOURCED): faults needed dropped 3->2 after Yosys FSM recoding and 4->2 after register merging; `set_dont_touch` restored 4. Our E2 replicates the effect on a toy design across 864 synthesis configs and adds a keep-attribute axis (`(* keep *)` changed no verdict). Counting conventions of other tools: `docs/report/COUNTING_CONVENTIONS.md`. / - **No novelty claim**: nothing established as new.`

### README.md
- before: `## Counting rule / `
- after: `## Which numbers rest on what (MEASURED; sources in `docs/FINAL_STATUS.md`) / - **Independent anchor:** the 36 reproduce rows (second simulator, `validation/VALIDATION.md`); M1's 255 consumer masks (brute force, T=4, k<=2, 255 of 255 agree). / - **z3 alone, no second engine:** the B3 rail-dip rows for V2, V5 and apt-synthesised netlists (brute force covered only V0 and V1 at T<=4, k<=2). Brute-force anchors for these are being added (agent ANCHOR, in progress): treat the rail rows as single-engine until then. /  / ## Counting rule / `

### START.md
- before: `- A supply dip over a whole rail or cone does not break V2 within 3 modelled events, but one dip that could choose its gates would (3 gates); whether a real dip can is open (B3, LAYOUT; r = 2.95 um, one supply net, no extraction).`
- after: `- Supply dips (1-to-0, SIMULATED basis): whole-rail and half-design events show no attack (>3) on V1, V2 or V5 alike, a polarity result and not a benefit of triplication; one SELECTIVE dip reaching just the three copies would cost 1 on V2 (3 gates); whether a real dip can select is open; the 0-to-1 control is pending (LEDGER). B3 rows for V2 rest on z3 alone (brute-force anchors in progress). B3, LAYOUT; r = 2.95 um, one supply net, no extraction.`

### START.md
- before: `| Number depends on synthesis (864 configs) | `research/c2/e2_variance/E2_REPORT.md` |`
- after: `| Number depends on synthesis (864 configs; previously shown by SYNFI, 3->2 and 4->2; our E2 replicates it on a toy design) | `research/c2/e2_variance/E2_REPORT.md` |`

### docs/FINAL_STATUS.md

### docs/FINAL_STATUS.md
- before: `(MEASURED; I re-ran the V2 k=2 case: PASS in 0.83 s)`
- after: `(MEASURED; the lead re-ran the V2 k=2 case, RUN_LOG entry 72: PASS in 0.83 s)`

### docs/FINAL_STATUS.md
- before: `and the project's solver agrees on that netlist (I ran it).`
- after: `and the project's solver agrees on that netlist (the lead ran it, RUN_LOG entry 72).`

### docs/FINAL_STATUS.md
- before: `SYNFI already studies and measures synthesis dependence (Yosys re-synthesis cut the needed faults from 3 to 2)`
- after: `SYNFI already studies and measures synthesis dependence (previously shown by SYNFI: faults needed dropped 3->2 after FSM recoding and 4->2 after register merging; `set_dont_touch` restored 4; our E2 replicates the effect on a toy design across 864 synthesis configs and a keep-attribute axis)`

### docs/FINAL_STATUS.md
- before: `## Scope of every V2 statement`
- after: `## Which headline numbers rest on what (added by FIX2, 2026-11-19) / - **Independent anchors (MEASURED):** the 36 reproduce rows re-checked with the independent simulator (`validation/VALIDATION.md`); M1's 255 consumer masks (brute force at T=4, k<=2: 255 of 255 agree, `research/c3/m1/M1_REPORT.md`); B3 rail rows for V0 and V1 only (T<=4, k<=2). / - **z3 alone (single engine):** B3 rail-dip rows for V2, V5 and apt-synthesised netlists (T=6); one encoding bug would move every "survives". ANCHOR is adding brute-force anchors (in progress, not finished at this writing). / - **Rail-d`

### docs/FINAL_STATUS.md
- before: `- **Rail dip and wrong-time capture** (B3, SIMULATED basis, bounded T=6, 3 events): whole-rail, half-hierarchy, union and fanout-cone dips give no attack for V2 and V5;`
- after: `- **Rail dip and wrong-time capture** (B3, SIMULATED basis, bounded T=6, 3 events; polarity result, not a benefit of triplication: V1 also shows none under whole-rail and half-design 1-to-0 events; 0-to-1 control pending, LEDGER; V2 rows rest on z3 alone): whole-rail, half-hierarchy, union and fanout-cone dips give no attack for V2 and V5;`

### docs/report/ONE_PAGE_SUMMARY.md
- before: `| Synthesis merges the copies (opt_merge) | **1** | MEASURED (edu agent) |`
- after: `| Synthesis merges the copies (opt_merge; effect previously shown by SYNFI, 3->2 and 4->2; our E2 replicates it on a toy design) | **1** | MEASURED (edu agent) |`

### docs/report/ONE_PAGE_SUMMARY.md
- before: `- Rail-dip model (SIMULATED, B3): V2 has no attack up to 3 events for whole-rail, half-design or cone dips; if one dip may choose its gates, 1 event (3 gates). Whether a real dip can choose is open.`
- after: `- Rail-dip model (SIMULATED, B3): no rail attack up to 3 events for whole-rail or half-design 1-to-0 dips on V1, V2 and V5 alike (polarity, not a benefit of triplication); a selective dip reaching the three copies costs 1 on V2 (3 gates). Whether a real dip can select is open; 0-to-1 control pending (LEDGER); V2 rows rest on z3 alone.`

### docs/report/PROJECT_REPORT.md
- before: `or if synthesis merges the copies;`
- after: `or if synthesis merges the copies (previously shown by SYNFI: 3->2 and 4->2 faults after FSM recoding and register merging, `set_dont_touch` restored 4; our E2 replicates it on a toy design);`

### docs/report/PROJECT_REPORT.md
- before: `- Rail-dip model (B3, T = 6, <= 3 events): V2 has no attack under whole-rail, half-design or cone dips; if one event may choose which gates fall, 1 event (3 gates, one per copy); whether a real dip can choose is open.`
- after: `- Rail-dip model (B3, T = 6, <= 3 events): no rail attack under whole-rail or half-design 1-to-0 dips on V1, V2 and V5 alike (polarity, not a benefit of triplication); if one event may choose which gates fall, 1 event on V2 (3 gates, one per copy); whether a real dip can choose is open; 0-to-1 control pending (LEDGER); V2 rows rest on z3 alone (brute-force anchors in progress).`

### docs/report/PROJECT_REPORT.md
- before: `When synthesis merges identical copies (opt_merge, 63 gates) V2 needs 1.`
- after: `When synthesis merges identical copies (opt_merge, 63 gates) V2 needs 1. SYNFI previously showed the same effect (3->2 and 4->2; `set_dont_touch` restored 4); E2 replicates it on a toy design across 864 configs plus a keep-attribute axis.`

### docs/report/SLIDES_OUTLINE.md
- before: `I ran V2 through 864 synthesis settings;`
- after: `The solver was run on V2 across 864 synthesis settings;`

### docs/report/SLIDES_OUTLINE.md
- before: `If I re-synthesise the same source`
- after: `If the same source is re-synthesised`

### docs/dossier/PROJECT_DOSSIER.md
- before: `the cause is common-subexpression merging of the three compare cones (E2).`
- after: `the cause is common-subexpression merging of the three compare cones (E2). Previously shown by SYNFI (faults needed 3->2 after FSM recoding, 4->2 after register merging; `set_dont_touch` restored 4); E2 replicates the effect on a toy design across 864 configs and a keep-attribute axis.`

### docs/dossier/PROJECT_DOSSIER.md
- before: `So V2 and V5 vs V1 is not 3 vs 1 in general but ">3 for rail-wide events, 1 if selective"`
- after: `V1 also shows >3 under whole-rail and half-design 1-to-0 events, so this is a polarity result, not a benefit of triplication; the 0-to-1 control is pending (LEDGER, `research/c5/ledger/`), and the V2/V5/apt rows rest on z3 alone (brute-force anchors in progress). So V2 and V5 vs V1 is not 3 vs 1 in general but ">3 for rail-wide events, 1 if selective"`

### docs/dossier/EVIDENCE_INDEX.md
- before: `copies merged by `opt_merge`, flatten-before-ABC, `abc -dff`; `keep` attribute changes no verdict |`
- after: `copies merged by `opt_merge`, flatten-before-ABC, `abc -dff`; `keep` attribute changes no verdict; effect previously shown by SYNFI (3->2, 4->2; `set_dont_touch` restored 4), E2 replicates it on a toy design |`

### docs/dossier/ONE_PAGE_FOR_THE_OWNER.md
- before: `- A supply dip over a whole rail, a whole block or a cone does not break V2 within 3 events (model, bounded); if one dip could pick its gates it takes 1 event (3 gates).`
- after: `- A 1-to-0 supply dip over a whole rail or half the design does not break V1, V2 or V5 within 3 events (model, bounded; a polarity result, not a benefit of triplication; 0-to-1 control pending, LEDGER); if one dip could pick its gates it takes 1 event on V2 (3 gates).`

### docs/wow/explainer.html
- before: `<li>Conda 0.38+92 was not run for the opt flow.`
- after: `<li>Synthesis dependence was previously shown by SYNFI (faults needed dropped 3 to 2 after FSM recoding and 4 to 2 after register merging; <code>set_dont_touch</code> restored 4); our E2 replicates the effect on a toy design across 864 synthesis configs and a keep-attribute axis. Supply-dip rows (SIMULATED basis): no rail attack under 1-to-0 whole-rail or half-design events for V1, V2 and V5 alike, a polarity result and not a benefit of triplication; a selective event costs 1; 0-to-1 control pending.</li> / <li>Conda 0.38+92 was not run for the opt flow.`

### docs/report/SLIDES.pptx slide shape
- before: `Synthesis merges copies`
- after: `Synthesis merges copies (SYNFI saw this first)`

### docs/report/SLIDES.pptx slide shape
- before: `MEASURED: E2 matrix, 864 settings (792 solved in all, 264 for V2).`
- after: `MEASURED: E2 matrix, 864 settings (792 solved, 264 for V2). Previously shown by SYNFI (3 to 2, 4 to 2); E2 replicates it on a toy design.`

### docs/report/SLIDES.pptx slide shape
- before: `MEASURED: research/c3/rep/REP_REPORT.md; R22 (physical fault-model literature, snippets and fetched pages).`
- after: `MEASURED: research/c3/rep/REP_REPORT.md; R22 (physical fault-model literature, snippets and fetched pages). Other tools: docs/report/COUNTING_CONVENTIONS.md.`

### docs/report/SLIDES.pptx notes 4
- before: `If I re-synthesise the same source`
- after: `If the same source is re-synthesised`

### docs/report/SLIDES.pptx notes 6
- before: `I ran V2 through 864 synthesis settings`
- after: `The solver was run on V2 across 864 synthesis settings`
