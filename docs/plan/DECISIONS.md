# Decision log

One entry per decision, newest first. Never edit an old entry; add a new one that replaces it. A decision
marked **proposed** is waiting for the maintainer; nothing that depends on it starts before it is accepted.

Template:

```markdown
## D-<number>: <short title>
Date: <YYYY-MM-DD>
Status: proposed | accepted | replaced by D-<number>
Phase / step: <for example P2.6>

Context: <two or three sentences: what forced a choice>
Options considered:
1. <option>: <one line for, one line against>
2. <option>: ...
Decision: <what was chosen>
Why: <the deciding reason, with a source or a computed result if there is one>
What it costs: <what becomes harder>
What is frozen to pay for it: <only for a new direction; see KILL_CRITERIA.md, "One in, one out">
How to undo it: <files to change, results to re-run>
Check again when: <an event, for example "after gate G3">
```

---

## D-022: Responsible-disclosure default of 90 days
Date: 2026-11-23
Status: accepted
Phase / step: all (`docs/RESPONSIBLE_DISCLOSURE.md`, section 2, step 6)

Context: The disclosure page needs a default for when nothing is agreed with the maintainers of an affected
project.
Decision: If no date is agreed, nothing is published until 90 days after the first report. An agreed date,
a fix or a refusal by the maintainers ends the wait earlier. No reply after two reminders: ask an
experienced person before doing anything else.
Why: 90 days is a common default in coordinated disclosure and gives a small project time to answer.
What it costs: A finding may wait three months before any public mention.
How to undo it: A new entry with the new default; change step 6 of `docs/RESPONSIBLE_DISCLOSURE.md` in the
same commit.
Check again when: The first report is sent.

