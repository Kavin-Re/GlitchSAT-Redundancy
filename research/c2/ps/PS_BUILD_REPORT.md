# PS_BUILD_REPORT: Face B package build

Package: `/home/user/project/product/` (name `faultbound-working-title`, console script `faultbound-wt`; title TBD, licence UNDECIDED, no LICENSE file, no SPDX field). Skeptic analysis: `research/c2/ps/PS_SKEPTIC.md`. All numbers below are MEASURED on this machine (Yosys 0.33, z3 5.4.1, Python 3.13.18) by the commands shown, unless stated.

## What was built
- `src/faultbound_wt/_engine.py`: COPY of the engine part of `scripts/glitchsat.py` (decision: copy with header, not import-by-path, so the wheel is self-contained; scripts/ untouched). Three marked changes (PS-CHANGE): `site_filter` predicate, net aliases, unsupported-cell check at load. Snapshot drifts unless re-synced by hand.
- `config.py` (TOML: faults.max_flips/cycles/kinds/include/exclude, attacker.input/legitimate_value/model, property.output/bad_value, netlist.top, solver.timeout_ms; unknown keys rejected), `runner.py` (Verilog via the same Yosys script as scripts/synth.sh, or Yosys JSON; provenance), `reports.py` (JSON, SARIF 2.1.0, JUnit XML), `cli.py`.
- Provenance block: tool version, command, python, z3, Yosys on PATH, Yosys `creator` string from the netlist JSON, Yosys used for synthesis and source hash (Verilog input), netlist SHA-256, gate and flop counts, UTC time.
- Exit codes: 0 none up to bound, 1 attack, 2 unknown, 3 input error; `--exit-zero`.
- Examples bundled: v0.json, v1.json, v2.json (copies of reference/spike_netlists), v0.v (copy of rtl/v0.v), threat.toml. README quickstart, `ci/github-actions-example.yml` (never run, not linted).

## Tests
- Dev venv: `pytest product/tests`: 10 passed, 8.6 s. Golden: V0 and V1 attack with 1 flip (k=0 none); V2 none at k=2, attack with 3 flips at k=3, T=6. Matches the repo's expected table (ci/expected_reproduce.json, spike netlists) for those rows only; I did not re-check the other rows.
- Also tested: provenance fields, exit codes, SARIF structure and hash link, JUnit well-formed with/without failure, five input-error cases exit 3, unsupported cell type exit 3, site-filter restriction (include glob matching nothing gives 0 sites and no attack; flops-only at k=2 on V2 gives none), Verilog input path (v0.v, records Yosys version).
- ACCEPTANCE on a copy (`/tmp/work_ps/acc`, fresh `python3 -m venv`): `pip install ./product` succeeded; README quickstart commands run verbatim: `--max-flips 2` gives NO_ATTACK_UP_TO_BOUND exit 0 (1.9 s, 68 gates, 8 flops); `--max-flips 3` gives ATTACK_FOUND exit 1 with out.json, out.sarif, out.junit.xml written (3 flips, the same net `new_n10_` in c0, c1, c2 at cycle 1; 6.5 s). `pip install "./product[test]"` then pytest in that venv: 10 passed, 12 s. Per-design k=1 sanity: v0 ATTACK (18 gates, 2 flops), v1 ATTACK (58 gates, 8 flops), v2 none.
- Not validated against an external SARIF schema validator or a real code-scanning upload (UNVERIFIED beyond my structural asserts). JUnit checked only for well-formedness.

## Missing / honest limits
- Time-varying attacker input: NOT implemented. `research/c2/e1_timevarying/` currently has only SymbiYosys-based scripts (gen_wrapper_free.py, run_sby_free.py, explicit_state_free.py, a results JSON), not an engine change; nothing copied. Config rejects `attacker.model != "constant"` with a TODO message. Revisit when E1 is finished.
- Only AND/OR/XOR/NOT/MUX/`$_DFF_P_` netlists; no cell-library netlists, reset flops, latches, multi-clock.
- Property: one output equals one value; no multi-output or alarm-style properties. Single-cycle flips only.
- Scale untested beyond 18 to 68 gates. No timeout benchmark.
- Restricted fault sites only remove attacks; a restricted "no attack" is weaker evidence (stated in README).
- The engine copy is not kept in sync automatically; no test compares it with scripts/glitchsat.py beyond the golden verdicts.
- Wheel contains example files; netlist path in provenance is whatever path was given (absolute in the quickstart); not normalised.
- Unrelated leftovers in product/ from my editable install and test runs: `src/faultbound_working_title.egg-info/`, `__pycache__/` dirs, `.pytest_cache/`. The sandbox blocked my removal; please delete them (do not ship).
- No novelty, security, or hardware claims. Verdicts are bounded and modelled.
