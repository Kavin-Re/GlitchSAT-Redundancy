#!/usr/bin/env python3
"""D3: targeted stale-line replacements (exact string, must match once). """
import sys, pathlib
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/user/project")
T = ("98 passed (root `pytest tests`) and 138 passed, 1 skipped (`product/tests` after `pip install ./product[test]`), "
     "MEASURED by RECON on a copy 2026-11-19; counts move when tests are added: run `make test` and quote your own, see `docs/NUMBERS.md`")
DA = "replicated by agent REP on 64 of 64 rows with one recipe list (`research/c3/rep/REP_REPORT.md`)"
E = [
("docs/ENGINE_STATUS.md",
 "(30 tests, ~29 s, all pass as of RA's 2026-11-19 re-run; it was 10 tests before the H1 hardening tests; product tests: 27 pass after `pip install ./product[test]`)",
 "(98 passed in 26.7 s and product tests 138 passed, 1 skipped in 98.9 s after `pip install ./product[test]`: MEASURED by RECON on a copy, 2026-11-19; history: 10 tests at first writing, 30 per RA, 27 product tests per PS2; run it and quote your own count, `docs/NUMBERS.md`)"),
("docs/ENGINE_STATUS.md",
 "MEASURED by that agent, not re-run here): over 32 re-synthesized",
 "MEASURED by that agent and " + DA + "): over 32 re-synthesized"),
("docs/dossier/AI_USE_DISCLOSURE_DRAFT.md",
 "Run `make test` (30 passed, MEASURED by RA)",
 "Run `make test` (98 passed on a copy, 2026-11-19, MEASURED by RECON; quote your own count)"),
("docs/dossier/PROJECT_DOSSIER.md",
 "MEASURED on a copy: `pytest tests` 30 passed;",
 "MEASURED on a copy at that time: `pytest tests` 30 passed (now 98, see s9);"),
("docs/dossier/PROJECT_DOSSIER.md",
 "The lead re-ran 30 passed and 36/36 on a copy (RUN_LOG entry 151).",
 "The lead re-ran 30 passed (then) and 36/36 on a copy (RUN_LOG entry 151)."),
("docs/dossier/PROJECT_DOSSIER.md",
 "`make test` 30 passed in 28.7 s;",
 "`make test` 30 passed in 28.7 s at that time (history; today 98 passed, RECON 2026-11-19);"),
("docs/dossier/PROJECT_DOSSIER.md",
 "(the \"10 passed\" count, fixed since by F2 in docs but still wrong in D1's dossier, fixed here)",
 "(the \"10 passed\" count at first writing, since superseded)"),
("docs/dossier/PROJECT_DOSSIER.md",
 "Product tests: 38 passed in 28.7 s (MEASURED by PS3, clean venv, after `pip install ./product[test]`; 21 before H1/PS2/PS3 additions).",
 "Product tests: 138 passed, 1 skipped in 98.9 s (MEASURED by RECON on a copy, 2026-11-19, after `pip install ./product[test]`; history: 21, 27 (PS2), 38 (PS3 count, not re-measured) before PS4/PS5/MT added files)."),
("docs/dossier/RUBRIC_MAP.md",
 "`tests/` (30 passed), `product/tests` (38 passed)",
 "`tests/` (98 passed), `product/tests` (138 passed, 1 skipped); RECON 2026-11-19 on a copy"),
("docs/dossier/RUBRIC_MAP.md",
 "scope block in every report, tests 38 passed",
 "scope block in every report, scope options (PS4/PS5), tests 138 passed, 1 skipped"),
("docs/dossier/VIVA_ANSWER_CARDS.md",
 "**E3-10. Is the structural predictor (928/928) validated?**",
 "**E3-10. Is the structural predictor validated? (No: 150 of 163 fresh cells exact, 92%; the 928/928 pooled figure is near-duplicate cells)**"),
("docs/dossier/VIVA_ANSWER_CARDS.md",
 "Trap: repeating \"30 tests\" without checking.",
 "Trap: repeating an old test count (the docs once said 30) without checking."),
("docs/dossier/VIVA_SHEET.md",
 "`pytest tests` 30 passed and `check-reproduce` 36/36 on copies",
 "`pytest tests` (98 passed on 2026-11-19; older pages said 30) and `check-reproduce` 36/36 on copies"),
("docs/report/CLAIMS_CHECK.md",
 "`make test` 10 passed (now 30 passed; product tests 27 passed after `pip install ./product[test]`)",
 "`make test` 10 passed at first writing (now 98 passed; product tests 138 passed, 1 skipped after `pip install ./product[test]`; RECON 2026-11-19)"),
("docs/report/CLAIMS_CHECK.md",
 "\"10 tests\" (now 30)",
 "\"10 tests\" at first writing (now 98)"),
("docs/report/DEMO_5MIN.md",
 "# 30 passed (product tests: 27 after `pip install ./product[test]`)",
 "# 98 passed (product tests: 138 passed, 1 skipped after `pip install ./product[test]`; RECON 2026-11-19, quote your own count)"),
("docs/report/ONE_PAGE_SUMMARY.md",
 "30 tests pass (MEASURED, RA 2026-11-19; product tests 27 pass after `pip install ./product[test]`)",
 "98 tests pass (MEASURED, RECON 2026-11-19 on a copy; product tests 138 pass, 1 skipped after `pip install ./product[test]`; quote your own count)"),
("docs/report/PROJECT_REPORT.md",
 "30 passed (10 at first writing; 30 per RA 2026-11-19; product tests 27 passed after `pip install ./product[test]`, PS2)",
 "98 passed (10 at first writing, 30 per RA, 98 per RECON 2026-11-19; product tests 138 passed, 1 skipped after `pip install ./product[test]`; 27 per PS2 earlier)"),
("docs/report/PROJECT_REPORT.md",
 "10 passed at that time (now 30)",
 "10 passed at that time (now 98)"),
("docs/report/PROJECT_REPORT.md",
 "(`research/c2/devils_advocate/DA_CYCLE1.md`; MEASURED by that agent, not re-run here)",
 "(`research/c2/devils_advocate/DA_CYCLE1.md`; MEASURED by that agent and " + DA + ")"),
("docs/report/PROJECT_REPORT.md",
 "`tests/` (30 tests; 10 at first writing)",
 "`tests/` (98 tests today; 10 at first writing, 30 per RA)"),
("docs/report/REVIEW_NOTES.md",
 "PASS: 10 passed in 20.2 s (at review time; now 30 passed)",
 "PASS: 10 passed in 20.2 s (at review time; now 98 passed, RECON 2026-11-19)"),
("docs/wow/W2_REPORT.md",
 "source DA_CYCLE1.md, MEASURED by that agent, not re-run)",
 "source DA_CYCLE1.md, MEASURED by that agent; replicated by REP on 64 of 64 rows, one recipe list)"),
("docs/wow/W3_REPORT.md",
 "(MEASURED by that agent, not re-run here)",
 "(MEASURED by that agent; replicated by REP on 64 of 64 rows, one recipe list)"),
]
bad = 0
for f, old, new in E:
    p = root / f
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        print("MISS", n, f, old[:60]); bad += 1; continue
    p.write_text(s.replace(old, new))
print("done, misses:", bad)
