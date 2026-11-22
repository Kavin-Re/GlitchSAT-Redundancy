# W2 report: wow fix round

## Changes and reasons (complaint -> fix)
1. Jargon from the twist section (all six: Yosys, V0/V2, netlist, solver, "attack found", "bounded", "clock ticks") -> main text now says "the same design turned into wires two ways", "Wiring A / Wiring B", "computer check". Tool versions, file paths, V-names only in "Evidence for engineers" (collapsed).
2. Long page (P4, P5: about 6900 px) -> explainer cut to 4 sections: hero, fix, twist, take-away. 4085 px at 390 px with the evidence closed (was about 6900). The two twist pictures became one picture with a Wiring A / B switch.
3. "one pen" (P2, P3, P4, P5, P6) -> removed everywhere (explainer, poster, script); analogy 4 now "one signer"; bank line is "three people who all sign with one shared signature are one approval". Also removed "surely", "quietly", "illustrative" in the main text.
4. Overlapping or clipped labels (P1-P6) -> game diagram redrawn: labels sit under circles, lines start below the label chip, "(flipped)" removed from labels (state is shown by YES/no), "joined wire X/Y" shortened to "wire X/Y", taller drawing. Explainer: same layout fix. Checked all six designs at 390 px (shots/game_390_all_designs.png): no overlap.
6. Table cut off on phones (P1, P3, P5, P6) -> already cards in the game; wording now "In this game / Computer check"; explainer evidence table is stacked cards on all widths. No horizontal scroll at 390 or 1366 (measured, light and dark).
7. Toy-vs-real confusion (P2) -> one line explains each; "not run" became "not checked".
8. Game V1 "lock holds" confusion (P1, P4) -> status after a wrong tap says the other guards still say no so the joined wire stays no, plus the hint.
9. Walls of small print (P3, P6) -> one short banner at the top ("A small model, checked on a computer. Nothing physical was done."); one boxed "What we did, and where it holds" instead of a long end box.
10. "Why would a wire flip?" (P3) -> a flip is defined in one sentence in plain words; no claim on cause.

## Honesty (FP/BC/CT)
- Reveal no longer rests on tool differences alone: it names both causes (exact wiring, and how a fault is counted: one fault per joined wire gives 2; one per output fed gives 3; source DA_CYCLE1.md, MEASURED by that step; replicated by REP on 64 of 64 rows, one recipe list). BC row 15 / DA-2.
- Scope box, visible not hidden: result word only (accept flag falls to 1 flip, CT-1), known start, inputs not attacked, up to 3 flips, small model, nothing physical, no real product shown weak. Pages say tested by simulated readers, not real people (BC Q4), in the engineers section.
- Numbers unchanged: 1/1/3/3/2. python3 docs/explainers/dev/check_game_answers.py: PASS (its explainer string check was updated to the new wording).

## Tests
research/c3/w2/shoot.py (headless Chromium, 390 and 1366 px, light and dark, buttons exercised): console errors 0, horizontal scroll none, text under 12 px none in all 8 runs. Screenshots: research/c3/w2/shots/. Playwright chromium-1255 was missing; used installed headless shell 1243.

## Not done
Round-2 persona test; real-person test; no 320 px or 200% zoom run; analogies.md otherwise unchanged; R12/W1_REPORT left as history.
