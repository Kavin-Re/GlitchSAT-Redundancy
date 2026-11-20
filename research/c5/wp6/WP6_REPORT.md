# WP6 report: wow persona test, wave 2 (P31 to P36)
ALL SIX PERSONAS ARE MODEL-SIMULATED READERS, NOT REAL PEOPLE. Simulated readers lean kind; I tried to be harsh, but treat every score as an optimistic upper bound, not a measurement of real readers. Seconds-to-aha are SIMULATED guesses from reading order and layout.

## Method (what was actually done)
- Pages under test: docs/wow/explainer.html, game.html, poster.md, script_60s.md, README.md (top 20 lines), START.md. No earlier persona or W reports read.
- Rendered with Playwright driving /usr/bin/google-chrome at 390x844 and 1366x800; screenshots in research/c5/wp6/shots/.
- Really clicked (MEASURED by script, both widths, 0 console/page errors, no horizontal scroll on either page):
  - Hero button "Flip the shared wire": door goes YES/DOOR OPEN, red "Shared wire: FLIPPED. Door open.", callout "one flip, three guards beaten", button becomes "Put the wire back"; second click reverts.
  - Wiring toggle, "Flip the next wire" x4, "Show the fewest flips"; counting switch "Count a wire as 1" -> "Count 1 per place it feeds": text changes to "Wiring B then needs 3 flips, the same as A".
  - Game: all 6 designs opened (par 1,1,1,3,3,2). Wrong taps: one guard on "own wires" = "Still shut after 1 flip" + hint; tap/untap resets to 0. Right taps: 3 guards = "opened after 3 flips. That is the fewest possible here." Shared-wire design: guard A, guard B = opened after 2, "fewest is 1" (a wrong-but-winning route); a third tap flips an already-YES wire back and shows "You flipped every wire and the lock still holds" in GREEN. "Show fewest flips" and "Reset" work.
- Visual checks: mobile top screen (banner, title, quotable sentence, model-only box) fits; hero button is below the first phone screen (about 1.5 screens down); ask-a-supplier box renders cleanly at 390 px.

## Defects seen by all, from the clicks (not persona opinion)
D1. Game: after the lock is already open, further taps are accepted; tapping a joined wire un-opens it and the message says "lock still holds" in a success-green box. A winner can accidentally "lose" and the colour contradicts the text.
D2. Game at 1366: the drawing starts below the fold (goal text, tabs, score, empty status box, then the figure). First screen shows no lock.
D3. Game: "Rebuilt: Wiring A/B" tabs and "Wiring A/B" on the explainer: A is 3 flips, B is 2, but tab order and naming give no cue which is "the surprise".
D4. Explainer: hero button is not visible on a 390 px first screen; a skimmer sees only text and an unlit diagram until scrolling.
D5. Explainer measured-vs-toy tags ("Toy picture (drawn, not computed)" next to "Measured by a computer check") are correct but crowd the hero result: 4 labels before the reader finishes the point.

---
## P31 Ferry captain, skimming on a phone in rain (SIMULATED)
- Seconds to first aha: about 25 (the signature sentence in the first screen, before any button). Would not scroll to the button in rain with wet thumb; aha is from the sentence, not the interaction.
- Own words: Three guards on one wire is really one guard. Give each its own wire and you need three tries. Ask the maker where the copies meet.
- Confused: "flip", "accept flag", "result word" appear before he has the picture; "wiring A / B" read like boats' hull plans. Lost interest at the supplier box because it is below long text.
- Visual defects: button below first screen; small grey caption text hard in glare; the green/yellow banners look alike.
- Quotable sentence: worked ("one approval, not three" is his own world: redundant watch crews on one radio). Supplier box: he read only the three bold questions; Good/Worrying lines too small to skim. Half worked.
- Would tell: "Backup that ends in one shared spot is one backup, not three. Ask the maker where the copies meet."
- Scores: understood 7, would tell 7. README top 20: understands the project 3 ("netlist", "re-synthesized", "masks", tables of flips).

