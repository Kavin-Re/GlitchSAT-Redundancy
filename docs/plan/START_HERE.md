# Start here

Written 23 November 2026 for `main` at commit `96b28f4` (version 0.9.0). Operating system assumed: Linux Mint
(22 preferred; notes for 21 where it differs). If the repository has moved on, trust the repository and fix
this file.

This file spells out the first four work sessions. After them you work from `BACKLOG.md`. You open
`ROADMAP.md` when a phase starts or a gate is reached, and `KILL_CRITERIA.md` at the start of every phase.

| Session | What you do | Time | Changes code? |
|---|---|---|---|
| 1 | Set up the laptop, run everything once, save a baseline | 2 to 3 hours | No |
| 2 | First real change: what the number counts (P0.1 to P0.4) | 2 to 3 hours | Text and the wording check |
| 3 | Re-derive the engine from scratch (L2 and C2) | 2 to 4 hours, may take two sittings | A new cross-check script, nothing shipped |
| 4 (later, after Stage A) | Install the chip-design flow and a PDK; real timing for V1 and V2 | 4 to 8 hours in two sittings, plus downloads | No (new outputs only) |

Three habits from the first minute:

1. **End every session with the session log.** The last ten minutes belong to the log, not to code. The line
   "Next session: start exactly here" is the most valuable line you write.
2. **One branch per backlog item, one topic per commit.** Never mix a wording change with a code change.
3. **Before a new module or phase, answer three questions in writing** (in the log or in `DECISIONS.md`):
   What is the model and what measurement supports it? Who has done this already (date of the search)? What
   result would show it is wrong?

Marks: commands without a mark were checked against the repository or the tool's documentation on the date
above. **(verify)** means not checked on a Linux Mint machine: run it, and if it fails use the fallback next
to it.

---

## Session 1: environment and baseline

### 1.1 Which Linux Mint do you have?

```bash
cat /etc/os-release | grep -E "^(NAME|VERSION|UBUNTU_CODENAME)="
python3 --version
```

- `UBUNTU_CODENAME=noble`: Linux Mint 22 (Ubuntu 24.04 base, Python 3.12, apt Yosys 0.33). Best case.
- `UBUNTU_CODENAME=jammy`: Linux Mint 21 (Python 3.10, older apt Yosys). Everything in Python works. The
  stored reproduce table was recorded with Yosys 0.33, so `make check-reproduce` may report mismatches that
  are tool differences, not bugs. Write that in the log and carry on.

