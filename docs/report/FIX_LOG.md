# Fix log (document pass after the three reviews)


Resolved fact used everywhere: the same `scripts/synth.sh` gives 85 gates (40 AND, 25 OR, 20 NOT, 8 DFF; 2-fault attack) with apt Yosys 0.33 and 83 gates (37 AND, 25 OR, 20 NOT, 1 MUX, 8 DFF; no 2-fault attack) with conda Yosys 0.38 (`0.38+92`).

| File | Change | Why |
|---|---|---|
| formal/FORMAL.md | Section 2 `v*` bullet and table row, section 3 discrepancy paragraph: removed "0.33 and 0.38 give an identical netlist" and "cause not investigated"; added a CORRECTION and the build explanation. Raw tables kept. | R2 #17, #18: the statement was wrong. |
| docs/FINAL_STATUS.md | "three-act" to "four-act"; layout row (antenna/off-grid results from VERIFY, not signoff); caveat names apt Yosys 0.33 and the cause; weak point 2 (SymbiYosys is installed in a /tmp env); next steps 2, 3, 4 updated (SYNFI done and its limits; DEEP and sby done; antenna/off-grid done). | R2 #43, #45, #48, #49. |
| docs/ENGINE_STATUS.md | Added V2 re-synthesis row for conda Yosys 0.38+92; named "apt Yosys 0.33" on the existing row; note that `ci/expected_reproduce.json` mismatches with another Yosys build; Limits: SymbiYosys available, one unbounded proof; runtime growth sentence reconciled. | R2 #19, #46, #11, ranked 9. |
| layout/v_designs/out_patched/RESULT.md | Plain-verdict line: antenna 0 violations, nothing off the 5 nm grid, not signoff, pointer to VERIFY.md. | R2 #42. |
| layout/triage/TRIAGE.md | Pointer to VERIFY.md section 3 (a[26] cause) under "What remains"; antenna/off-grid line updated. | R2 #66. |
| README.md | Removed "validated" and "strong evaluated project" and the stale "Intended shape (hypothesis...)" paragraph; one-sentence result first; four acts; pointers to docs/FINAL_STATUS.md and docs/report/. | R1 #8. |
| docs/report/PROJECT_REPORT.md | 6.4 rewritten with the cause; section 6 plain-reading sentence; runtime growth sentence; section 5 mutation row (2 of 3 RTL mutants NOT caught); fuzzing row relabelled "reported by a spike, not in this repo (UNVERIFIED)"; 6.6 and limits 6 for door-lock LVS (netgen final line, VGND missing, devices and nets only); limit 3 cause; limit 13 and section 8 SYNFI qualifier; section 9 items 1 and 2. | R2 #13, #18, #53, #61, #65, #11. |
| docs/report/ONE_PAGE_SUMMARY.md | Rewritten: answer sentence first; one label per paragraph (MEASURED once, on the table); large counts moved to the report; caveat names the build; SYNFI qualifier and "enumerates, does not search"; door-lock LVS line; "Next" updated. | R1 #9, R2 #6, #7. |
| docs/report/DEMO_5MIN.md | Prep block: formal step needs conda env at /tmp/mm_root (env `formal`), fallback to read formal/FORMAL.md section 4; Act 2 cause sentence; question 1 (removed "pending", added SYNFI limits); question 2 names both builds. "Act 1 ... V2" wording left as is. | R1 #10, R2 #18, #50. |
| docs/report/SLIDES_OUTLINE.md | Slide 6 and slide 8 caveats now also in the slide bullets; slide 10 cause; slide 13 netgen wording; slide 14 SYNFI bullet and notes (no "still running"; venue UNVERIFIED); slide 17 next steps. | R1 #11, R2 #7, #51. |
| docs/report/SLIDES.pptx | Same changes on slides 6, 8, 10, 13, 14, 17 (text and notes). Re-rendered with soffice; looked at 6, 8, 10, 13, 14, 17: text fits, no overflow. Slide 13 and 14 text lengthened by one to three lines. | R2 #6, #7, #18, R1 #11. |
| docs/report/CLAIMS_CHECK.md | "cause not found" row and SYNFI row updated (not asked explicitly; same fact, found by the final grep). | consistency. |
| docs/PRIOR_ART.md | SYNFI venue marked UNVERIFIED (arXiv page gives none); "UNVERIFIED whether it searches" resolved with pointer to SYNFI_RESULT.md; pointer in section (2). | R2 #55, #56. |
| compare/COMPARISON.md | Added a dated NOTE at the top: SYNFI was run, enumerates and does not search, limits, venue UNVERIFIED. Table cells left as written. | R2 #55. |
| real_designs/second/REPORT.md | Layout row: netgen final line "Top level cell failed pin matching", VGND missing from layout ports; devices and nets only. | R2 #61. |
| THIRD_PARTY.md, NOTICE.md | Dropped "nothing is vendored"; listed copied Apache-2.0 design files (real_designs/second/src, layout/second/rtl/door.v, real_designs/fsm.v and work/, dl_repo as not-checked); SYNFI licence from `compare/synfi_run/src/LICENSE`. `real_designs/src/` does not exist. fsm.v licence is from the earlier report, marked UNVERIFIED. | R2 #58, #57. |
| LICENSE_CHOICE.md | Same: copied files keep their licence; SYNFI licence read (Apache-2.0); "not vendored" removed. | R2 #57, #58. |

## Not changed (on purpose)
- `docs/report/REVIEW_NOTES.md` still contains the old "FORMAL.md says both gave 83 gates" remark: it is a dated record of an earlier review.
- `docs/DEEP_RESULTS.md` already held the correct growth wording; used as the reference.
- Dashboard items (R2 ranked 1-3, 12) are the integration step's.
