# GlitchSAT roadmap (revision 2)

Revision 2, written 23 November 2026 against `main` at commit `96b28f4` (version 0.9.0, Apache-2.0).
It replaces revision 1 and corrects the weak points found in its physics, formal methods, industry use,
open-source maintenance and teaching assumptions.

**How to use this file.** Read sections 1 to 4 once. Then work from `START_HERE.md` (first sessions) and
`BACKLOG.md` (numbered items). Come back here when a phase starts, when a gate is reached, or before writing
anything public. Read `KILL_CRITERIA.md` at the start of every phase. Decisions go in `DECISIONS.md`.

Words used for certainty in this file:

- **verified**: checked against the tool's own documentation or the repository on the date above.
- **verify**: not checked, or only partly. Check before relying on it (section 12 lists them).
- **judgement**: reasoning, not measurement. It can be wrong.

---

## 1. Direction

### 1.1 North star (unchanged in height, changed in wording)

GlitchSAT becomes **the open, physically grounded fault-analysis tool that learners and chip designers really
use**. You give it a design from an open flow (netlist, timing, placement) and pick an injection method. It
tells you which faults physics allows, the cheapest attack inside that set, what happens instead of an attack
(alarm, reset, nothing), and what to change. Every fault set comes from something measurable. Every result says
which model produced it and what the model leaves out. The same tool teaches a newcomer why any of this
matters, in plain words, on their own laptop. Evidence good enough for a design sign-off is the far goal. It is
a goal, never a present-tense claim (section 9).

The single design idea that carries the whole plan: **physics is computed outside the solver and handed to it
as plain sets, in a documented file format.** The solver stays simple; anyone, in any language, can produce or
check the sets.

### 1.2 The near-term path: the minimum version

The north star is reached by one small, sharp question first:

> **Does adding timing change the verdict of a formal fault search on a real protected block?**

Bit-flip counting misprices the commonest cheap attack. One clock or voltage glitch disturbs many flip-flops
and costs an attacker one event; a logical tool charges several faults for it, or allows flips no glitch can
cause. No open, reproducible answer to the question above was found (as of November 2026, in a search that
was not exhaustive). Either answer is worth publishing: "it changes on block X, for this reason", or "it does
not, and here is why bit-flip analysis is enough there".

The minimum version is: one question, one non-toy block, one encoding family, three result tables, one short
technical note. Everything beyond it (section 7) is kept in the plan, in order, and **starts only after the
gate at the end of the minimum version is passed**.

### 1.3 Three rules that shape the gates

1. **Depth before breadth.** One in, one out: before a new direction is added, the direction frozen to pay
   for it is named in `DECISIONS.md`. When there is a menu, one item is picked and a date is set to look at
   the others.
2. **Document before extending.** No module is extended until it has a design note or module docstring that
   explains what it does and why, and tests that cover the part being changed. New core code goes in small
   commits.
3. **The evidence standard applies to the plan itself.** Every technical claim in this plan is sourced,
   computed or marked as an assumption. Before any new module, three questions are answered in writing: what
   is the model and what measurement supports it; who has done this already (with the date of the search);
   what result would show it is wrong.

---

## 2. Where the project stands (November 2026)

What works and is checked:

- A bounded search for the minimum number of **modelled single-cycle bit flips** that reach a goal on a Yosys
  gate-level netlist (reference engine with z3; a direct CNF encoder in `tools/fastsat`).
- Agreement with a published open tool on that tool's own example netlists (4,226 recorded injections), with
  one caveat listed below.
- A "did the protection survive the build?" check (`tools/checker`, `tools/surface`): the same design needs
  3, 2 or 1 modelled faults depending on how it was built.
- An own-design intake (`glitchsat.yaml`), plain-words findings, SARIF output, and the Studio teaching app.

Known limits and defects (each has a backlog item):

| Limit or defect | Why it matters | Fixed in |
|---|---|---|
| Lesson, quiz, story and findings text teach "a glitch = one bit flip" and "three copies need three glitches" | Physically wrong for clock and voltage glitches; the first thing an expert reader objects to | Phase 0 |
| Evidence output prints attack-potential scores and can gate a CI job on them | A tool cannot give a lab's rating; under default settings the score is constant | Phase 0 (removed, not reworded) |
| The installed command can import code found in a parent folder of the current directory | Running the tool inside a cloned design could execute that design's files | Phase 0.5, first item |
| The test runner reports PASS when no test ran; 133 tests skipped in one recorded run | A green result means little | Phase 0.5 |
| The wheel ships about 50 MB, including research files and third-party sources | Not installable in tool bundles; licensing noise | Phase 0.5 |
| Several separate engines and netlist readers; the installed `analyze` command runs a copied engine | New models would not reach the installed product | Phases 0.5 and 1 |
| The agreement with the published tool was computed with a small built-in solver standing in for the real one | Not an independent re-run yet | Phase E |
| Delays in the timing lab are ASSUMED; no hardware measurement exists anywhere | Every timing result is uncalibrated | Phase 2 and later |
| On the toy locks, setup slack is nearly flat (about 6.8 to 7.05 ns at a 10 ns clock) | A timing model says little on them; one block with real path spread is needed | Phase 2 |
| No tag exists, yet some files point at `v0.9.0` | Templates and hooks point at nothing | Phase 0.5 |
| Much of the code outside the owned core has no design note yet | A security tool must be explainable to the people who rely on it | Phase C |

---

## 3. Principles

1. **Label everything.** Verdicts carry one of three labels: **PROVED** (holds for any number of cycles, by a
   proof whose certificate is stored), **BOUNDED** (holds up to k faults or events and N cycles, inside a
   named model), **SAMPLED** (from simulation or sampling; not exhaustive). Numbers carry a provenance label:
   COMPUTED (a command in the repository produced it; older files say MEASURED), SIMULATED, ASSUMED, SOURCED,
   or recorded (stored earlier, not re-run now). "Measured" is reserved for instruments.
2. **Physics first.** A fault model is added only when a cited measurement supports its mechanism. If the
   support is an inference, the model card says "inference".
3. **Never hide an attack to look realistic.** When physics is uncertain the model allows more, not less. A
   "no attack" statement is printed only by a mode that over-approximates (section 6, Phase 2), and it always
   names its depth limit and waveform shape.
4. **Say what the number counts.** Results are **modelled bit flips** or **modelled events under model M**.
   They are not physical glitches, not probabilities, not a lab rating, not a proof of security.
5. **Validation must be able to fail.** A check that holds by construction is called a demonstration, not a
   validation. Hypotheses are written down before the run that tests them.
6. **Novelty claims are hedged and dated.** "To our knowledge, as of <month year>, in the sources we
   checked."
7. **Open and reproducible.** The project's own published results use open tools and open PDKs. The tool
   accepts standard-format inputs produced by any flow, read locally. Every result carries the command, tool
   versions and input hashes.
8. **Learner first in words, never in physics.** Plain words may simplify a model; they must not contradict
   it. This rule governs the Studio, the labs and the learner profile. The command line and CI output use an
   engineer profile from the same result file.