### 1.2 System packages

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip yosys iverilog gtkwave graphviz
yosys -V
iverilog -V | head -1
```

Expected on Mint 22: `Yosys 0.33` and `Icarus Verilog version 12.0`.

### 1.3 Git identity and push access

Use the project's commit identity (see the handoff file at the repository root), with a no-reply address so
no private email enters the history:

```bash
git config user.name  "<name as used in this repository's history>"
git config user.email "<id+username>@users.noreply.github.com"
```

Set these per repository (no `--global`) after cloning. For pushing you need either `gh auth login` (verify:
`sudo apt-get install gh`) or an SSH key added to your account. **Only the maintainer pushes.**

### 1.4 Clone and Python environment

```bash
mkdir -p ~/work && cd ~/work
git clone https://github.com/Kavin-Re/GlitchSAT-Redundancy.git
cd GlitchSAT-Redundancy
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r ci/requirements-ci.txt          # z3-solver (pinned) and pytest
pip install pyyaml jsonschema numpy networkx   # needed by the module suites until P05.3 declares them
pip install python-sat                         # CaDiCaL and others (verify: wheel exists for your Python)
pip install -e .                               # editable install (verify); plain "pip install ." if it fails
```

Every later session starts with:

```bash
cd ~/work/GlitchSAT-Redundancy && . .venv/bin/activate && git status
```

If `pip install python-sat` fails, skip it today; the bundled Python solver works for small designs (it is a
teaching fallback, not a path for published results).

**Until P05.1 is done:** run `glitchsat` only from inside this checkout or from a folder you trust. The
installed command can pick up code from a parent folder of the current directory.

### 1.5 Run everything once

Write the last line of each into the session log.

```bash
make check-tools                                  # yosys, iverilog, z3, pytest found?
python3 -m pytest -q tests product/tests          # engine and command line
python3 scripts/test_all.py                       # every module suite
python3 tools/check_wording.py tools product scripts
python3 scripts/check_numbers.py --verify
make reproduce && make check-reproduce            # 36 of 36 rows with Yosys 0.33, about 25 seconds
make validate                                     # independent simulator, no z3
```

Two warnings about what you see:

- `scripts/test_all.py` reports PASS for a suite in which nothing ran or everything skipped (fixed in
  P05.2). Read the counts, not the word PASS. List every suite with zero passed tests in the log.
- `make reproduce` and `make test` rewrite tracked files under `results/` and `tb/`. After looking:

```bash
git status
git checkout -- results tb        # only if you have made no changes of your own there
```

### 1.6 Three commands to see the tool work

```bash
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6
python3 tools/fastsat/scripts/glitchsat_sat.py sweep reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6
glitchsat-studio          # opens in the browser on 127.0.0.1; stop with Ctrl+C
```

Expected: the first two report an attack with a minimum of **3 modelled bit flips** for V2 (and none with 2
or fewer). If the numbers differ, stop and write down exactly what you saw; do not go on to session 2 until
the baseline is understood.

### 1.7 Save the baseline

The plan files are already in `docs/plan/`. Add the environment record:

```bash
git checkout -b plan/baseline
{
  echo "# Environment baseline"
  date -I
  grep -E "^(NAME|VERSION)=" /etc/os-release
  python3 --version
  yosys -V
  iverilog -V | head -1
  python3 -c "import z3; print('z3', z3.get_version_string())"
  pip freeze | grep -i -E "z3|sat|pytest|numpy|networkx|yaml|jsonschema"
  git rev-parse HEAD
} > docs/plan/ENVIRONMENT.md
python3 tools/check_wording.py docs
git add docs/plan/ENVIRONMENT.md
git commit -m "Plan: environment baseline"
```

The proposed entries in `DECISIONS.md` (time boxes D-014, packaging D-006, repository name D-012, the two
smaller ones) were settled on 2026-11-23 as D-016 to D-022. Read them once; change one only with a new entry.

### 1.8 Close the session

Fill the session log (see `SESSION_LOG_TEMPLATE.md` for where it is kept).

**Session 1 is done when:** all suites ran, you know which ones skipped or ran nothing and why, the three
commands gave the expected answer, and `docs/plan/ENVIRONMENT.md` is committed.

---

## Before session 2: one reading item (L1)

Read the 2010 paper "When Clocks Fail" (sections on the fault mechanism) and the first third of the 2024
survey of fault injection written for apprentices. Write half a page on why one clock glitch can corrupt
several flip-flops in the same cycle, and why that is not the same as k chosen bit flips.
This is the idea Phase 0 puts on the screens.

---

## Session 2: the first change, what the number counts (P0.1 to P0.4)

### 2.1 Why this is first

The tool counts **modelled bit flips**: single flips at netlist nodes, chosen by the solver. The README and
the app say it counts **glitches**. Those differ in both directions. One real clock or voltage glitch hits
the whole chip and can corrupt many flip-flops in one cycle; and many modelled flips cannot be produced
physically. The app goes further and teaches that three copies of a check need three glitches. Against a
global glitch, identical copies can fail together. Both points are corrected in Phase 0, starting here.

The replacement paragraph (keep it word for word in the README "Limits" section and in the model card):

> k is the minimum number of single-bit transient faults (bit flips at netlist nodes, at most one per node per
> cycle) that GlitchSAT's logical fault model needs to reach the attack goal within N unrolled cycles. It is
> **not** a count of physical glitches or laser shots: one physical glitch can flip many bits, and some
> modelled flips cannot be produced physically. The model treats each flipped bit as an independent fault, so
> it does not show that identical copies can fail together under one power or clock glitch. Results are exact
> within this model and assume analog glitch and light sensors are bypassed. They are not calibrated against
> silicon and are not a success probability or a lab rating.

### 2.2 The rule (decision D-001, already accepted)

- A number is always followed by **"modelled bit flip(s)"** or **"modelled fault(s)"**; in learner text
  **"flipped bit(s) in the model"**.
- **"glitch"** stays for the physical act in stories: "an attacker glitches the clock".
- Never: a number directly in front of "glitch" or "glitches". Never: "exactly" for what the model does.

### 2.3 Branch

```bash
git checkout main && git pull
git checkout -b wording/p0-readme
```

### 2.4 Exact text changes (P0.2)

`README.md` (line numbers are for commit `96b28f4`):

| Line | Now | Change to |
|---|---|---|
| 1 | `# GlitchSAT: how many glitches does it take to break a chip's protection?` | `# GlitchSAT: how many faults does it take to break a chip's protection?` |
| 10 | `> **What is the smallest number of well-timed glitches that still breaks it?**` | `> **What is the smallest number of well-placed faults (single flipped bits, in a computer model) that still breaks it?**` |
| 12 | `More glitches needed means a harder attack.` | `More faults needed means a harder attack in this model. One real glitch can flip several bits at once, so this number is not a count of glitches (see [Limits](#limits)).` |
| 26 | `... **1** glitch is enough.` | `... **1** modelled fault is enough.` |
| 27 | `Three separate copies need **3** glitches on the stored design.` | `Three separate copies need **3** modelled faults on the stored design.` |
| 90 | `"One well-timed glitch can make this happen: ..."` | Reword the sentence around it to "Expected: one critical finding saying that a single modelled fault opens the lock". The tool output itself changes in P0.5 |
| 161 | `... a stated number of clock cycles and glitches.` | `... a stated number of clock cycles and modelled faults.` |

