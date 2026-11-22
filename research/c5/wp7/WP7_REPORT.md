# WP7 report: wow persona test, wave 3 (six new simulated readers)

ALL SIX PERSONAS ARE SIMULATED. None is a real person; no real reader saw these pages. Simulated readers lean kind; I tried to score harshly, but these numbers are my model's judgment, not user data. Treat as a smoke test only.

Pages read: docs/explainers/explainer.html, game.html, poster.md, script_60s.md, README.md top 40 lines, START.md head (rules read from PROCESS_RULES.md only). No earlier reports read, so trend figures (R5 5/6, WP6 4/6, README 4.5) come from the work plan.

## What I actually did (headless Chrome via playwright, executable /usr/bin/google-chrome, 390 px and 1366 px)
Scripts and raw output: research/c5/wp7/run.py, game2.py, game3.py, run.json; screenshots in research/c5/wp7/shots/.
- Hero button: "Flip the shared wire" -> status "Shared wire: FLIPPED. Door open.", red banner "one flip, three guards beaten"; button becomes "Put the wire back" and toggles back. Works at both widths.
- Counting switch: "Count a wire as 1" -> Wiring B 2 flips; "Count 1 per place it feeds" -> 3 flips, text updates. Works.
- Wiring buttons: Wiring B pick, "Flip the next wire" x3, "Show the fewest flips", "Start over": all work; "Drawing only, not a result" notice shows.
- "Tell a friend": both copy buttons show "Copied." and the clipboard really holds the 10-word and 25-word sentences (read back via navigator.clipboard).
- Game: 6 tabs. Tab "No backup": one tap opens lock (par 1), a further tap after opening is ignored ("Round finished: press Reset"), Reset and "Show fewest flips" work. Tab "3 guards, own wires": tapped guard A twice (flip then un-flip, counter 1 -> 0), then A, B, C: opened at 3 = par, "fewest possible". Extra tap after the lock opened: counter stays 3, no state change. Wrong/partial taps give "Still shut after N flips" plus hint. Tab "3 guards, 1 wire": one tap on a guard gives a clear "other guards still say no" message.
- Console errors: none at either width. No horizontal scroll, no element past the viewport, no text under 13 px, no external network URLs (page is offline-safe; explainer about 35 KB, game about 25 KB).

Visual defects found (real, small):
1. Mobile: the page title is wrapped by a boxed "What this project is" block before the hero; the hero button sits at about y=660 of 844, so tight, and after tapping the new state banner pushes the figure's caption near the fold. Works but cramped.
2. Desktop 1366x768: the hero drawing runs below the fold (caption "Three guards all say no" at the very bottom); the two tag pills under the button are tiny (about 13 px) and look like leftovers.
3. Explainer is about 1,900 words with the engineers section; the one-glance README table is far heavier. On a phone the full page is a long scroll.
4. Game tab "No backup" (par 1, one circle) is a non-game; first impression of the game is a one-tap round.
5. "Par" is golf jargon, used without explanation for non-golfers.
No broken layout, no overlap, no dead buttons.

## README top 20 lines (all personas read only lines 1-20)

| Persona | README top "I understand what the PROJECT is" (1-10) | Why |
|---|---|---|
| P37 rider | 3 | Bullet 1 reads "a computer check ... toy lock"; then "netlist", "Yosys" lost me. Not sure why a lock matters. |
| P38 teacher | 4 | Bullets ok; "bit flips", "synthesis", "redundant guard copies" opaque; safety notice scary. |
| P39 biomedical tech | 6 | Gets "redundancy" and "glitch"; wants to know if it touches devices; "toy" and "nothing physical" answers that. |
| P40 CTO | 5 | Understands the claim but "synthesis", "netlist" and the table require a hardware person; unsure what the deliverable is (tool? paper?). |
| P41 electrician | 4 | "Redundant guard copies" fine; the rest is a foreign language. |
| P42 journalist | 7 | Knows glitching; honest labelling helps; but "found: how many depends on wiring" is vague, and the safety notice raises questions. |
Mean = (3+4+6+5+4+7)/6 = **4.83**. Gate (>= 6): FAIL.

