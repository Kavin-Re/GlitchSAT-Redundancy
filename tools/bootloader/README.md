# Labs: bootloader fault hardening

**Status: EXPERIMENTAL (GlitchSAT Labs).** Experiments in progress: try them, don't rely on them.
Every result below is labelled MEASURED, SIMULATED or UNTESTED (meaning in `tools/labs/README.md`).

**Experimental analysis of a real bootloader's fault hardening; details withheld pending responsible disclosure.**
What was found, where, and in which build is kept out of this public file and out of the public result file until
the owner of this project has decided how to report it. Related work on this bootloader's hardening has been
published by others, so the result may already be known.

## Limits first

- The code under test is a small harness around the bootloader's own fault-hardening code, not the bootloader.
  The full bootloader (flash layout, image parsing, signature check, swap logic) is not compiled here.
- One compiler (clang for RV32), one optimisation setting at a time, one modelled fault at a time, on an
  instruction-set simulator. This is not how the bootloader is usually built or shipped.
- A result of the model is a reason to look closer, not a proven attack on any device; "nothing found" is not a
  proof of safety either.

## What it tries to answer

Some bootloaders have optional *fault-injection hardening*: checks are done twice, success values are unusual
numbers, a counter tracks that every check ran. This module asks: **if an attacker makes the processor skip one
instruction, or take one branch the wrong way, does a tampered image still get refused, and does the compiler's
optimisation level change that?**

## Run it

```
python3 scripts/run_labs.py        # about 6 s with the private notes present; writes results/labs_result.json
python3 -m pytest -q tests         # public checks: nothing specific is in the public files
```

Without the private notes the runner says so and the stored public result is shown. The full result, the harness
and the runner are kept in the private folder `to_report/` (see "Private notes" below).

## WHAT WORKS

- A boot ROM for the RV32 simulator of the firmware module whose accept/reject decision uses the bootloader's own
  fault-hardening library, compiled unchanged from `third_party/` (kept in the private notes).
- Built with clang for rv32imc and run on the firmware module's simulator with its image format, MAC engine and
  exhaustive single-fault search.
- Sanity check without faults (SIMULATED): the builds boot good images and refuse tampered payload, tampered MAC,
  rolled-back and bad-magic images.

## WHAT DOESN'T (yet)

- UNTESTED: the real bootloader as it is built and shipped.
- UNTESTED: other hardening profiles and optimisation levels, two or more faults, register-flip and PC-offset models.
- UNTESTED: Arm Cortex-M with gcc, which is how the bootloader is usually built; code (and results) will differ.

## HOW FAR TO TRUST RESULTS

- The hardening code is real and compiled by a real compiler (MEASURED: the builds in `work/`).
- The faults are a model on a Python instruction-set simulator (SIMULATED).
- The search is exhaustive for one fault of each model (every executed instruction tried), within the simulator.

## Private notes

`to_report/` holds the full result, a minimal reproduction and a reporting checklist. It is private: it is listed in
`.gitignore` and pruned in `MANIFEST.in`, and must not be copied into a public tree or package. Nobody has been
contacted and no issue has been opened.

## Files

`scripts/run_labs.py` runs the example when the private notes are present · `tests/` public checks ·
`results/labs_result.json` (format `labs-result/1`, details withheld; no per-build outcomes) · `third_party/` the
bootloader's source (Apache-2.0, unchanged; fetched, not shipped) · `work/` builds · `to_report/` private, not
published (harness, runner, smoke test, full result).
