# Backlog (revision 2)

This is the project's ordered plan, not a list to paste into the issue tracker in one go. The numbers of
revision 1 are retired; this file renumbers from #001.

**How an entry becomes a public issue.** Entries marked **[issue]** are written so that someone without the
project's history could do them: the heading is the issue title, the text is the body, "Done when" is the
acceptance test. Open them one at a time, when you are ready to review an answer. Suggested labels:
`good first issue`, `help wanted`, `kind/bug`, `kind/feature`, `kind/docs`, `kind/design`, `area/core`,
`area/cli`, `area/schema`, `area/studio`, `area/checker`. Use milestones named after phases, not phase labels.
Entries without the mark are maintainer work (setup, reading, decisions, core review).

**Fields.** Step = the step in `ROADMAP.md`. Size: S = one session (about 2 hours); M = two or three; L = four
or more, split it when you start. Depends on = entries that must be done first.

**Rules.** Work top to bottom inside a phase. One session in three may be a background-reading (L) or core-review (C)
entry. No entry from Stage B starts before gate G1; none from Stage C before gate G3. Before adding an entry
for a new direction, name what is frozen to pay for it in `DECISIONS.md`.

---

## Setup

### #001 Set up the laptop and record a baseline
Step: START_HERE session 1 | Size: S | Depends on: -

Install packages, create the environment, run every suite, `make reproduce`, and the three demo commands.
Done when `docs/plan/ENVIRONMENT.md` is committed and every suite with zero passed tests has a known reason.

### #002 Confirm the proposed decisions
Step: START_HERE 1.7 | Size: S | Depends on: #001

Read `DECISIONS.md` entries marked proposed (D-006, D-012 to D-015) and accept or replace each.
Done when no entry needed by Phase 0 or 0.5 is still "proposed".
**Done 2026-11-23:** D-016 to D-022.

---

## Phase 0: accuracy fixes

### #003 Reword README and START; rewrite NOTICE
Step: P0.2 | Size: S | Depends on: #001

Apply the before/after tables in `START_HERE.md` 2.4. NOTICE becomes a short notice with no folder notes.
Done when `grep -n -i -E "[0-9]+\**\s+glitch" README.md START.md NOTICE.md` finds nothing.

### #004 Write fault-model card M0 with a formal statement row
Step: P0.3 | Size: S | Depends on: #003

Create `docs/FAULT_MODEL_CARD.md` from the skeleton in `START_HERE.md` 2.5.
Done when the README "Limits" section links to it and the card has the independence and formal-statement rows.

### #005 Extend the wording check with glitch-count patterns [issue]
Step: P0.4 | Size: M | Depends on: #003

Add a "unit" finding kind to `tools/check_wording.py` (patterns in `START_HERE.md` 2.6), paragraph-level,
with a shrinking not-yet-fixed list. The file-name exemption for the two root handoff files is already in place (D-020).
Done when the check fails on a planted "3 glitches needed" in a fixed file and passes on the fixed files.

### #006 Claims file for learner text
Step: P0.4 | Size: S | Depends on: #005

Write `docs/edu/CLAIMS.md`: each claim a learner page may make about glitches, copies and the number.
Done when the Studio, the class plan and the lab sheet are on the check's list against it.

### #007 Remove attack-potential output
Step: P0.6 | Size: M | Depends on: #001

Remove the scheme totals, band and level verdicts from JSON, SARIF, HTML and Markdown under
`product/src/faultbound_wt/evidence/`; remove the level-gating option from the CLI, CI and the action. No
default `security-severity`; `precision: medium`. Regenerate `product/examples/evidence/`.
Done when a new test fails on any rating word in default output and `python3 -m pytest -q product/tests` passes.

### #008 Findings text: independence sentence and severity rule
Step: P0.5 | Size: M | Depends on: #005

In `tools/findings/plain_findings.py` and `SEVERITY.md`: count "modelled faults"; the "protection held" card
carries the independence sentence; severity is not lowered for k of 2 or more without it.
Done when a test asserts the sentence wherever "protection held" fires, and `tools/findings/tests` pass.

### #009 Rewrite the mechanism screens (story)
Step: P0.7 | Size: M | Depends on: #006

`tools/studio/first_run_view.py`: glitch event, then many slow flops capture wrong values in one cycle, then
the model as a simplification. Remove "exactly". End the protection screen with the question that leads to
"Two models disagree".
Done when the screens pass the claims check and `python3 scripts/test_all.py --only studio` passes.

### #010 Rewrite the lesson and quiz
Step: P0.7 | Size: M | Depends on: #009