9. **Software only for now.** Nothing before Phase 8 needs hardware or money.
10. **Defensive use only.** The tool analyses designs you own or that are openly licensed. Findings in other
    people's designs follow `docs/RESPONSIBLE_DISCLOSURE.md`.
11. **Small steps, each one valuable.** A step ends with something committed. If a step takes more than three
    sittings, split it.
12. **Local only.** No network calls or uploads from the tool. Tested, not just promised.
13. **No deadline.** The project has no fixed dates. Work resumes from the "start exactly here" line of the
    last session record.
14. **Upstream first.** If an existing open tool can answer the question, export to it or contribute to it
    before building a local copy.

---

## 4. Path, gates and effort

One session is about 2 hours. Hours are judgement, given as ranges; expect the upper end.

| Stage | Phase | What it is | Hours (range) |
|---|---|---|---|
| A. Make what exists accurate and maintainable | 0 | Accuracy fixes (wording, learner misconceptions, score removal) | 40 to 70 |
| | 0.5 | Repository health (security fix, strict tests, packaging, one result format, one CLI) | 40 to 80 |
| | C | Core review: re-derive, document and mutation-test the core | 30 to 50 |
| | L | Background reading (in parallel, any time) | 60 to 80 |
| | E | Survival checker 1.0 and the upstream comparison | 40 to 60 |
| **Gate G1** | | Stage A done; decide to enter Stage B and set its time box | |
| B. Minimum version | R | Reading gate: three papers, one page | 10 to 15 |
| **Gate G2** | | Does the page leave a gap worth filling? | |
| | 1 | Core: one engine, fault-set file format, effects, certificates | 60 to 90 |
| | 2 | Timing model on one non-toy block, three tables, note N1 | 90 to 140 |
| **Gate G3** | | Did timing change the verdict, and is the answer robust? | |
| C. Only after G3 | 3 to 13 | Spot model, outcomes, weighted search, benchmark, firmware link, bench, own chip, hardening, passive attacks, platform | not sized until G3 |

Totals to the end of the minimum version: **about 370 to 585 hours**. Revision 1 said 88 hours; it left out
background reading, the core review, repository health and the non-toy block.

**Order.** 0, then C and 0.5 interleaved (C first when both are possible), then E, then R, 1, 2. Background
reading L and the reading gate R are reading work and can fill short sessions from the first day. No new model
code is written before C is done and G2 is passed.

**Interleave rule.** Phase 0 is mostly wording. To keep the work alive, one session in three may be a
background-reading item or a core-review item.

**Time boxes.** Each stage has a box of logged hours, written in `DECISIONS.md` before the stage starts
(D-016: Stage A 240 hours, Stage B 250 hours). When a box is spent, the gate question is answered with
what exists; see `KILL_CRITERIA.md`.

**What each gate asks**

- **G1 (after Stage A).** Is v0.9.1 released with accurate wording? Does the strict test run pass with zero
  unexpected skips? Does each core file have a design note? Is the comparison
  posted where the upstream maintainers can see it? If an upstream maintainer invited a contribution, that
  outranks Stage B.
- **G2 (after the reading gate).** One page compares the planned model with the three closest works. If an
  open tool already gives timing-derived fault sets usable in a formal search, do not rebuild: contribute or
  compare. If the page shows the plain timing-violation model is known to be the wrong abstraction for clock
  glitches, the model in Phase 2 is redesigned on paper before any code.
- **G3 (after the minimum version).** Three tables exist. If timing changes the verdict and the change
  survives the sensitivity test, Stage C opens, one phase at a time. If the verdict does not change, the
  negative result is published and Stage C is reduced to the teaching and survival-check lines. If the answer
  is not robust, the tool reports sets and sensitivity only.

---

## 5. Vocabulary

| Say | Do not say | Why |
|---|---|---|
| "k modelled bit flips under model M0" | "k glitches" | One real glitch can disturb many flip-flops; some modelled flips cannot be produced physically |
| "glitch event" (one physical disturbance in the model) | "bit flip" for a glitch | One event may fault many flops |
| "independent faults (a model assumption)" | "three copies need three glitches" | A global glitch is one event that can hit all identical copies |
| "minimum glitch depth, as a level and as a fraction of the period, at corner C" | a bare number of picoseconds | The delivered depth on a bench differs from the computed one |
| "no attack within model M, mode X, shape S, depth up to level L, up to k events and N steps" | "secure", "proved secure" | The statement holds only inside those limits |
| "hold: heuristic attack finder" | "realistic mode" | It is one point inside the allowed behaviours |
| "free (setup side only)" until hold-side sets exist | "sound over-approximation" | Hold-side failures sit outside the setup sets |
| "effective undetected fault", "effective detected fault", "reset or mute", "no effect" | "exploit", "detected", "reset", "none" | Reaching a modelled goal is not a demonstrated exploit; matches the field's terms |
| "k-fault resistant under M up to N cycles" | "margin k" | Matches the fault-resistance literature |
| "facts a lab may use" (events, cycles apart, sites) | attack-potential points, levels, "in scope" | A rating is a lab's judgement of a performed attack |
| "likelihood under assumed weights" | "success probability" | Weights are priors until calibration exists |
| "physically motivated, uncalibrated model" | "physically accurate", "silicon-validated", "sign-off" as a fact | No silicon data |
| "analog sensors assumed bypassed; digital timing sensors modelled" | silence about sensors | Analog detectors are outside the model |
| "instruction-skip model (an assumption at instruction level)" | "the glitch skips an instruction" | Not derived from the netlist |
| "observed in the open-flow build with <tool, version, script>" | "vulnerability in project X" | Build artefacts of an open flow are not product weaknesses |

---

## 6. Stages A and B in detail

Step numbers look like `P0.3`. The same numbers are used in `BACKLOG.md`.

### Phase 0: accuracy fixes

**Goal.** No shipped sentence equates the tool's number with physical glitches, a probability, a rating or a
proof. The learner material teaches the physics first and introduces the model as a simplification of it.

**Why first.** It costs days, it is correct whatever happens later, and it removes the two statements an
expert objects to within minutes.

**Steps.**

- **P0.1** Decide the counted words (decision D-001): a number is followed by "modelled bit flip(s)" (M0) or
  "modelled event(s) under model M"; "glitch" names only the physical act.
- **P0.2** Reword `README.md`, `START.md`, `product/README.md`. Rewrite `NOTICE.md` as a short notice
  (copyright line and required third-party notices); drop notes about folders that are not in the repository.
- **P0.3** Write `docs/FAULT_MODEL_CARD.md` for **M0, bit flip**: effect, sites, counting rule, bounds,
  assumptions, exclusions, the sentence "not calibrated against silicon", and one **formal statement row**
  (every quantifier and input pinned: netlist hash, start state, goal, k, N).
- **P0.4** Extend `tools/check_wording.py` (do not add a parallel test) with the glitch-count patterns; scan
  all shipped files by default with a shrinking exemption list. Add `docs/edu/CLAIMS.md`: the list of claims
  a learner page may make; the check covers the Studio, the class plan and the lab against it.