## D-021: Learner text says COMPUTED, not MEASURED, for model results
Date: 2026-11-23
Status: accepted (accepts the proposed part of D-010)
Phase / step: P0.9 (backlog #015)

Context: D-010 proposed that learner-facing text stop using MEASURED for numbers a command produced, because
readers expect an instrument behind that word.
Decision: Accepted. Learner-facing text says COMPUTED for every result a command in this repository
produced. The change itself is Phase 0 work (P0.9, backlog #015); nothing is reworded by this entry.
Why: No number in this repository comes from an instrument (`AGENTS.md`, section 2).
What it costs: Stored files keep the old word until they are regenerated.
How to undo it: A new entry; not expected.
Check again when: #015 is done.

## D-020: Wording-check exemption for the two handoff file names
Date: 2026-11-23
Status: accepted and implemented (accepts D-015)
Phase / step: P0.4 (part of backlog #005)

Decision: Option 1 of D-015. `tools/check_wording.py` removes the exact names `AGENTS.md` and `CLAUDE.md`
from a line before the word scan. Any other spelling, and the word on its own, is still reported.
`tests/test_check_wording.py` covers both sides. Done ahead of the rest of P0.4 so that the pointer file
passes the check from its first commit.
What it costs: One exemption to maintain.
How to undo it: Remove `HANDOFF_NAMES` and `HANDOFF_RX` from the check and the test file; the pointer file
then needs another wording.
Check again when: P0.4 is done.

## D-019: Sensitivity kill threshold is 20% of draws
Date: 2026-11-23
Status: accepted (accepts D-013)
Phase / step: P2.13, kill criterion K5

Decision: As proposed in D-013. The verdict is "too sensitive" if it, or the cheapest witness, changes in
more than 20% of the per-cell Monte Carlo draws at the middle ASSUMED spread. Spreads 3%, 5% and 10%; at
least 100 draws each. Fixed now, before any data exists.
How to undo it: Only by a new entry written before the P2.13 run. After the run the threshold is not
changed.
Check again when: Before P2.13.

## D-018: No rename and no move to an organisation account for now
Date: 2026-11-23
Status: accepted (settles D-012 for now)
Phase / step: P05.9

Decision: Option 2 of D-012, for now. The repository keeps its name and stays on the owner's account.
Why: Nothing cites the address yet, and a move adds upkeep before there is a second maintainer.
What it costs: If the name changes later, links change (the hosting service redirects old ones).
How to undo it: A new entry choosing option 1. It must be written before the first archive identifier,
paper or bundle cites the address (P2.19 at the latest).
Check again when: Before the first tagged release that gets an archive identifier.

## D-017: One repository, core-only wheel now
Date: 2026-11-23
Status: accepted (accepts D-006, narrowed)
Phase / step: P05.5 (backlog #026 to #030)

Decision: One repository. The wheel built in P05.5 ships the core only. Splitting into separate
repositories happens later, and only if it is needed (as D-006 says: when a second one has a user).
Why: It removes the blocker (a large wheel carrying other projects' files) with the least upkeep for one
maintainer.
What it costs: The repository stays larger than a pure core until the archive step is done.
How to undo it: Split later with history filtering on a copy; a new entry first.
Check again when: Gate G1.

## D-016: Time boxes: Stage A 240 hours, Stage B 250 hours
Date: 2026-11-23
Status: accepted (accepts D-014)
Phase / step: Gates G1 and G3

Decision: Stage A has a box of 240 logged hours and Stage B a box of 250 logged hours, as proposed in
D-014. When a box is spent, the gate question is answered with what exists (`KILL_CRITERIA.md`, K7 and
K12).
What it costs: Work may stop with tables unfinished.
How to undo it: A new entry with new numbers and the reason; never a silent extension.
Check again when: Each gate.

Note on D-016 to D-022: they were decided together on 2026-11-23 (backlog #002). In the earlier entries only
the Status line was changed, to point here.

## D-015: Wording-check exemption for the two handoff file names
Date: 2026-11-23
Status: accepted 2026-11-23, see D-020
Phase / step: P0.4

Context: The repository's wording check rejects one word that is also part of the conventional name of the
handoff file at the repository root. The one-line pointer file next to it must name that file, so it cannot
pass the check as the check stands.
Options considered:
1. Add a file-name exemption for exactly those two root files: keeps the check strict everywhere else.
2. Rename the handoff file: tools that look for the conventional name would not find it.
Decision: (proposed) option 1, as part of P0.4.
Why: The check's purpose is the wording of shipped text, not a file name convention.
What it costs: One exemption to maintain.
How to undo it: Remove the exemption.
Check again when: P0.4 is done.

## D-014: Time boxes for Stage A and Stage B
Date: 2026-11-23
Status: accepted 2026-11-23, see D-016
Phase / step: Gates G1 and G3

Context: A time budget is needed before starting. Section 4 of `ROADMAP.md` puts the cost to the end of the
minimum version at several hundred hours.
Options considered:
1. Stage A 240 hours, Stage B 250 hours of logged time: inside the ranges of `ROADMAP.md` section 4.
2. No box: an open-ended cost.
Decision: (proposed) option 1. Final numbers are set before Phase 0 starts.
Why: A box turns an open-ended cost into a bounded one, and makes K7 and K12 checkable.
What it costs: Work may stop with tables unfinished.
How to undo it: A new entry with new numbers and the reason; never a silent extension.
Check again when: Each gate.

## D-013: Kill threshold for sensitivity (K5)
Date: 2026-11-23
Status: accepted 2026-11-23, see D-019
Phase / step: P2.13

Context: K5 needs a threshold fixed before the run.
Decision: (proposed) the verdict is called "too sensitive" if it or the cheapest witness changes in more
than 20% of draws at the middle ASSUMED per-cell spread. Spreads: 3%, 5%, 10%; at least 100 draws each.
Why: Fixed before the data, so the result cannot choose its own threshold.
What it costs: The numbers are judgement; a reviewer may ask for others.
How to undo it: New entry before the run. After the run the threshold is not changed.
Check again when: Before P2.13.

## D-012: Repository name and account
Date: 2026-11-23
Status: settled for now 2026-11-23, see D-018
Phase / step: P05.9

Context: A product-style name and an organisation account are worth considering before any archive
identifier, paper or bundle cites the address, because those citations are permanent.
Options considered:
1. Rename and move before the first archive identifier.
2. Keep the current name and account.
Decision: open. Must be settled before P2.19 at the latest.
What it costs: Option 1 changes links (the hosting service redirects old ones). Option 2 fixes the current
name into permanent citations.
Check again when: Before the first tagged release that gets an archive identifier.

## D-011: Headline quantity is minimum glitch depth, not minimum event count
Date: 2026-11-23
Status: accepted
Phase / step: P2.13

Context: With the depth free, "minimum glitch events" collapses towards 1 on almost every design in the
proof modes.
Decision: The headline is Δ\*(k) per mode and shape: the smallest level at which an attack with at most k
events exists, as a level index and a fraction of the nominal period at a named corner, next to the validity
ceiling Δ_max. Event count is a second column at a fixed depth.
Why: Attack existence is monotone in depth in `either`, `ternary` and `free`, so Δ\* is well defined.
What it costs: The result is harder to say in one word; learner text needs the "waterline" picture.
How to undo it: Not expected.
Check again when: Gate G3.

## D-010: Labels
Date: 2026-11-23
Status: accepted (the learner-text rename: accepted 2026-11-23, see D-021)
Phase / step: P0.9

Context: Verdicts and numbers used one mixed list of labels, and "measured" confused readers who expect an
instrument.
Decision: Verdict labels are PROVED, BOUNDED, SAMPLED. Number labels are COMPUTED (older files: MEASURED),
SIMULATED, ASSUMED, SOURCED, recorded. Proposed: learner-facing text switches from MEASURED to COMPUTED and
shows three labels on first contact.
What it costs: Stored files keep the old word until they are regenerated.
Check again when: P0.9.

## D-009: Fault-model modes, shapes and limits for the timing model
Date: 2026-11-23
Status: accepted
Phase / step: P1.4, P2.6, P2.7

Context: A check of the first draft showed that its three modes had no stated relation,
that the "realistic" mode was neither an over- nor an under-approximation, and that one clock glitch is not
always one moved edge.
Decision: Modes `hold`, `either`, `ternary`, `free` with the label rules of `ROADMAP.md` section 6 (only
`ternary` and `free` may print a no-attack verdict). The `band` mode is dropped. A depth bound is required
and a validity ceiling is computed. Clock-glitch shapes: shortened period, extra edge, narrow pulse,
swallowed pulse. Hold-side sets with an `early` effect. Until the extra shapes and hold sets exist, results
say "shortened-period waveform only" and "free (setup side only)".
Why: A "no attack" statement is the one a designer acts on; it must over-approximate.
What it costs: More effects and sets in Phases 1 and 2.
How to undo it: Not expected; a shape may be dropped only with a result that shows it never matters.
Check again when: After the transistor-level check (P2.14).

## D-008: Voltage glitch is a relabelling unless delays change unequally
Date: 2026-11-23
Status: accepted (replaces the first draft's open question on derating the clock tree)
Phase / step: P2.7

Decision: No per-factor timing loop. Two bracket runs (clock derated with the data; data only), union of
the sets. Cell delay and check times are derated, wire delay is not. A regression test checks that uniform
scaling gives the same sets as the clock model.
Why: Uniform scaling keeps the order of arrivals.
Check again when: A measurement or paper shows strongly regional effects on small designs.

## D-007: The owned core, and "document before extending"
Date: 2026-11-23
Status: accepted
Phase / step: C1

Decision: The owned core is `scripts/glitchsat.py`, `tools/fastsat/scripts/glitchsat_sat.py`,
`validation/` and `tools/vlab/`. Everything else is carried, not extended, until documented. New core code
goes in small commits. A module that still has no design note after a second attempt leaves the release (K10).
What it costs: Slower progress for the first hundred hours.
Check again when: Gate G1.

## D-006: Packaging split now, separate repositories later
Date: 2026-11-23
Status: accepted 2026-11-23, see D-017
Phase / step: P05.5

Context: One option was three new repositories and an archive. A project with one maintainer pays an upkeep
cost for every repository.
Options considered:
1. Full split into several repositories now.
2. One repository, two packages (core wheel and Studio), research material archived under a tag, third-party
   material fetched by script. Separate repositories only when a second one has a user.
Decision: (proposed) option 2.
Why: It removes the blocker (a 50 MB wheel with other projects' files) at a fraction of the upkeep.
What it costs: The repository stays larger than a pure core until the archive step is done.
How to undo it: Split later with history filtering on a copy.
Check again when: Gate G1.

## D-005: The survival checker and the upstream comparison move ahead of the research phases
Date: 2026-11-23
Status: accepted
Phase / step: Phase E

Decision: Phase E runs right after Phase 0.5 and depends only on Phase 0. Upstream contributions come before
local re-implementation (principle 14).
Why: It is the output a design team could use first, and it needs no new physics.
What is frozen to pay for it: Automatic hardening (Phase 10) and assertion export.

## D-004: Attack-potential scores are removed, not reworded
Date: 2026-11-23
Status: accepted
Phase / step: P0.6

Decision: No default output contains a scheme score, level or band. A test enforces it. A `lab_facts` block
of plain facts replaces it in Phase 4.
Why: A rating is a lab's judgement of a performed attack; under default settings the printed score was
constant.

## D-003: Learner material is corrected now; new learner features are frozen
Date: 2026-11-23
Status: accepted
Phase / step: Phase 0

Decision: The mechanism screens, quiz, stories and findings text are corrected in Phase 0. No new Studio
view, lesson or lab until the model it shows exists and has passed its checks. Principle 8 reads "learner
first in words, never in physics".

## D-002: Public and private split of the planning material
Date: 2026-11-23
Status: accepted

Decision: This repository holds the technical roadmap, backlog, decisions and kill criteria. Non-technical
planning, correspondence and the details of any finding under responsible disclosure are kept outside it.

## D-001: The near-term path is the minimum version; the north star stays
Date: 2026-11-23
Status: accepted
Phase / step: all

Context: Revision 1 planned a five-year platform. A narrow first version holds up on its own; the platform
plan as a whole did not.
Decision: The north star keeps its height. The path to it is Stage A (accurate and maintainable), then Stage B (one
question, one non-toy block, three tables, one note), with gates G1 to G3 and the kill criteria. Everything
else is Stage C and starts only after G3. Also decided here: the counted words are "modelled bit flips" and
"modelled events under model M"; "glitch" names only the physical act.
What it costs: Width. Phases 3 to 13 wait.
Check again when: Gate G3.