`tools/studio/learn_view.py`: the "what is a glitch" quiz item and its answer; "copies of a check" with the
diversity explanation; a new "diversity" protection card; the quiz item that says "perfectly-timed".
Done when the changed items pass the claims check.

### #011 Class plan and answer key
Step: P0.7 | Size: S | Depends on: #010

Bring `/teach`, `docs/edu/ANSWER_KEY.md` and `INSTRUCTOR_NOTES.md` in line; add the four misconception rows;
review and date the instructor notes.
Done when no learner file contradicts `docs/edu/CLAIMS.md`.

### #012 True stories: "What GlitchSAT models of this"
Step: P0.7b | Size: S | Depends on: #009

One line per story card with one of the three answers; delete "exactly what GlitchSAT counts".
Done when every story card has the line.

### #013 Screen "What the attacker actually searches"
Step: P0.7b | Size: M | Depends on: #010

Reuse the existing clock-glitch sweep grid; state "perfectly timed" as a model assumption.
Done when the screen is in the lesson path and passes the Studio suite.

### #014 Screen "Two models disagree" and the number fold
Step: P0.8 | Size: M | Depends on: #013

Bit-flip result next to the clock-glitch sweep on the same lock, labelled SIMULATED with assumed delays; an
old value / new value table; a fixed fold "What does this number mean?".
Done when both are reachable from every result screen.

### #015 Learner labels and glossary strip
Step: P0.9, P0.10 | Size: M | Depends on: #002

COMPUTED in learner text; three labels on first contact; a strip mapping plain words to chip-design terms;
the vocabulary table in `docs/GLOSSARY.md`.
Done when D-010 is accepted and the first-run screens show three labels.

### #016 Remaining Studio and own-design text
Step: P0.7 | Size: M | Depends on: #009

`tools/studio/studio.py` and `tools/byod/tools/studio/byod_view.py`: only what is counted changes.
Done when the not-yet-fixed list of #005 no longer contains a Studio file.

### #017 Concept check and outside read
Step: P0.12 | Size: S | Depends on: #011

Five questions with defensible answers in `docs/edu/`; one person who has not seen the project reads the
README and the card and writes what "the answer is 2" means.
Done when their sentence is in the log and contains "model", or the text was fixed again.

### #018 Pilot with a small group
Step: P0.13 | Size: M | Depends on: #014, #017

3 to 10 people use the corrected material on a prepared machine; record times, errors, quotes, and scores
before and after.
Done when the results are written up (no names) and kill criterion K14 has been checked.

### #019 Regenerate stored examples and release v0.9.1
Step: P0.14 | Size: M | Depends on: #007 to #016, #033

Regenerate `tools/byod/examples/*` stored outputs; run all suites; `docs/NUMBERS.md` headers;
`python3 scripts/check_numbers.py --verify`; changelog entry "what our number means"; tag.
Done when the tag exists and no file points at a tag that does not.

---

## Phase 0.5: repository health

### #020 Import only from the installed package (security) [issue]
Step: P05.1 | Size: M | Depends on: #001

Remove the search through parent folders in `product/src/faultbound_wt/glitchsat_main.py` and the
`sys.path` fallbacks; a checkout is used only through an explicit environment variable.
Done when a test that runs the CLI from a folder containing a decoy `tools/byod/glitchsat_byod/cli.py` shows
the decoy is not executed, and `SECURITY.md` describes the fix.

### #021 One import package
Step: P05.1 | Size: L | Depends on: #020

Make the own-design intake, findings and the encoder real sub-packages under one import name; old import
name kept as a shim for one minor release.
Done when no shipped file manipulates `sys.path`.

### #022 Strict test mode [issue]
Step: P05.2 | Size: S | Depends on: -

`scripts/test_all.py --strict`: a suite fails if it collects nothing or skips more than its declared budget.
The masking suite skips cleanly when Yosys is missing.
Done when a suite with zero collected tests fails in strict mode and CI uses strict mode.

### #023 Remove duplicate and orphan tests; stop rewriting tracked files
Step: P05.2 | Size: M | Depends on: #022

Keep one copy of each duplicated test; run or delete test files under `docs/`; generated output goes to an
ignored `build/` folder.
Done when `make reproduce && git status` shows a clean tree.

### #024 Declare dependencies; wheel-only CI job; lock file [issue]
Step: P05.3 | Size: S | Depends on: -

Done when CI installs the built wheel into an empty environment with no extra install lines and the core
suite passes.

### #025 Pinned analysis container
Step: P05.4 | Size: M | Depends on: #024