In the "Limits" section add as the first bullet:

```markdown
- **What the number counts.** <the replacement paragraph from 2.1>. The exact model is on one page:
  [`docs/FAULT_MODEL_CARD.md`](docs/FAULT_MODEL_CARD.md).
```

`START.md`:

| Line | Now | Change to |
|---|---|---|
| 3 | `counts how many well-timed glitches an attacker needs to break a chip's protection, on a computer model` | `counts how many faults (single flipped bits) an attacker's glitch would have to cause to break a chip's protection, on a computer model` |
| 30 | `Expected: 1, 1 and 3 glitches.` | `Expected: 1, 1 and 3 modelled faults.` |
| 35 to 36 | `needs 3, 2 or 1 glitches depending on how it was built` | `needs 3, 2 or 1 modelled faults depending on how it was built` |
| 47 | `(glitch count, clock cycles, one gate list)` | `(number of modelled faults, clock cycles, one gate list)` |

`product/README.md` already separates flips from glitches; read it once and change only what breaks the rule.

`NOTICE.md`: rewrite as a short notice (copyright line and the required third-party notices). Its title
still carries the old question, and it describes folders that are not in the repository; both go.

If the files have moved on, find the lines with:

```bash
grep -n -i -E "glitches|well-timed|glitch is|glitch count" README.md START.md NOTICE.md
```

### 2.5 The fault-model card (P0.3)

Create `docs/FAULT_MODEL_CARD.md` and fill each line from the docstring at the top of `scripts/glitchsat.py`
and the README "Limits" section:

```markdown
# Fault-model cards

One card per fault model. A result always names the card it was computed under.

## M0: bit flip (the model of every result up to version 0.9)

| Item | Value |
|---|---|
| Effect | The value of one net is inverted for one clock cycle, as every reader of that net sees it |
| Fault sites | Output net of any combinational gate; Q net of any flip-flop. Input nets are not fault sites by default |
| Counting rule | One flipped net in one cycle counts as one fault, however many gates read it |
| Independence | Each flipped bit is an independent fault. One physical event that upsets several bits is charged several faults |
| What k means | <the replacement paragraph> |
| Bounds | At most k faults in total, within N unrolled clock cycles |
| Attacker input | Free, held constant; must differ from the legitimate key |
| Start state | Known power-up state |
| Sensors | Analog glitch and light sensors are assumed bypassed (a conservative worst case) |
| Not modelled | Timing (which flops a glitch can really disturb), layout (what one spot covers), several bits from one physical event, stuck-at faults, faults lasting more than one cycle |
| Calibration | None. Nothing was measured on a chip |
| Verdict label | BOUNDED |
| Formal statement | For netlist <hash>, start state s0, goal G, bounds k and N: there is / there is no assignment of at most k (net, cycle) flips and a constant input other than the key such that G holds at some cycle up to N |
| Evidence for the model | It is the standard logical fault model of the formal fault-analysis literature. It is not derived from physics |

## M1 and later

Planned: timing-derived glitch (M1). Others only after gate G3 of the roadmap.
```

### 2.6 Keep the fix in place (P0.4)