- **P0.5** Findings text (`tools/findings/plain_findings.py`, `SEVERITY.md`). The "protection held" card must
  say: under model M0, where each flipped bit is an independent fault; one power or clock glitch can upset
  all identical copies at once; this count does not cover that. The severity rule does not lower the level
  for k of 2 or more without that sentence. A test enforces it.
- **P0.6** **Remove** attack-potential output: the two scheme totals, the band and the level verdicts leave
  JSON, SARIF, HTML and Markdown; the CI option that gates on a level is removed. The margin gate stays on
  the minimum number of modelled faults. A test fails if any default output contains a rating. SARIF:
  no default `security-severity` number; `precision` set to `medium` with the reason given. Regenerate the
  stored evidence examples.
- **P0.7** Rewrite the mechanism screens (story, lesson, quiz, class-plan answer key) so the chain is:
  glitch event, then every slow-enough flip-flop captures a wrong value in the same cycle, then "in the
  model we simplify this to chosen bits". Remove "exactly" from "models exactly that flip". Rewrite the quiz
  item on what a glitch is. Replace "glitch every copy at the same moment" with the diversity explanation
  (copies placed apart help against a spot; against a global glitch identical copies can fail together;
  designers add different encodings, a later second check, sensors). Add "diversity" as a protection card.
- **P0.7b** True stories: each card gets a line "What GlitchSAT models of this" with one of three answers
  (the instruction-skip assumption; the same kind of decision as a netlist bit-flip model on a toy lock; not
  modelled). Add one screen "What the attacker actually searches" from the existing sweep grid: "perfectly
  timed" becomes a stated model assumption.
- **P0.8** One screen "Two models disagree", built from results already in the repository (bit-flip model
  against the clock-glitch sweep on the same lock), labelled SIMULATED with assumed delays, with an old
  value / new value table. Fixed fold "What does this number mean?" (counting rule, horizon, one of many
  minimum attacks).
- **P0.9** Learner labels (decision D-010): learner text says COMPUTED where older text says MEASURED; three
  labels on first contact, the rest one click away; a short glossary strip that maps plain words to the
  terms a chip-design student knows.
- **P0.10** Glossary: the vocabulary table of section 5.
- **P0.11** Result files: write the draft `glitchsat-result/1` envelope (Phase 0.5, P05.7) with a
  `fault_model` block, not an ad-hoc field.
- **P0.12** Concept check: five questions, used before and after (in `docs/edu/`). Outside read: give the
  README and the card to one person who has not seen the project.
- **P0.13** Pilot: one small group (3 to 10 people) uses the corrected material; record times, errors and
  the before/after concept-check scores.
- **P0.14** Regenerate stored examples; run every suite; update `docs/NUMBERS.md` headers; release v0.9.1
  (precondition: P05.9 release files exist and no file points at a tag that does not exist).

**Done when.** The wording check covers all shipped text and passes; no default output contains a rating;
the five mechanism items are rewritten; the card exists and is linked; v0.9.1 is tagged.

**Success metric.** The outside reader's sentence about "the answer is 2" contains "model". In the pilot,
concept-check scores rise, and the item on identical copies under one supply glitch is answered correctly by
most participants afterwards.

**Frozen during Phase 0.** New Studio views, new lessons, new labs. Corrections lead; features wait.

### Phase 0.5: repository health

**Goal.** A core that installs cleanly, cannot run code it was not installed with, tells the truth about its
tests, and has one result format and one command line that later phases will not have to change.

**Steps (in this order).**

- **P05.1 Import-path security fix.** The command imports only from the installed package. A checkout is
  used only through an explicit environment variable. Sub-packages live under one import name, so no path
  manipulation is needed. A regression test runs the command from a folder that contains a decoy module and
  requires that the decoy is not executed. `SECURITY.md` is updated; private vulnerability reporting is
  enabled.
- **P05.2 Strict tests.** `scripts/test_all.py --strict` fails a suite that collects nothing or skips more
  than its declared budget. Each suite declares which skips are expected for which missing tool. CI runs the
  strict mode with every tool present (expected skips: zero). Duplicated test files are removed; test files
  under `docs/` are either run or deleted. Generated output goes to an ignored `build/` folder, so a test run
  no longer rewrites tracked files.
- **P05.3 Dependencies.** Every runtime dependency is declared. A CI job installs the built wheel into an
  empty environment with no extra install lines and runs the core suite. A hashed lock file for CI.
- **P05.4 Pinned analysis environment.** One container image, referenced by digest, with the chosen Yosys,
  Icarus Verilog, CaDiCaL, a proof checker, z3 and PySAT. Every result names it. The flow image for Phase 2
  is an existing one referenced by revision, not a home-made one.
- **P05.5 Packaging split and archive** (decision D-006). The wheel ships the core
  only (target: a few megabytes, no research files, no third-party sources). The Studio becomes its own
  installable package built from the same repository. `research/`, the report and slide folders and the
  step reports are frozen under a tag `archive/pre-split-0.9` and removed from the default branch after the
  inputs that code still reads are moved to `tests/data/`. Third-party designs and sources are fetched by
  script at a pinned commit with checksums instead of being vendored; `real_designs/fsm.v` is pinned with its
  licence file or removed. A licence lint runs in CI. Separate repositories are created only when a second
  repository has a user.
- **P05.6 Section 2 table gets a "fate" column**: core, Studio package, fetched, or archived, per folder.
- **P05.7 One result envelope** `glitchsat-result/1` (draft until 1.0): schema id, tool and commit, inputs
  with hashes, environment, fault model (card id, parameters, fault-set file hash), bounds (including a
  `depth_bound` field), verdict (`ATTACK`, `NO_ATTACK_WITHIN_BOUNDS`, `UNKNOWN`, `ERROR`), verdict label,
  minimum, witnesses, outcomes (empty until Phase 4), proof hash, and a free payload per module. A short
  compatibility page says which fields may change.
- **P05.8 One command line.** `glitchsat` with sub-commands; old names print a deprecation notice. Exit
  codes are documented as an interface. A reference page is generated from `--help` and checked in CI. SARIF
  rule ids are fixed; fingerprints are documented.
- **P05.9 Release hygiene.** `RELEASING.md`, `CHANGELOG.md` (with a `result-affecting` mark for any release
  that can change a verdict on unchanged input), `CITATION.cff`. Version numbers mean interface stability,
  not research milestones. The release workflow and the CI action are run once on scratch targets.
- **P05.10 Contributor basics.** Sign-off rule with a check, pull-request template with the label checklist,
  a "result disagreement" issue template, a code of conduct, a linter on the core only, branch protection
  with required CI.
- **P05.11 Docs.** User documentation (tutorial, how-to, reference, explanation) is separated from project
  history. A page marked as not yet reviewed is reviewed or removed. Internal step names leave public docs.

**Done when.** The decoy test passes; the strict run passes with zero unexpected skips in CI; a clean
environment installs the wheel and runs the core suite; every result validates against the envelope.

