# W6 report: final polish
Edited only docs/wow/ (explainer.html, game.html, poster.md, script_60s.md, new script_90s.md, this file) and research/c3/w6/ (shoot.py, shots/). No persona test; no score claim.

## Changes
1. Fix wording: "The fix: give every guard its own wire" is now "What giving each guard its own wire showed"; box says "3 flips, one per guard (picture). Measured result word: 3 flips. But the accept flag itself falls to 1 flip." Hero pink box: "Copies only help if each has its own road" replaced by "Here the copies meet at one point, so they act as one." Wiring A caption: "every guard keeps its own wire (illustration of the structure, not measured)". Script: "In our toy picture, one flip beats all three."
2. First screen: the quotable "Three people signing with one shared signature..." sits under the question (bottom at the position printed by the check, inside 844 px). Counting switch box now open by default. One glossary line (flip, result word, accept flag) under the hero text.
3. script_60s.md rewritten (159 words, with click cue). The long text kept as script_90s.md (about 250 words, honest name, toy label added). poster.md trimmed to 208 words. Supplier box: "These are prompts, not a pass/fail standard." Game: "flips can cancel" message replaced by "a flip turns a wire to the opposite of what it was, so flipping a wire that is already right makes it wrong."
4. New section "What the guard's boss actually checks matters" (tag: measured by a computer check on a small design): full word 3 flips (2 on another build of the same design); 4-light reader typically 1 or 2 (4 of 68 such readers still 3); accept flag alone 1. Source research/c3/m1/M1_REPORT.md; toy design, k<=3, 6 ticks.

## Checks
check_game_answers.py: OVERALL PASS. Chrome headless at 390, 1366, 320, 640x400, explainer and game: no console errors, no sideways scroll, no HTML text under 12 px. Screenshots in research/c3/w6/shots/ (shoot.py reproduces).
Limits: not re-timed by speaking; the 60 s script is a word count (159) estimate. Wiring B drawing still an illustration.
