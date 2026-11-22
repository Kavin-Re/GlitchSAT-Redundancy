# WP_REPORT: wow persona test, round 2

**IMPORTANT: every reader below is a SIMULATED persona. None is a real person. Simulated readers tend to be too kind, too articulate and too patient. These scores are ESTIMATED/ILLUSTRATIVE only; real people must repeat this test before any claim about comprehension.**

Method: pages docs/explainers/explainer.html and docs/explainers/game.html opened in headless Chrome (playwright; the bundled chromium shell was missing, so /usr/bin/google-chrome with --no-sandbox was used; no tracing), 390 px and 1366 px, deviceScaleFactor 1, full-page screenshots in this folder (explainer_phone.png, explainer_desk.png, game_phone.png, game_desk.png, plus *_phone_N.png crops). Also read poster.md and script_60s.md. Nothing else in the repo was read. I did not click through every state; I read the initial rendered state and the page text, so interactive-state problems may be missed.

## What the screenshots actually show (shared by all personas)
- Phone explainer (page 4085 px tall, no horizontal overflow): clean, large type, the first diagram (3 guards, "no", shared wire, DOOR SHUT) is clear and the big blue button is thumb-sized. Good.
- The first diagram's button label reads "Flip the shared wire / put it back": a slash label, slightly clumsy; on desktop it renders as a small button in a wide empty page.
- The Twist diagram loads already in the "bad" state (red YES, DOOR OPEN) before the reader has done anything; the reader sees a red alarm with no setup and must read the caption to learn this is "Wiring A, 3 flips". The Wiring A / Wiring B toggle buttons are small (about 70 px wide, ~36 px tall) and look like tabs, not like "pick which build to see".
- Desktop (1366 px): content is a ~390 px-wide column floating in the middle of a very wide page (text column about 50% of width, body text visually about 13 px in the downscaled view). Lots of empty margin; diagrams are small. Not broken, but under-uses the screen.
- Game phone: the eight "lights" are about 24 px dots with eight dashed lines fanning from one tiny point; the fan lines crowd the "the guard" label (lines touch it). Design buttons are text-heavy (two-line labels, "Same design, rebuilt: Wiring A"). Status box under the diagram has a tall empty green area. "Put the wires back" and "Show the fewest flips" are left-aligned small buttons.
- Game: "The lock opens when all 8 lights are lit" is a new rule not explained in the explainer (3 wires there, 8 lights here). The results table repeats "In this game / Computer check" six times, with labels ILLUSTRATIVE/MEASURED in small print at the end.
- "Evidence for engineers" is a collapsed section; its visible text extract was empty ("[]") in my probe, i.e. nothing a lay reader sees.
- Plain-text probe found no elements under 12 px; no overlapping other than the fan-line/label crowding noted.

