# WP3 report: six new simulated personas (P13 to P18), round 3
All six readers are SIMULATED; none is a real person. Simulated readers tend to be too kind; I tried to be harsh, but every score below is ILLUSTRATIVE, not measured human data, and "seconds to aha" is a model's guess.

Pages read: docs/explainers/explainer.html, game.html, poster.md, script_60s.md (and PROCESS_RULES.md for rules). Nothing else.
Method: Playwright with /usr/bin/google-chrome, screenshots at 390 px and 1366 px (this folder: expl_*.png, game_*.png). No horizontal overflow at either width (scrollWidth equals viewport), no console or page errors.
Actually clicked (390 px): explainer hero button (door opens, "1 flip"); "own wire" button x4; Twist picker switched to Wiring B with 3 "next wire" clicks (reaches DOOR OPEN with 2 flips); count toggle "Count 1 per light it feeds" (text changes to "same as Wiring A"). Game: all 6 designs played to LOCK OPEN, including wrong-order taps (a guard first in the joined designs: "Still shut after 1 flip ... joined wire stays no", correct), over-flipping (3 flips on the 1-flip designs says "fewest possible here is 1", correct), "Show fewest flips", Reset. Results cards match the explainer table (1,1,1/not checked,3,3,2).

## Visual and behaviour defects seen (shared by all personas)
1. Explainer at 390 px is about 5200 px tall (nine screens). The story is long for a bus.
2. The blue quote box (the quotable sentence) is 6 lines at 390 px and sits above the lock; the first tappable button is below the fold on a 844 px phone (about 1.1 screens down).
3. In the game, the "Three guards, one shared wire" design shows "Computer check: not checked" in the same card list as measured rows; correct but a lay reader sees a gap and asks why.
4. Game design 0 draws a fan of 8 dashed red lines to 8 lights; fine on desktop, busy on phone. The 6 tab labels wrap to 3 rows of 2 at 390 px; "Rebuilt: Wiring A" vs "3 guards, own wires" are visually near-identical designs (the page says so, but the first-time player cannot tell why both exist).
5. Hint text in the game after a wrong tap on the "Rebuilt: Wiring A" design ("it looks like the one before. Is it the same?") gives no information to a novice.
6. The game offers no score or goal number up front ("use as few as you can" but not "can you beat 3?"), so a successful round ends flat.
7. The "Evidence for engineers" block is dense but collapsed on phone, open at 900 px and wider: good.

## P13: 60-year-old taxi author, smartphone, little patience
- Seconds to aha (simulated): about 35 (needs to scroll past the quote and header, then press the button; the red "One flip. Three guards beaten" lands at once).
- Own words: "A door has three guards but they all talk down one wire, so tricking the wire fools all three. Give each guard his own wire and you need three tricks. Something about building it differently making it weaker, I lost that."
- Confused: "flip", "netlist-style" nothing, but "building program", "joined wire", "Count 1 per light". The Twist section was where he gave up reading; he went to the game and tapped round things.
- Visual: the yellow banner and the quote look like adverts at first; small grey text.
- So what: partly. He thinks "a backup is not a backup if they share a thing", which is useful. The quotable sentence was read as too long to repeat.
- Would tell: "Three guards on one wire is one guard."
- Understood 7, would tell 5.

## P14: secondary-school physics teacher
- Aha: about 20 s (hero button; maps to a shared-resource / common-mode idea he knows from circuits).
- Own words: "A lock with three redundant checks fails as one if they share a single point of failure. Separate paths give you three. The twist is that an automatic tool rebuilt the same design and merged wires, so the apparent safety changed, and whether you call that 2 or 3 depends on how you count a fault."
- Confused: "flip for one moment" is fine; "building program" should say "synthesis tool" for him. Liked the 3 worked and 2 did not note. Would like the cards to say what is measured in plain terms.
- Visual: none serious; SVG text small at 390 px. Game usable with a thumb.
- So what: worked ("ask where the copies meet" is classroom-ready). The "three signatures = one approval" line he would use verbatim.
- Would tell: "Three guards that share one wire are one guard; ask where the copies meet."
- Understood 8, would tell 8.