Extend the existing check, `tools/check_wording.py`; do not add a second, parallel test. Add one more kind
of finding next to the three it has, with patterns of this shape:

```python
NUM = r"(?:\d+|one|two|three|four|several|more|fewer|fewest|many)"
UNIT_RX = re.compile(
    rf"\b{NUM}\**\s+(?:well-timed\s+|perfectly-timed\s+|precise\s+|successful\s+)?glitch(?:es)?\b"
    r"|\bglitches\s+(?:are\s+)?(?:needed|required|enough)\b"
    r"|\bhow many glitches\b|\bnumber of glitches\b|\bglitch count\b"
    r"|\bexactly that flip\b|\bglitch every copy\b",
    re.IGNORECASE)
# Sentences that explain the difference are allowed.
UNIT_OK = re.compile(r"not\s+(?:a\s+)?(?:count|the number)\s+of\s+(?:physical\s+)?glitches"
                     r"|one\s+(?:real|physical|power|clock)\s+(?:or\s+\w+\s+)?glitch\s+can", re.IGNORECASE)
```

Check whole paragraphs, not single lines, so a phrase split across a line break is still found. Keep a
short list of files that are **not yet fixed** and shrink it as Phase 0 proceeds; a file outside the list
must pass. Today the fixed files are `README.md`, `START.md`, `NOTICE.md` and the card. This page and the
other files in `docs/plan/` quote the old sentences on purpose; put `docs/plan/` on the exemption list for
this one kind of finding.

Already done for P0.4 (D-015, accepted as D-020): a file-name exemption for the two handoff files at the
repository root, so that the pointer file can name its neighbour. Keep `tests/test_check_wording.py` passing
when you extend the check.

### 2.7 Check and commit

```bash
python3 tools/check_wording.py README.md START.md NOTICE.md docs
python3 -m pytest -q tests product/tests
python3 scripts/check_numbers.py --verify        # the number register must still agree with the README
git diff --stat
git add README.md START.md NOTICE.md docs/FAULT_MODEL_CARD.md tools/check_wording.py
git commit -m "Wording: the number counts modelled faults, not glitches; fault-model card M0"
```

If `scripts/check_numbers.py --verify` fails because it looks for a sentence you changed, update the expected
sentence in `docs/NUMBERS.md` and the script in the same commit, and say so in the commit message.

### 2.8 Close the session

Fill the session log. "Next" is P0.6 (remove the rating output) or P0.5 (findings text).

**Session 2 is done when:** the extended check passes on the fixed files, all old tests pass, the card exists
and the README links to it.

---

## Session 3: re-derive the engine (L2 and C2)

This is the first core-review item. It can be interleaved with Phase 0 (one session in three).

1. Work through a z3 tutorial far enough to write Boolean constraints, a loop that unrolls a circuit, and an
   at-most-k constraint.
2. **Without opening `scripts/glitchsat.py`**, write a script of 100 to 150 lines that: reads
   `reference/spike_netlists/v0.json`; builds the circuit for 6 cycles; adds one flip variable per net and
   cycle; limits the flips to k; asks whether the goal can be reached with a wrong key.
3. Run it for k = 0, 1, 2, 3 on V0, V1 and V2. Expected minima: 1, 1, 3.
4. Only now compare with the engine. Write down every difference in approach, and every part of the engine
   the short script does not cover.

Keep the script outside the shipped tree (for example `scratch/`, which is ignored). It is a cross-check, not
a product.

**Session 3 is done when:** the script gives the same three minima, and the list of differences is in the
log.

---

## Session 4 (after Stage A): chip-design flow and real timing

Do the reading items L3 (static timing) and L4 (the open flow) first. Do not multitask during the install.
Use a separate Python environment for flow tooling (`python3 -m venv ~/work/eda-venv`), so it cannot disturb
the project's environment.

**Sitting 4a: install and smoke test.**

1. Check the laptop: `free -g` (8 GB minimum, 16 GB better), `df -h ~` (20 GB free), `nproc`.
2. Pick one route, in this order of preference, and write the choice in `DECISIONS.md`:
   - **Route A, LibreLane by Nix** (verified in its documentation): `git clone
     https://github.com/librelane/librelane`, enter the folder, `nix-shell`, then `librelane --smoke-test`.
     It brings OpenROAD, OpenSTA and the PDK.
   - **Route B, a prebuilt OpenROAD package** for the Ubuntu base of your Mint version (Mint 22 only;
     verify), plus the PDK through `pip install ciel` and `ciel enable --pdk-family sky130 <hash>` (verify
     the exact hash with `ciel ls-remote --pdk-family sky130`).
   - **Route C, a container image** with the open tools (verify the commands in its documentation).
