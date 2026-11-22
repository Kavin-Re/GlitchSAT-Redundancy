# W4 report: wow fix round 4
Edited only docs/explainers/ (explainer.html, game.html, poster.md, script_60s.md, this file) and research/c3/w4/ (shoot.py, h.py, s.py, o.py, shots/). Complaints come from research/c3/wp3/WP3_REPORT.md (simulated readers, ILLUSTRATIVE; gate 4 of 6, weak on "would tell"; expert P18 flagged overreach). No persona run was done, so no score claim is made.

## Changes mapped to complaints
1. Honesty (P15, P18 points 1-6)
   - Claims carry a tag: "Toy picture (drawn, not computed)" or "Measured by a computer check on small designs", on both pages.
   - "No safer than one guard" is gone. The headline is tagged a toy picture. The nearest measured result is stated: two checks into one shared wire fell to 1 flip, the same as one check alone (V1 vs V0). The three-check version was not run.
   - Wiring B "covers all 8 lights" is labelled an ILLUSTRATION on both pages. I found no cited result for it: research/c2/b2_scope gives only the minimum 2, and research/c3/m1 holds RTL plus a script, with no per-bit result.
   - 3-vs-2 is now "measured on one small design family: 26 of 32 rebuilds needed 2 flips and 6 needed 3; replicated". The counting caveat is in plain words: counting a wire once per place it feeds gives 3 for all 32. Toy designs only. Partial-branch flips were not tested. Neither rule is shown to be physical. The evidence block adds that REP shared the recipe list with DA.
   - Counting button changed from "per light" to "per place it feeds" to match what REP measured (pins, flop inputs, output bits).
   - Scope box kept. It now adds that changing an assumption, such as the accepted flag as goal, makes the result stop applying.
2. Quotable (P13, P17, P14, P18): the H1 is "Three guards on one wire are really one guard." Directly under it is "Where do the copies meet?", then the model-only scope line. The old long hedged quote is removed. The same sentence is in poster.md and script_60s.md.
3. So-what (P15): an early "What to ask a supplier" box with 3 questions (where do the copies meet; how do you count a fault; what is checked at the end). It says it tests no supplier.
4. Phone path (P13, P17)
   - The hero button sits at y=470 to 518 on a 390x844 screen, and at 584 to 632 at 320x640.
   - "Skip to the game" link at the top.
   - Fresh-load page height at 390 px is 4193 px (was about 5200). The "fix" section no longer has its own picture; Wiring A serves as the picture. Pictures were shrunk. The counting widget is collapsed, with its conclusion kept in the red box.
   - Game: the Wiring A hint is now "each guard still has its own wire here, so you must fool all 3 guards. Rebuilding changed nothing in this case." The Wiring B hint is "only two joined wires, X and Y, are in play. Flip both." A "Flips used / Par (goal)" scoreboard is shown up front, and the intro says to use as few flips as the par.

## Tests (research/c3/w4/shoot.py, Google Chrome headless, buttons exercised, shots/)
- check_game_answers.py: PASS.
- 390 (light and dark), 1366 (light and dark), 320, 640 (200% zoom of a 1280 window): 0 console errors, no sideways scroll, no HTML text under 12 px, all buttons at least 44 px.
- 195 px (200% zoom on a phone): no sideways scroll. SVG text scales to about 9 px and is NOT fixed.

## Not done
- The height target is met only on fresh load (4193). After opening the counting details and tapping, the page is about 4700 px.
- Game page height at 390 px is 3747 px. The game's 6 design tabs are still 3 rows of 2.
- Whether the headline is repeated more often by readers is untested.
