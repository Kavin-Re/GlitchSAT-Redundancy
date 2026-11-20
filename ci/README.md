# CI

Workflows are in `.github/workflows/`. They have never run on GitHub; the YAML was parsed with PyYAML and the same commands were run locally (`ci/clean_install_log.txt`). actionlint was not run.

## PR tier (`ci.yml`, about 3-4 min)
Ubuntu 24.04, Python 3.12, apt `yosys iverilog`, pip `ci/requirements-ci.txt` (z3-solver 5.4.1.0, pytest). Runs `make check-tools`, `make test` (10 engine tests), `make reproduce` (V0/V1/V2, k=0..3, 6 cycles, three netlist routes), `make check-reproduce` (36 verdict/min-fault rows against `ci/expected_reproduce.json`), `make replay` (iverilog replay of found attacks). Uploads results as an artifact. `make ci` runs the same steps locally.

## Nightly (`nightly.yml`, cron + manual)
All of the above plus `make validate` (independent gate-level simulator), `make mutate`, `make bench` (about 2 min), `make dashboard`, and an informational verilator lint (does not fail the job).

## What CI does NOT cover
- The layout flow (`layout/`: OpenROAD, magic, netgen, sky130): needs a ~12 GB micromamba install; not run, not reproduced here.
- SymbiYosys proofs: run separately (see formal/FORMAL.md; needs the `formal` conda env, not part of CI).
- Different tool versions: apt on ubuntu-24.04 may give yosys/iverilog newer than the tested 0.33 / 12.0; verdict differences there would fail `check-reproduce` and need a human look (could be a real change or a tool difference).
- Dashboard correctness in a browser, numerics audit, fuzzing, `real_designs/`.
- Bounds: results hold only for the stated cycles and fault counts.
- Expected values were MEASURED on one machine; regenerate deliberately, never to silence a failure.
