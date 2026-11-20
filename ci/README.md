# CI

The workflow is `.github/workflows/ci.yml`. It has never run on GitHub; the YAML was parsed with PyYAML and the same commands were run locally (`ci/clean_install_log.txt`). actionlint was not run. Check the first run on GitHub by hand.

## Push / pull-request workflow (`ci.yml`)
Ubuntu 24.04 (pinned: its apt Yosys is 0.33, the version the expected table was recorded with), Python 3.12, apt `yosys iverilog`, pip `ci/requirements-ci.txt` (z3-solver 5.4.1.0, pytest) plus numpy and `./product[test]`. Runs `make check-tools`, `make test` (engine tests and the `docs/wow` data checks), the product tests, `make reproduce` (V0/V1/V2, k=0..3, 6 cycles, three netlist routes), `make check-reproduce` (36 verdict/min-fault rows against `ci/expected_reproduce.json`), `make replay` (iverilog replay of found attacks), `make validate` (independent gate-level simulator) and `scripts/check_numbers.py --verify`. Uploads results as an artifact. `make ci` runs the core steps locally.

## Not in the workflow (run by hand when needed)
`make mutate`, `make bench` (about 2 min), `make dashboard`. There is no nightly workflow.

## What CI does NOT cover
- The layout flow (`layout/`: OpenROAD, magic, netgen, sky130): needs a ~12 GB micromamba install; not run, not reproduced here.
- SymbiYosys proofs: run separately (see formal/FORMAL.md; needs the `formal` conda env, not part of CI).
- Different tool versions: the runner is pinned to ubuntu-24.04 because its apt packages are the tested Yosys 0.33 / Icarus 12.0. On another runner image or Yosys build, verdict differences would fail `check-reproduce` and need a human look (could be a real change or a tool difference).
- Dashboard correctness in a browser, numerics audit, fuzzing, `real_designs/`.
- Bounds: results hold only for the stated cycles and fault counts.
- Expected values were MEASURED on one machine; regenerate deliberately, never to silence a failure.
