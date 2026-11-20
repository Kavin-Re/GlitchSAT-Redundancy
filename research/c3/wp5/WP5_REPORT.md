# WP5 report: wow persona test, round 5 (final)
Working title TBD. Licence: UNDECIDED.

**All six readers (P25-P30) are SIMULATED by a language model. None is a real person. Simulated readers lean kind; I tried to be harsh, but treat every score as an optimistic upper bound, and every "seconds to aha" as a guess (UNVERIFIED), not a timing.**

## What I actually did (MEASURED by script, research/c3/wp5/run.py, game.py, shots/)
- Rendered docs/wow/explainer.html and game.html in headless Chrome (playwright, /usr/bin/google-chrome) at 390 and 1366 px; screenshots in research/c3/wp5/shots/.
- Clicked: hero button (state text went "NOT flipped. Door shut." to "FLIPPED. Door open.", aria-pressed true, drawing changed); wiring tabs Wiring A/B, "Flip the next wire" x3, "Show the fewest flips", "Start over"; counting switch (after opening the collapsed "Why the counting matters" box; 1-per-wire gives "needs only 2 flips", 1-per-place gives "3 flips, same as A"). No JS errors, no horizontal overflow at either width.
- Game: played "2 guards, 1 wire" with a wrong tap (a guard: "Still shut after 1 flip"), a second guard tap (opened after 2 flips, par 1, told fewest is 1), a third tap ("You flipped every wire and the lock still holds ... Flips can cancel"), Reset, then "Rebuilt: Wiring B" (2 taps, opened, par 2, matched), "Show fewest flips". Works.
- Layout facts: page is about 5450 px tall at both widths; supplier box starts about 1040 px down at 390 px (about 780 px at 1366, in the first screen of scroll); buttons 48-64 px tall (fine for thumbs); smallest text 13 px; the engineer box is closed at 390 px, open at 1366 px.
- Word counts: script_60s.md body is 236 words (about 90 to 100 s at normal speaking pace, not 60 s); poster.md is 323 words.

## Persona results

### P25 street-food vendor, old phone, cracked screen, spotty data (SIMULATED)
- Seconds to aha: about 25 (hero picture plus "Flip the shared wire"; the first screen at 390 px shows the whole drawing and the big blue button).
- Own words: "Three guards but they all tell one wire, so if that wire lies the door opens. Giving each its own wire is safer. Something about it being a pretend model."
- Confused: "flip", "wire saying the wrong thing for a moment" took two reads; everything below the hero (twist, counting, 32 rebuilds, "result word", "accept flag") lost them by the second screen; "" banner reads as "is this real?".
- Visual defects: the cracked-screen reader said the thin dashed lines and the small grey "toy picture" pills are hard to see; the yellow top banner takes about 70 px of a small screen; 5450 px of scroll is long on data that is spotty (page itself is one file, so fine offline, which they liked).
- Quotable sentence / supplier box: the "three people signing with one shared signature" line is far down and they never reached it; supplier box seen only by scrolling, and "redundant copies" is not their word. Box did not work for them.
- Would tell: "If three guards all report to one wire, it's really one guard."
- Scores: understood 6, would tell 7.

### P26 retired civil servant, reads every word (SIMULATED)
- Seconds to aha: about 40 (reads the banner, the boxed "Model only" note, then clicks).
- Own words: "A lock with three guards sharing one wire fails with one fault; separate wires need three. The same design built two ways needed two or three faults depending on how the builder joined wires, and how you count changes the answer. It is only a small computer model, not a real product."
- Confused: the same caveat ("result word only; the accept flag itself falls to 1 flip") is repeated about ten times and, to a careful reader, undercuts the "fix" section: "if the accept flag falls to 1 flip, what exactly was fixed?" Terms "result word", "accept flag", "8 lights" are introduced in different places. "3 worked and 2 did not" took a re-read.
- Visual defects: none blocking. Counting switch is hidden inside a collapsed box at 390 px (a reader skimming never finds it); two labels on the same line (toy pill + measured pill) are visually near-identical in weight.
- Quotable / supplier box: both worked. The supplier box is clear and the Good/Worrying pairs are usable as a checklist. They would print it.
- Would tell: "Ask the supplier where the backup copies meet, how they count a fault, and what was checked at the end."
- Scores: understood 8, would tell 8.

