# Contributing

1. Set up as in the README quickstart; run `make check-tools`.
2. Before a change: `make test` and `make reproduce && python3 ci/check_reproduce.py` must pass (this is what CI runs).
3. If a verdict legitimately changes, update `ci/expected_reproduce.json` in the same change and say why. Never edit it just to silence CI.
4. Label every number MEASURED, SIMULATED, ESTIMATED or ILLUSTRATIVE (`docs/EVIDENCE_LABELS.md`). Say UNVERIFIED for anything not run. Faults are modelled, not physical.
5. Do not commit `.venv/`, `results/work/`, generated testbenches or absolute personal paths (use paths relative to the repository root).
6. The project is licensed Apache-2.0 (`LICENSE`); contributions are accepted under the same terms.