**Not in this phase.** Renaming the repository or moving it to an organisation account was settled
for now by keeping the current name and account (D-012, D-018); any change must be decided before an
archive identifier, paper or bundle cites the address.

### Phase C: core review

**Goal.** The core is documented and independently re-checked, file by file.

- **C1** Choose the owned core (decision D-007): `scripts/glitchsat.py`,
  `tools/fastsat/scripts/glitchsat_sat.py`, `validation/`, `tools/vlab/` (about 3,600 lines). Everything else
  is "carried": it keeps working, but it is not extended until it is documented.
- **C2** Re-derive the engine: write from scratch, without looking at the repository, a short z3 script that
  unrolls V0 for 6 cycles with at most k flips. It must give the same minima as the engine on V0, V1, V2.
- **C3** Write `tools/fastsat/ENCODER_MAP.md` for the CNF encoder: where fault
  variables, totalizer outputs and assumptions are created; what fault collapsing assumes.
- **C4** Break it on purpose: `make mutate` and hand-made mutations; predict which test fails before running.
  Five predictions logged, hits and misses.
- **C5** Design notes: for each core file, one page on what it does, why, and what it assumes. Every open
  question becomes an issue.

**Done when.** C2 matches; the map exists; five predictions are logged; four design notes exist.

**Rule from here on.** A module without a design note is not extended and not offered for outside review. If
a note still cannot be written after a second attempt, the module leaves the release (K10).

### Track L: background reading (parallel)

| Item | Topic | Hours | Done when |
|---|---|---|---|
| L1 | Fault attacks: the classic guide to fault attacks (Bar-El et al., 2006), Agoyan et al. 2010, the 2024 survey written for apprentices | 6 to 8 | A one-page note on why one clock glitch can corrupt several flip-flops and why that is not k bit flips |
| L2 | SAT and bounded model checking (a z3 tutorial; two textbook chapters on decision procedures; PySAT cardinality encodings) | 12 to 16 | Same as C2 |
| L3 | Static timing analysis (a standard textbook, first chapters; the OpenSTA guide) | 15 to 20 | A worked example: setup slack for a two-flop path from a Liberty table, matched with `report_checks` |
| L4 | The open flow (LibreLane documentation and smoke test; open-shuttle teaching material) | 10 to 15 | A list of every file in a run folder that Phase 2 needs |
| L5 | Hardware security in context (the SYNFI and FIRMER papers; a public lecture series) | 10 to 15 | A two-page note: where GlitchSAT sits |
| L6 | Scientific writing (two short workshop papers read end to end) | 4 to 6 | An abstract for note N1 written as if Phase 2 were done, with a list of what is missing |

L1 before P0.7. L2 before Phase 1. L3 and L4 before the flow is installed. L5 and L6 any time.

### Phase E: survival checker 1.0 and the upstream comparison

**Goal.** The part of the tool a design team could use first is finished and accurate: a regression check for
"did the countermeasure survive the build?", on the user's own machine. It needs no new physics. In parallel,
the comparison with the closest open tool is made independent and offered upstream.

**Why here.** From the industry side, this check, with its baseline diff and SARIF output, is the one
output a chip team might put next to its own flow. It was scheduled behind three research phases; it depends
only on Phase 0.

**Steps.**

- **PE.1 Stable identity.** Carry Yosys `src` attributes (file and line) into findings. Where a net has
  none, report the nearest named register or port. Fingerprints use countermeasure id, goal id, model id, RTL
  signal and cycle offset, never generated net names. Test: two builds with a harmless change give identical
  fingerprints.
- **PE.2 Countermeasure ids.** A `requirement:` or `countermeasure_id:` field in `glitchsat.yaml`; standard
  tags are read where a design carries them. The id travels into JSON, SARIF properties and the report. The
  report has a traceability table: declared countermeasure, present after build, weakened, removed.
- **PE.3 Report template** `docs/REPORT_TEMPLATE.md`: scope and versions; objectives and countermeasure
  table; model card reference; bounds with justification; findings with traces; what was not analysed;
  detection ability of the tool itself (PE.6); header "contains fault-attack paths; handle as
  security-sensitive design information".
- **PE.4 Loader realism (subset).** A list of supported and unsupported constructs; an unsupported construct
  stops the run with a message, never a silent skip. Black-box outputs are treated as free and the report
  says so. Functional-mode constraints in the project file (for example scan enable held at 0).
- **PE.5 Regression use.** A waiver file (fingerprint, reason, owner, expiry; an expired waiver fails the
  job). Two profiles from the same result file: `engineer` (default for CLI, CI, SARIF) and `learner`. The CI
  action does not upload SARIF by default; evidence is written as a job artefact.
- **PE.6 Seeded-defect suite (small).** Hardened designs with one known weakening each (merge two copies,
  cut the alarm wire, reduce an encoding distance, share one comparator). Detection and false-alarm counts
  are printed in every release note.
- **PE.7 Exports.** Each minimal trace as a simulation testbench that reproduces the fault in any Verilog
  simulator; the netlist cut and fault set in the input format of the closest open tool (verify the format).
  Assertion export stays optional.
- **PE.8 Independent comparison.** Re-run the published tool's reference in the pinned container with its
  real solver and dependencies; store those reference results; delete the stand-in shims; route the
  comparison through the core encoder. Write a **semantic alignment table** (fault sites, effects, counting,
  time model, goal, and the configuration under which both tools answer the same question). Compare only
  under that configuration.
- **PE.9 Upstream, in this order.** (a) An issue on the published tool's repository with the reconciliation
  of the one differing published number, with the exact command. (b) A small change offered there that makes
  two heavy imports optional on the injection path. (c) An issue asking the authors of a second SAT-based
  tool to add a licence, before any comparison with their code. (d) A local build fix for a third tool,
  offered upstream instead of kept as a modified copy. Before anything is filed as a weakness: check whether
  it is present at RTL; follow `docs/RESPONSIBLE_DISCLOSURE.md`.

**Done when.** Fingerprints are stable across rebuilds; the traceability table renders; the seeded-defect
counts are in the release notes; the reference re-run is independent; item (a) is posted.

**Time box.** 40 to 60 hours. If everything outside the minimum version is frozen, the checker is
frozen with P0.6 and PE.1 done; those two are about accuracy and noise, not features.

### Phase R: reading gate (before any model code)

Read, in this order, and write one page (`docs/PRIOR_ART.md`, dated):

1. The 2024 paper on characterising and modelling synchronous clock-glitch fault injection (Marotta et al.,
   COSADE 2024). Its publisher page describes clock glitches induced by electromagnetic injection and
   evaluates the timing fault model and the sampling fault model; a later research post builds an
   "energy-threshold" fault model on it. **What it concludes about plain timing-violation models has not
   been read in full text by this project (verify).** This is the first item because it may redirect Phase 2.
2. FLAT (layout-aware timing fault assessment, 2024), full text.
3. GlitchGlück (2025) and its public artifact: licence, contents, which parts need a commercial simulator.

