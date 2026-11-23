# GlitchSAT: how many glitches does it take to break a chip's protection?

Author: Kavin.K.K. Licence: Apache-2.0. Repository: GlitchSAT-Redundancy.

GlitchSAT is a free tool and a learning app about **fault attacks on chips**. An attacker can disturb a chip for
an instant (a short dip in the supply voltage, an extra-fast clock edge) and hope that it makes a wrong decision:
start a fake program, open a lock, skip an alarm. Designers protect important decisions, for example by doing a
check three times. GlitchSAT answers one question about such a protection:

> **What is the smallest number of well-timed glitches that still breaks it?**

More glitches needed means a harder attack. GlitchSAT computes that number on a computer model of the circuit,
shows the attack step by step, and says in plain words what went wrong and what to change.

## Who it is for

- **Learners with no hardware background**: GlitchSAT Studio opens with a short story, a lesson ("Why protect
  chips?") and a guided path through three tiny locks. No setup beyond the install below.
- **Students of chip design (VLSI)**: try a protection, rebuild it with Yosys, watch the number change; open your
  own Verilog design.
- **Engineers**: a command line (`glitchsat`) with a project file, JSON and SARIF reports for code scanning, and a
  GitHub Action.

## What it found (short)

- Doing a check twice does not help when both copies meet in one shared wire: **1** glitch is enough.
- Three separate copies need **3** glitches on the stored design. The answer depends on the build: on a whole
  open-source chip design (PicoSoC with a three-copy boot check) it goes **3 / 2 / 1** across three ways of building
  it. The drop to 2 is most likely a weak stored code (the copies are still apart); the drop to 1 is the build tool
  merging the three copies. The V2 drop to 2 after a rebuild also comes from one stored code (see
  [`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md)).
- On real OpenTitan security hardware (published SYNFI netlists), GlitchSAT gives the same answer as lowRISC's own
  tool SYNFI on all 4,226 of SYNFI's fault injections.

Every number is a model result inside stated limits (see [Limits](#limits)); nothing was measured on a real chip.

## Install and first run (Linux Mint or Ubuntu)

You need Python 3.10 or newer (Linux Mint 21 has 3.10; Linux Mint 22 and Ubuntu 24.04 have 3.12) and git. In a terminal:

```bash
git clone https://github.com/Kavin-Re/GlitchSAT-Redundancy.git
cd GlitchSAT-Redundancy
python3 -m venv .venv
. .venv/bin/activate
pip install z3-solver
pip install .
```

Optional, for rebuilding designs from Verilog source (the "rebuilt" designs and your own designs):

```bash
sudo apt-get install -y yosys
```

Then start the app:

```bash
glitchsat-studio
```

It opens in your web browser, runs only on your own computer (address 127.0.0.1) and needs no internet. The first
screen is a short welcome story; "Skip" is always there. Without z3 or Yosys the app still works and shows the
project's recorded results, labelled as recorded. Stop it with Ctrl+C in the terminal.

Next time, open a terminal in the same folder and run `. .venv/bin/activate` before `glitchsat-studio`.

## The `glitchsat` command

| Command | What it does |
|---|---|
| `glitchsat studio` | the app (same as `glitchsat-studio`) |
| `glitchsat examples` / `glitchsat examples copy hello_lock` | list the example gallery / copy one example to try |
| `glitchsat init` | write a project file `glitchsat.yaml` for your own Verilog design |
| `glitchsat run` | analyse the project in the current folder; findings first, in plain words, then the technical details |
| `glitchsat explain GS052` | what an error or warning code means and how to fix it |
| `glitchsat check` | check a project file without running it (`glitchsat check --targets glitchsat.toml` is the CI check) |
| `glitchsat doctor` | show which tools were found (Yosys, solvers) |
| `glitchsat analyze NETLIST.json` | the netlist engine directly (JSON, SARIF and JUnit reports) |
| `glitchsat --help` | everything else (`margin`, `evidence`, `sarif`, `liberty`, `import-synfi`, ...) |

A first try on the command line:

```bash
glitchsat examples copy hello_lock
cd hello_lock
glitchsat run        # needs Yosys (without it: exit code 3 and a message that Yosys is missing)
```

Expected: one critical finding, "One well-timed glitch can make this happen: The lock opens although the right code
was never entered", with the place in the source and how to check a fix.

## What is inside the app

| View | What you do there |
|---|---|
| Welcome story | a few minutes: why this was built, how a glitch attack works, what was found, the limits |
| Why protect chips? | a short lesson with true stories (a game console, hardware wallets, a tracker) |
| Guided path | three toy locks: one check, two copies, three copies; predict first, then see the attack replayed |
| Findings | every result as a card: severity, what an attacker gets, why it happened, how we found it |
| Explore a real chip | the whole-chip results (PicoSoC, Ibex) with their limits |
| Open my design | the example gallery and a five-step wizard for your own Verilog |
| Labs (in "More") | experiments in progress, clearly marked: masking, OpenTitan primitives, a bootloader study |

## The research behind it (three toy boot checks)

The project started as a study of three tiny 8-bit boot checks: V0 (one check), V1 (two checks joined by one wire)
and V2 (three checks with separate output bits). All rows are MEASURED (a command in this repository produced
them; labels in [`docs/EVIDENCE_LABELS.md`](docs/EVIDENCE_LABELS.md)). Bounds: modelled single-cycle bit flips,
6 clock cycles, at most 3 flips.

| Design | Stored reference netlist | `rtl/*.v` rebuilt (apt Yosys 0.33, flows `plain` and `opt`) |
|---|---|---|
| V0, one check | 1 flip | 1 flip |
| V1, two checks joined by one AND gate | 1 flip (the shared net `ok`) | 1 flip |
| V2, three checks with separate output bits | **3 flips** (no attack with 2 or fewer) | **2 flips** |

How the V2 number moves when one assumption changes:

| Setting (V2) | Minimum flips | Source |
|---|---|---|
| Full 8-bit word, stored netlist | **3** | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) |
| Full 8-bit word, `rtl/v2.v` rebuilt with apt Yosys 0.33 (cause: the encoding of one state word, not the Yosys version) | **2** | [`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md) |
| Consumer that checks only 4 of the 8 bits (stored netlist) | 1 to 3 (28 / 36 / 4 of 68 masks need 1 / 2 / 3) | [`research/c3/m1/m1_all_masks.csv`](research/c3/m1/m1_all_masks.csv) |
| Goal is the accept flag `boot_ok`; or input nets are fault sites; or arbitrary non-accepting power-up state | **1** | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) (360 cells) |
| 264 build settings (152 distinct netlists) | 1 in 180, 2 in 60, 3 in 24 | [`research/c2/e2_variance/E2_REPORT.md`](research/c2/e2_variance/E2_REPORT.md) |
| Counting rule on 32 rebuilt netlists: a flipped net counts once (headline rule) vs. once per gate input it feeds | holds against 2 flips on 6 of 32 vs. 32 of 32 | [`research/c3/rep/REP_REPORT.md`](research/c3/rep/REP_REPORT.md) |

Never quote "V2 resists 2 flips" without its qualifiers: full word, input nets not fault sites, known power-up,
stored netlist, 6 cycles. Every headline number and its source row is in [`docs/NUMBERS.md`](docs/NUMBERS.md).

Reproduce the table (Yosys 0.33 and Icarus Verilog 12.0, the apt versions on Ubuntu 24.04 and Linux Mint 22):

```bash
sudo apt-get install -y yosys iverilog
pip install -r ci/requirements-ci.txt
make check-tools && make test
make reproduce && make check-reproduce          # 36 of 36 rows, about 25 s
make validate                                   # independent simulator without z3
```

`make reproduce` and `make test` rewrite files under `results/` and `tb/`; `git status` shows what changed.
`ci/expected_reproduce.json` was recorded with Yosys 0.33; another Yosys build can give a different (still
correct) V2 netlist and so a different minimum.

## How much to trust the numbers

- **Checked by a second method:** a separate gate-level simulator without z3
  ([`validation/VALIDATION.md`](validation/VALIDATION.md)) agrees with the solver on the stored netlists; solver
  attacks replay in Icarus Verilog (`make replay`); a second solver and SymbiYosys bounded checks agree
  ([`formal/FORMAL.md`](formal/FORMAL.md)).
- **What those checks cover:** they share the same fault model, so they test the encoding, not whether the model
  matches a real glitch.
- **Labels everywhere:** MEASURED, SIMULATED, BOUNDED (exact within the stated number of clock cycles), recorded
  (a stored result, not computed now), PROVED (only for the unbounded proofs that say so).

## Limits

- **Model only.** Faults are modelled bit flips in a gate list. No chip, glitcher or measurement was used. The
  layouts in `layout/` are flow demonstrations, never fabricated.
- **Bounded.** Each answer covers a stated number of clock cycles and glitches. "No attack up to the bound" is not
  "secure".
- **Build-dependent.** The answer belongs to one gate list. Another synthesis tool, setting or cell library can
  change it; that is one of the main findings.
- **Not new as a method.** SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover formal fault analysis, and SYNFI
  already showed that synthesis changes the number of faults needed. GlitchSAT's aim is to make the question easy
  to ask, to see and to learn from ([`docs/PRIOR_ART.md`](docs/PRIOR_ART.md)).
- **Counting rule is a convention.** One flipped net counts as one fault however many gates read it.
- **Untrusted input.** The Verilog path calls Yosys, which is not sandboxed. Only analyse files you trust
  ([`SECURITY.md`](SECURITY.md)).
- **Labs are experiments.** Results in Labs must not be used to decide whether a product is safe.

## Repository map

| Path | Contents |
|---|---|
| `tools/studio/` | GlitchSAT Studio (the app), its lesson, Labs and first-run views, and its test suites |
| `tools/byod/` | "Open my design": project file, templates, Liberty import, the example gallery |
| `tools/findings/` | plain-words findings and the severity rules ([`tools/findings/SEVERITY.md`](tools/findings/SEVERITY.md)) |
| `tools/<module>/` | the analysis modules; list in [`tools/README.md`](tools/README.md) |
| `tools/real/` | real OpenTitan netlists from SYNFI, the OpenTitan primitives study |
| `product/` | the `glitchsat` command, evidence and SARIF tools, the GitHub Action |
| `rtl/`, `reference/` | the three toy designs and their stored gate lists |
| `scripts/` | `glitchsat.py` (reference engine), Yosys flow, reproduce and replay scripts |
| `tests/`, `ci/` | engine tests; the expected reproduce table and its checker |
| `validation/`, `formal/` | independent simulator; second-solver and SymbiYosys checks |
| `results/`, `research/`, `docs/` | measured results, one folder per experiment, the written report and number register |

Pages that need no install (open in a browser): [`docs/explainers/index.html`](docs/explainers/index.html).
A 10-minute guided start: [`START.md`](START.md).

## Tests

```bash
python3 -m pytest -q tests product/tests          # engine and command line
python3 scripts/test_all.py                       # every module suite under tools/
```

Tests that need z3, Yosys or a SAT solver binary skip with a one-line reason when the tool is missing.

## Licence

Apache License 2.0 (SPDX: Apache-2.0); see [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md). Copyright 2026
Kavin.K.K. Third-party material (OpenTitan, SYNFI, PicoSoC and others, each under its own licence):
[`THIRD_PARTY.md`](THIRD_PARTY.md).