## P37: delivery rider, phone, mobile data (simulated)
- Seconds to first aha (simulated): about 25 s (reads heading, taps blue button, door goes red). Page loads fast (no external requests, 35 KB).
- Own words: "A lock has three guards but they all report down one wire, so if you mess with that one wire the door opens anyway. Giving each guard its own wire makes you need three tries. It was only a computer model, nothing real."
- Confused: "flip" (took it as flip a coin), "result word" and "accept flag" (two different things, lost me), "Wiring A/B", the 32 rebuilds paragraph. Gave up scrolling before the engineers section.
- Visual defects: pills under the hero button too small to read on a phone; box above the hero eats the first screen.
- Quotable sentence ("three people signing with one shared signature are one approval, not three"): worked, liked it. The "Copies that meet at one point may count as one" 10-word line: unclear alone.
- Tell a friend box: copy worked, but "paste where?" no share button; the 25-word line is long and abstract.
- Supplier box: did not apply to me; "who is my supplier?". Not useful.
- Sentence I'd tell someone: "If all the backup guards report through the same wire, one glitch beats all of them."
- Scores: understood 7, would tell 5. (Page fails for this reader on would-tell.)

## P38: primary-school maths teacher
- Seconds to aha: about 20 s.
- Own words: "Three guards sharing one wire are really one guard. If each has its own wire you need three flips. The answer also changed depending on how the wires were built and how you count the flips."
- Confused: "par" (not a golfer), "rebuilds" and "building program", why counting "per place it feeds" matters. The first game tab is trivially one tap.
- Visual defects: none beyond small pills; game tabs wrap into 3x2 on phone, fine for tapping.
- Quotable sentence: worked well, would use it with pupils.
- Tell a friend box: copy worked; would paste into staff chat.
- Supplier box: not hers, but she can read it; good/worrying structure is clear.
- Sentence: "Backups that all end in one wire are really just one backup."
- Scores: understood 8, would tell 7. Pass.

## P39: hospital biomedical-equipment technician
- Seconds to aha: about 20 s; the three-guard/one-wire picture matches how he thinks about redundant sensors and a single common-cause failure.
- Own words: "A voting setup is only as strong as the point where the votes meet. In their model, one glitch on the shared point beats all three. How it was built changes the count from 3 to 2, and the accepted-light drops to 1."
- Confused: whether this applies to medical devices (page says no product tested, he accepts that); "accept flag falls to 1 flip" repeated about eight times, reads as a hedge sticker; "boot".
- Visual defects: none.
- Quotable sentence: worked. 
- Tell a friend: copy worked; the 25-word line is the one he'd paste to a colleague.
- Supplier box: worked best for him: "where do copies meet" is a question he can ask a vendor today; "good vs worrying answer" is useful; disclaimer "not a pass/fail standard" noted and appreciated.
- Sentence: "Ask the vendor where their redundant copies actually meet and how they count a fault; one shared wire makes three checks into one."
- Scores: understood 8, would tell 7. Pass.

## P40: startup CTO, not a hardware person
- Seconds to aha: about 30 s.
- Own words: "A voting setup with three copies is useless if they join at one point. They measured how many modelled glitches are needed, and it depends on the build and on how you count. It's a toy study with no physical test."
- Confused: what is the actionable output; the headline "3 flips" is immediately undercut by "accept flag falls to 1 flip" so which number matters? "Result word" vs "accept flag" is the real point and is explained late. Also unsure if this is a tool, a paper or a demo (README gives no deliverable).
- Visual defects: none; page very text-heavy lower down.
- Quotable sentence: worked (one-glance-able).
- Tell a friend: worked; wants a link and a title, but the title is "TBD".
- Supplier box: worked, he'd forward the three questions to his chip vendor. Wants one more question about what the accept path looks like.
- Sentence: "Redundant copies only help if they stay separate until the very end; ask your vendor where they meet."
- Scores: understood 7, would tell 7. Pass (narrow).

## P41: 70-year-old retired electrician
- Seconds to aha: about 15 s on the hero (it is a common-mode / series-parallel idea to him).
- Own words: "Three guards, one shared wire at the end, so one fault gets past all three. Separate wires and you need three faults. Same design built differently can need two."
- Confused: "flip" (he says "a fault" or "a short"), "synthesis/building program" (never defined as a thing), "Wiring A vs B" because B's drawing is flagged as "only an illustration". Reading 1,900 words is a lot.
- Visual defects: text size ok (16 px+), buttons large. The dashed boxes read as "disabled" to him.
- Quotable sentence: liked it, "that's a ganged switch, one handle".
- Tell a friend: copy worked; he does not know what "paste" means on his tablet; would read it out aloud instead.
- Supplier box: worked, the "good answer / worrying answer" format is like a checklist he knows.
- Sentence: "Three safeties wired to one trip point are really one safety."
- Scores: understood 8, would tell 7. Pass.

