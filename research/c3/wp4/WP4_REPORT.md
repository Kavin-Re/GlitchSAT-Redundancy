# WP4 report: round-4 persona test (P19 to P24)
Working title TBD. License: UNDECIDED.

**All six readers are SIMULATED by a language model. None is a real person. Nothing here is user research.** Simulated readers lean kind; I tried to be harsh, but treat every score as ILLUSTRATIVE, not MEASURED.

## What was actually run
Pages read: docs/wow/explainer.html, game.html, poster.md, script_60s.md (plus the rules file). No earlier reports read.
Method: headless Google Chrome via Playwright (`research/c3/wp4/drive.py`, log `research/c3/wp4/drive_log.txt`), viewports 390x844 and 1366x800, screenshots in `research/c3/wp4/shots/`.
Clicked: hero button (x2), wiring A/B toggle, "Flip the next wire" x3, "Show the fewest flips", Start over, counting switch (1 vs per place), evidence drawer, and in the game all 6 designs: tapped every wire in order (wrong and right taps), Reset, "Show fewest flips". Results: no console or page errors; no horizontal overflow at 390 or 1366; every game state matched the cards (par 1,1,1,3,3,2); wrong-tap messages were sensible ("Still shut after 2 flips", "opened after 3 flips; fewest is 1", "flips can cancel").

## Objective defects found (these are real, from the renders, not simulated opinion)
1. **Mobile hero: the button is above the figure and the figure is mostly below the fold.** At 390 px the button sits at y=451-499 and the drawing starts about y=735. Tapping it changes nothing the reader can see without scrolling. The reaction ("DOOR OPEN") is further down. This hurts the "aha".
2. **The red box "One flip. Three guards beaten." is shown before the reader does anything,** and while the drawing still says DOOR SHUT. It gives away the punchline.
3. **Hero state is ambiguous.** The page auto-plays; my first click left the figure at "no / DOOR SHUT", the second gave "YES / DOOR OPEN". The button label never changes, so a reader cannot tell whether they opened or closed the door.
4. **Game on mobile: the score ("Flips used / Par"), hint and status sit below the 450-high drawing,** so while tapping wires the feedback is a screen away.
5. **Results box "Original wiring 3 flips / Wiring A / Wiring B" carries no MEASURED tag on the rows;** the label is in a note below. "Original wiring" is never defined on the page.
6. **Game: the three "own wires" tabs are trivial** (any three taps win). Only tabs 2 and 3 involve a mistake, and their hints say where to tap.
7. Poster and card text cite repo paths (results/reproduce_summary.json) that a lay reader cannot open.

---
## P19: market stallholder, cheap phone, cracked screen (SIMULATED)
- Seconds to first aha: about 40 (mobile; the button is visible but the figure is not, so she scrolls, taps, then understands). Cracked top-left corner hid part of the "SKIP TO THE GAME" link only.
- Own words: There is a lock with three guards. They all pass their answer through one wire, so if you mess with that wire the door opens. The fix is one wire each.
- Confused by: "flip" (took it as flipping a coin until the line "a wire saying the wrong thing"); "wiring A/B", "rebuilds", "clock ticks"; the page after the hero is long and mostly grey small print. Gave up before the twist.
- Visual defects (390 px): small-print tags (the pill labels) are hard to read at her brightness; the drawing is below the button.
- Quotable sentence ("Three guards on one wire are really one guard"): worked for her. Supplier box: she read it, said "I would not know who to ask," but liked "where do the copies meet".
- She would say: "If three guards all report down the same wire, you've only got one guard."
- Understood 6, would tell 6.

## P20: secondary-school maths teacher (SIMULATED)
- Aha: about 20 s on desktop.
- Own words: It's a fault-tolerance argument in disguise: redundancy is worthless if the copies share a single point of failure. The count of faults needed depends on how you define "one fault". The game lets you search for the smallest set of flips.
- Confused by: "par" (golf term, unexplained for non-golfers); "defender" appears once in the glossary and is not used again; the 2-vs-3 result is hard to follow because the real quantity, "fewest faults to defeat", is never said as a sentence with units. Liked that flips can cancel, which is a good teaching moment, but it is only visible after tapping everything.
- Visual defects: none at 1366; at 390 the game figure and score separation (defect 4).
- Quotable sentence: worked, "like a series circuit". Supplier box: worked as a checklist but she would add an example answer for each question.
- She would say: "Backup copies don't count as extra protection if their answers get merged into one wire."
- Understood 8, would tell 7.