## P15: venture investor, ten minutes
- Aha: about 25 s on the explainer; but his own "so what for me" took until the poster text, and never fully arrived.
- Own words: "A toy model where redundancy that shares a wire gives no extra safety, and the way a design tool synthesises it changes the result 3 vs 2. Interesting academic point; heavily caveated; no product, no customer, no market."
- Confused: who is it for ("anyone who has been told 'we have a backup'" is generic); no stake, no number he can put in a deck beyond "1 vs 3 flips". The caveat wall ("nothing physical, no real product, licence undecided") reads as nothing to buy. He also noticed the headline claim ("no safer than one guard") is stated for a hand-drawn toy in the first picture, not a measured design; only in the evidence block does it say that picture has no solver run.
- Visual: none.
- So what: the intellectual one landed; the commercial one did not (and is not the page's aim). The quote is hedged enough to be forgettable.
- Would tell: "Redundancy only counts if the copies don't meet; some tool results flip on how you count." He would not forward it.
- Understood 8, would tell 5.

## P16: software tester who does not know chips
- Aha: about 15 s (this is common-mode failure / single point of failure, which he knows from test strategy).
- Own words: "Three checks that all write into one shared variable are one check. Separate outputs fix that. Then the same logic compiled differently merged outputs, so the minimum fault count dropped from 3 to 2, unless you count each affected output separately."
- Confused: the game feel; what "light" stands for; why the "accepted" flag falls to 1 flip (he found this in the caveat and thought it undercuts the story: "so the lock's actual decision is easier to break than the answer?"). He noticed the page admits this, which he rated as honest but confusing.
- Visual: after a wrong tap the status text is clear and helpful; the 6-tab selector is crowded.
- So what: worked. Quotable sentence worked for him ("how you count a fault changes who looks safe" is like how you count a bug).
- Would tell: "Three checks on one wire are one check; and how you count the fault decides which build looks safer."
- Understood 8, would tell 7.

## P17: nursing student, on a bus, phone, interrupted
- Aha: about 40 s (first screen has no picture; the hero needs scrolling; the bus jolts, small tap targets for wires in the game).
- Own words: "Three guards sharing one wire are really one guard. Give each one their own wire. Then something about building it two ways, I think the lesson is check the wiring."
- Confused: "flip", "netlist" absent which helped; the Twist and "Why the counting matters" were two screens of abstraction she skipped. Lost her place after an interruption (no progress marker).
- Visual: long page; game wire circles (about 48 px) fine; tab buttons fine; text size ok.
- So what: she got a medical analogy herself: "three nurses signing one form". The quotable sentence was too long to remember; the "three people sign with one shared signature" line was the one she kept.
- Would tell: "Three people who sign with one signature are one approval, not three."
- Understood 7, would tell 7.

## P18: electronics lecturer from another institution, expert hunting for overclaims
- Aha: about 10 s for the premise, which he already knows (common-mode, shared net, fanout).
- Own words: "A bounded SAT-style fault search on a small netlist finds a 1-flip break when redundancy shares a net. Re-synthesis changes the minimum from 3 to 2 depending on tool and flow, which is an artefact of the fault model's per-net counting. Fine as an illustration; the headline sentence is stronger than the evidence."
- Claims that overreach or mislead:
  1. Headline quote: "three backup guards that share one wire were no safer than one guard". Supported only by a hand-drawn toy computed on the page (ILLUSTRATIVE), not by any project design: the "3 guards, 1 wire" design has "no solver run". The quote says "In a small computer model" which blurs toy vs solver. A reader cannot tell which parts are measured without opening the evidence block.
  2. "needed 3 flips one way and 2 the other" is presented as a property of the design and tool; the page itself notes in evidence that 26 of 32 variants needed 2 and 6 needed 3 (by another step, not re-run), and that conda was not run for the opt flow. The headline pair is one example each; "builder joined some wires" is the page's explanation but "which exact bits are covered is UNVERIFIED". The mechanism sentence is stronger than the evidence.
  3. "Wiring B ... the two joined wires cover all 8 lights" is a simplified drawing; the page admits UNVERIFIED, but the figure shows it as fact in the main story.
  4. "Count each wire once and B looks weaker; count per light and the two look the same": the 3 comes from an step experiment not re-run here; and "who looks safe" implies a fault-count convention dispute that no one in the literature is cited for. Fine as a framing; it should say "no rule is argued to be the physical one" in the main text, not only the evidence block.
  5. "Computer check = MEASURED" for results up to 3 flips and 6 cycles, one constant attacker input, goal = result word only. Stated, well. But "3 worked and 2 did not" is understandable only if you read the legend.
  6. Silent on whether the 1-flip result for shared nets is physically meaningful (single-cycle bit flips on a net are a model, not glitches); the page says "faults are modelled bit flips" in evidence only.
  Not claimed, to its credit: first/novel, security of any product, physical results.
- Visual: fine.
- So what / quote: the quote overreaches slightly (see 1); the take-away "where do the copies meet?" is correct and he would quote it.
- Would tell (to students): "Redundancy only helps where the copies don't meet; and how you count a fault on a shared net changes the ranking."
- Understood 8, would tell 7.

## Scores
| Persona | Aha (s, simulated) | Understood | Would tell | Both >= 7? |
|---|---|---|---|---|
| P13 taxi author | 35 | 7 | 5 | no |
| P14 physics teacher | 20 | 8 | 8 | yes |
| P15 investor | 25 | 8 | 5 | no |
| P16 software tester | 15 | 8 | 7 | yes |
| P17 nursing student | 40 | 7 | 7 | yes |
| P18 expert lecturer | 10 | 8 | 7 | yes |

## Verdict
Gate (at least 5 of 6 with 7+ on both): NOT MET (4 of 6). Failures are on "would tell", not "understood". The page teaches well (all six reach 7 or 8 understood) but the quotable sentence is too long and hedged for a layperson to repeat (P13, P17) and offers no stake for a decision-maker (P15). All numbers are simulated opinions, so treat the gate failure as a hint about where the weakness is, not a measurement.

## Top three fixes
1. Make the quotable sentence short and put it first: "Three guards on one wire are one guard." (and "Ask: where do the copies meet?") above the long hedged quote; move the hedged version into the caption. Make the headline quote say plainly that the 3-guards-one-wire case is a toy picture and that the 3 vs 2 result is the measured part (fixes P13, P17, P18 point 1).
2. Add an early "so what" line for a decision-maker without overclaiming: one sentence on what to ask a supplier ("where do the copies meet, and how do you count a fault?") with a button or anchor to the game, so the page ends with an action, and show the hero button above the fold on a phone (fixes P15, P17).
3. Shorten the phone path: collapse the Twist and "Why the counting matters" behind a "Skip to the game" link and a position marker; label the fig "toy picture, not measured" next to the first picture; fix the near-useless Wiring A hint and show a target ("beat 3 flips?") in the game (fixes P13, P17, P18, defects 1, 5, 6).
