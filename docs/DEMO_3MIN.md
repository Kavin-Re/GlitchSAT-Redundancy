# 3-minute stage demo (zero typing)

built from `docs/wow/DIAL_NOTES.md` (P40), `docs/wow/THEATRE_NOTES.md` (P21) and `docs/wow/WALL_NOTES.md` (P24). License: Apache-2.0. GlitchSAT. Toy designs, modelled single-tick bit flips, nothing physical, nothing established as new.

**Timings are ESTIMATED and UNPILOTED**: nobody has spoken this script aloud with a clock. The owner should time it once and cut words, not beats. The longer version with live commands stays in `docs/report/DEMO_5MIN.md`.

## Before you go on (2 minutes, off stage)
Open four tabs in one browser window, in this order, then press F11 (full screen). Switch tabs with Ctrl+1 to Ctrl+4; nothing is typed on stage.

| tab | open | prepare |
|---|---|---|
| 1 | `docs/wow/dial.html` | Press **F** (big screen) and **P** (predict first). The dial starts on V2, whole word, stored, pins no, known power-up. |
| 2 | `docs/wow/theatre.html` | Leave it on step 1. Keys: Space next, Left back. |
| 3 | `docs/wow/wall.html?stage=1` | Press Space once, so it rests on step 2 (grey tiles, no verdicts yet). |
| 4 | `docs/comms/staircase.png` | Only for a communications audience; otherwise skip the last beat. |

Every digit on these pages is a copy of a measured row (MEASURED) or a replay of one (SIMULATED); "not measured" means nobody ran it.

## The script (estimated 3:00 in total)
| time | beat | do | say (first person, plain words) |
|---|---|---|---|
| 0:00 | Dial, opener (0:20) | Tab 1. Digit hidden. | "This toy lock checks the key three times. A flip is one modelled glitch: one bit wrong for one clock tick. Before I show you: how many flips does it take to open it with the wrong key? One, two or three? Shout it." |
| 0:20 | Dial: 3 (0:15) | Press the room's guess, then **R**. | "Three. A solver found no attack with fewer than three flips, looking up to 6 ticks, on the stored netlist. That is as far as we looked, not 'safe'." |
| 0:35 | Dial: 2 (0:20) | Build -> **Re-built**. Ask, press the guess, **R**. | "Same design text, built again with the plain recipe of the same Yosys version. Now it is two. The build left two shared wires that move the bits that matter." |
| 0:55 | Dial: 1 (0:15) | Reader -> **Accept flag**. Ask, guess, **R**. | "Now I ask who reads the answer. If the next block reads the one-wire accept flag, it is one flip, whatever the three copies do." |
| 1:10 | Dial: 0 (0:15) | Power-up -> **Any**. Ask, guess, **R**. | "And if the lock may wake up in any state, it can wake up open. Zero. The toy has no reset. Same lock, four questions: three, two, one, zero." |
| 1:25 | Theatre: V1 (0:20) | Tab 2. Space (step 2). Point at the red wire. | "Here is one of those answers happening. This is the solver's own witness, replayed in a gate-level simulation. The two-copy lock: both checks say no, but both feed this one wire. One flip at tick 1, and one tick later the lock reads open." |
| 1:45 | Theatre: V2 (0:25) | Space (step 3). Point at the green box, then the red strips. | "The three-copy lock: the solver looked at 456 places a flip could go and found no attack with one or two flips within 6 ticks. With three it does: one wire per copy, all at tick 1. Replayed: it opens." |
| 2:10 | Theatre: flag caveat (0:15) | Space (step 4). | "One caveat. If the next stage reads only the accept flag, the solver needs one flip again: the flag wire itself. The reader is a wire too." |
| 2:25 | Wall: one reveal (0:20) | Tab 3. Space once (verdicts). | "Last: I gave the same design file to 264 synthesis settings. They built 152 different netlists. Twenty still need three flips; 94 open with one. Same blueprint, different builders. This effect is not new: SYNFI showed it before us." |
| 2:45 | Staircase, comms audience only (0:15) | Tab 4. | "For the coding people: the state words are a textbook code. With only the stored bits attackable, the flips needed follow the code distance; once every wire is attackable, the cost stops at about one flip per copy. A code protects the codeword, not the circuit that reads it." For a general audience, say instead: "Toy design, modelled flips, nothing physical; every number on these pages names its source." |
| 3:00 | end | | |

Beat lengths: 0:20 + 0:15 + 0:20 + 0:15 + 0:15 + 0:20 + 0:25 + 0:15 + 0:20 + 0:15 = 3:00 (ESTIMATED).

## Honest labels you must keep saying
- "Measured in a model", "no attack found with fewer, up to 6 ticks", "modelled flip". Never "safe", "secure", "proves", "glitch a chip", "first" or "new".
- Stored and re-built are both Yosys 0.33; they differ in source and recipe, not in tool version (`docs/report/WHY_TWO_FLIPS.md`).
- The theatre's waveforms are parsed from the simulator's VCD; the two small schematics are hand-drawn ("simplified diagram").
- The wall's "3" means no attack was found with 2 or fewer flips within 6 cycles; the 264 settings are one grid on one design, not independent experiments.

## If a page fails
- **Page blank or frozen:** go to the next tab and say the number from this script (the wall's headline, counts and caveats are static text, so it still reads correctly with JavaScript off; the dial and theatre need JavaScript).
- **Dial keys do nothing:** click a switch with the mouse; guesses can be skipped (press **R** only).
- **Theatre keys do nothing:** use the on-screen Step button or the buttons 1 to 5.
- **Wall does not step:** a button has focus; click the page background, or press the "Next" button.
- **Browser gone:** show the screenshots: `research/c6/p40/shots/1366_light_big.png` (dial), `research/c6/p21/shots/step2_1366.png` to `step4_1366.png` (theatre), `research/c6/p24/shots/wall_1366_stage3_verdicts.png` (wall); or the deck slides on the dial, the replay and the wall (`docs/report/SLIDES.pdf`).

## 10-minute booth loop (unattended, with a person nearby)
Kiosk query strings (both tested by their checkers in headless Chrome only, not on a real booth screen):
- Screen A: `docs/wow/theatre.html?kiosk=1` (auto-plays the five steps and loops).
- Screen B: `docs/wow/wall.html?kiosk=1` (steps change every 7 s; add `&theme=dark` in a dark room).
- Tablet or laptop for visitors: `docs/wow/dial.html` with predict first on (press **P**); let them guess before they reveal.

With one screen only: alternate the two kiosk tabs by hand about every 5 minutes (no page switches tabs by itself). A loop of 10 minutes for the person at the booth:
| minute | screen | say to a visitor who stops |
|---|---|---|
| 0 to 5 | theatre kiosk | "Two checks on one wire behave like one check: watch the red flip open the left lock." |
| 5 to 10 | wall kiosk | "Same design, 152 builds; colour = flips needed. Most open with one." |
| any | dial tablet | "Guess first, then reveal. Every digit names its source row." |

The "Beat the Solver" game (P23) does not exist yet; `docs/wow/game.html` is the older game.