## P32 High-school chemistry teacher (SIMULATED)
- Aha: about 40 s; the hero click made the idea land.
- Own words: A model shows redundant checks can all depend on one shared wire. One flip there beats all. Rebuilding the same design a different way changed whether it took 2 or 3 flips, so how you count matters.
- Confused: why "AND into net ok" in the evidence block; "par" (golf?) explained only once; did not know what a "synthesis build" is; wanted to know if "3 flips" means 3 flips in time or on different wires.
- Visual defects: D1 confusing; counting-switch result is text only, nothing in the drawing changes, so she wondered if she clicked it.
- Quotable: worked, she would use it in a lab-partner analogy ("three students copying one answer sheet"). Supplier box: worked, clear Good/Worrying format, she liked it best.
- Would tell: "If three safety checks all end at one wire, you have one check wearing three hats."
- Scores: understood 8, would tell 8. README: 4 (understands "a study of redundant boot checks"; table meaningless).

## P33 Bank risk officer (SIMULATED)
- Aha: about 20 s; this is common-mode failure, her daily vocabulary. Aha before any click.
- Own words: Redundancy that shares a single point of failure is not independent redundancy. A computer check on tiny designs showed the real number of failures needed depends on how the design was built and how failures are counted. The authors do not claim any real product is weak.
- Confused: nothing conceptual. Annoyed at hedging density: "measured", "toy", "model only", "not independent", "one recipe" repeated until she cannot tell what finding to take away; wanted one line: "result depends on counting rule and build, 2 vs 3". Wants a number for "how often", which is absent (correctly).
- Visual defects: none blocking; tag clutter (D5).
- Quotable: worked and was already known to her ("common mode"). Supplier box: strongest part, maps to vendor due-diligence questions; she would copy it. Missing: "ask for evidence under both counting rules" is buried.
- Would tell: "Three redundant checks that meet at one shared point count as one, so ask the vendor where the copies meet and how they count a fault."
- Scores: understood 9, would tell 8. README: 5 (problem sentence ok if she skips "netlist"; first table does not tell her why it matters).

## P34 Embedded-firmware engineer, adjacent field, impatient (SIMULATED)
- Aha: about 10 s; "TMR with shared voter", old news; the real interest came at the 2-vs-3 re-synthesis result (about 60 s).
- Own words: Toy TMR where the voter/AND net is the single point of failure; one flip there wins. Synthesis tool choice changes minimum fault count from 3 to 2, and counting per-fanout-pin vs per-net flips the verdict. Accept flag falls to 1 flip.
- Visual defects: D4; "wiring A/B" drawing is explicitly illustration, which he found unsatisfying (the evidence is not drawn).
- Quotable: "one approval, not three" felt like a cliche to him but fine. Supplier box: okay, but question 3 (finished wiring, which outputs) is the genuinely sharp one and is listed last.
- Would tell: "Synthesis can merge your voter copies; check the post-synthesis netlist, and count fanout branches separately."
- Scores: understood 8, would tell 6 (he would tell it only to a colleague, and thinks the hero oversells the obvious). README: 8.

## P35 Elderly retired judge, reads every sentence (SIMULATED)
- Aha: about 90 s (reads in order, does the button when told).
- Own words: The authors drew a lock with three guards that all report through one wire, so one false signal defeats them. On small computer-checked designs, the minimum number of false signals depended on how the design was built and counted. They say plainly it proves nothing about real products.
- Confused: "" and repeated disclaimers were welcome but the sheer repetition tires; "measured" vs "toy picture" tags are good, he asked what "result word" and "par" meant (defined once, then forgotten); "AND into net ok" in evidence; "Nothing physical" vs "no real product" seen as repetitive. Fussed at "we did not find a check of which counting matches real hardware": who is "we"?
- Visual defects: small tags tiny; D1 green "lock still holds" message after he opened the lock: he thought the game was broken. Needed 2 retries in the game.
- Quotable: worked; legal analogy (joint signature, single approval). Supplier box: worked, he approved of "prompts, not a pass/fail standard".
- Would tell: "Three signatures from one pen are one signature; ask where the copies meet."
- Scores: understood 8, would tell 7. README: 3.