### P27 hardware security researcher (SIMULATED expert)
- Seconds to aha: about 15 (knows the common-mode / voter single point of failure; hero is a restatement). Real interest starts at the 2-vs-3 flip counting result.
- Own words: "A TMR-style design with a shared voter or shared net is one fault, which is old news. The interesting part is that resynthesis of the same RTL gives min-fault 2 or 3 depending on the netlist, and the answer flips on whether a fault on a fan-out net counts once or per pin, with no check of which is physical. All of it is bounded model checking on toy 8-bit designs, goal is the result word only."
- Claims that still overreach, are mislabelled, or are easy to misread:
  1. "Copies only help if each one has its own road to the door" (hero box): an unlabelled universal statement. The measured support is V1 (two checks, shared wire, 1 flip = V0). The supplier box itself says a shared place can be "protected on its own", which contradicts "only help if".
  2. "The fix ... Now it takes 3 flips" is the headline of a section whose own caveat says the accept flag, the output an attacker would more plausibly target, falls to 1 flip. The caveat is present but small and after the claim. The measured goal choice dominates the story; "fix" is too strong a word for something that fixes the 8-bit word only.
  3. Wiring A is captioned "every guard keeps its own wire" next to a measured 3. The measured thing is only "min 3 flips on the conda 83-gate netlist"; nothing cited says guards remain structurally separate after synthesis. That caption is a toy/structural claim sitting in a measured slot.
  4. "Three guards, one shared wire" (the headline picture) is toy only, and the hero says "Three were not run". Good. But the spoken script says "One flip beats all three" and "three guards on one wire are really one guard" with no toy label in the line; spoken, the label is lost.
  5. The "Good answer / Worrying answer" lists in the supplier box are guidance, not a result: nothing shows suppliers' answers correlate with security. It is labelled "Drawn from a small model; tests no supplier" but the Good/Worrying framing implies validated criteria.
  6. "Count 1 per place it feeds" is the project's own per-pin model (gate input, flop input, output bit), not "place"; two counting models out of many, neither shown physical (that part is disclosed well). Branch-level flips untested is disclosed only in the engineer box.
  7. Game "Par" for toy designs is computed on a drawing; for "3 guards, 1 wire" it looks like a number from the project; the cards do separate toy and measured. Mostly fine. "A bigger number of flips is better for whoever builds the lock" is a general claim; more flips is not always cheaper or better overall.
  8. "Tested by simulated readers" appears; nothing else overclaims novelty. Good.
- Visual defects: engineer box closed on phone; the mapping table is dense but acceptable.
- Quotable / supplier box: quotable sentence is fine, box good; they would add "and show me the netlist after synthesis".
- Would tell a colleague: "Where do the redundant copies meet, and does your fault count change if you count a fan-out net per pin?"
- Scores: understood 9, would tell 7 (would tell only the second half; the three-guard headline they consider textbook).

### P28 procurement lawyer (SIMULATED)
- Seconds to aha: about 35.
- Own words: "A small computer model suggests that backup copies sharing a single point do not add protection, and that the way you count a failure changes the number. It is not a test of any product. It gives me three questions for a supplier."
- Confused / concerns: who stands behind the numbers ("", "Licence undecided", "Working title TBD") reads as unfinished; "the sources we read" is vague; they would not cite it. The Good/Worrying answers invite being used as pass/fail criteria in a tender, which the page itself says it does not support. Wants one explicit line: "not a standard, not for contract terms".
- Visual defects: none. Dashed boxes with disclaimers are readable.
- Quotable / supplier box: the box worked best for them: three plain questions, each with an observable good/worrying answer. Would paste it into a questionnaire as a prompt for the supplier to explain, not as a scored criterion.
- Would tell: "Ask where the redundant copies meet, how a fault is counted, and what is checked at the end: the finished wiring, not only the plan."
- Scores: understood 8, would tell 7.