## P21: hospital IT manager who buys equipment (SIMULATED)
- Aha: about 15 s. The "ask a supplier" box is what he scrolls to first.
- Own words: When a vendor says "redundant", ask where the copies join, how they count a fault, and what was checked in the final design. This is a small computer model, not a test of any product. The twist is that different builds of the same design look stronger or weaker depending on how you count.
- Confused by: "How do you count a fault?" is too abstract to put in an RFP; "what is checked at the end... which output" has no plain example. He would want a one-line "good answer / bad answer" for each question. The 2-or-3 table is irrelevant to him.
- Visual defects: the supplier box is directly under the hero button, which is good; on mobile it is below a long hero.
- Quotable sentence worked. Supplier box worked as three bullets, partly; question 3 weakest.
- He would say: "Ask the vendor where the backup copies actually meet. If it's one wire, it's one backup."
- Understood 8, would tell 7.

## P22: hardware engineer at a chip company (expert, hunting overclaims) (SIMULATED)
- Aha: 10 s (he knew it). Then 10 minutes on what he does not accept.
- Own words: A drawing showing a shared voter/AND net defeats replication, which is textbook (a single point of failure). The "measured" part is a bounded SAT/SMT search over a modelled bit-flip fault set on small resynthesized netlists, and the 2-or-3 split depends entirely on whether a net with fanout counts as one fault. That is a statement about the fault model, not about hardware.
- Confused by: nothing technical; annoyed by the mix of toy and measured in the same cards.
- Visual defects: none.
- **Claims that still overreach or are mislabelled toy vs measured:**
  1. **Headline "Three guards on one wire are really one guard" is stated as a general fact and used as the poster title, but is a TOY (ILLUSTRATIVE).** The nearest MEASURED result is two checks (V1) into net `ok`, 1 flip equal to one check. The page says "Three were not run" in tiny print, below the pink box that says "One flip. Three guards beaten." in bold.
  2. **Pink box "One flip. Three guards beaten." is a claim of result, sits above the TOY tag and is shown before the action.**
  3. **"Copies that end in one shared point count as one."** (supplier box) is a rule asserted without a label, and is only true under the single-flip fault model chosen.
  4. **Game card "Three guards, one shared wire": In this game 1 flip, Computer check "not checked"** is correctly marked, but the game's par value for this tab ("fewest is 1") is presented like the others in an identical card format.
  5. **Wiring B drawing and game tab: two wires X and Y fan out to all 8 lights, and the hint says "Flip both".** The page itself says which lights are covered is UNVERIFIED, but this is one small italic note under the figure (in the game, in the evidence drawer). The card then places "In this game 2 flips" beside "Computer check 2 flips" as if the toy reproduces the measurement. It reproduces only the number 2.
  6. **"Wiring A: every guard keeps its own wire" / "Rebuilding changed nothing in this case."** The measurement is a minimum of 3; that three guard-specific wires exist in the Yosys netlist is inferred from the minimum, not shown (the page text calls it a fact in the toggle caption).
  7. **"26 of 32 rebuilds ... replicated (every row matched)."** The 32 are 2 Yosys builds x 2 flows x 8 ABC settings of one design, not 32 independent designs. The replication shared the recipe list with the first run (admitted only in the evidence drawer). The visible results box says "replicated" with no such caveat. Also "Conda 0.38+92 was not run for the opt flow" is only in the drawer.
  8. **"Count it once per place it feeds: all 32 needed 3."** MEASURED, but "per pin" is a modelling convention chosen by the project; the page's counting toggle is a TOY and its closing line "all 32 rebuilds needed 3" sits in the same paragraph as the toy. The partial-branch flips were not tested, yet the toggle presents the two options as the whole space.
  9. **"Nobody has shown which counting matches real hardware."** A universal negative about the literature; the project cannot know this and its own rules say not to claim novelty. Rephrase as "we did not test this and did not find a source in our search" or drop.
  10. **Scope line: the result is for the 8-bit result word only; with the accept flag as goal the design fell to 1 flip.** This is stated, but only at the bottom. Above the fold, "Three guards ... 3 flips" invites the reading "the triplicated design needs 3 flips". The 2-or-3 headline contradicts the 1-flip result for the flag that actually gates acceptance. That should be near the 3-flips claim.
  11. **"Original wiring 3 flips" row** (spike netlist, hand-made) is shown as equivalent in kind to the resynthesized rows.
  12. The poster says "no tracking", "works offline": not an overclaim, fine. "Replicated, research/c3/rep/" in public copy is a file path, not evidence for a reader.