---
## P7. Primary-school head teacher (woman, 50s, desktop at school office, between a parents' call and an Ofsted-style inspection; mood: wary, time-poor, thinks in safeguarding terms)
- Time to first aha (simulated): about 25 seconds, at "Three guards all say no. Door shut." then the red box. She maps it to "three people sign off but they all go through the same office door."
- Own words: "It's about a lock with three guards, but if they all report through one shared wire, one slip beats them all. Giving each guard their own wire fixes it. Then there's a surprise about how the builder wires it up that I didn't follow."
- Did NOT understand: what "flip" means in practice (she reads "a wire saying the wrong thing for one moment" as a rumour, not a glitch); why "joined wires" makes 2 flips; what "counting once per output it feeds" means; what this is FOR (is this about school IT? A door system?). "Final result word" is meaningless. "Wiring A/B" never tied to anything she knows.
- Visual: desktop column is narrow with huge margins; text a bit small. Twist diagram starts in a red alarm state and alarmed her ("is something broken?").
- Would tell someone: lukewarm. "There's a neat little page showing why having three safeguards is useless if they all go through the same single point of failure." (She'd say it about safeguarding, not chips.)
- Scores: understood 6, would tell 6.

## P8. Hospital procurement officer (man, 40s, laptop plus a tender spreadsheet open; mood: impatient, suspicious of vendor fluff, wants "so what do I buy or ask")
- Time to first aha: about 20 seconds at the first diagram, then a second one at "Ask: where do the copies meet?"
- Own words: "Redundancy is only real if the backups don't share a single path. The same design can pass or fail depending on how it's built and how you count faults. Ask the supplier where the copies meet."
- Did NOT understand: whether this applies to medical devices at all (page says no real product tested; the disclaimers make it feel like it says nothing to him); what "counting a fault" means; "the 2 becomes 3" feels like a sleight of hand. He wants a checklist question for a vendor and gets one line.
- Visual: nothing broken. The long "holds only if" list reads like legal hedging; he skims it.
- Would tell: a bit. "Ask your supplier one question about backup systems: where do the copies meet?" (He likes that line, it is the only usable thing.)
- Scores: understood 7, would tell 6.

## P9. Mechanical engineer (woman, 30s, hydraulics/structures; sceptical, reads on laptop, likes numbers; mood: "show me the method")
- Time to first aha: about 15 seconds. This is a common-cause failure / single point of failure, which she knows from FMEA.
- Own words: "Triple redundancy with a shared signal path has a common-cause failure; separate paths need three faults. Then a synthesis tool merged two nets and the minimum cut set dropped from 3 to 2, unless you weight a fault by fan-out. So the answer depends on the fault model."
- Did NOT understand: what the "design" really is (what is being protected? a counter? a lock?), what the computer search was exactly (SAT? exhaustive?) because "a program" is all she gets, what "final result word" and "clock ticks" mean, why the toy has "8 lights". She distrusts "MEASURED" without seeing the data and finds "Evidence for engineers" empty/collapsed.
- Visual: the game's results table is clear to her; "not checked" for three-guards-shared-wire in "Computer check" looks like an unexplained gap. Desktop wastes space.
- Would tell: yes, a colleague, with a caveat. "It's a neat common-cause-failure demo from digital design: same redundancy, one synthesis step merges nets and your 3 faults become 2."
- Scores: understood 8, would tell 7.

## P10. Journalist on a deadline (man, 30s, phone on a train then laptop; mood: rushed, wants a quotable headline and the catch)
- Time to first aha: about 12 seconds from the headline "One flip beats all three."
- Own words: "Researchers show that three backups don't help if they share a wire; one glitch beats them. Giving each its own wire needs three glitches, but how it is built changes the answer. Is it about a real chip? No, it's a computer model."
- Did NOT understand: who made this and why it matters (no named chip, no source he can cite, "", licence undecided, no author, no paper); is it a finding or a toy? "Nothing established" sounds like it is saying nothing. He cannot quote anything safely.
- Visual: on a phone the page is fine. The sticky-looking top banner takes 2 lines of the screen; the hedging is the first thing he reads, which dulls the hook.
- Would tell: only as a tip, not a story. "Interesting explainer: three backups that share one wire are really one; it's a model, not a real product, so I can't write it up."
- Scores: understood 7, would tell 5.

## P11. Retired bus driver on a phone (man, 70, large-print habit, one thumb, slow reader; mood: curious but easily lost, reads every word from top)
- Time to first aha: about 60-75 seconds; he needs to press the blue button first, sees DOOR SHUT stay or flip, and gets it from the red box "One flip. Three guards beaten."
- Own words: "Three guards but one wire, and if that wire goes wrong the door opens. If every guard has his own wire it's harder. Then something about two ways of wiring that I got lost on."
- Did NOT understand: the whole Twist section (the table with "3 flips / 3 flips / 2 flips", "joined", "count it once for each output it feeds"); the "Wiring A / B" toggle (did not realise it was a button; may never tap it); "final result word", "start state"; the page is 4085 px of scrolling and he gives up around the table. In the game, eight tiny dots and fanned lines are hard to hit with a thumb, and two-line design buttons are small print for him.
- Visual: phone text is large enough in the explainer. In the game the eight lights (~24 px) and the dashed lines are too small and the lines run into the "the guard" label.
- Would tell: yes, about the first half. "My grandson showed me a thing: three guards at a door, but if they all use the one wire, you only have to trick the one."
- Scores: understood 5, would tell 6.

## P12. First-year biology student (woman, 18-19, phone in a lecture hall, scrolling a link a friend sent; mood: bored, distractable, will bail in 30 seconds without a hook)
- Time to first aha: about 20 seconds; she compares it to one gene pathway backing up three things.
- Own words: "If three things all depend on one shared link, they're not really independent; break the link and all fail. Separate links mean you need more breaks. Then it says the answer changes depending how it's built, which is like how pathways can merge."
- Did NOT understand: why she should care (nothing connects to her life); "chip", "synthesised", "output it feeds". She skims the twist. She is uncertain whether "3 flips" is good or bad (for whom?). In the game, "A bigger number is better for the defender" confuses her: who is the defender?
- Visual: nothing overlapping. Buttons fine. Long page; she stops after the first two diagrams.
- Would tell: maybe. "Look at this lock puzzle, tap the button, it's oddly satisfying." She would send the game link, not the explainer.
- Scores: understood 6, would tell 6.

---
## Score table (simulated, ESTIMATED)
| Persona | Understood | Would tell | Both >= 7? |
|---|---|---|---|
| P7 head teacher | 6 | 6 | no |
| P8 procurement | 7 | 6 | no |
| P9 mech. engineer | 8 | 7 | yes |
| P10 journalist | 7 | 5 | no |
| P11 bus driver | 5 | 6 | no |
| P12 biology student | 6 | 6 | no |

## Gate verdict: at least 5 of 6 personas >= 7 on BOTH scores
**FAIL (1 of 6 passes, and that is a simulation likely to be too kind).** The first half (shared wire vs own wires, "where do the copies meet?") works for nearly everyone within 30 seconds. The Twist section, the jargon in the "holds only if" box and the lack of a stated purpose/audience-relevance are what pull scores to 5-7. "Would tell" is the weaker score: people would repeat the one-line shared-wire idea, not the page's actual finding.

## Three highest-impact fixes
1. **Rewrite the Twist for a layperson and fix its first view.** Open it in the neutral/shut state (not red DOOR OPEN) with a clear "Wiring A / Wiring B: pick one" label, make the toggle button-sized, and replace "count a flip once per output it feeds" with a concrete picture (one wire drawn feeding two lights, "one cut, two lights out"). Drop or footnote the "2 becomes 3" counting argument in the main flow; it lost P7, P11 and P12.
2. **Add one sentence on "so what / who is this for" and a takeaway the reader can use or quote** near the top (what real thing this models, e.g. any system with backups; what to ask a supplier), and shorten the hedging banner/"holds only if" list into plain words, defining or removing "final result word", "start state", "clock ticks". Journalist and procurement personas could not use or cite anything.
3. **Fix size/layout in the game and wide screens.** On phone make the 8 lights and tap targets at least 44 px, stop the fan lines running into the "the guard" label, shorten design button labels, remove the empty green status area; on desktop widen the diagram/text column. Explain "8 lights" and "defender", and either fill or explain "not checked" and the empty "Evidence for engineers" (the engineer persona flagged all three).

## Limits
Simulated only; initial rendered states were inspected, not every interaction; I did not test offline use or real touch accuracy; real people should repeat this, especially older and non-technical readers, who the simulation probably overrates.