The page states, per work: what it does that the planned model does not, and the reverse. Then answer gate G2
(section 4). Also on the page: FIESTA has a public artifact under BSD-3-Clause (revision 1 said "unknown");
CRAFT; the open formal tools.

### Phase 1: core

**Goal.** One engine. Physics enters as a file. Every "no attack" answer has a certificate.

**Steps.**

- **P1.0 One engine.** The CNF encoder is the only production path. The z3 engine moves to `tests/oracles/`.
  The copied engine in the product package is deleted and `glitchsat analyze` calls the core. Toy defaults
  (goal value, key) move out of the core interface into the example configurations.
- **P1.1 Golden corpus.** One corpus covering the 36 reproduce rows, the published-tool regions, the
  secure-boot variants and the hardened V-family. It compares **verdict and minimum** and **replays each
  witness** in the independent simulator; it does not compare witness identity. The independent simulator
  (`validation/k1.py`) and the SymbiYosys checks in `formal/` are regression oracles.
- **P1.2 Real solvers and certificates.** Published results use CaDiCaL or a PySAT solver only. For every
  `NO_ATTACK` verdict in the corpus and in releases, the solver writes a proof and a checker verifies it; the
  proof hash goes into the result. The small built-in solver is labelled "teaching fallback", prints a
  warning, and is fuzzed against CaDiCaL.
- **P1.3 Fault-set file format** `glitchsat-faultsets/1` (JSON, schema in the repository): netlist path and
  hash; naming rule; `events[]`, each with id, allowed steps, cost, coupling to other events, and `sites[]`
  with an effect; provenance (tool, version, command, corner, label). M0 is the trivial producer: one event
  per site, cost 1. Producers are separate commands; `glitchsat analyze --faultsets file.json` consumes the
  file.
- **P1.4 Effects.** `flip`, `set`, `reset` on nets; on flip-flops: `hold` (keeps q), `either` (q or d, the
  solver chooses), `free` (any value), `early` (captures the next value: hold-side), `branch_skip` (a group
  of flops below one clock buffer misses the edge together). `ternary` is added in Phase 2. Each effect has a
  brute-force test on a hand-written three-flop netlist.
- **P1.5 Event cost and spacing.** One event may fault many sites for cost 1. Per-step and faulty-step
  bounds. `burst_len` and `min_gap` per injection method, printed with every multi-event result. The unrolled
  bound N counts **steps (clock transitions), not wall-clock periods**.
- **P1.6 Fault collapsing.** A `collapsible()` rule that defaults to off; collapsing is allowed only where a
  model-specific proof is written in the module README. Every effect is cross-checked with and without it.
- **P1.7 Property and metamorphic tests** on random small netlists: SAT minimum equals brute force for k up
  to 2; a larger site set never raises the minimum; `free` never needs more events than `either`, and
  `either` never more than `hold`; renaming nets or reordering cells does not change the verdict; an event
  whose sites are all inert changes nothing.
- **P1.8 One loader for mapped netlists.** Try first: let Yosys read the Liberty file and lower the cells,
  and check that flop instance names survive (verify on the placed V2). If they do, the three hand-written
  cell adapters are deleted. State-element kinds (reset, enable, scan) each get a test. Unsupported cells stop
  the run.
- **P1.9 Standard-format export.** Write the instrumented problem (fault selectors as inputs, the budget as a
  constraint) as AIGER or BTOR2, so existing model checkers can answer unbounded questions. `tools/unbounded`
  is archived once this works.
- **P1.10** Result validation against the envelope; module README "how to add a fault-set producer";
  release 0.10.0.

**Done when.** Corpus unchanged in verdict and minimum; all effects cross-checked; every `NO_ATTACK` in the
corpus has a checked proof; the installed `analyze` command runs the core.

**Parked.** Reproducing the published 3-to-2 weakening of a control state machine (it needs a special
front-end build; the original publication is cited instead).

### Phase 2: timing-derived glitch model (the minimum version)

**Goal.** Answer the question of section 1.2 on one non-toy block, with statements that say exactly what
they cover and checks that could have failed.

#### 2.1 The model

Static timing analysis on the post-route netlist with parasitics gives, per flip-flop data pin, a **setup
slack** (late side) and a **hold slack** (early side), kept separately for rising and falling arrivals. For a
glitch of depth Δ, `S_Δ` is the set of flops whose data may arrive too late. The sets change only at distinct
slack values, so a short sorted list of **levels** is exact; the solver needs no arithmetic.

**Capture modes (a lattice, not three unrelated options).** For flop i in `S_Δ` at a glitched step:

| Mode | Allowed next value | Use | May print "no attack"? |
|---|---|---|---|
| `hold` | q (forced) | Heuristic attack finder only. Not monotone in depth | Never |
| `either` | q or d, chosen per flop | "The attacker may suppress any subset of the transitions on late endpoints." Monotone in depth | Only as "no attack under the hazard-free hypothesis" |
| `ternary` | d if the endpoint is stable under ternary simulation of the transition, otherwise any value | Proof mode, tighter than `free`. Dual-rail encoding on the fan-in cones of late endpoints | Yes |
| `free` | any value | Proof mode. Often trivial at depth | Yes |

The old `band` mode is dropped. Each endpoint has an interval [arrival at the fast corner with early derate,
arrival at the slow corner with late derate]; the slow end decides set membership in the proof modes; the
whole interval decides whether a witness is **robust** or **fragile** in replay.

**Depth limit, always.** Without a bound, `free` at the deepest level lets one event write any state, so
every design falls. Therefore:

- `--max-level` is required for `either`, `ternary` and `free`. Every statement says "for depth up to level L
  (slack at most x at corner C)". The result envelope carries `depth_bound`.
- The tool computes a **validity ceiling** Δ_max: the depth at which any clock-tree cell or flop clock pin
  falls below its minimum pulse width, or the clock latency leaves the analysed bounds. Above it the slack
  ordering is not claimed to hold; the tool switches to branch sets or refuses a verdict.

**Clock-glitch shapes.** One physical clock glitch is not always "one edge moved". Every result names its
shape:

| Shape | What happens | In the model |
|---|---|---|
| `short_period` (shortened period) | One capture edge arrives early | One glitched step at level L |
| `inserted_edge` (extra edge) | An added edge at offset o gives two short periods, o and T − o, and one extra state update | Two consecutive glitched steps with coupled levels, plus one extra unrolled step; the second step uses `ternary` or `free` only |
| `narrow_pulse` | A pulse shorter than the minimum pulse width; flops may miss the edge or sample badly whatever their slack | Every flop on a surviving clock branch gets `free` |
| `swallowed_pulse` | A runt pulse dies in some clock-tree branches and not others | **Branch sets** from the clock tree (one set per clock buffer, the flops below it) with the `branch_skip` effect |

Until `inserted_edge`, `narrow_pulse` and `swallowed_pulse` exist, every clock-glitch statement says in the
result string itself: "holds for the shortened-period waveform only".

