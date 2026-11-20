import json, sys
exec(open('research/c6/int/apply_edits.py').read().split('# ---------- README')[0])
E[:] = json.load(open(ROOT/'research/c6/int/edits_log.json'))
O='docs/report/SLIDES_OUTLINE.md'
rep(O, "  > SAY: I do not know the exact reason two Yosys versions disagree. I only know that it happens and that a verdict belongs to one exact netlist file. This is measured, bounded, toy designs.",
 "  > SAY: I used to say two Yosys versions disagree. That was wrong: the stored netlist was made by the same Yosys 0.33. The real cause is the encoding, which I show on slide 'Why 2 and not 3?'. Encoding sets the floor; the synthesis flow decides whether the floor is reached. A build or flow difference changes the netlist, not the underlying weakness. This is measured, bounded, toy designs.")
rep(O, "# Slides outline (16 slides: 12 main + 4 appendix)", "# Slides outline (19 slides: 14 main + 5 appendix; slides 13 and 14 added by agent INT, 2026-11-20)")
new_slides = """## 13. Redundancy is a code   (added by INT)
- Picture: `docs/comms/staircase.png` (flips needed against code distance; flops only and all nets).
- The state words are codewords of a textbook code (distance 4); the copies are a repetition code.
- Flops only: flips needed = distance to the nearest non-accept word (15 of 15 codebooks).
- All nets: about one flip per copy; 3 of 16 three-copy codebooks fall to 2 (my prediction failed).
- Modelled, toy, observed not a theorem. MEASURED: 19 codebooks, T=6, apt Yosys 0.33; `results/comms/distance_sweep.csv`, `docs/comms/CODING_VIEW.md`.
- Speaker notes (say this):
  > SAY: Here is a way a communications engineer would read the design. The state words of the boot machine form a small textbook code, a Reed-Muller code with distance four, and the copied comparators are a repetition code.
  > SAY: On this plot, the diagonal is what happens when only the state register may flip: in all 15 codebooks with distance up to six, the flips needed equal the distance to the nearest word that is not accept. When every net may flip, the curve stops at about one flip per comparator copy, so a bigger distance buys nothing past three.
  > SAY: Some of my predictions failed and I keep them visible. The flops-only count follows the nearest fail word, not the idle word. On the project flow 3 of 16 three-copy codebooks sit at 2, and the order of the words matters: F0 then CC gives 2, CC then F0 gives 3. I did not dissect why. This is modelled, on a toy design, observed and not a theorem, and nothing here is new coding theory.

## 14. Why 2 and not 3?   (added by INT)
- At cycle 0 the machine loads the armed word 0xCC. 0xCC xor 0x96 = bits {1,3,4,6}: they belong to only 2 of the 3 copies.
- So 2 flips of next-state nets can turn that load into 0x96. Not a Yosys-version effect: the stored netlist (3 flips) is also Yosys 0.33, another flow.
- Table, 8 synthesis flows, apt Yosys 0.33: v2 (armed 0xCC, 2 copies) 2 1 1 2 2 2 2 2; v2e (armed 0xA5, 3 copies) 3 1 1 3 3 3 3 3.
- The 1s are flows that merge the copies (opt_merge, flatten before ABC): no encoding fixes those.
- Encoding sets the floor; the synthesis flow decides whether it is reached.
- MEASURED by agent P01a, re-run by the lead 2026-11-20: `docs/report/WHY_TWO_FLIPS.md`, `rtl/v2e.v`. Stem rule, T=6, k<=3, toy design; conda 0.38 gives 3 only on its plain flow.
- Speaker notes (say this):
  > SAY: Earlier I blamed the Yosys version for V2 needing three flips on one netlist and two on another. That was wrong, and a fresh-eyes review caught it: both netlists come from Yosys 0.33.
  > SAY: The real reason is in the encoding. Before the key check, the machine loads the armed word CC. CC and the accept word 96 differ in four bits, and those four bits belong to only two of the three comparator copies. So an attacker does not need to fool all three copies: two flips at the moment CC is loaded are enough, if the netlist has one shared net per copy.
  > SAY: To test that, only the one constant was changed to A5, which touches all three copies. Over the same eight synthesis flows V2 gives 2, 1, 1, 2, 2, 2, 2, 2 and the re-encoded design gives 3, 1, 1, 3, 3, 3, 3, 3. The ones are flows that merge the copies, and no encoding fixes that. So: encoding sets the floor, the flow decides whether it is reached. Toy design, modelled flips, bounded at six cycles and three flips.

## 15. A1. Counting rule: one flipped net is one fault"""
rep(O, "## 13. A1. Counting rule: one flipped net is one fault", new_slides)
rep(O, "## 14. A2. Predictor", "## 16. A2. Predictor")
rep(O, "## 15. A3. The one unbounded proof", "## 17. A3. The one unbounded proof")
rep(O, "## 16. A4. Layout", "## 18. A4. Layout")
rep(O, "## 17. A5. Ledger", "## 19. A5. Ledger")
json.dump(E, open(ROOT/'research/c6/int/edits_log.json','w'), indent=1); print(len(E))
