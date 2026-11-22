# DASH report: dashboard data and text refresh
Work copy /tmp/work_dash; applied to the tree after tests. Backups of the three changed files: research/c4/dash/backup/ (build.py, template.html, index.html as they were). make was not run. Look, layout and tokens unchanged; only data, text, one tab and two bug fixes.

## 1. Regeneration with the hardened build.py
- Regenerating the OLD build.py/template with the current build.py (before my edits) changed exactly 1 line of index.html (line 106, the embedded `const DATA`): strings now HTML-escaped (`k&lt;=2`, `&#x27;`), `<`, `>`, `&` written as <, >, &. Everything else byte-identical (MEASURED, diff).
- Final index.html: exactly one `</script>` (the real one), no raw `<` or `>` inside DATA; the template inserts only cleaned strings or esc()d fault names into innerHTML.
- Headless Chrome (google-chrome, playwright), 390 and 1366 px, all four tabs clicked: 0 console errors, scrollWidth == viewport at both sizes (research/c4/dash/shot.py).
- ERR_FILE_NOT_FOUND: NOT a missing asset. It is the Act 4 image `../layout/v_designs/out_patched/v1_zoom_ok.png` (relative path), which exists in the tree (1.09 MB). It fails only when index.html is copied away from the project (e.g. /tmp/iso/index.html -> file:///tmp/layout/...). In the tree: no error. Left as is (a self-contained page would need embedding 1 MB; not done, author choice).

## 2. Data added (new tab "Scope", reuses the tab and card mechanism)
build.py reads the stored result files at build time (no hand-typed numbers); each block carries its label and source file on the page:
- Scope table, MEASURED, research/c2/b2_scope/matrix.jsonl: result word, known init, input nets not sites: V0 1, V1 1, V2 spike 3, V2 apt-0.33 2; boot_ok: 1 for all; input nets as sites: 1; arbitrary non-accepting power-up: 1; arbitrary power-up: 0.
- Flips vs consumer width, MEASURED, research/c3/m1/m1_all_masks.csv (= PS5 --sweep-widths): n=1..8 -> 0,1,1,2,2,3,3,3.
- E2 variance, MEASURED, research/c2/e2_variance/raw/matrix.csv: V2 min 1/2/3 in 180/60/24 of 264 solved; V1 233/31/0; V0 264/0/0 (24 per design unreadable by the engine, shown, not counted as safe).
- Rail-dip note, label SIMULATED (SPICE basis EL1; the solver result is MEASURED, stated on the card), research/c4/b3/matrix_T6.jsonl: rail-wide, half-hierarchy and cone events: V2 and V5 ">3" (bounded, not a proof); V0 falls to 1 to the cone event; the "any gate subset" bound row gives 1 for all (not supported by the SPICE basis); selectivity stated as the open question.

## 3. Scope caveats
Added SCOPE_NOTE under the V2 verdict in Act 1 and Act 2 (result word only; boot_ok falls to 1 flip; modelled bit flips only, nothing physical); a scope line under the k/verdict table; "for the result word (boot_ok falls to 1 flip)" in the engine-table note; the Scope tab carries the "the 3 is about the result word only" paragraph. The earlier F1 caveats (TEXT_FIXES) are untouched (all still match once).

## 4. Numbers page vs source (research/c4/dash/verify_numbers.py, output verify_numbers_output.txt)
115 values compared (scope table 20, widths 16, E2 3 rows, rail table 25, engine summary rows, curve runtimes vs reproduce_summary.json and deep/sweep_main.json): 115 match, 0 mismatches. It compares the page's embedded DATA with an independent re-read of the source files, and the task's stated expectations; it does not check prose text.

## 5. Accessibility (report plus two fixes)
- Smallest rendered text 12.48 px (badges); body 16 px. SVG text 14 px in a 600 px minimum width container.
- Contrast of existing tokens (not changed): all text/background pairs >= 4.5:1 in light and dark; lowest: light est on card 4.87, good on goodbg 4.75, bad on badbg 4.92.
- Bug found and fixed: tabs and timeline buttons were rebuilt on every click, so keyboard focus fell to the body after Enter/Space. Now focus is restored to the same button (tested: Enter and Space on tabs keep focus; Tab order natural; :focus-visible outline exists). Not checked: screen reader output, the SVG schematics' text alternatives beyond their aria-label.

## Not done / limits
Layout image not embedded; chart note text "about 294 s at 20 cycles" left as is (matches deep sweep 293.5 s); apt-0.33 dashboard note of V5 not added as a tab; no visual-diff regression of the unchanged tabs beyond the console/scroll checks. Screenshot of the new tab: research/c4/dash/scope_tab_1366.png.