**Hold side.** Hold failures happen on the shortest paths (shift registers, counters, direct flop-to-flop
connections); those flops have large setup slack and never enter `S_Δ`. Min-delay analysis gives hold sets
`H_σ` for a skew-perturbation parameter σ (bounded by clock-tree depth times an ASSUMED per-stage
variation); proof modes allow the `early` effect on `H_σ`. Until this exists, the mode is printed as
"free (setup side only)" and the word "sound" is not used.

**Voltage glitch.** If every delay is scaled by the same factor, the sets are identical to the clock model's
and only the label on the depth axis changes. So there is no per-factor timing loop; a regression test checks
that the two families are equal. Effort goes only into what can reorder endpoints: two bracket runs (clock
path derated with the data; data only), union of the sets, derating cell delay and check times but not wire
delay (verify the option names in your OpenSTA). A multi-cycle droop profile with overshoot, and a clock
generated on chip, are listed as exclusions in the card for the minimum version.

**Headline quantity.** Not "minimum number of glitch events" (with the depth free it collapses towards 1).
The headline is the **minimum glitch depth Δ\*(k) per mode**: the smallest level at which an attack with at
most k events exists, reported as a level index and as a fraction of the nominal period at a named corner,
next to Δ_max. A design is "safe under M1 for one event, shape S" only if Δ\* lies above Δ_max. Event count is
a second column at a fixed depth. Picoseconds appear only in a debug field.

**Formal statement.** Card M1 and note N1 state a containment claim and its assumptions: if per-arc delays
lie within the analysed bounds, clock arrivals lie within the latency bounds under the glitch, pulse widths
stay above the minimum (depth at most Δ_max), and a flop whose input is stable over its setup and hold window
captures that value, then every capture behaviour of the timed netlist under a glitch event of depth Δ is
allowed by `ternary` (and so by `free`) at level Δ. The novelty sentence is: "a SAT fault model whose
candidate sets come from static timing on an open flow, with a containment argument relative to stated delay
bounds (to our knowledge, as of <date>, in the sources we checked)".

#### 2.2 Steps

*Stage 2A: real timing.*

- **P2.1** Install the flow (see `START_HERE.md`, session 4; 4 to 8 hours, split in two sittings). Record
  the flow revision.
- **P2.2** Real SDF for V1 and V2; re-run the timing lab; the delay label changes from ASSUMED to
  SOURCED (sdf). Note what changed.
- **P2.3** Full flow run with parasitics and two corners for V2.
- **P2.4** Timing extraction that cannot silently drop paths: input delays set on every input except the
  clock; the run **fails** on any unconstrained endpoint or path; the number of reported endpoints is
  asserted to cover all endpoints; setup and hold slack, rise and fall, at two corners. Output is a neutral
  slack file (endpoint, clock, corner, setup slack, hold slack, arrival, required) so that a report from any
  timing tool can be converted. Test: a case with an unconstrained path makes the extraction fail.
- **P2.4b** Common-mode timing check (a cheap, useful by-product): for each set of redundant copies, report
  whether their slacks are so close that one glitch level takes all of them.

*Stage 2B: the model in the solver.*

- **P2.5** Level sets, hold sets and branch sets, written as `glitchsat-faultsets/1`.
- **P2.6** Modes `hold`, `either`, `free` with the required depth bound and the shape parameter; verdict
  label rules from the table above. **P2.6b** `ternary` mode.
- **P2.7** Shapes `inserted_edge`, `narrow_pulse`, `swallowed_pulse`; hold-side `early` effect in proof
  modes.

*Stage 2C: evidence that can fail.*

- **P2.8 Implementation consistency** (renamed; it is not a physics check): the event simulator, fed with
  delays **sampled per arc inside the [fast, slow] interval** and with states **drawn from reachable
  traces**, never shows a mis-capturing flop outside the sets. Cross-check the simulator against one external
  SDF-annotated simulator on a few hundred vectors; record which constructs that simulator ignores.
- **P2.9 Mode coverage** (replaces the old test B, which held by construction): the fraction of simulated
  faulty captures inside `hold`, `either` and `ternary`. Any capture outside `ternary` is a bug.
- **P2.10 Witness replay.** Every `hold` or `either` attack is replayed in the timing simulator at the slow
  corner, the fast corner and N random delay samples, with the exact inputs, step and shape. Each witness is
  labelled `REPLAYED x/N` or `STA-only (path sensitisation not confirmed)`.
- **P2.11 The non-toy block.** One block with real path spread and a real countermeasure, plus one design
  with a **digital glitch detector** (a canary flop on a lengthened path or a tapped delay line) wired as the
  alarm. Its **detector margin** (levels between detector onset and first critical-flop onset) is a headline
  column. State the analysis window: from reset, from a concrete prefix, or from an invariant.
- **P2.12 Hypotheses written first.** Before the headline run, commit the ranking hypotheses (which build or
  variant is expected to need a deeper glitch, and why).
- **P2.13 Three tables.** (1) M0 verdict next to Δ\*(k) per mode and shape, with Δ_max and the detector
  margin. (2) **Sensitivity by per-cell Monte Carlo** (independent per-cell factors at three ASSUMED spreads,
  at least 100 draws each) and a per-region perturbation: the fraction of draws in which the verdict or the
  cheapest witness changes, and the spread of Δ\*. Uniform scaling is shown only to illustrate how the depth
  label moves; it cannot change a verdict. (3) Replay and mode-coverage results.
- **P2.14 Transistor-level check on one small block** (a few hundred cells, ngspice with the open PDK models
  and extracted parasitics): the four clock shapes and one droop; compare captured values with the model's
  sets and effects; list every mismatch. This is the only check before hardware that can expose pulse-width,
  clock-branch, hold and hazard effects. **Until it is done, note N1 makes no "no attack" statement for
  clock glitches**; it reports attacks found, sets and sensitivity.
- **P2.15 Demonstrations, labelled as such.** "The least-slack flop faults first" and "more bits fault as
  the glitch deepens" hold by construction; they are shown as illustrations, not as validation against
  published measurements.
- **P2.16** Pruning reported **per level** with ablations; no speed claim until measured with standard
  hygiene (fixed seeds, time limits, the pinned machine description).
- **P2.17** `tools/timing/SOUNDNESS.md` and card **M1**: assumptions, the lattice, the formal statement, and
  exclusions written into result strings, not only into a document.
- **P2.18** Literature sweep, dated, before anything is published.
- **P2.19** Note N1 (4 to 6 pages) with an `ARTIFACT.md`; a tagged pre-release; an archive identifier.

**Done when.** The three tables exist with labels; every statement carries mode, shape and depth bound; the
extraction fails on unconstrained paths; witnesses are labelled; the note is public.

**Parked for the minimum version.** A delay-against-supply characterisation; a second and third larger
target; the multi-cycle droop profile.

**What can be shown to learners (after the checks pass).** A "waterline" view: flops sorted by slack, a line
that rises as the glitch deepens, the bit-flip model and the timing model side by side, and the sensitivity
drawn as a band, not a line.

---

## 7. Stage C: only after gate G3

Kept in order, each with the corrections already identified. Nothing here is sized or started before G3.
One phase at a time; one in, one out.