## P42: security journalist who knows glitch attacks
- Seconds to aha: about 10 s (immediately sees it is a common-mode/voting-point argument), then 60 s to find what is actually measured.
- Confused: what "flip" corresponds to physically (voltage glitch, EM, laser?), the page admits no check; "rail-dip" appears only in README table (outside the 20 lines); whether "one recipe, 32 rebuilds" is a finding or an artefact.
- Visual defects: none.
- Claims that look overreaching or mislabelled (toy vs measured):
  1. Hero banner "In this picture: one flip, three guards beaten" is a drawing (ILLUSTRATIVE) while a green "Measured: 2 checks on one wire fell to 1 flip" pill sits right next to it on the hero. A skimmer reads the page as measured "three guards beaten by 1 flip". The nearest measured result is V1 (2 checks) not 3; the page says so only in "Evidence for engineers".
  2. "Three people signing with one shared signature are one approval" is stated as a result; it is an analogy, and the headline "three guards on one wire are really one guard" is called a toy picture only deep in the evidence section.
  3. The title "Three guards, one wire" and "Break the lock" suggest a break demonstrated; nothing is broken, models only.
  4. Wiring A/B are described as "wirings" but A is "illustration of the structure, not measured" and B's "joined wires" are explicitly UNVERIFIED as to which bits; the game still shows par 3 and 2 with a drawn circuit, so the figure looks like a result.
  5. "26 of 32 needed 2 flips" reads like a statistic; the page does say one recipe, but a headline of "2 or 3 flips" generalises from one design family and a z3-only anchor for some rows (README, outside top 20).
  6. "Count 1 per place it feeds: all 32 needed 3" is measured, but which counting is physical is unknown, so "how you count changes who looks safe" is partly a modelling choice dressed as a finding.
  7. The Supplier box is labelled "prompts, not a standard" which is good, but "Good answer" lines imply a standard of correctness the study did not test.
  8. README safety notice (command execution bug) is unrelated to the study claim and unexplained: reads like the project is unsafe to run.
  9. Poster: "Measured on a small design: 3 flips ... 26 needed 2" okay; "The twist" language overstates one recipe family.
- Quotable sentence: functional but he would not quote it; he would not repeat it as a finding.
- Tell a friend: worked mechanically; 25-word line is accurate and he would reuse it as a caveat.
- Supplier box: the three questions are sensible; "what is checked at the end" is the strongest; he'd still want a real-hardware reference.
- Scores: understood 9, would tell 5 (nothing publishable, no physical result). Fail on would-tell.

## Scores summary
| Persona | Understood | Would tell | Both >= 7 | README top |
|---|---|---|---|---|
| P37 rider | 7 | 5 | no | 3 |
| P38 teacher | 8 | 7 | yes | 4 |
| P39 biomed tech | 8 | 7 | yes | 6 |
| P40 CTO | 7 | 7 | yes | 5 |
| P41 electrician | 8 | 7 | yes | 4 |
| P42 journalist | 9 | 5 | no | 7 |
Pass count: **4 of 6** (needs 5). README top mean **4.83** (needs 6).

## Gate and trend
- Gate: FAIL on both criteria (4/6 page pass; README mean 4.83 < 6).
- Trend vs earlier simulated rounds (figures from the plan): R5 5/6 (narrow pass) -> WP6 4/6 -> WP7 4/6: flat at the failing level; README top 4.5 -> 4.83: +0.3, within noise (different personas, simulated). The explainer is not the problem (understood scores 7-9 for all six); the "would tell" scores for the two outsiders at the ends (rider, journalist) and the README are.

## Verdict
Pages work technically (every button, copy, round, lock-open tap behaves; no defects of substance). The explainer is understood by all six; the gate fails on motivation to share (rider, journalist) and on the README's opening, which is still written for specialists after line 3. Not a pass.

## Top three fixes
2. Hero honesty and payoff: move the green "Measured: 2 checks on one wire fell to 1 flip" pill away from the toy tag, so the toy drawing is never visually adjacent to a MEASURED label; and add one "why you care" line (a real-world shape: "a backup that ends at one point is not a backup") so rider and journalist have a reason to pass it on. Drop "Three guards, one wire" implying a break; avoid "twist".
3. Cut length and jargon: define "flip" as "a momentary wrong value" once with the word "fault" as synonym; replace "par" with "fewest flips possible"; make the "No backup" game tab not the default (start on "3 guards, own wires"); reduce the repeated "accept flag falls to 1 flip" to one boxed statement; add a Share/paste hint under Tell a friend ("paste into a message").
