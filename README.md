# GlitchSAT: How Many Glitches Does Redundancy Stop?

**Bounded SAT-Based Fault Analysis of Redundant Boot Checks.** Author: Kavin.K.K. Licence: Apache-2.0. Repository: GlitchSAT-Redundancy.

GlitchSAT finds the smallest number of modelled bit flips that make a small digital boot check accept a wrong key, and shows how much that number depends on the assumptions behind it.

## In plain words

A chip often checks a key before it starts ("secure boot"). An attacker can disturb the chip for an instant, for example with a voltage or clock glitch, hoping it accepts a wrong key. A common defence is to do the check two or three times. GlitchSAT asks a computer model of the circuit: *what is the smallest number of one-moment glitches that gets a wrong key accepted?* More glitches needed means harder to attack. The answer is exact inside the model, but only inside the model: three tiny 8-bit designs, modelled bit flips, a fixed number of clock steps. No hardware was used, nothing physical was measured, and no novelty is claimed (earlier tools such as SYNFI cover the method; see [Limits](#limits)).

The short finding: two checks that meet in one shared wire fall to **one** flip. Three checks with separate outputs need **three** flips on the stored circuit, but only under one combination of assumptions; change the attacker's goal, the power-up state, the synthesis settings or the counting rule and the number drops to 2, 1 or 0.

## Results at a glance

All rows are MEASURED (a command in this repository produced them; labels in [`docs/EVIDENCE_LABELS.md`](docs/EVIDENCE_LABELS.md)). Common bounds: modelled single-cycle bit flips, 6 clock cycles, at most 3 flips, toy 8-bit designs.

**Baseline** (`make reproduce`, 36 rows in [`results/reproduce_summary.json`](results/reproduce_summary.json); goal: the 8-bit word `boot_word` equals the accept value `0x96` while the input is not the key):

| Design | Stored reference netlist | `rtl/*.v` re-synthesized (apt Yosys 0.33, flows `plain` and `opt`) |
|---|---|---|
| V0, one check | 1 flip | 1 flip |
| V1, two checks joined by one AND gate | 1 flip (the shared net `ok`) | 1 flip |
| V2, three checks with separate output bits | **3 flips** (no attack with 2 or fewer) | **2 flips** |

**How the V2 number moves when one assumption changes:**

| Setting (V2) | Minimum flips | Source |
|---|---|---|
| Full 8-bit word, stored netlist | **3** | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) |
| Full 8-bit word, `rtl/v2.v` re-synthesized with apt Yosys 0.33 (cause: the encoding of one state word, not the Yosys version) | **2** | [`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md) |
| Consumer that checks only 4 of the 8 bits (stored netlist) | 1 to 3 (28 / 36 / 4 of 68 masks need 1 / 2 / 3) | [`research/c3/m1/m1_all_masks.csv`](research/c3/m1/m1_all_masks.csv) |
| Goal is the accept flag `boot_ok`; or input nets are fault sites; or arbitrary non-accepting power-up state | **1** | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) (360 cells) |
| 264 solved synthesis configurations (of 864 in total) | 1 in 180, 2 in 60, 3 in 24 (152 distinct netlists: 94 / 38 / 20) | [`research/c2/e2_variance/E2_REPORT.md`](research/c2/e2_variance/E2_REPORT.md) |
| Counting rule on 32 re-synthesized netlists: a flipped net counts once (headline rule) vs. once per gate input it feeds | holds against 2 flips on 6 of 32 vs. 32 of 32 | [`research/c3/rep/REP_REPORT.md`](research/c3/rep/REP_REPORT.md) |

Never quote "V2 resists 2 flips" without its qualifiers: full word, input nets not fault sites, known power-up, stored netlist, 6 cycles. Every headline number and its source row is in [`docs/NUMBERS.md`](docs/NUMBERS.md).

## Open GlitchSAT Studio (the app)

GlitchSAT Studio is a local app that runs the engine on the three designs, or shows recorded results when z3 or Yosys is missing. From the repository root:

```
bash tools/studio/glitchsat-studio.sh
```

It runs only on your own computer, and it says on screen whether a result is live (computed now) or recorded.

## How to run (Linux Mint or Ubuntu)

Quick check, using the stored netlists (needs only Python 3 and z3):

```
python3 -m venv .venv && . .venv/bin/activate
pip install z3-solver
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
```

Expected: the first finds a 1-flip attack on the shared net `ok`; the second prints `NO_ATTACK_UP_TO_BOUND`; the third finds a 1-flip attack on `boot_ok`. Each run prints its bound. `python3 scripts/glitchsat.py check --help` explains every option (it works without z3).

Full reproduction (tested with Yosys 0.33 and Icarus Verilog 12.0, the versions `apt` provides on Ubuntu 24.04; Linux Mint 22 uses the same packages):

```
sudo apt-get install -y yosys iverilog
pip install -r ci/requirements-ci.txt           # z3-solver, pytest
make check-tools && make test
make reproduce && make check-reproduce          # 36 of 36 rows, about 25 s
make validate                                   # z3-free simulator, single flips, 6 cycles
```

- `make reproduce` and `make test` rewrite files under `results/` and `tb/`; `git status` shows what changed. `make help` lists all targets.
- `ci/expected_reproduce.json` was recorded with Yosys 0.33. Another Yosys build can give a different V2 netlist and so a different (still correct) minimum; `make check-reproduce` then fails and needs a human look.
- Test counts as last recorded: `pytest tests` 189 passed, 2 skipped; product tests 324 passed. `tests/test_cli_help.py` (5 tests) was added after that count. Without z3 the solver tests are skipped with a one-line reason. Run `make test` and quote your own counts.

**Two command-line tools, one engine.** `scripts/glitchsat.py` is the reference engine behind the tables above. The installable **GlitchSAT CLI** (`pip install ./product`, command `glitchsat`; the older name `faultbound-wt` still works) wraps a copy of the same engine and adds scope options, JSON/SARIF/JUnit reports and sweeps ([`product/README.md`](product/README.md)). Exit codes differ: `scripts/glitchsat.py` exits 0 for both verdicts (read the printed verdict), while `glitchsat analyze` exits 0 for no attack and 1 for an attack found. Both use 2 for solver unknown/timeout and 3 for input errors.

**Pages that need no install** (open in a browser): [`docs/explainers/explainer.html`](docs/explainers/explainer.html) (picture story, no jargon), [`docs/explainers/dial.html`](docs/explainers/dial.html) (four switches move the measured number 3 -> 2 -> 1 -> 0), [`docs/explainers/theatre.html`](docs/explainers/theatre.html) (solver attacks replayed step by step), [`docs/explainers/wall.html`](docs/explainers/wall.html) (264 synthesis configurations) and [`dashboard/index.html`](dashboard/index.html) (every measured run). Index: [`docs/explainers/index.html`](docs/explainers/index.html).

## How much to trust the numbers

- **Checked by a second method:** a separate gate-level simulator that does not use z3 ([`validation/VALIDATION.md`](validation/VALIDATION.md)) agrees with the solver on the stored netlists: every single flip, and every pair of flips for V2 at 6 cycles (103,740 pairs, none succeeds). Solver attacks replay in Icarus Verilog (`make replay`). A second solver (boolector) and SymbiYosys bounded checks agree ([`formal/FORMAL.md`](formal/FORMAL.md)).
- **What those checks cover:** they share the same fault model, so they test the encoding, not whether the model matches a real glitch.
- **One unbounded result:** ABC PDR reports that the stored V2 netlist has no attack with 2 or fewer flips for any number of cycles (word goal). It is tool-reported, covers one netlist and was replicated by a second, independent implementation (k = 0, 1, 2 proved for all time, k = 3 attack).

## Limits

- **Model only.** Faults are modelled single-cycle bit flips in a netlist. No chip, glitcher, measurement, fabrication or sign-off. The layouts in `layout/` are flow demonstrations.
- **Toy scale and bounded.** 8-bit designs; the baseline netlists have under 100 gates (V0 18, V1 58, V2 68 stored; up to 85 re-synthesized), and some synthesis-sweep variants reach 122 (V1) and 141 (V2) gates (`research/c2/e2_variance/raw/matrix.csv`). Bounds are 6 cycles and at most 3 flips. "No attack up to the bound" is not "secure".
- **Not novel.** SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the method, and SYNFI already showed that synthesis changes the number of faults needed (3 -> 2 and 4 -> 2; SOURCED). This project replicates that effect on a toy design and adds teaching material ([`docs/PRIOR_ART.md`](docs/PRIOR_ART.md); the k-FRP and FIVER full texts were not read).
- **Counting rule is a convention.** One flipped net counts as one fault however many gates read it. Neither this rule nor the per-reader alternative has been shown to be physical.
- **Assumptions inside the headline number.** Known power-up state, constant attacker input that is never the key, input and clock nets not fault sites, goal is the full 8-bit word.
- **Untrusted input.** The Verilog path calls Yosys, which is not sandboxed. Only analyse files you trust ([`SECURITY.md`](SECURITY.md)).
- **Some referenced material is not in this repository** (folders named `handoff/`, `compare/`, `numerics_audit/` and `formal/runs/` in older reports). Statements that rest only on those are marked UNVERIFIED.

## Where to read more

| Question | File |
|---|---|
| A 10-minute guided start | [`START.md`](START.md) |
| The full written report | [`docs/report/PROJECT_REPORT.md`](docs/report/PROJECT_REPORT.md) |
| Status with every bound | [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md) |
| Every number and its source | [`docs/NUMBERS.md`](docs/NUMBERS.md) |
| Related work | [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) |
| Known weaknesses | [`docs/dossier/CRITIQUE.md`](docs/dossier/CRITIQUE.md) |
| Short names used in reports | [`docs/GLOSSARY.md`](docs/GLOSSARY.md) |
| The experiment archive | [`research/README.md`](research/README.md) |

## Repository map

| Path | Contents |
|---|---|
| `rtl/` | The designs: `v0.v`, `v1.v`, `v2.v`, and variants `v2e.v`, `v2c.v`, `v2_secded.v` |
| `reference/spike_netlists/` | The stored gate-level netlists behind the headline rows |
| `scripts/` | `glitchsat.py` (engine), `synth.sh` (Yosys flow), `reproduce.py`, `replay.py`, `check_numbers.py` |
| `product/` | The installable GlitchSAT CLI (`glitchsat`) |
| `tools/studio/` | GlitchSAT Studio and its launcher |
| `tests/`, `ci/` | Engine tests; the expected reproduce table and its checker |
| `validation/`, `formal/` | z3-free simulator and second-solver checks; SymbiYosys and ABC runs |
| `results/` | Outputs of `make reproduce` and the deeper sweeps |
| `docs/` | Report, status, number register, dossier and Q&A sheets (`docs/dossier/`), classroom kit (`docs/edu/`), browser pages (`docs/explainers/`) |
| `dashboard/` | Offline HTML dashboard of every measured run |
| `research/` | One folder per experiment or review; see [`research/README.md`](research/README.md) |
| `layout/`, `real_designs/`, `integrations/` | sky130 flow-demonstration layouts (not signed off, never fabricated), two outside designs tried, adapters for other tools |

## Licence

Apache License 2.0 (SPDX: Apache-2.0); see [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md). Copyright 2026 Kavin.K.K. Third-party material: [`THIRD_PARTY.md`](THIRD_PARTY.md). The licence decision is recorded in [`LICENSE_CHOICE.md`](LICENSE_CHOICE.md).
