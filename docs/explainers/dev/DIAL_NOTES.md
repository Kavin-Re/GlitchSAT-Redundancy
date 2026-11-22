# Verdict Dial: stage notes

License: Apache-2.0. GlitchSAT. Toy designs, modelled bit flips, nothing physical, nothing established as new.

File: `docs/explainers/dial.html` (single file, opens offline from `file://`). Data: `docs/explainers/dial.json`, built by `build_dial.py`, re-checked by `check_dial.py`. Every digit on the dial is MEASURED (a copy of one source row); 94 of the 432 switch combinations have a row, the other 338 show "not measured".

## Use it on stage in 60 seconds

1. Open `dial.html` in a browser. Press **F** (big screen), then the browser's own full-screen key (F11). The page does not go full screen by itself.
2. The dial starts at **3**: V2, whole word, stored netlist, pins out of reach, known power-up.
3. Press **P** (predict first). The digit is now hidden after every switch change.
4. Change one switch. Ask the room. Press the guess they shout (**0** to **3**), then **R** to reveal.
5. Tap "Source" under the digit to show the file and row. That is the answer to "where does that number come from?".

Keys: F big screen, P predict first, 0-3 guess, R reveal, Tab between switch groups, arrow keys inside a group. A link can carry the state: `dial.html#v2.word.plain.no.known;predict;big` (design.reader.build.pins.power).

The stage path that stays on measured cells (checked by `check_dial.py`): stored 3 -> Build "Re-built" 2 -> Reader "Accept flag" 1 -> Power-up "Any" 0.

## The 3-minute script (zero typing)

| time | do | say |
|---|---|---|
| 0:00 | Dial on screen, big mode, predict on, digit hidden. | "This toy lock checks the key three times. A flip is one modelled glitch: one bit wrong for one clock tick. Hands up: how many flips to open it with the wrong key? One? Two? Three?" |
| 0:20 | Press the room's guess, then R. Digit: **3**. | "Three. Measured by a solver on the stored netlist: no attack found with fewer than 3 flips, up to 6 ticks. Not 'safe': that is as far as we looked." |
| 0:40 | Build -> "Re-built". Take a guess, reveal: **2**. | "Same design text, built again with the plain recipe. Two. The tool left two shared wires that move the four bits that matter." |
| 1:05 | Build -> "Merging". Guess, reveal: **1**. | "A recipe that merges identical logic turns three copies into one. One flip." |
| 1:25 | Build -> "V2e". Guess, reveal: **3**. | "We changed one constant. Back to three in this recipe: 6 of the 8 recipes we ran. The 2 merging recipes stay at 1. So not a cure." |
| 1:50 | Build -> "Stored", Reader -> "Accept flag". Guess, reveal: **1**. | "Now ask who reads the result. If the next block reads the one-wire accept flag, not the 8 lights, it is one flip, whatever the three copies do." |
| 2:10 | Reader -> "Only 4 lights", try the four masks: **3, 2, 1, 0**. | "A reader that checks 4 of the 8 lights gets 3, 2, 1 or 0, depending on which four." |
| 2:30 | Reader -> "Whole word", Power-up -> "Any". Reveal: **0**. | "And if the lock may wake up in any state, it can wake up open. Zero. The toy has no reset." |
| 2:45 | Scroll to "What we did NOT show". Optional: pick Merging + Accept flag to show "not measured". | "The number is a property of the design, the build and the question together. Toy design, modelled flips, nothing physical, one tool family, and where we did not run it the dial says so." |

V1 opener from the plan ("Dial on V1 (1)"): Lock design -> V1 shows 1 on the stored and the re-built netlist ("two copies, but both answers meet on one wire").

## What to say, and what not to say

- Say "measured in a model", "no attack found with fewer, up to 6 ticks", "modelled flip". Never "safe", "secure", "proves", or anything about real chips.
- "Stored" and "Re-built" are the same Yosys version (0.33); they differ in source and recipe, not in tool version.
- "V2e back to 3" is true for the plain recipe row shown and for 6 of 8 recipes on Yosys 0.33; say the 2 merging recipes stay at 1.
- "Not measured" means nobody ran it. Do not guess aloud what it would be (the flag on the merging build "would obviously be 1" is a guess until run).
- The 0 for "lights 7, 4, 3, 0" is a reader that cannot tell idle from open (the idle codes already match on those lights), not an attack.
- The reason line under the digit is a plain-language lookup written by an step from B2_REPORT, M1_REPORT and WHY_TWO_FLIPS; the digit is the measurement, the sentence is the explanation.

## Rebuild and check

```
python3 docs/explainers/dev/build_dial.py             # reads the source files, writes dial.json, re-inlines it in dial.html
python3 docs/explainers/dev/check_dial.py --browser   # all 432 combinations, in the data and on screen at 390 and 1366 px
python3 research/c6/p40/shoot.py           # screenshots into research/c6/p40/shots/
```
