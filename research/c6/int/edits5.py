import json, re
exec(open('/home/user/project/research/c6/int/apply_edits.py').read().split('# ---------- README')[0])
E[:] = json.load(open(ROOT/'research/c6/int/edits_log.json'))
files = ['README.md','START.md','docs/ENGINE_STATUS.md','docs/FINAL_STATUS.md','docs/report/CLAIMS_CHECK.md','docs/report/ONE_PAGE_SUMMARY.md',
 'docs/report/PROJECT_REPORT.md','docs/report/REVIEW_NOTES.md','docs/report/SLIDES_OUTLINE.md','docs/dossier/AI_USE_DISCLOSURE_DRAFT.md',
 'docs/dossier/CRITIQUE.md','docs/dossier/EVIDENCE_INDEX.md','docs/dossier/ONE_PAGE_FOR_THE_OWNER.md','docs/dossier/PROJECT_DOSSIER.md',
 'docs/dossier/RUBRIC_MAP.md','docs/dossier/VIVA_ANSWER_CARDS.md','docs/dossier/VIVA_SHEET.md']
for f in files:
    p = ROOT/f; bk = ROOT/'research/c6/int/backup'/f
    if not bk.exists(): bk.parent.mkdir(parents=True, exist_ok=True); bk.write_text(p.read_text())
    lines = p.read_text().split('\n'); ch = 0
    for i, l in enumerate(lines):
        if re.search(r'\b136\b', l) and not l.startswith('|') or (l.startswith('|') and re.search(r'\b136\b', l)):
            n = re.sub(r'\b136\b', '150', l)
            n = n.replace('(RECON5); 133 and 321 at RECON4', '(INT); 136 at RECON5; 133 and 321 at RECON4')
            n = n.replace('136 passed in 15.4 s', '150 passed in 19.9 s').replace('150 passed in 15.4 s', '150 passed in 19.9 s')
            n = n.replace('RECON5', 'INT, 2026-11-20 05:13 UTC') if '136 at RECON5' not in n else n
            if n != l:
                E.append({'file': f, 'before': l, 'after': n}); lines[i] = n; ch += 1
    p.write_text('\n'.join(lines)); print(f, ch)
json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1); print(len(E))
