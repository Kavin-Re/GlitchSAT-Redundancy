# Handoff notes for any contributor or tool

Read this file first, whoever or whatever you are: the maintainer after a long break, a new contributor, or a
software tool asked to work in this repository. It is written so that work can continue with no memory of
earlier conversations. Keep it short and true; when the phase or the next step changes, update the two
sections marked **(keep current)**.

## 1. What this project is

GlitchSAT is an open-source (Apache-2.0) fault-analysis tool for digital chip designs, built for learners
first. Given a gate-level netlist from Yosys, it searches for the smallest number of **modelled bit flips**
that defeat a protection (for example a boot check), reports the finding in plain words, and checks whether
a protection survived synthesis ("did the countermeasure survive the build?"). A teaching app, the Studio,
explains why chips are protected and what the results mean. The long-term aim is an open, physically
grounded fault-analysis tool whose fault sets come from timing and layout; the near-term path is one small
question: does adding timing change the verdict on a real protected block?

## 2. Current state and known limits

- Version 0.9.0, `main` at `96b28f4` when this file was written (23 November 2026). No release tag exists yet.
- Every result is a **modelled** result. Nothing was measured on hardware. Delays in the timing lab are
  ASSUMED.
- The fault model in use (M0) flips single bits independently. It does not show that one clock or voltage
  glitch can upset many flip-flops, or all identical copies, at once.
- Known defects, all with backlog entries: learner text that teaches "a glitch = one bit flip" and "three
  copies need three glitches"; evidence output that prints scheme scores; the installed command can import
  code from a parent folder of the current directory (**run it only in folders you trust**); the test runner
  reports PASS when nothing ran; an oversized wheel; several duplicate engines.
- Treat anything outside the owned core (section 3) as "carried": keep it working, do not extend it. New
  work goes into the core first.

Full table: `docs/plan/ROADMAP.md`, section 2.

## 3. Repository map

| Path | What it is | Status |
|---|---|---|
| `scripts/glitchsat.py` | Reference engine (z3), bounded bit-flip search | Owned core |
| `tools/fastsat/` | Direct CNF encoder; the future single engine | Owned core |
| `validation/` | Independent gate-level simulator (test oracle) | Owned core |
| `tools/vlab/` | Timing-based clock-glitch simulation on placed layouts | Owned core |
| `tools/checker/`, `tools/surface/` | "Did the protection survive the build?" and merge lint | Carried; finished first in Phase E |
| `tools/findings/`, `tools/byod/` | Plain-words findings; own-design intake (`glitchsat.yaml`) | Carried |
| `tools/studio/`, `docs/edu/`, `docs/explainers/` | The teaching app, lab sheets, explainers | Carried; text corrected in Phase 0, features frozen |
| `product/` | The installable package: CLI, evidence, SARIF, CI action | Carried; contains a copied engine to be removed |
| `formal/` | SymbiYosys re-checks (test oracle) | Carried |
| `tools/real/`, `tools/soc/`, `tools/secboot_hw/`, `layout/`, `real_designs/` | Real open designs and layouts | Carried; third-party parts to be fetched by script |
| `tools/shots/`, `tools/harden/`, `tools/firmware/`, `tools/unbounded/`, `tools/scale/`, `tools/masking/`, `tools/bootloader/`, `tools/labs/`, `tools/opentitan/`, `tools/datasets/` | Earlier experiments | Frozen until gate G3 |
| `research/`, `docs/report/`, `docs/dossier/`, `docs/comms/` | Project history | To be archived under a tag |
| `tools/check_wording.py` | Wording and path check for shipped files | Use it on everything you write |
| `docs/plan/` | Roadmap, backlog, decisions, kill criteria | The plan of record |

## 4. Set up and test (Linux Mint 22; details and fallbacks in `docs/plan/START_HERE.md`)

```bash
sudo apt-get install -y git python3-venv python3-pip yosys iverilog graphviz
git clone https://github.com/Kavin-Re/GlitchSAT-Redundancy.git && cd GlitchSAT-Redundancy
python3 -m venv .venv && . .venv/bin/activate
pip install -r ci/requirements-ci.txt pyyaml jsonschema numpy networkx python-sat
pip install -e .

make check-tools
python3 -m pytest -q tests product/tests
python3 scripts/test_all.py                 # read the counts: PASS with 0 passed means "did not run"
python3 tools/check_wording.py tools product scripts docs
make reproduce && make check-reproduce      # 36 of 36 rows with Yosys 0.33
git checkout -- results tb                  # reproduce rewrites tracked files; restore them
```

