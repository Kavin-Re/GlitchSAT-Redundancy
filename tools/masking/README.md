# Labs: side-channel masking survival

**Status: EXPERIMENTAL (GlitchSAT Labs).** Experiments in progress: try them, don't rely on them.
Every result below is labelled MEASURED, SIMULATED or UNTESTED (meaning in `tools/labs/README.md`).

## What it tries to answer

A chip can leak a secret key through its power use. *Masking* splits each secret bit into random-looking
pieces ("shares") so that no single wire carries the secret. This module asks: **if someone could measure one
wire of the circuit, would they learn anything about the secret, and is that still true after the circuit has
been synthesised and when signals "glitch" (briefly show wrong values before settling)?**

## Run it

```
. ./env.sh        # your own tool setup: puts Yosys (and a Yosys with read_slang) on PATH
python3 tools/masking/scripts/run_labs.py          # about 2 s; writes results/labs_result.json
python3 tools/masking/scripts/run_labs.py --quick  # own gadgets only (no OpenTitan sources needed)
python3 -m pytest -q tools/masking/tests           # smoke test
```

## WHAT WORKS

- `masking/probe.py`: an exact first-order probing check of a small gate-level Yosys netlist. Every wire is
  computed as a truth table over all share and random bits, and for every probe the distribution of what it
  sees is counted for every secret value. Two models: **standard** (a probe sees its wire) and **glitch**
  (a probe sees every input and register output in its wire's logic cone).
- Input labels use the format of the GlitchSAT project file (`tools/byod/docs/SCHEMA.md`, masking labels
  `secret N`, `static_random`, `volatile_random`, `unimportant`), plus `fixed 0`/`fixed 1` for control inputs.
- A check that the output shares still combine to a value fixed by the secrets alone (the gadget still computes).
- The example: 3 textbook gadgets (own Verilog in `gadgets/`), each built twice with Yosys 0.33 (`plain`: structure
  kept; `synth`: full `synth` + `abc`), and 2 OpenTitan gadgets elaborated with Yosys 0.71 `read_slang` from the
  fetched sources in `work/ot` (`shims/` stand in for primgen primitives).

## Results of the example (all EXPERIMENTAL)

| gadget | flow | standard model | glitch model | expected (textbook) | label |
|---|---|---|---|---|---|
| `naive_and2` (no randomness) | plain | leaks | leaks | leaks / leaks | SIMULATED |
| `naive_and2` | synth | leaks | leaks | leaks / leaks | SIMULATED |
| `isw_and2` (ISW, no registers) | plain | no leak found | leaks | secure / leaks | SIMULATED |
| `isw_and2` | **synth** | **leaks** | leaks | secure / leaks | SIMULATED |
| `dom_indep_and2` (DOM, registered cross terms) | plain | no leak found | no leak found | secure / secure | SIMULATED |
| `dom_indep_and2` | synth | no leak found | no leak found | secure / secure | SIMULATED |
| OpenTitan `prim_dom_and_2share` (DW=1) | plain | no leak found | no leak found | - | SIMULATED |
| OpenTitan `aes_dom_indep_mul_gf2pn` (NPower=2) | plain | no leak found | no leak found | - | SIMULATED |
| OpenTitan `aes_sbox_dom` (full masked S-box) | plain | not checked | not checked | - | UNTESTED |

- SIMULATED: all five plain-flow textbook results match the textbook answer (known secure and known insecure cases).
- SIMULATED: **synthesis broke the ISW gadget.** Yosys `synth` regrouped `a1&b0 ^ a1&b1` into `a1&(b0^b1)` (7 cells
  instead of 8, MEASURED); the new wire `b0^b1` is the unmasked `b` itself, and `a1&(b0^b1)` depends on it. The masking did not survive synthesis,
  as the literature warns for unconstrained synthesis of masked logic.
- MEASURED: the full OpenTitan masked S-box elaborates with Yosys 0.71 `read_slang` (1714 single-bit cells).

## WHAT DOESN'T (yet)

- UNTESTED: the full OpenTitan S-box. It has far more than 20 share and random bits; exhaustive counting cannot
  handle it. A symbolic or sampling engine is needed.
- UNTESTED: transition leakage (a value changing from one cycle to the next), couplings, multi-cycle history.
- UNTESTED: second and higher orders. `check(order=2)` exists but has no validated example.
- Flip-flops are evaluated as "inputs held stable, enable on, register settled"; pipelines that rely on timing
  between cycles are not modelled.
- Not integrated with `glitchsat check` or the project file yet (the `masking` check kind stays "format only").

## HOW FAR TO TRUST RESULTS

- The counting is exact *for the model*: "no leak found" means no single probe in that model sees a
  secret-dependent distribution. It does **not** mean the chip is safe against power analysis.
- "Leaks" in the standard model is a strong warning (a single wire carries secret information); "leaks" in the
  glitch model is the usual conservative warning.
- Nothing was measured on hardware; no power traces exist. The netlists are MEASURED (real Yosys runs); the
  security verdicts are SIMULATED.
- The textbook gadgets act as known answers; the smoke test fails if any of them changes.

## Files

`masking/probe.py` engine · `scripts/run_labs.py` example · `gadgets/` textbook gadgets · `shims/` primgen stand-ins ·
`tests/test_masking_smoke.py` · `results/labs_result.json` (format `labs-result/1`) · `work/ot` fetched OpenTitan sources
(Apache-2.0, unchanged) · `work/labs` build outputs.