| Phase | Goal | Corrections carried forward |
|---|---|---|
| 3. Spot model in SAT (laser; EM as exploration) | A shot faults only cells under one footprint | Exact breakpoints or an inflated footprint, since a grid is not exact; the centre rule and set/reset tables never support a "no attack" statement; effective spot size is swept, not taken from optics; combinational transients with a latching window and clock-phase sensitivity; the EM mode gets a multiplicity bound and an EM-on-clock sub-mode, every EM result says "uncalibrated; no validation is planned in this project", and EM stays out of headline tables; the separation lesson is worded as "helps against a spot, not against a global event" |
| 4. Outcomes | Four classes inside the formal search | Each class is a **minimum cost** (`k_silent`, `k_any`, `k_detected`, `k_reset`) plus one universal statement ("every effective fault with at most k events raises the alarm within d steps"); detection latency d is a parameter; horizon rule (N at least goal step plus d, else "silent within horizon"); reset is terminal per attempt by default, with a flag for warm reset with retained state; crash and hang are also **derived** (illegal state, no progress for K steps), since bench crashes come mostly from logic, not from tagged cells; a `lab_facts` block of plain facts (events, steps apart, sites) with no points or levels |
| 5. Weighted search | Cheapest attack under labelled priors | The optimum is an upper bound under assumed weights, never a probability; report a Pareto front (events against weight); prior-art sweep before any claim; ship only if rankings survive perturbation |
| 6. Open benchmark | Designs with and without countermeasures, re-runnable | Two-layer artifact with **frozen EDA outputs**, not only pinned tools; alignment table per baseline; standard performance protocol; other tools are run unmodified or cited by published numbers, never re-implemented; licence audit covers cell libraries and mapped netlists; the full seeded-defect suite |
| 7. Firmware link | Instruction effects derived from netlist faults | The memory interface and external fetch path become a role of their own (that is where faults are seen in practice); memory macros are black boxes with free outputs; nothing is claimed as a first |
| 8. Low-cost bench (first hardware) | Test the method's predictions on an FPGA, from the FPGA's own timing | See section 8 |
| 9. Own chip on an open shuttle | Per-flop comparison on the analysed netlist | See section 8 |
| 10. Hardening advice | Suggest, apply to a copy, re-check | "Raises the minimum under model M from a to b", never "fixes"; all models re-run after a fix |
| 11. Papers | Written only when a gate is passed | A first paper needs an experienced co-author who has read the draft |
| 12. Passive attacks | Same intake for masking, secret flow, constant-time | Export to established verifiers before building any check |
| 13. Platform and education | Labs a teacher can run without the author | Offline release bundle with wheels; a Windows smoke test; syllabus placement page; static slide export; an ethics and law paragraph linking the disclosure page; a "report from a class" template; success is counted in named users, outside issues and outside re-runs, not in downloads |

---

## 8. Hardware notes (corrected; nothing is bought before G3)

- **ChipWhisperer-Nano cannot produce clock glitches** (verified in the vendor documentation). It offers a
  crowbar voltage glitch with steps of about 8.3 ns and offset jitter up to about 200 ns, so cycle-exact
  voltage targeting is not possible with it; only statistics over a window.
- **PicoEMP is not for this project.** Its own documentation says it is not designed for professional or
  educational environments, that the shield is critical for safe operation, and that the output (about
  250 V) is uncalibrated. EM hardware is removed from the plan; the EM model stays unvalidated and says so.
  No infrared laser setup is built or used.
- **Tiny Tapeout clock:** the pad documents a maximum input frequency of 66 MHz and an insertion delay of up
  to 10 ns between pad and project clock (verified on the specification page). That shared path is not in the
  tile's timing files and will reshape or swallow narrow pulses. So an **on-chip glitch generator is the
  primary source**, measured on every attempt by an on-chip delay-line ruler; a ring oscillator is divided on
  chip and its count read out.
- **Bench design (Phase 8), if it is ever built.** The read-out sits outside the glitched clock domain, or is
  shown by the model itself to be unfaultable at the swept depths. The delay ladder is a **ruler**, not the
  prediction target; targets are designs whose delays were not chosen. Per faulty flop the bench logs old
  value, expected value and captured value, so the **stale fraction** is measured: that is the model's central
  unverified assumption. Hypotheses, the statistic (rank correlation with a permutation test, a resolution
  check, a negative control), the attempt budget and the thresholds are tagged in git before power-up. A
  second board is the main repeat; temperature only checks uniform scaling.
- **Own chip (Phase 9).** A core-rail glitch also hits shared logic; a signature register and a project-id
  read after every attempt separate "shared-logic upset" from the design's own outcomes. A second placement
  of the same check is described only as a timing-diversity test. Spread across dies from one run is
  "within-lot spread".

---

## 9. Do-not-claim list

| Do not claim | Say instead |
|---|---|
| First SAT or formal gate-level fault tool; first minimum-fault search | "An open re-implementation of established bounded fault search over Yosys netlists" |
| First timing-aware glitch assessment; "physics-aware prior work is closed" | Simulation-based timing-aware work exists, some with a public artifact. Use the hedged sentence of section 6, 2.1 |
| First layout-aware laser or EM analysis; first link from gate faults to instruction faults; first outcome classes | Name the earlier work; describe only the combination |
| "Nobody combines these parts" as a fact | "In the sources we checked, as of <month year>, we found no tool combining ..." |
| "Physically accurate", "silicon-validated", "certified", "sign-off" in the present tense | "Physically motivated, uncalibrated model"; "sign-off" only as the far goal |
| "k glitches needed"; "success probability"; "three copies need three glitches" | Section 5 |
| "Proves the design secure"; "sound" for a setup-only mode | "No attack within model M, mode, shape, depth bound, k and N" |
| A depth in picoseconds as if it could be dialled on a bench | Level index and fraction of the period, at a named corner |
| That self-consistency between two programs fed the same delays validates the physics | "Implementation consistency" |
| A fixed direction for glitch faults (only 1 to 0) | Direction follows the data; rise and fall sets come from timing |
| "Hitting a clock buffer always resets the chip" | Reset as a possible outcome, reported separately |
| "SPICE-derived" without a SPICE run in the repository | Name ngspice only where the run exists |
| Per-cell calibration from an FPGA; that hardware "proves" a warning | Method-level agreement rates only |
| Attack-potential points or levels as tool output | Plain facts a lab may use |
| "Existing tools failed adoption" | "Existing open formal tools model faults logically, as their authors state" |
| New methods in masking, secret flow, constant-time | "Same workflow, survival through the build" |
| A weakness in someone else's project from an open-flow build alone | "Observed in the open-flow build with <tool, version, script>; please confirm with your production flow" |
| Any number not re-run this release | Mark it "recorded" with date and versions |

---

## 10. Field map (technical positioning only)

From a survey made in November 2026. It was not exhaustive; many groups were not checked. Read every "not
found" as "not found in that survey".

