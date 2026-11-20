# RECON4 report
Measured on a fresh tar-pipe copy /tmp/work_recon4/p (venv /tmp/work_recon4/venv, `pip install ./product[test]` + pytest z3-solver pyyaml). MEASURED:
- `pytest product/tests`: 321 passed, 0 skipped, 81.3 s (310 + 11 in test_h4.py)
- `pytest tests`: 133 passed, 14.9 s
- `ci/check_reproduce.py`: 36/36, 0 FAILED; `--rerun`: 36/36, 0 FAILED, 0 problems, exit 0
- `check_numbers.py --verify --pytest` (copy with updated docs): 10/10 verify OK; collected 133 and 321 = NUMBERS.md
- Tree: no product/build, no egg-info.

Changed (originals in research/c5/recon4/backup/): README.md, START.md, docs/FINAL_STATUS.md, docs/ENGINE_STATUS.md, docs/NUMBERS.md, docs/dossier/{RUBRIC_MAP,CRITIQUE,EVIDENCE_INDEX,VIVA_ANSWER_CARDS,PROJECT_DOSSIER,ONE_PAGE_FOR_THE_OWNER}.md, docs/report/{SLIDES_OUTLINE,ONE_PAGE_SUMMARY,PROJECT_REPORT,CLAIMS_CHECK}.md, docs/report/SLIDES.pptx (slide 9 text and notes only: 310 -> 321) and SLIDES.pdf (LibreOffice re-render, 17 pages, slide 9 viewed). Current 310 became 321 (80.9 s -> 81.3 s, RECON3 -> RECON4 on those lines); "now 133 and 310 after H2/H3" became "now 133 and 321 after H4; 310 at H2/H3 time". docs/edu, dashboard (build.py, template.html, index.html) and deck notes beyond slide 9 had no 310: not touched, no rebuild needed.
NUMBERS.md: RECON4 measurement section, T.prod.* = 321, T.hist.prod extended, new rows H4.cycles (cap 200), H4.pyyaml, H4.reportdir, RT3.summary (about 300 payloads, 0 canaries; F1 fixed by the lead, netlist identity v2 d776226e, v1 931050a5, lead canary 02:15), JSON `current`, rule values, rule T.prod.310 now also flags 310 as a current product count (tested: matches 18 old lines in the backups), hist_re markers `H2/H3 time` and `after H4`, SAFETY rule wording.
START.md and FINAL_STATUS.md: safety bullet now says RT3 re-attacked the fix with about 300 payloads, found one remaining path in a classroom script (fixed) and an uncapped --cycles (fixed by H4); limits unchanged (Yosys unsandboxed, Action/Dockerfile never run). The time "02:xx UTC" is written as "about 02:xx UTC" in those pages (RT3 report gives no exact minute).
Gates: check_numbers 52 files, 0 STALE, 15 HISTORICAL (all pre-existing history lines); grep 'H2 in progress|until the fix lands|until the hardening fix' finds only the rule itself in NUMBERS.md.
Not done: no make run; the dashboard text carries no product test count so nothing was rebuilt.