### P29 high-school student presenting to a class tomorrow (SIMULATED)
- Seconds to aha: about 12 (hero button is a satisfying click).
- Own words: "If three guards all report through one wire, hacking that wire beats all three. Building each guard its own wire needs three hacks. But how the wires get built changes it to two, and nobody knows which counting is real."
- Confused: "flip" vs "hack"; "result word" and "8 lights". Does not know what a netlist or Yosys is (they skipped the engineer box).
- Defects: the "60-second script" is 236 words, which runs about 90 to 100 s when read aloud; they would run over. The script says "Show explainer.html while speaking" but gives no cue for when to click the button. The one-page poster is 323 words, too dense to read from a distance. The game works well: right tap, wrong tap and Reset were obvious; the "flips can cancel" message after tapping all wires is confusing for a first-time player.
- Quotable / supplier box: "Three people signing with one shared signature are one approval, not three" is the line they would use in class; the supplier box is too grown-up for their audience.
- Would tell: "Three guards that all send their answer down one wire are really one guard."
- Scores: understood 8, would tell 8.

### P30 cardiologist, other field, impatient (SIMULATED)
- Seconds to aha: about 10 (maps it straight to a shared lead or shared power supply failing three redundant monitors).
- Own words: "Redundancy fails if the copies share a single point. A computer simulation of small chip designs shows one design needed 2 or 3 faults depending on how it was built. Only a simulation, not a real device."
- Confused: "flip", and everything after the hero (they stopped at the supplier box). The twist section takes too long; wanted a single sentence: "same design, rebuilt, was weaker or stronger."
- Defects: first screen is a banner plus a skip link plus the title; no one-line summary above the fold at 390 px except the title. At 1366 px the hero fits one screen, which is good.
- Quotable / supplier box: the "three signatures" sentence worked and is the line they would repeat to a colleague; the supplier box is applicable ("where do the redundant copies meet") to device vendors, but they would not use "fault counting" wording.
- Would tell: "Backups that share one point are one backup; ask where they meet."
- Scores: understood 8, would tell 8.

## Summary table (SIMULATED scores)
| Persona | Aha (s, guess) | Understood | Would tell |
|---|---|---|---|
| P25 street-food vendor | 25 | 6 | 7 |
| P26 retired civil servant | 40 | 8 | 8 |
| P27 hardware security researcher | 15 | 9 | 7 |
| P28 procurement lawyer | 35 | 8 | 7 |
| P29 high-school student | 12 | 8 | 8 |
| P30 cardiologist | 10 | 8 | 8 |

## Gate: at least 5 of 6 with 7+ on BOTH
5 of 6 pass (P26-P30); P25 fails on "understood" (6). **Gate: PASS, narrowly.** Caveats: simulated readers, which run kind; a single point lower for P27 or P28 would flip this to FAIL; P25 is the closest model of a real low-literacy, small-screen reader and he did not get past the first screen. Real-person testing has not happened.

## Verdict
The hero (button plus drawing), the supplier box and the "three people signing" line work across all six simulated readers, and the click paths (hero, wiring, counting, game rounds) function without errors at both widths. The measured-vs-toy labelling is now good enough that an expert reader finds only a few residual overreaches (list under P27). Readers below the hero fade quickly; the pages are strongest in their first screen and weakest as one long 5450 px page.

## Top three remaining fixes
1. Rename or soften "The fix" and make the accept-flag caveat part of the heading line itself ("Fix for the 8-light answer only: 3 flips; the accept flag still falls to 1"); delete or qualify "Copies only help if each one has its own road to the door" (contradicts "or that place is protected on its own"); caption Wiring A as "3 flips measured" without asserting guards stay separate; add a toy label to the spoken "One flip beats all three".
2. Make the first screen at 390 px carry a one-sentence takeaway and the "three people signing one signature" line (currently far down), and shorten the page for phone users (about 5450 px; open the counting switch by default or give it a visible link). Define "flip" with a plain synonym once and use "8 lights/result word/accept flag" with one consistent glossary line.
3. Fix presenter assets: script_60s.md is 236 words (about 90 to 100 s), trim to about 150 words or rename to 90 seconds and add a click cue; trim the poster (323 words) or label the one-glance part; add one explicit line that the supplier questions are prompts for a conversation, not a pass/fail or contractual standard, and soften the game's "flips can cancel each other" message shown after tapping every wire.

Not done: no real people, no real-device test (physical phone, slow network, screen reader), no timing of actual reading. All reader quotes are model-generated.