One image by digest (Yosys, Icarus Verilog, CaDiCaL, proof checker, z3, PySAT); CI uses it; the Dockerfile
no longer uses an unpinned base.
Done when every result written in CI names the digest.

### #026 Folder fate table
Step: P05.6 | Size: S | Depends on: #002

For every top-level folder and every folder under `tools/`: core, Studio package, fetched by script, or
archived.
Done when the table is in `docs/plan/` and D-006 is accepted.

### #027 Move inputs that code still reads out of `research/`
Step: P05.5 | Size: M | Depends on: #026

Find non-research files that reference `research/...` paths; move those inputs to `tests/data/`.
Done when `grep -rn "research/" --include=*.py tools scripts product tests` finds no read of a research path.

### #028 Archive tag and slim default branch
Step: P05.5 | Size: M | Depends on: #027

Tag `archive/pre-split-0.9`; remove `research/`, report, slide and step-report folders from the default
branch.
Done when all suites pass on the slim branch.

### #029 Core-only wheel; Studio as its own package
Step: P05.5 | Size: L | Depends on: #021, #028

Done when the core wheel is a few megabytes and contains no third-party sources, and `glitchsat-studio`
installs from the same repository.

### #030 Third-party material fetched by script; licence lint
Step: P05.5 | Size: M | Depends on: #028

Fetch at pinned commits with checksums; pin or remove `real_designs/fsm.v`; licence lint in CI.
Done when the lint passes and `THIRD_PARTY.md` describes only what is in the repository.

### #031 Result envelope `glitchsat-result/1` (draft) [issue: design]
Step: P05.7, P0.11 | Size: M | Depends on: #002

Schema with tool, inputs, environment, fault model, bounds including `depth_bound`, verdict, verdict label,
minimum, witnesses, outcomes, proof hash, payload; a compatibility page.
Done when the two engines' writers validate against it in tests.

### #032 One command line; exit codes; generated reference [issue]
Step: P05.8 | Size: M | Depends on: #021

Done when old command names print a deprecation notice, `docs/reference/cli.md` is generated from `--help`
and CI fails on drift.

### #033 Release files and a dry run
Step: P05.9 | Size: S | Depends on: -

`RELEASING.md`, `CHANGELOG.md` with the `result-affecting` mark, `CITATION.cff`; run the release workflow
and the action once on scratch targets; fix every reference to a tag that does not exist.
Done when `git grep -n "v0.9.0"` shows only true statements.

### #034 Contributor basics
Step: P05.10 | Size: S | Depends on: -

Sign-off rule with a check, pull-request template with the label checklist, "result disagreement" issue
template, code of conduct, linter on the core, branch protection, private vulnerability reporting enabled.
Done when a pull request without sign-off fails its check.

### #035 Documentation tidy
Step: P05.11 | Size: M | Depends on: #028

Tutorial, how-to, reference, explanation; review or remove any page marked as not yet reviewed; remove
internal step names from public docs.
Done when `docs/` has those four groups and no such page.

---

## Phase C: core review

### #036 Re-derive the engine from scratch
Step: C2 (START_HERE session 3) | Size: M | Depends on: #001

Done when an independent script gives minima 1, 1, 3 on V0, V1, V2 and the differences are logged.

### #037 Encoder map
Step: C3 | Size: M | Depends on: #036

`tools/fastsat/ENCODER_MAP.md`: fault variables, totalizer outputs, assumptions, fault collapsing and what
it assumes.
Done when the map gives the file and line range of each of those places.

### #038 Break it on purpose
Step: C4 | Size: S | Depends on: #037

Five mutations, each with a prediction of which test fails, written before running.
Done when five predictions with hits and misses are in the log.

### #039 Design notes for the four core parts
Step: C5 | Size: M | Depends on: #037

One page each: the reference engine, the CNF encoder, the independent simulator, the timing lab.
Done when four notes exist and every open question is an entry or an issue.

---

## Track L: background reading

### #040 L1 Fault attacks | Size: M | Before #009
### #041 L2 SAT and bounded model checking | Size: L | Before #036
### #042 L3 Static timing analysis | Size: L | Before #060
### #043 L4 The open flow | Size: L | Before #060
### #044 L5 Hardware security in context | Size: L | Any time
### #045 L6 Scientific writing | Size: S | Before #079

"Done when" for each is in `ROADMAP.md`, Track L.

---

## Phase E: survival checker 1.0 and the upstream comparison

### #046 Stable finding identity [issue]
Step: PE.1 | Size: M | Depends on: #031

