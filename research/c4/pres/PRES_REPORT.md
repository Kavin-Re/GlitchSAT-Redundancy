# PRES report: presentation set rebuilt around the current story

Working title TBD; licence UNDECIDED. Faults are modelled bit flips on toy designs; nothing physical; nothing established as new.

## Files (owned by PRES)
- `docs/report/SLIDES.pptx` (rebuilt, 16 slides: 12 main + 4 appendix; speaker notes on every slide, spoken first person), `SLIDES_OUTLINE.md` (generated from the deck, includes the notes), `DEMO_5MIN.md`, `ONE_PAGE_SUMMARY.md`, `PROJECT_REPORT.md` (all rewritten).
- `research/c4/pres/`: `build_deck.py`, `figs.py` (rebuild: `python3 figs.py && python3 build_deck.py` in a scratch dir that has `fig/`; copies of the three generated figures are in `img/`), `render/SLIDES.pdf` and `render/s-NN.png` (40 dpi previews), `backup/*.orig` (the five originals: outline, pptx, demo, one-pager, report). Work was done in `/tmp/work_pres/`; nothing was run with make in the tree.

## Story and slides
Words per main slide (all visible text except footer and slide number; titles included): 41, 15, 31, 37, 32, 24, 28, 35, 26, 24, 16, 30. Slides 1 and 4 exceed 35 slightly (title slide carries the problem sentence; slide 4 is the scope table). Appendix slides are denser by design (55 to 74 words).

## Checks
- Render: LibreOffice headless to PDF (16 pages), then PNG; every slide viewed at 50 dpi in contact sheets. No text overflow or overlap found after one fix (slide 2: the ILLUSTRATIVE label overlapped the sub-line; moved). A script check found no shape outside the 13.33 x 7.5 in slide. Fonts: Calibri in the file, rendered with the Carlito substitute here; PowerPoint may wrap slightly differently, leave 10 to 15% slack if you edit.
- Demo commands verified on a copy (`/tmp/work_pres/copy`, own venv, `pip install ./product`): glitchsat V1 k=1 0.5 s (ok, 1 flip); V2 k=2 NO_ATTACK_UP_TO_BOUND 2.1 s, exit 0; k=3 ATTACK_FOUND 3 flips (one per compare copy, cycle 1) 7.9 s, exit 1; boot_ok k=1 ATTACK_FOUND 0.5 s; `--sweep-widths` 18.8 s: 0,1,1,2,2,3,3,3; `--scope-sweep --sweep-masks 0x0F,0x6A` 17.9 s: rows 3/1/0/0, 2/1/0/0, 3/1/0/0, 1/1/0/0; `--timeout-s 2` gave UNKNOWN_TIMEOUT exit 2 after 2.1 s. The `--max-flips 2` fallback for sweeps was not run (documented from the tool's own `>k` semantics).
- Wording scan: no "secure/safe/proved/validated" without scope in the five rewritten files (matches are only "NOT proven", "not validated linter", "no claim that V2 is secure"). `python3 scripts/check_numbers.py` lists no stale rows in my files.

## Things the lead should know
- Numbers not yet rows in `docs/NUMBERS.md`: 2.95 um (LAYOUT_REPORT), the L2 spread-layout facts (radius 11.15 to 17.91 um, 15 um, LVS fail in 4 of 4, wire +29 to +50%, die x1.26 to x2.5; L2_REPORT) and the radius-bar figure on slide 8. They are labelled SIMULATED on MEASURED placement. Suggest adding NUMBERS rows. Also: the L2 minimal-radius values come from a 4-cell enumeration and are upper bounds (v8's true threshold is between 8 and 10 um for the selective case).
- Task wording "4-bit consumer 1-2" was written "1 to 3" (28 / 36 / 4 of 68 masks need 1 / 2 / 3, NUMBERS M1.four).
- "Synthesis merges the copies: 1" rests on the edu exercise (G.v2.merge, MEASURED by the edu agent, 63-gate netlist), not re-run by me. The mutation score 67% is REPORTED.
- References in PROJECT_REPORT section 6 are labelled SOURCED (read by R10/R21/R22/R23 agents, abstracts or snippets); I read none of them, k-FRP full text still unread.
- The old demo's live PDR (`sby`) step and the dashboard acts were dropped for time; PDR is backup slide A3 only. The conda `formal` env lives in /tmp and may be gone.
