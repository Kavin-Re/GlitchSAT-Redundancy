# W5 report: wow fix round 5
Edited only docs/wow/ (explainer.html, game.html, poster.md, script_60s.md, this file) and research/c3/w5/ (shoot.py, view.py, shots/). No persona test run, so no score claim. Complaints from research/c3/wp4/WP4_REPORT.md (simulated readers).

## Changes
1. Mobile hero (explainer): figure now sits above the button (CSS grid order; two columns on desktop). Button reveals the change in view: on 390x844 the figure top is at 272 px and the pink box ends at 836 px after a tap; at 320x640 the page scrolls so the figure starts at 8 px. The auto-flip timer was removed, and the pink box is hidden until the user flips (it says "In this picture: one flip, three guards beaten"). Button toggles "Flip the shared wire" / "Put the wire back"; a state pill says "Shared wire: NOT flipped. Door shut." or "FLIPPED. Door open."; tapping the circle in the drawing updates both. H1 is now "Picture: how one shared wire can beat three guards" (poster and script match).
2. Honesty: each result row is tagged measured, with its scope. Every "3 flips" mention carries "result word only; the accept flag itself falls to 1 flip" (explainer hero/fix/counting/results/oh box, game cards/bullets, poster, script). "Nobody has shown..." removed everywhere; replaced by "In the sources we read we did not find a check of which counting matches real hardware". The 32 rebuilds are stated as one recipe (2 builds x 2 flows x 8 settings), not independent designs; REP is described as a re-run of the same recipe list. Wiring B coverage: a dashed "Drawing only, not a result" box sits under the figure; the measured numbers live in a separate green "Computer results (measured, not drawn)" box further down, whose Wiring B row says "count only, lights not measured". Game: Wiring B card says the same; card rows read "In this game (toy)" / "Computer check (measured)".
3. Supplier box: each of the 3 questions has a Good answer and a Worrying answer line. No fourth question added.
4. Game on mobile: score and status are above the drawing (grid order; beside it on desktop); choosing a design scrolls the score/status into view. Jargon decoded at first use: par, flip, 8 lights/result word, guard, joined wire, accept flag; "defender" removed.

## Checks (Chrome headless, playwright; screenshots in research/c3/w5/shots/)
- check_game_answers.py: OVERALL PASS.
- 390, 1366, 320, 640x400 (200% zoom): no console errors, no sideways scroll, no HTML text under 12 px, no SVG text under 11.5 px. Dark mode at 390 and 1366 also clean.
- Out of scope extreme (195 px wide): game scrolls sideways by 7 px and SVG text renders small; not fixed.

## Not done / limits
Simulated readers only; no real person or device test. Evidence drawer text was edited for wording only; the cited files were not re-opened. Poster and script were not re-timed (script now about 250 words, roughly 70 to 80 s spoken). Whether the stallholder and expert gates now pass is unknown until a persona round.