Carry Yosys `src` attributes into findings; fingerprints from countermeasure id, goal id, model id, RTL
signal and cycle offset.
Done when two builds of V2 that differ by an unused wire give identical fingerprints.

### #047 Countermeasure ids and the traceability table
Step: PE.2 | Size: M | Depends on: #046

Done when a `countermeasure_id` in `glitchsat.yaml` appears in JSON, SARIF properties and the report table.

### #048 Report template
Step: PE.3 | Size: M | Depends on: #047

Done when `docs/REPORT_TEMPLATE.md` renders for one gallery example with all sections filled.

### #049 Unsupported constructs stop the run [issue]
Step: PE.4 | Size: M | Depends on: -

A list of supported and unsupported netlist constructs; black-box outputs free; functional-mode constraints
in the project file.
Done when a netlist with an unsupported cell exits with a clear message and a non-zero code.

### #050 Waivers and profiles
Step: PE.5 | Size: M | Depends on: #046

Waiver file with expiry; `--profile engineer|learner` from one result; the action does not upload SARIF by
default.
Done when an expired waiver fails the job.

### #051 Seeded-defect suite (small) [issue]
Step: PE.6 | Size: M | Depends on: #046

Four weakenings of a hardened design, each with an expected finding; each untouched design with an expected
"no finding within bounds".
Done when detection and false-alarm counts print in CI.

### #052 Trace export as a simulation testbench [issue]
Step: PE.7 | Size: M | Depends on: #031

Done when the exported testbench reproduces the finding in Icarus Verilog for every gallery example.

### #053 Independent reference re-run and semantic alignment table
Step: PE.8 | Size: L | Depends on: #025

Run the published tool unmodified with its real dependencies in the pinned container; store the reference;
delete the stand-in shims; route the comparison through the core.
Done when the agreement test runs against the stored independent reference and the alignment table is in
`docs/PRIOR_ART.md`.

### #054 Upstream: reconciliation issue
Step: PE.9a | Size: S | Depends on: #019, #053

Draft the issue with the exact command; the maintainer posts it.
Done when it is posted and the link is in the log.

### #055 Upstream: three small offers
Step: PE.9b to PE.9d | Size: S each | Depends on: #054

Optional-import change; licence question to the second tool's authors; build fix for the third tool.
Done when each is posted or a reason not to is logged.

### #056 Export in the other tool's input format
Step: PE.7 | Size: M | Depends on: #053

Done when one finding is re-run in the other tool from the exported files (format: verify first).

### #057 Checker 1.0 release and gate G1
Step: Gate G1 | Size: S | Depends on: #019 to #056

Answer the four G1 questions in `DECISIONS.md`; record the outside-user count (K9); set the Stage B time box.
Done when the entry is written.

---

## Phase R: reading gate

### #058 Read the three works and write the one page
Step: Phase R | Size: L | Depends on: -

In order: the 2024 synchronous clock-glitch modelling paper; FLAT; GlitchGlück and its artifact. Also
record FIESTA's public BSD-3-Clause artifact.
Done when `docs/PRIOR_ART.md` has the dated page with "what it does that we do not, and the reverse".

### #059 Gate G2
Step: Gate G2 | Size: S | Depends on: #058

Done when K1 and K2 are answered in `DECISIONS.md`.

---

## Phase 1: core (after G1 and G2)

### #060 Install the flow; real timing for V1 and V2
Step: P2.1, P2.2 (START_HERE session 4) | Size: L | Depends on: #042, #043, #057

Done when `report_checks` prints a path for the placed V2 and the timing lab ran with sourced delays.

### #061 One engine
Step: P1.0 | Size: L | Depends on: #037, #057

Done when `glitchsat analyze` runs the CNF core, the copied engine is deleted and the z3 engine lives under
`tests/oracles/`.

### #062 Golden corpus with witness replay and oracles
Step: P1.1 | Size: L | Depends on: #061

Done when the corpus covers the 36 rows and the other listed designs, compares verdict and minimum, and
replays witnesses.

### #063 Real solvers, proof checking, fallback solver fuzzed
Step: P1.2 | Size: M | Depends on: #062

Done when every `NO_ATTACK` in the corpus has a checked proof and its hash in the result.

### #064 Fault-set file format and the M0 producer [issue: design]
Step: P1.3 | Size: L | Depends on: #031, #061

Done when `glitchsat analyze --faultsets` reproduces the corpus from M0 fault-set files.

### #065 Effects: set, reset, hold, either, free
Step: P1.4 | Size: L | Depends on: #064

Done when each effect matches brute force on the three-flop netlist.

