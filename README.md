# GlitchSAT: How Many Glitches Does Redundancy Stop?

**Bounded SAT-Based Fault Analysis of Redundant Boot Checks**

Repository name: GlitchSAT-Redundancy.

A model-only university project. No hardware was used, nothing physical was measured, and no novelty is claimed (see [Limitations](#limitations)).

## What this is, in plain words

A secure-boot check compares an input against a key and decides "boot" or "do not boot". A fault-injection attacker
tries to disturb the circuit (a voltage or clock glitch) so that a wrong input is accepted. The usual defence is
redundancy: do the comparison two or three times.

This project asks one question about that defence: **what is the smallest number of single-cycle bit flips that makes
the circuit accept a wrong input, and how much does that number depend on the assumptions behind it?**

- **Built:** a small solver, `scripts/glitchsat.py`. It reads a gate-level netlist (Yosys JSON), unrolls it for a fixed
  number of clock cycles, allows at most *k* flips of gate outputs or flip-flop outputs, and asks the SMT solver z3
  whether a wrong input can reach the "boot" value. It then lowers *k* until no attack remains, which gives the minimum.
- **Studied:** three toy 8-bit designs in `rtl/`: V0 (one compare), V1 (two compare copies joined by one AND gate),
  V2 (three compare copies, each owning separate bits of the result word).
- **Found:** copies that share one wire do not help (V1 falls to one flip on the shared net `ok`). The triplicated V2
  needs 3 flips in exactly one setting and 1 or 2 in the others. The answer moves with the attack goal, the number of
  bits the consumer checks, the power-up state, the synthesis flow and the counting rule.

The result is a sensitivity table, not a security claim: "V2 resists 2 flips" is true only with all of its qualifiers.

## Results at a glance

All rows are MEASURED (a command in this repository produced them; labels are defined in
[`docs/EVIDENCE_LABELS.md`](docs/EVIDENCE_LABELS.md)) unless a row says otherwise. Common bounds: modelled single-cycle
bit flips, 6 clock cycles, at most 3 flips, toy 8-bit designs.

**Baseline** (`make reproduce`, 36 rows in [`results/reproduce_summary.json`](results/reproduce_summary.json), goal: the
8-bit word `boot_word` equals the accept value `0x96` while the input is not the key):

| Design | Stored reference netlist | `rtl/*.v` re-synthesized (apt Yosys 0.33, flows `plain` and `opt`) |
|---|---|---|
| V0, naive | 1 flip | 1 flip |
| V1, duplicated | 1 flip (the shared net `ok`) | 1 flip |
| V2, triplicated | **3 flips** (no attack with 2 or fewer) | **2 flips** |

**How the V2 number moves when one assumption changes:**

| Setting (V2) | Minimum flips | Source |
|---|---|---|
| Full 8-bit word, stored netlist | **3** | [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md), [`research/c3/m1/M1_REPORT.md`](research/c3/m1/M1_REPORT.md) |
| Full 8-bit word, `rtl/v2.v` re-synthesized with apt Yosys 0.33 (85 gates; the stored netlist is also Yosys 0.33, 68 gates, another flow, so this is not a version effect) | **2** | [`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md), [`research/c6/p01/P01_REPORT.md`](research/c6/p01/P01_REPORT.md) |
| Consumer that checks only 4 of the 8 bits (stored netlist) | 1 to 3 (28 / 36 / 4 of 68 masks need 1 / 2 / 3) | [`research/c3/m1/m1_all_masks.csv`](research/c3/m1/m1_all_masks.csv) |
| Goal is the accept flag `boot_ok`; or input nets are fault sites; or arbitrary non-accepting power-up state | **1** | scope matrix, 360 cells: [`research/c2/b2_scope/B2_REPORT.md`](research/c2/b2_scope/B2_REPORT.md) |
| Synthesis flow: 864 configurations in total (3 Yosys builds x 3 designs x 96 option sets); V2 over its 264 solved configurations | 1 in 180, 2 in 60, 3 in 24 (152 distinct netlists: 94 / 38 / 20) | [`research/c2/e2_variance/E2_REPORT.md`](research/c2/e2_variance/E2_REPORT.md) |
| Counting rule, 32 re-synthesized netlists: a flipped net counts once (headline rule) vs. once per gate that reads it | holds against 2 flips on 6 of 32 vs. 32 of 32 | [`research/c3/r22/R22_REPORT.md`](research/c3/r22/R22_REPORT.md), [`research/c3/rep/REP_REPORT.md`](research/c3/rep/REP_REPORT.md) |

For comparison, V0 and V1 need 1 flip in every known-power-up setting tried, except that V1 needs 2 in 31 of the 264
re-synthesis configurations.

Why V2 can fall to 2: the "armed" state word `0xCC` differs from the accept word `0x96` only in bits owned by 2 of the
3 compare copies. The encoding sets that floor; the synthesis flow decides whether the floor is reached, and a flow
that merges the copies gives 1 ([`docs/report/WHY_TWO_FLIPS.md`](docs/report/WHY_TWO_FLIPS.md)).

Never quote "V2 resists 2 flips" without its qualifiers: full word, input nets not fault sites, known power-up, stored
netlist, 6 cycles.

Further results (rail-dip event models, layout geometry, a structural predictor, a coding-theory reading of the state
words) are summarised with their limits in [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md) and
[`docs/report/PROJECT_REPORT.md`](docs/report/PROJECT_REPORT.md). Every headline number and its source row is listed in
[`docs/NUMBERS.md`](docs/NUMBERS.md).

## How much to trust the numbers

- **Checked by a second method (MEASURED):** a separate gate-level simulator that does not use z3
  ([`validation/`](validation/VALIDATION.md)) agrees with the solver on the stored netlists: every single flip, and
  every pair of flips for V2 at 6 cycles (103,740 sets, none succeeds). The solver's attacks also replay in Icarus
  Verilog (`make replay`). A second solver (boolector) and SymbiYosys bounded checks agree
  ([`formal/FORMAL.md`](formal/FORMAL.md)).
- **What those checks cover:** they share the same fault model, so they test the encoding, not whether the model
  matches a real glitch.
- **Solver only, no second engine:** rail-event rows at 6 cycles with 3 events, and all rows for the extra design V5.
- **One unbounded result:** ABC PDR reports that the stored V2 netlist has no attack with 2 or fewer flips for any
  number of cycles (word goal). It is tool-reported, covers one netlist and was not replicated by a second tool.

## How to run

Three commands that need only Python 3 and z3 (`pip install z3-solver`); they use the stored netlists:

```
python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
```

Expected: the first finds a 1-flip attack on the shared net `ok`; the second prints `NO_ATTACK_UP_TO_BOUND`; the third
finds a 1-flip attack on `boot_ok`. Each run prints its bound.

Full reproduction (Linux; tested with Yosys 0.33 and Icarus Verilog 12.0, the versions `apt` provides on Ubuntu 24.04):

```
sudo apt-get install -y yosys iverilog
python3 -m venv .venv && . .venv/bin/activate
pip install -r ci/requirements-ci.txt           # z3-solver, pytest
make check-tools && make test
make reproduce && make check-reproduce          # V0/V1/V2 sweeps, about 25 s, 36 of 36 rows
make validate                                   # z3-free simulator, single flips, 6 cycles
```

- `make reproduce` and `make test` rewrite files under `results/` and `tb/`; `git status` shows what changed.
- `ci/expected_reproduce.json` was recorded with Yosys 0.33. Another Yosys build can produce a different V2 netlist and
  so a different (still correct) minimum; `make check-reproduce` then fails and needs a human look.
- Test counts as last recorded: root `pytest tests` 189 passed, 2 skipped; product tests 324 passed after
  `pip install ./product[test]`. Counts change when tests are added: run `make test` and quote your own.
- `make help` lists all targets. The same steps run in GitHub Actions: `.github/workflows/ci.yml`.

To look without installing anything, open in a browser: [`docs/wow/explainer.html`](docs/wow/explainer.html) (five
minutes, no jargon), [`docs/wow/dial.html`](docs/wow/dial.html) (four switches move the measured number 3 -> 2 -> 1 -> 0),
[`docs/wow/theatre.html`](docs/wow/theatre.html) (solver witnesses replayed gate by gate),
[`docs/wow/wall.html`](docs/wow/wall.html) (the 264 synthesis configurations) and
[`dashboard/index.html`](dashboard/index.html) (every measured run).

## Repository map

| Path | Contents |
|---|---|
| `rtl/` | The designs: `v0.v`, `v1.v`, `v2.v`, and variants `v2e.v`, `v2c.v`, `v2_secded.v` |
| `reference/spike_netlists/` | The stored gate-level netlists behind the headline rows |
| `scripts/` | `glitchsat.py` (solver), `synth.sh` (Yosys flow), `reproduce.py`, `replay.py`, `check_numbers.py` |
| `tests/`, `ci/` | Engine tests; expected reproduce table and its checker |
| `validation/`, `formal/` | z3-free simulator and second-solver checks; SymbiYosys and ABC runs |
| `results/` | Outputs of `make reproduce` and the deeper sweeps |
| `dashboard/`, `docs/wow/` | Offline HTML dashboard and explainers |
| `docs/` | [`START.md`](START.md) points here first. [`docs/report/PROJECT_REPORT.md`](docs/report/PROJECT_REPORT.md) is the full report, [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md) the status with every bound, [`docs/NUMBERS.md`](docs/NUMBERS.md) the number register, [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md) related work, [`docs/dossier/`](docs/dossier/) the dossier, critique and viva sheet, [`docs/edu/`](docs/edu/) a classroom kit |
| `research/` | One folder per experiment or review (`c2` to `c6` are successive rounds). Reports use short codenames; [`docs/GLOSSARY.md`](docs/GLOSSARY.md) maps each codename to a plain description and its folder |
| `product/` | `faultbound-wt`, a small command-line packaging of the same engine with scope options (separate from the study's claims) |
| `layout/`, `real_designs/`, `integrations/` | sky130 flow-demonstration layouts (not signed off, never fabricated), two outside designs tried, adapters for other tools |

## Limitations

- **Model only.** Faults are modelled single-cycle bit flips in a netlist. No chip, glitcher, measurement, fabrication
  or sign-off. The layouts are flow demonstrations.
- **Toy scale and bounded.** 8-bit designs of under 100 gates; bounds are 6 cycles and at most 3 flips. "No attack up
  to the bound" is not "secure".
- **Not novel.** SYNFI, FIRMER, k-FRP, CLEAVE, FIVER and uArchiFI cover the method, and SYNFI already showed that
  synthesis changes the number of faults needed (3 -> 2 and 4 -> 2; SOURCED from the paper). This project replicates
  that effect on a toy design and adds teaching material ([`docs/PRIOR_ART.md`](docs/PRIOR_ART.md); the k-FRP and
  FIVER full texts were not read).
- **Counting rule is a convention.** One flipped net counts as one fault however many gates read it. Neither this rule
  nor the per-reader alternative has been shown to be physical.
- **Assumptions inside the headline number.** Known power-up state, constant attacker input that is never the key,
  input and clock nets not fault sites, goal is the full 8-bit word. Changing any one of the first, third or fourth
  drops V2 to 1 flip.
- **Running on untrusted input.** The solver calls Yosys on the Verilog file it is given, and Yosys is not sandboxed.
  File and module names are validated before they reach Yosys (`scripts/synth.sh`, `product/`), but do not run the
  Verilog path or the GitHub Action on files you do not trust. Details: [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md),
  [`docs/dossier/CRITIQUE.md`](docs/dossier/CRITIQUE.md).
- **Some referenced material is not in this repository** (folders named `handoff/`, `compare/`, `numerics_audit/` and
  `formal/runs/` in older reports). Statements that rest only on those are marked UNVERIFIED in the reports.

## Licence

Apache License 2.0 (SPDX: Apache-2.0); see [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md). Copyright 2026 Kavin K K. The decision is recorded in [`LICENSE_CHOICE.md`](LICENSE_CHOICE.md). Third-party material: [`THIRD_PARTY.md`](THIRD_PARTY.md),
[`NOTICE.md`](NOTICE.md).