- Quotable sentence: "mostly works but is the thing I'd cut: it is a theorem-sounding sentence about a drawing." Supplier box: fine as questions; he would add "and the fault model you used".
- He would say (if he said anything): "Redundant copies that merge into one net are one point of failure, but the 2-vs-3 thing is just a fault-counting convention on toy netlists."
- Understood 9, would tell 5 (the TOY/MEASURED mixing and the unlabelled box stop him from forwarding it).

## P23: law student (SIMULATED)
- Aha: about 20 s; the "three people signing with one shared signature" line did it, not the hero.
- Own words: A safeguard that looks like three checks is only as strong as the place where they join. How you define "one fault" decides whether a design counts as safe. The authors limit what they claim to a small computer model.
- Confused by: "" banner and "License: UNDECIDED" make it feel unfinished as a source; she liked the scope box ("what we did and where it holds") as the best-written part. Wants a definition of "flip" before it is used. "Nobody has shown" would be a flag in a citation.
- Visual defects: none significant; the scope box is below the fold on mobile and she nearly did not reach it.
- Quotable sentence worked. Supplier box worked as a contract-clause checklist; she would phrase each as a representation and warranty.
- She would say: "Three signatures from one pen are one approval, so ask where the copies meet."
- Understood 8, would tell 8.

## P24: 15-year-old who likes games (SIMULATED)
- Aha: about 8 s on desktop (clicks the hero button, door opens); about 25 s on phone.
- Own words: You break a lock by flipping wires. If all guards share a wire, one flip wins; if each has its own wire, you need three. Some builds let you win in 2, which is the weird twist.
- Confused by: "par" (knows it from golf); no win effect except a line of text; on phone the score is off-screen so the game has no tension. The first three tabs are over in one tap; the "3 own wires" tab has no decision, any three taps win. No reward for finding the minimum; "Show fewest flips" removes the puzzle. The 2-vs-3 twist is better as a game than the guards.
- Visual defects: the phone layout (score below the drawing). The drawing's tap targets are fine (48px+).
- Quotable sentence: he would not repeat it; "really one guard" is a good line though. The supplier box meant nothing to him.
- He would say: "Three guards on one wire is really one guard, one flip and the door opens."
- Understood 8, would tell 7.

---
## Score table (all SIMULATED)
| Persona | Aha (s) | Understood | Would tell | Both 7+ |
|---|---|---|---|---|
| P19 stallholder | 40 | 6 | 6 | no |
| P20 maths teacher | 20 | 8 | 7 | yes |
| P21 hospital IT | 15 | 8 | 7 | yes |
| P22 chip engineer | 10 | 9 | 5 | no |
| P23 law student | 20 | 8 | 8 | yes |
| P24 15-year-old | 8 | 8 | 7 | yes |

## Gate: at least 5 of 6 with 7+ on both. Result: 4 of 6. **FAIL.**
Caveat: all simulated and probably too kind. A real stallholder would likely score lower.

## Top three fixes
1. **Fix the hero and the headline claim.** Mobile: put the figure above or beside the button (or make the button sticky and scroll the figure into view on tap). Remove or hide the pink "One flip. Three guards beaten." until after the flip, and give the button a state label ("Flip" / "Put back"). Retitle the page/poster so the headline is visibly a drawing ("In our picture, three guards on one wire are one guard"), or lead with the measured V1 fact (two checks, one shared wire, 1 flip, same as one check). That fixes P22's would-tell and P19's aha.
2. **Stop mixing toy and measured in one card/table.** Tag each row (In this game = toy; Computer check = measured, with scope "result word only, accept flag falls to 1 flip") including "Original wiring" and the "replicated" line (say: 32 = 2 builds x 2 flows x 8 settings, not independent). Put the "result word only; the accept flag falls to 1 flip" line next to every "3 flips" claim. Reword "Nobody has shown which counting matches real hardware" as a statement of what was tested here. Make the Wiring B "which lights are covered is unverified" note visible at the figure, not only in small print.
3. **Make the supplier box usable and the mobile game playable.** Add a one-line example good/bad answer for each of the three questions and a fourth ("what fault model did you use?"); define "flip" before first use and drop "par"/"defender" or explain them. Mobile game: put Flips used/Par/status directly above or sticky next to the drawing; make the "own wires" tab require a choice (for example a wrong tap that cancels) so it is a puzzle, and delay "Show fewest flips" behind a first attempt.

## Not done / limits
Simulated readers only; no real person, no screen-reader, no real cracked-screen or slow-phone test. I did not open the evidence drawer's cited files (out of scope) so claims about replication and counting are judged only on how the pages word them. Files: research/c3/wp4/WP4_REPORT.md, drive.py, drive_log.txt, shots/.