| Line of work | What it has | Relation to this plan | Open? |
|---|---|---|---|
| SYNFI | Formal fault injection on Yosys netlists of an open secure chip | Baseline 1; same kind of search with logical faults; the comparison of Phase E | Apache-2.0 |
| FIRMER | SAT encoding of fault resistance with two-level bounds | Baseline 2; compared only through its unmodified code or published numbers | Licence to be confirmed (verify) |
| FIVER, VERICA, FIESTA | Decision-diagram and statistical verification; combined fault and side-channel analysis | Baselines for scale and for Phase 12. **FIESTA has a public artifact under BSD-3-Clause**; it is statistical, not exhaustive | VERICA open; FIESTA open |
| uArchiFI and fault-resistant partitioning | Formal fault proofs on processors with software; a research line on formal clock-glitch modelling built on bench characterisation | Closest research neighbour for Phase 2; cite first; do not claim a first | Partly public (verify) |
| FLAT and related layout-aware flows | Criticality analysis, then layout feasibility | Closest prior art for timing- and layout-derived sets; by simulation | Closed flows |
| CRAFT | Clock-glitch sweeps on a post-synthesis processor netlist, checked on FPGA; post-route delays mattered | Template for an agreement table | No code found |
| GlitchGlück | Gate-level simulation with layout-derived timing for clock glitches; register coordinates for a laser spot | Closest simulation-based neighbour; **has a public artifact** (licence and contents: verify) | Artifact public; simulator commercial |
| Two surveys written for newcomers (2024) | Taxonomy of fault simulators; open problems: feasibility, benchmarks, open tools | Framing for the learner mission | Open papers |
| Low-cost clock-glitch benches (published designs) | Multi-fault clock-glitch hardware | Designs to study if Phase 8 opens | Public |

One-line position: the SAT search is shared with the formal tools; the physics is shared with the
simulation-based tools; what was not found is the joint package of open source, physics taken from an open
flow, and explanation for learners. It is a niche of combination, not of any single technique.

**Possible first users** (what must exist first): designers on open shuttles with a lock or boot check in
their tile (Phase E); teachers of hardware-security or chip-design classes (Phase 0 and the pilot);
verification engineers trying it on open designs at home (PE.7 exports). Adoption into a tape-out sign-off
flow is not in any horizon of this plan.

---

## 11. What "done" looks like (no dates)

- **After Stage A:** accurate wording everywhere; the app teaches the physics before the model; a small,
  secure, strictly tested and documented core; the survival checker at 1.0; an independent comparison posted
  upstream.
- **After Stage B:** three tables and a short note that answer the one question, with a tagged release and
  an archive identifier. Three named people outside the project have run something and said so, or the count
  is recorded as zero.
- **Far goals (kept, not scheduled):** the open benchmark re-run by someone else; predictions committed
  before a bench or silicon measurement, with misses published; labs a teacher elsewhere can run without
  contacting the author; one confirmed RTL-level weakness or one accepted improvement to an open project's
  build constraints, reported responsibly; installation with one command for the core and one pinned
  container for the flow.

---

## 12. Verify list (short form)

| Item | Status |
|---|---|
| ChipWhisperer-Nano clock glitching | **verified: no**; crowbar steps about 8.3 ns, offset jitter up to about 200 ns |
| Tiny Tapeout clock pad limit 66 MHz; insertion delay up to 10 ns | **verified** (specification page); tile dimensions, external clock source, shared-rail contents: verify |
| FIESTA artifact licence | **verified**: public, BSD-3-Clause |
| PicoEMP vendor scope statement | **verified** (project readme) |
| What the 2024 synchronous clock-glitch paper concludes about timing-violation models | verify (Phase R, first item) |
| GlitchGlück artifact: licence, contents | verify (Phase R) |
| FIRMER repository and licence | verify |
| OpenSTA: `report_checks -format json`, per-endpoint options; `set_timing_derate` cell-delay and cell-check options; command that lists unconstrained endpoints | options exist in the current reference; exact names on your build: verify with `help` |
| Older option names in `tools/vlab/eda/regen_sdf.tcl` | may fail on a current build: verify |
| Yosys Liberty lowering keeps flop instance names on the placed V2 | verify (P1.8) |
| LibreLane install route on Linux Mint; run-folder file names | verify (session 4) |
| Input format of the closest open tool for PE.7 | verify |
| iCE40 PLL fine-delay step; nextpnr SDF export | verify (only if Phase 8 opens) |
| Proof-checker availability for the chosen solver | verify (P1.2) |
| Every hardware price and every event date | verify when needed |

---

## 13. What could change

| Assumption | Sign that it is wrong | New route |
|---|---|---|
| No open tool already gives timing-derived fault sets for a formal search | Phase R finds one | Contribute to it or publish a comparison only |
| Slack ordering is the right abstraction for clock glitches | Phase R full-text reading says otherwise | Redesign Phase 2 on paper first; branch sets and sampling effects become primary |
| A late flop keeps its old value in most captures | Mode coverage or the transistor-level check shows many other captures | `either` is no longer offered as an attack finder; `ternary` is the default |
| Hold-side faults are rare | The transistor-level check shows early captures | Hold sets become mandatory in every M1 statement |
| Narrow pulses behave like shortened periods | The transistor-level check shows branch-skip faults | `inserted_edge` and `narrow_pulse` become the default shapes |
| Witnesses from `hold` are usually real | Replay confirms fewer than half | Only replayed witnesses are reported as attacks |
| The verdict is stable under delay variation | Monte Carlo flips it in a large share of draws | Report sets and sensitivity only (kill criterion K5) |
| A laptop can run the open flow on the chosen block | Flow runs fail or take days within the time box | Stay with toy designs; teaching tool, no research claim (K6) |
| The project keeps a single maintainer | True by default | Continuity measures are on the main path: reviewed pages, pinned environment, release notes, this handoff |
| Learners are the first audience | Most real users turn out to be engineers | Keep the story first; the engineer profile already exists |

Standing checks: a literature sweep twice a year and before every public text; the strict test run and the
wording check before every release; sections 5 and 9 re-read before every talk, paper or README change.

---

## 14. Sources to read yourself

1. Agoyan et al., "When Clocks Fail: On Critical Paths and Clock Faults", CARDIS 2010.
2. Zussa et al., power glitches as timing-constraint violations.
3. Marotta et al., "Characterizing and Modeling Synchronous Clock-Glitch Fault Injection", COSADE 2024.
4. Dutertre et al., FDTC 2018 (laser, 28 nm); Dumont, Lisart, Maurine, FDTC 2019 (EM sampling faults).
5. Nasahl et al., SYNFI. Tan et al., FIRMER. Tollec et al., uArchiFI and fault-resistant partitioning.
6. CRAFT (2025); FLAT (2024); GlitchGlück (2025).
7. The 2024 systematisation-of-knowledge papers on fault injection tools.
8. The smartcard attack-potential document and the PSA attack-method notes (what labs count).
9. lowRISC's notes on pre-silicon and physical security testing (why FPGA results do not transfer).

Tool documentation: OpenSTA, OpenROAD, LibreLane, the PDK manager `ciel`, the IHP open PDK.