### #066 Effects: early and branch_skip
Step: P1.4 | Size: M | Depends on: #065

Done when a shift-register test shows an early-capture fault and a two-branch test shows a branch skip.

### #067 Event cost, bounds, spacing; N counts steps
Step: P1.5 | Size: L | Depends on: #065

Done when one event that corrupts three flops costs 1 and a test shows `min_gap` removing a two-event attack.

### #068 Collapsing off by default; cross-check with and without
Step: P1.6 | Size: M | Depends on: #065

Done when every effect agrees with and without collapsing, or collapsing is off for that effect.

### #069 Property and metamorphic tests [issue]
Step: P1.7 | Size: L | Depends on: #067

Done when the listed properties run on seeded random netlists in CI.

### #070 One mapped-netlist loader
Step: P1.8 | Size: L | Depends on: #060, #061

Done when the placed V2 loads with flop names intact, is equivalent to the RTL on all 256 inputs, and the
other adapters are deleted or justified.

### #071 Standard-format export; archive the unbounded module
Step: P1.9 | Size: L | Depends on: #064

Done when an existing model checker gives the same PROVED answers on the small designs.

### #072 Release 0.10.0
Step: P1.10 | Size: S | Depends on: #061 to #071

---

## Phase 2: timing-derived glitch model

### #073 Full flow run with parasitics and two corners for V2
Step: P2.3 | Size: L | Depends on: #060

### #074 Timing extraction that fails on unconstrained paths; neutral slack file [issue]
Step: P2.4 | Size: L | Depends on: #073

Done when a planted unconstrained path makes the extraction fail, and setup, hold, rise and fall are in the
slack file.

### #075 Common-mode timing check for redundant copies
Step: P2.4b | Size: S | Depends on: #074

### #076 Level sets, hold sets, branch sets as fault-set files
Step: P2.5 | Size: L | Depends on: #064, #074

### #077 Modes hold, either, free with required depth bound; ternary
Step: P2.6, P2.6b | Size: L (split) | Depends on: #066, #076

Done when no M1 result without `depth_bound` validates, label rules are enforced, and `ternary` matches
exhaustive timed simulation on small cases.

### #078 Shapes: extra edge, narrow pulse, swallowed pulse; hold side in proof modes
Step: P2.7 | Size: L | Depends on: #077

Done when each shape has a brute-force test and every result names its shape.

### #079 Choose the non-toy block and the detector design; write hypotheses first
Step: P2.11, P2.12 | Size: L | Depends on: #073

Done when the choice, the analysis window and the ranking hypotheses are committed before the headline run.

### #080 Implementation consistency with sampled delays; external simulator cross-check
Step: P2.8 | Size: L | Depends on: #076

### #081 Mode coverage and witness replay
Step: P2.9, P2.10 | Size: L | Depends on: #077, #080

Done when every witness in the tables carries `REPLAYED x/N` or `STA-only`.

### #082 Three tables
Step: P2.13 | Size: L | Depends on: #078, #079, #081

Done when the verdict table, the Monte Carlo sensitivity table (threshold from D-013 fixed beforehand) and
the replay table exist with labels.

### #083 Transistor-level check on one small block
Step: P2.14 | Size: L | Depends on: #073, #078

Done when a SIMULATED (SPICE) table lists agreement and every mismatch; K13 checked.

### #084 Soundness notes and card M1
Step: P2.17 | Size: M | Depends on: #082

### #085 Literature sweep, note N1, pre-release, gate G3
Step: P2.18, P2.19, Gate G3 | Size: L | Depends on: #083, #084

Done when the note and `ARTIFACT.md` are public and the G3 answer is in `DECISIONS.md`.

---

## Stage C: parked until gate G3

Not sized, not ordered beyond the roadmap table (section 7). Each line becomes entries only when its phase
opens, and only after an entry in `DECISIONS.md` names what is frozen for it.

- Spot model in SAT with the corrections listed in the roadmap.
- Outcome classes as minimum costs, with detection latency and plain facts for labs.
- Weighted search with a Pareto front.
- Open benchmark with frozen EDA outputs, alignment tables and the full seeded-defect suite.
- Firmware link with the memory-interface role.
- Bench and own chip (first hardware; read roadmap section 8 first).
- Hardening advice with a verify-after-fix loop.
- Passive attacks through export to established verifiers.
- Platform and education: offline bundle, Windows smoke test, labs, static slide export, redaction.
- Parked single items: assertion export; a delay-against-supply characterisation; a second PDK;
  documentation site; request for inclusion in tool bundles; multi-cycle droop profile.
