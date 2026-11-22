# F1_FIX_LOG
Required V2 scope text (CT-1, integration step re-run CONFIRMED; CT-2, CT-3, CT-4) was added verbatim in substance to every file below. Earlier F1 edits (CC-1..CC-21 items already in the tree) were checked and left as they are.

| file | what changed | why | register id |
|---|---|---|---|
| README.md | new paragraph "Scope of every V2 statement" before Status | V2 claim must carry goal, input nets, init state, netlist, boot_ok 1-flip, input-buffer 1-flip (reported), apt 85-gate 2-flip, conda 83-gate none | CT-1, CT-2, CT-3, CT-4 (FIXED wording) |
| docs/FINAL_STATUS.md | new section "Scope of every V2 statement" (incl. PDR not replicated by reviewer, layout netlist not analysed by project solver); engine bullet qualified | same | CT-1..CT-6 wording |
| docs/report/PROJECT_REPORT.md | scope paragraph after the honest summary | same | CT-1..CT-4 |
| docs/report/ONE_PAGE_SUMMARY.md | scope paragraph; V2 spike table row says "for the 8-bit word goal"; boot_ok breaks with 1 | same | CT-1..CT-4 |
| docs/report/DEMO_5MIN.md | "scope to say aloud" paragraph; hard question 2 qualified | same | CT-1..CT-4 |
| docs/report/SLIDES_OUTLINE.md | slide 6 scope bullet and notes; slide 18 hard-question note | same | CT-1..CT-4 |
| docs/ENGINE_STATUS.md | V2 scope paragraph after first section | same | CT-1..CT-4 |
| docs/DEEP_RESULTS.md | re-run note (work/nl not stored, absolute paths, scope pointer) | stale/unsafe re-run instruction | CC-18 FIXED |
| dashboard/build.py (TEXT_FIXES) | six new text pairs: scope bullet in the intro, Act 3 exception bullet, V2 "why" text, timeline message, reveal text, Act 2 caveat | dashboard V2 claims carried no goal/input/init scope | CT-1..CT-4 |

Dashboard build and test: patched on a copy (/tmp/work_f1), rebuilt with python3 dashboard/build.py (all TEXT_FIXES matched exactly once), then rebuilt in the tree. Chromium (google-chrome headless, Playwright) at 1100 and 390 px: 0 console errors in the tree (the copy showed only the missing layout image because layout/ was not copied), no horizontal page scroll, both V1 and V2 tabs clicked. Template.html was not edited (the pairs are applied at build time); no restyle.

Rows checked and found ALREADY FIXED in the tree by the earlier F1 pass (verified by grep): CC-1, CC-2, CC-3, CC-4, CC-5 (DEMO/slide wording), CC-6, CC-7, CC-8, CC-9, CC-10, CC-11, CC-12, CC-13, CC-14, CC-15, CC-16, CC-17, CC-19, CC-20. Residual CC-21 physical wording: the ONE_PAGE and DEMO text now say modelled bit flips / flow-demo layout.
Rows NOT fixable by me (outside my files or author-only): CC-18 script half (results/deep/run_one.py hard-coded paths, integration step decides); CT-11, CT-12, CT-14 (engine and formal/FORMAL.md wording, not in my scope); CE-11 (rtl/v1.v comment); CE-2 and D1-4 (author); K-1..K-4, DA-1/DA-2 and E1-2 are dossier/threat-model wording owned by the dossier step (README/ONE_PAGE already carry the DA and K wording). CT-2 numbers are the reviewer's, UNVERIFIED by me and marked "being re-measured" everywhere.
Not run: make reproduce, make test (not allowed in tree); PDR not re-run.