3. Record the flow revision or image digest in `docs/plan/ENVIRONMENT.md`.
4. If you are stuck for more than one sitting, ask in the tool's public discussion forum with a minimal
   example, and log the question.

**Sitting 4b: timing for the layouts that exist.**

1. Find the Liberty file: `find ~ -name '*tt_025C_1v80.lib' 2>/dev/null | head`.
2. Smoke test: OpenSTA reads `layout/v_designs/out_patched/v2_pnr.v` and prints one timing path
   (`report_checks`).
3. Real SDF (P2.2): `LIB=<path to the .lib> STA=openroad tools/vlab/eda/regen_sdf.sh`. If OpenSTA rejects
   the options `-group_count` or `-endpoint_count` in `tools/vlab/eda/regen_sdf.tcl`, replace them with
   `-group_path_count` and `-endpoint_path_count` (verify with `help report_checks` on your build).
4. Re-run `python3 tools/vlab/run_vlab.py`. The delay label should change from ASSUMED to SOURCED (sdf).
   Write down what changed in the results.

**Session 4 is done when:** `report_checks` prints a path for the placed V2 and the timing lab ran once with
sourced delays.

---

## When you have only 30 minutes

Pick one, do it, log it.

**Reading**

1. One section of the 2010 "When Clocks Fail" paper; five lines on what a model must reproduce.
2. The published open tool's section on what it does not model; copy the exact sentences into
   `docs/PRIOR_ART.md` with page numbers.
3. One item of the reading gate (Phase R): start with the 2024 paper on modelling synchronous clock-glitch
   injection. Note, with page numbers, what it says about plain timing-violation models.
4. One module README of the owned core (`tools/vlab`, `tools/fastsat`); list three things that surprised you.
5. The OpenSTA page for `report_checks`; write down the options P2.4 needs.
6. One short workshop paper end to end (L6); note how it states its limits.

**Checks**

7. `python3 scripts/test_all.py`; note any suite whose skip reason you do not understand.
8. `grep -rn -i -E "[0-9]+ glitch|glitches needed" tools/studio/*.py | wc -l`; record the count. It should
   fall to zero during Phase 0.
9. Pick one function in the owned core that has no docstring and write one. Every open question becomes a
   line in the log.

**Small edits**

10. Fix the wording in one small file from the Phase 0 list and take it off the not-yet-fixed list.
11. Add one row to the vocabulary section of `docs/GLOSSARY.md`.
12. Write one decision into `DECISIONS.md` that you have been carrying in your head.
13. Write one concept-check question (P0.12) and its defensible answer.

**Housekeeping**

14. `git status`, `git stash list`, `git branch`: delete merged branches; write down what any stash contains.
15. Re-read the last session record and correct the "next" line if the plan has changed.
16. Update `docs/plan/ENVIRONMENT.md` after any tool upgrade.

---

## If something goes wrong

| Symptom | First thing to try |
|---|---|
| `make check-reproduce` reports mismatches | Check `yosys -V`. Anything other than 0.33 can give a different, still correct, V2 netlist. Log it; never edit `ci/expected_reproduce.json` to silence it |
| A suite fails only inside `scripts/test_all.py` | Run it alone: `python3 -m pytest -q tools/<name>/tests -x` |
| A suite shows PASS with 0 passed | It did not run. Find the skip reason; this is the defect P05.2 fixes |
| `glitchsat` command not found | `. .venv/bin/activate`, then `pip install -e .` again |
| Studio shows old text after an edit | The installed copy may be a snapshot: reinstall, or run the Studio from the checkout as its README describes |
| `pip install python-sat` fails | Use the bundled solver for small designs today; published results need CaDiCaL (P1.2) |
| A check fails on your machine but "works locally" elsewhere | A failing check is either fixed or written in the log as a known open item with a date. It is never ignored |
| Nix install fails or is too large | Route B or C in session 4 |
| OpenSTA says a cell is unknown | Wrong Liberty library, or the netlist is not the post-route one |
| You have lost track of where you were | Read the newest session record, then `git log --oneline -10`, then `git status` |
