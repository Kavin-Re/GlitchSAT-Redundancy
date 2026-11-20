# PS2 report: product package hardening, Face B
Scope: product/, research/c3/ps2/. Worked on a copy in /tmp/work_ps2/work/product, applied to the tree after tests passed. Backups of the 7 changed files: research/c3/ps2/backup/. No make run, nothing pushed or enabled. Labels: MEASURED = I ran it (command given).

## Changes
1. Async-reset crash (DA2 C5.3). H1 had already turned the KeyError into exit 3 with a generic message. Now the message names the case: `$_DFF_PP0_`/`PN0`/... "flop with an ASYNCHRONOUS reset/set ... not modelled; re-synthesize with a synchronous reset or run async2sync". Decision: fail loudly, not model it (reset timing inside a cycle would need its own semantics). MEASURED: `faultbound-wt analyze examples/pin_lock/pin_async.v --top pina --config examples/pin_lock/pin.toml` -> exit 3, no traceback.
2. Canned explanation (DA2 C5.2). `explain()` in product/_engine.py rewritten. "Redundant checks converge / duplicated upstream" now appears only if two direct fan-in gate outputs of the flipped gate are distinct nets with identical, non-empty support over the attacker input bits (`_parallel_fanins`); the text then says "parallel checks", not "redundant". k>=2 text no longer claims "independent redundant copies"; it states net/cycle counts only. Fix patterns are labelled "generic design pattern, not derived from this netlist". MEASURED: v1 k=1 prints the STRUCTURE sentence (fan-in `c1.m`, `c2.m`); v0 (flop), v2 k=3, and the PIN lock print no such claim (tests/test_ps2.py). Limit: "same support" is a structural heuristic, not a proof that the checks are functionally redundant.
3. Wrong or missing legitimate_value. The honest (fault-free, legitimate input) run is now computed BEFORE solving. If it does not reach the goal: verdict `CONFIGURATION_PROBLEM`, no solve, exit 3, message "the honest input does not reach the goal in the fault-free design: configuration problem ...", reports still written (SARIF rule FBWT003, JUnit error). `--no-honest-check` downgrades to a stderr warning. Config keys not set by the user (input, legitimate_value, output, bad_value; or all, if no --config) are listed in `scope.defaulted_config_values` and warned on stderr. A 0-flip attack with a good honest run prints "NO FAULT NEEDED ... check the config". MEASURED: PIN lock with legitimate_value 5 instead of 10 -> exit 3 (was ATTACK_FOUND 0 flips, exit 1).
4. Scope block: JSON `scope`, SARIF `runs[0].properties.scope` (and the sentence in the result message), JUnit `scope_*` properties and system-out, text lines `scope:`. Fields: goal, input_treatment (all non-clk inputs free and constant; inputs not fault sites), init_state (explicit init count vs default-0 count), fault_model (counting rule), bounds, netlist_sha256, tool_version, defaulted_config_values, statement "bounded result under this model; not a proof of security". Report schema string bumped to `faultbound-wt-report/1`. SARIF `informationUri` ("about:working-title-tbd", not a valid URI) removed.
5. Docs: product/QUICKSTART.md, product/examples/github-actions-sarif.yml (SARIF upload, permissions security-events: write, upload step `if: always()`; never run, not linted), product/examples/pin_lock/{pin.v,pin_async.v,pin.toml}, README updated. Tests: product/tests/test_ps2.py (7 new), test_hardening.py adjusted (synthetic netlists use `--no-honest-check`).

## Acceptance test (MEASURED, /tmp/work_ps2/venv, Python 3.13, install in 3.2 s; only PyPI used for z3-solver 5.4.1.0 and pytest)
`python3 -m venv /tmp/work_ps2/venv; . venv/bin/activate; pip install ./product` (from /home/user/project)
| command | result |
|---|---|
| analyze v0.json --max-flips 1 (+ json/sarif/junit reports) | ATTACK_FOUND, st[0]@5, exit 1 |
| analyze v1.json --max-flips 1 | ATTACK_FOUND, ok@1, exit 1 |
| analyze v2.json --max-flips 2 | NO_ATTACK_UP_TO_BOUND, exit 0 (1.5 s) |
| analyze v2.json --max-flips 3 | ATTACK_FOUND, exit 1 (11.0 s) |
| v2 --cycles 0 | exit 3 |
| nonexistent file | exit 3 |
| pin_lock/pin.v --top pin | ATTACK_FOUND 1 flip, exit 1 |
| pin_async.v --top pina | exit 3, async message |
| pin.toml with legitimate_value 5 | CONFIGURATION_PROBLEM, exit 3 |
`python -m pytest tests` in product/: 27 passed (23.5 s; installed package, then again with PYTHONPATH after the final small fix, 27 passed). Generated reports parsed: JSON has all scope keys, SARIF version 2.1.0, JUnit well-formed. egg-info, build/, __pycache__ removed from product/ afterwards (checked with find). Sample output: research/c3/ps2/example_v1.sarif.
One bug found and fixed during the acceptance run: the config-problem output wrongly said "check was disabled by --no-honest-check".

## Not done
- Async reset is refused, not modelled. Enable/sync-reset-pin flops (`$_DFFE_`, `$_SDFF_`) also refused (need `dfflegalize`-style mapping).
- SARIF/GitHub upload never exercised; workflow YAML not linted; SARIF not validated against the official schema (only version field and JSON parse checked).
- Verilog path with hostile sources untested (as in H1). `yosys` was apt 0.33.
- Explanation heuristic is structural only; no equivalence check of the "parallel" checks.
- Scope text says attacker inputs are constant; time-varying input still unsupported in the product.
- `scripts/glitchsat.py` not touched, so the original CLI still has the old canned explain text and no honest-input error; product/_engine.py now differs from it in explain().
- Scale beyond 68 gates not tested. The v2 k=3 time is on this machine only.
