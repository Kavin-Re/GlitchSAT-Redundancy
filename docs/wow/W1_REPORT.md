# W1 report: wow for any audience
Folder: docs/wow/. Nothing outside it was edited.

## Built
- explainer.html: 8-scene scroll story, inline SVG/CSS/JS, no external resources, with in-place explanation of "the tool"/Yosys. Auto-demo of a flip on scenes 2 and 4 (skipped under prefers-reduced-motion; buttons and keyboard still work). Links to game.html.
- game.html "Break the lock": 5 designs (V0, V1, V2 original, V2 rebuilt by apt Yosys 0.33, V2 rebuilt by conda Yosys 0.38+92). Visitor flips wires, "cheapest break" button, live table of toy results (1/2/3 flips) beside MEASURED solver verdicts. Toy model is a JSON block in the page and is used by the page itself.
- check_game_answers.py: parses the model out of game.html and re-derives outcomes by brute force; compares to results/reproduce_summary.json and results/reproduce/*.json (read-only). Result: ALL PASS (run: python3 docs/wow/check_game_answers.py). The conda row (v2b) is checked only against the text of docs/ENGINE_STATUS.md, not a solver output (that run is in the formal env, not results/reproduce).
- R12_science_communication.md, analogies.md (8, each with where it breaks), script_60s.md, poster.md, DASHBOARD_LINK_SNIPPET.md.

## Tests done (Chromium via node playwright 1.63 from /opt/node22, chromium-1243 binary)
- Loaded both pages at 390x800, 1100x800 and 360x740: console errors none, external requests none, scrollWidth == viewport width in all six loads, smallest rendered font 16px (SVG text scaled by viewBox ratio included).
- Game clicked through in Chromium: for each design the "cheapest break" gave 1,1,3,2,3 flips (matches solver min_faults 1,1,3,2; conda 3 from docs); a single flip of the first wire opened V0 only.
- Reduced-motion context: explainer still shows correct state; buttons work (scene 6 reaches "only 2 flips needed").
- Screenshots in shots/ (top and full-page, 390 and 1100). I viewed the 390 game top, the V2-rebuilt break and the 390 explainer; fixed label/line overlap after viewing.

## Unverified / limits
- Contrast >= 4.5:1 was chosen from palette (dark ink on near-white, white on #b3261e/#17653a/#1f4e9c, estimated above 6:1) but not machine-measured.
- Not tested on real phones or other browsers (Firefox, Safari); no screen reader test beyond aria-labels; keyboard flip implemented, not exhaustively tested.
- Timing of the story (~3 minutes) is an estimate, not measured with readers.
- The toy shape for "rebuilt by tool A" (two shared wires covering all 8 lights) is a simplification: the solver found 2 faulted gates feeding several result bits; the exact bit sets are UNVERIFIED. The toy does not flip the lights or internal gates; real netlists have 58 to 85 gates.
- R12: no search result page was opened; ncase.me fetch returned no text. Sources are marked UNVERIFIED.
- No persona/reader testing yet. Toy outcomes are ILLUSTRATIVE; real columns are MEASURED but bounded (<=3 flips, 6 cycles).