Baseline that must hold: V0, V1, V2 need 1, 1 and 3 modelled bit flips
(`python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6`).

## 5. Standing rules

1. **Commit identity.** `Kavin K K <219786728+Kavin-Re@users.noreply.github.com>`. No co-author lines or
   trailers. Commit messages describe the change only.
2. **Do not push, tag, publish or open issues.** Only the maintainer does. Prepare branches or patches and stop.
   Never contact a third party on the project's behalf.
3. **The repository describes the tool.** No affiliations, programmes of study or names of people other
   than cited authors and contributors who asked to be credited.
4. **No private details** in this repository: no personal contacts, correspondence or work logs. They are
   kept outside it (section 9).
5. **Results are modelled bit flips (or modelled events under a named model), never "glitches".** "Glitch"
   names only the physical act. See the vocabulary table in the roadmap, section 5.
6. **Label everything.** Verdicts: PROVED, BOUNDED or SAMPLED. Numbers: COMPUTED (older files: MEASURED),
   SIMULATED, ASSUMED, SOURCED or recorded. A "no attack" statement always names model, mode, shape, depth
   bound, k and N.
7. **Learners first, in words, never in physics.** Plain words may simplify a model; they must not
   contradict it. Every finding says its severity, where and how it was found, why it matters, and what the
   number does not cover.
8. **No overclaiming.** Check `docs/plan/ROADMAP.md` section 9 (do-not-claim list) before writing any README,
   release note, talk or paper text. Novelty sentences are hedged and dated.
9. **Withheld material stays withheld.** One finding is under responsible disclosure; its identifiers are
   refused by the wording check. Do not add them, describe them or work around the check. See
   `docs/RESPONSIBLE_DISCLOSURE.md`.
10. **Depth before breadth.** Do not add a module, a model or a direction that is not the next backlog
    entry. If asked to, first name what is frozen to pay for it and write it in `docs/plan/DECISIONS.md`.
11. **Document before extending.** New core code is small, readable and documented (module docstring or
    design note) before it is merged. Prefer deleting duplicates to adding layers.
12. **A failing check is fixed or logged, never ignored.** Never edit expected results to silence a test.
13. **Software only.** No step needs hardware or paid services.
14. **Run `python3 tools/check_wording.py <files>` on every file you add or change.**

## 6. Where the plan is

| File | Use |
|---|---|
| `docs/plan/ROADMAP.md` | Direction, phases, gates, vocabulary, do-not-claim list |
| `docs/plan/START_HERE.md` | The first sessions, step by step |
| `docs/plan/BACKLOG.md` | Numbered entries in order |
| `docs/plan/DECISIONS.md` | Decision log; entries marked "proposed" wait for the maintainer |
| `docs/plan/KILL_CRITERIA.md` | When to stop or change direction; read at the start of every phase |
| `docs/plan/SESSION_LOG_TEMPLATE.md` | The end-of-session record |
| `docs/RESPONSIBLE_DISCLOSURE.md` | What happens when the tool points at someone else's weakness |

## 7. Current phase and next step **(keep current)**

- **Stage A, before Phase 0.** The plan files are in place. Backlog #002 is done: the proposed decisions
  were settled on 2026-11-23 (D-016 to D-022), and the wording-check exemption of D-015 is implemented.
- **Next concrete step:** backlog #001 (`START_HERE.md`, session 1): set up, run everything once, commit
  `docs/plan/ENVIRONMENT.md`.
- **Then:** #003 to #005 (session 2: wording, card M0, the extended wording check), #007 (remove the rating
  output), and #020 (the import-path security fix), which may be done at any time and should not wait.
- **Do not start:** any new fault model, any new Studio view, anything in Stage B or C.

## 8. How to log a session **(keep current: last session date)**

Last session: none yet under revision 2.

At the end of every session fill `docs/plan/SESSION_LOG_TEMPLATE.md` (ten minutes; sections 1, 3 and 8 are
required). A contributor puts it in the pull-request description; the maintainer keeps theirs outside this
repository. Decisions go to `docs/plan/DECISIONS.md`. If
the phase or the next step changed, update section 7 of this file in the same commit.

## 9. Private notes

Non-technical planning and correspondence are kept outside this repository. Nothing in them is needed to
work on any backlog entry here.
