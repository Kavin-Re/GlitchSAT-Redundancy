#!/usr/bin/env python3
"""RECON2 text fixes. Usage: fix_counts.py ROOT BACKUPDIR [--dry]
Backs up each changed file to BACKUPDIR/<relative path> (first change only) and applies regex fixes."""
import os, re, sys, glob, shutil
root, bk = sys.argv[1], sys.argv[2]
dry = "--dry" in sys.argv
files = []
for g in ["README.md", "START.md", "docs/*.md", "docs/report/*.md", "docs/dossier/*.md", "docs/wow/*.md", "docs/edu/*.md"]:
    files += glob.glob(os.path.join(root, g))
skip = {"docs/NUMBERS.md", "docs/report/FIX_LOG.md", "docs/report/WORDING_FLAGS.md"}
MUT = ("root `tests/` 72.5% (50 of 69 runs), product 67.6% (50 of 74 runs; T2 had 65.8% over 79 runs before T3 and "
       "5 mutants no longer apply)")
SUBS = [
    # test counts (RECON2 re-measure 2026-11-19: root 99 passed, product 139 passed + 1 skipped)
    (r"\b98 passed", "99 passed"), (r"\b138 passed", "139 passed"),
    (r"\b98 root passed", "99 root passed"), (r"\b98 root\b", "99 root"),
    (r"\b98 main tests", "99 main tests"), (r"\b98 tests\b", "99 tests"),
    (r"\b138 product passed", "139 product passed"), (r"\b138 in the product suite", "139 in the product suite"),
    (r"tests 138 passed", "tests 139 passed"),
    (r"98\.9 s; 139 collected", "33.2 s; 140 collected"), (r"98\.9 s\)", "33.2 s)"),
    (r"\bnow 98\b", "now 99"), (r"today 98\b", "today 99"),
]
changed = []
for p in sorted(set(files)):
    rel = os.path.relpath(p, root)
    if rel in skip:
        continue
    t = open(p, encoding="utf-8").read(); o = t
    for a, b in SUBS:
        t = re.sub(a, b, t)
    if t != o:
        changed.append(rel)
        if not dry:
            d = os.path.join(bk, rel)
            if not os.path.exists(d):
                os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(p, d)
            open(p, "w", encoding="utf-8").write(t)
print("\n".join(changed))