## P36 Game-design student (SIMULATED)
- Aha: about 45 s via the game; the hero click was nice but the game tabs gave the arc (no backup, 2 guards, 3 guards, own wires, rebuilt).
- Own words: A puzzle where you open a lock with the fewest flips; designs with a shared wire fall in one flip; own wires need three; the rebuilt designs differ. It is a lesson about counting, dressed as a puzzle.
- Confused: it is not a game: no loss state, no score beyond a number, no feedback you did "well" except par text; the first tab ("No backup", one tap) is a boring opener; D1 is a real bug-like moment (win, then undo). Tab labels not sorted by discovery. Hint text tells the answer too early.
- Visual defects: D1, D2; status box empty padding on desktop; win state not celebratory (same green as "holds").
- Quotable: worked in the explainer; in the game the point is "par", which she did not link to the quotable sentence. Supplier box: she skipped it (looks like homework).
- Would tell: "It is a little puzzle about why three backups on one wire are one backup."
- Scores: understood 7, would tell 6. README: 4.

---
## Scores table (SIMULATED)
| Persona | Understood | Would tell | Both >= 7 | README understood |
|---|---|---|---|---|
| P31 ferry captain | 7 | 7 | yes | 3 |
| P32 chem teacher | 8 | 8 | yes | 4 |
| P33 bank risk | 9 | 8 | yes | 5 |
| P34 firmware eng | 8 | 6 | NO | 8 |
| P35 retired judge | 8 | 7 | yes | 3 |
| P36 game student | 7 | 6 | NO | 4 |

**Gate (at least 5 of 6 with 7+ on both page scores): FAILED, 4 of 6.** Page "understood" is 6 of 6 at 7+; the miss is "would tell" for the two personas for whom the hero is either obvious (P34) or the game is not a game (P36).

## README top 20 lines (all six)
Mean 4.5 of 10 (3,4,5,8,3,4). Only the adjacent-field engineer understands the project. The top 20 lines are the problem sentence plus a dense table of flip counts in jargon (netlist, re-synthesized, masks, boot_ok, scope cell). Non-experts cannot say what the project is for. The pages succeed where the README fails: the README gives no link to docs/wow/explainer.html in its first 20 lines (not seen there) and no one-line plain-language "what this is".

## Trend vs earlier rounds
Round 5 (P1 to P6) passed 5 of 6 narrowly (per the task statement; I did not read the records). This round is 4 of 6 on a new, deliberately harder panel (two adjacent or non-lay readers, a game-oriented reader). Direction: slightly worse on the gate, not comparable like-for-like (different personas, one tester, and simulated readers). Stable: the "understood" score holds (all six 7+), the quotable sentence and supplier box worked for 5 of 6. Weak spot: "would tell", i.e. the hero is trivial to experts and the game is thin for game-minded readers. Not a significant regression, but it does not support "passes comfortably".

## Verdict
Gate not met (4 of 6). The explainer communicates; the retell value is limited by (a) hero not above the fold on phones and (b) game round feedback bugs. README does not communicate the project to non-experts.

## Top three fixes
1. Game round logic: lock the board once the lock has opened (or show the win state sticky and do not let a later tap show a green "still holds"), and give the win a distinct colour/message; show the drawing above the fold on desktop and phone. (D1, D2)
2. Put a plain-language 2-line "what this project is" plus a link to docs/wow/explainer.html at the very top of README.md, above the table; move the jargon table below the fold.
3. Make the hero work in the first phone screen (shrink intro text so the button and the drawing are visible without scrolling, tighten to one result tag); put the supplier box's question 3 (finished wiring, which outputs) with the 2-vs-3 finding earlier, since experts find that the real "wow".

Limits: simulated readers only; one run each; seconds-to-aha are guesses; no real device or rain; screenshot review at two widths only.
