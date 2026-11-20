# CO findings: outsider critic


## (1) What the project is about, in my words
It is a computer model of a thief giving a lock a tiny shock so it opens with the wrong key; the lock is the check inside a chip that decides whether to start up. The authors found that making two or three copies of the check does not help if all copies feed one shared wire, but giving each copy its own wire held up against one and two shocks and failed at three. Surprise: the answer changed depending on which program built the circuit, so "safe" depends on the tool, not just the design.
**How well it landed:** The dossier section 16 landed well (safe/lock/thief analogy). The one-page summary and README did not; they assume a reader who already knows the field. Section 16 is the only part an outsider can use, and it is buried at section 16 of a long file.

## (2) Words and sentences I did not understand
- CO-1 "secure-boot chip boot with the wrong key" (summary): what is booting, what key?
- CO-2 "wire glitches" vs "modelled one-cycle bit flips": are these the same thing? What is a cycle, a bit?
- CO-3 "netlist" ("V2 spike netlist", "on one netlist and not on another").
- CO-4 "V0 naive / V1 / V2": no one says what these are until later, and V1 vs V2 differences are given only as jargon ("shared decision wire `ok`").
- CO-5 "triplicated", "duplicated", "redundancy".
- CO-6 "re-synthesized from its source with apt Yosys 0.33"; "synthesis tool tidies it up"; "Yosys build"; "conda Yosys 0.38".
- CO-7 "85 gates ... 83 gates (with a MUX)": gate, MUX.
- CO-8 "z3 5.4.1", "SymbiYosys, ABC PDR", "SAT solver" (explained in the dossier only), "solver output and its bound".
- CO-9 "bounded" and "one unbounded proof ... for any number of cycles ... no independent certificate".
- CO-10 "sky130 GDS", "router DRC 0", "LVS 'match uniquely'", "antenna 0 violations", "off grid", "missing-tap false positives", "filler over a routed wire", "VGND port", "netgen 'Top level cell failed pin matching'". Entire "Real layout" and "Real designs" paragraphs are opaque.
- CO-11 "SYNFI, FIRMER", "enumerates fault sets and does not search", "transition from a hand-chosen start state".
- CO-12 "MEASURED / SIMULATED / ESTIMATED / ILLUSTRATIVE / UNVERIFIED" labels: useful idea, but unexplained in the summary.
- CO-13 "OTP FSM", "door-lock comparator", "attacker input constant", "CI workflows", "clean-install test", "toy 8-bit designs".
- CO-14 "Fewest flips that break it": a "flip" is never defined in the summary; "none with 1 or 2; 3 break it" reads like a riddle.
- CO-15 "Act: break it / fix it / prove it / lay it out" (README): dashboard of what?

## (3) Where I felt bored or lost
- Lost at the first sentence of the summary ("what is the fewest wire glitches...").
- Lost at the table: the row labels V0..V2 have no meaning to me, so the numbers 1/1/none/2 carry no story.
- Lost and bored in "Biggest caveat" (gate counts, tool versions) and everything from "How far the claims reach" down: a wall of tool names and file paths in brackets.
- "Real layout" and "Real designs" read as a list of unexplained acronyms; I could not tell whether they are good or bad news.
- README quickstart is for installers, not understanders; I skipped it.
- Bracketed file paths after every sentence break the reading flow.

## (4) The "oh!" moment
Yes, one: "two copies that feed one shared wire are still one weak point" (summary, plain lesson; dossier para 2). A second, weaker one: the same blueprint gave a safe circuit with one tool and an unsafe one with another. Both are strong, but the summary places them after a table of jargon, so the reader arrives tired.

## (5) What I would still not know if I had to explain it to a friend
- What a "bit flip" physically stands for, and why a thief would need exactly that.
- What the three designs (V0, V1, V2) actually are, in a picture.
- How "3 shocks" compares to the real world: is 3 a lot? Is 1 easy? (No scale of difficulty.)
- Why Yosys versions disagree and whether that is a bug or normal (the text says unexplained).
- Why the work matters if it is "not novel", "toy", and shows nothing about real chips. Who benefits?
- What "the solver says none exists" guarantees, in a sentence a friend would trust.

## (6) Ten rewrites in plain words
- CO-R1 Summary line 1 ("**Answer.**"): "Having three copies of a safety check protects a chip only if each copy has its own separate output wire. If they all feed one wire, one tiny disturbance still beats them all."
- CO-R2 "What it is": "A computer model that hunts for the smallest number of tiny disturbances that trick a chip's start-up check into accepting the wrong key. It is a model only; no real chip was touched."
- CO-R3 Define "flip" once, up top: "A flip means one stored 0 turning into 1 (or back) for a single clock tick. We use it as a stand-in for a physical glitch."
- CO-R4 Rename or explain the rows: "V0 = one check; V1 = two checks sharing one output wire; V2 = three checks, each with its own wire." Add a small drawing.
- CO-R5 Table header: "Fewest disturbances needed to trick it" instead of "Fewest flips that break it"; replace "none with 1 or 2; 3 break it" with "survived 1 and 2; fell to 3".
- CO-R6 Replace "netlist" with "the finished circuit diagram (what the tool produced from the design text)", and say so once.
- CO-R7 Caveat paragraph: "Same design text, two versions of the conversion program, two different circuits: one survived two disturbances, the other did not. So safety belongs to the finished circuit, not the design text."
- CO-R8 Replace "bounded / unbounded proof" with: "Most checks cover up to 20 ticks of the clock. One check covers any length of time, but only for the 3-copy circuit, only up to 2 disturbances."
- CO-R9 Collapse "Real layout", "Real designs", "Repo" into a three-line box "Extras (skip on first read)": "We also drew the circuits as real chip layouts and tried two real small designs; nothing alarming was found. Details for specialists: ...". Move the DRC/LVS jargon to an appendix.
- CO-R10 Put the dossier's safe-and-thief paragraph (section 16, para 1) at the top of the README and summary, add a one-line "why this matters / who cares" and a one-line explanation of the labels ("every number is tagged by how we got it: ran it ourselves, simulated, guessed, or not checked").

## (7) Score: understood in 60 seconds
- Summary alone: **2/10** (I grasped only "copies on one wire don't help", from a lucky phrase).
- README top 30 lines alone: **3/10** (the one-sentence result is decent; the rest is install steps).
- Dossier section 16 alone: **7/10** (clear analogy; loses points for no picture, no difficulty scale, and the unexplained "Yosys").
- Overall as the project's front door: **3/10**.
Caveat: simulated reader; a real outsider may differ, especially on how much "SAT solver" and "Yosys" intimidate.
