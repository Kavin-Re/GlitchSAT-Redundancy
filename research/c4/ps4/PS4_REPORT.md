# PS4 report: scope options in the shipped product
Agent PS4, 2026-11-19. Faults are MODELLED single-cycle bit flips on toy netlists; nothing here is a hardware or security statement. Every number is MEASURED with the command shown unless marked. Work copy `/tmp/work_ps4/p` (tar-pipe copy), applied to the tree only after it passed. `make` was not run in the tree. Backups of the 7 changed existing files: `research/c4/ps4/backup/`.

## What was built (product/src/faultbound_wt)
| option (CLI / TOML key) | behaviour | engine origin |
|---|---|---|
| `--consumer-bits MASK` / `[property] consumer_bits` | goal = the masked bits of the output equal the accept value on those bits only (M1 semantics). Hex `0xF0`, bit list `0-3,6`, or TOML int/list. Empty mask, garbage, bits beyond the width: exit 3. A mask covering every bit is identical to no mask. Reported in scope `goal` text and `scope.options.consumer_bits`. | M1 `gs_mask.py` 2-line patch |
| `--goal-out PORT`, `--accept-value N` | CLI overrides of the already existing `[property] output / bad_value` (these existed in config only, not on the CLI). Goal on `boot_ok` vs `boot_word` is thus selectable. | existing |
| `--input-sites {none,all}` / `[faults] input_sites` | `all`: every input-port bit except `clk` is a fault site (one shared site per bit, seen by all fanout = equivalent to an input buffer). Input faults appear as `kind: input_net` in reports. `include/exclude` globs still apply. | B2 `gs.py` |
| `--init {known,arbitrary}` / `[faults] init` | `arbitrary`: each flop's power-up value is a solver variable. The report states plainly: "ZERO FLIPS NEEDED under ARBITRARY power-up state ... shows the design has no reset, not a fault-tolerance result", lists a witness (`initial_state_witness_flops_set_to_1`). The honest-input check always uses the known state. | B2 `init_mode=free` |
| `--count-rule {stem,branch}` / `[faults] count_rule` | `stem` (default, existing rule). `branch` is NOT ported: exit 3 with an explanation (B1's branch_flip did not finish on spike V2, so porting safely was not possible in the cap). | none |
| `--scope-sweep` (+ `--sweep-masks`, `--cell-timeout-ms`, `--sweep-out FILE.json/.csv`) | matrix goal(s) x input-sites x init; one table of the minimum flips per cell, `>k` for no attack up to k, `unknown` for a per-cell solver timeout (exit 2 if no cell found an attack), `<=n` if minimisation timed out. Rows: configured goal, each extra mask, and `boot_ok` if present. Schema `faultbound-wt-sweep/1`. | new |

Unchanged: exit codes 0/1/2/3/4, report schema name `faultbound-wt-report/1` (new keys are additions: `scope.options`, plus `initial_state_witness...` and `minimize_incomplete` when relevant), the scope block keys that tests check, all default behaviour. The engine copy `_engine.py` header records the PS4 changes (marked `PS4-CHANGE`); the original `scripts/glitchsat.py` is untouched.

## Verification (MEASURED)
Spike V2 (`product/src/faultbound_wt/examples/v2.json`, `threat.toml`, 6 cycles), `faultbound-wt analyze V2 --config threat.toml ...`:
| scope | expected | measured |
|---|---|---|
| default, `--max-flips 2` | none | NO_ATTACK_UP_TO_BOUND, exit 0 |
| full word, `--max-flips 3` | 3 | 3 flips (word[0], c1/c2 new_n14, cycle 1), 21 s |
| `--goal-out boot_ok --accept-value 1 --max-flips 1` | 1 | `boot_ok@1`, exit 1 |
| `--input-sites all --max-flips 2` | 1 | `c0.a[1]@1` (input net), exit 1 |
| `--init arbitrary --max-flips 2` | 0 | 0 flips, plain-language text, exit 1 |
| `--count-rule branch` | exit 3 | exit 3 "NOT IMPLEMENTED" |
- Consumer masks vs `research/c3/m1/m1_all_masks.csv` (column `v2_spike_min_flips`): 10 sampled popcount-4 masks (seed 7; script `data/masks.py`, output `data/masks4.txt`): 10 of 10 agree (1,1,1,1,2,2,2,2,3,3). A first sample of 10 mixed-popcount masks (seed 4, including a colliding mask giving 0): 10 of 10 agree. No mismatch seen; this is 20 of 255 masks, not the full table.
- Sweep (`--max-flips 3 --scope-sweep --sweep-masks 0x0F,0x6A`, 33 s, `data/sweep_v2.json`): word 3 / 1 / 0 / 0; bits 0xF 2 / 1 / 0 / 0; bits 0x6A 3 / 1 / 0 / 0; boot_ok 1 / 1 / 0 / 0 (columns: sites none+known, all+known, none+arbitrary, all+arbitrary). `--cell-timeout-ms 1` gives all-`unknown`, exit 2.
- Reproduce rows: the 36 rows of `ci/expected_reproduce.json` come from `scripts/glitchsat.py` (not edited, so unchanged by construction). Through the product engine I re-ran the 24 rows of flows `rtl/plain` and `spike/given-netlist`: 24 compared, 0 differences (`data/repro.py`). The 12 `rtl/opt` rows were not run through the product (its synthesiser has only the plain flow).
- Tests: new `product/tests/test_ps4.py` (25 tests incl. 10 M1 masks, exit codes, all report formats, sweep). Clean venv: `python3 -m venv /tmp/work_ps4/venv && pip install "./product[test]"`, then `pytest product/tests` from `/tmp` against the installed package: 62 passed, 1 skipped in 81 s (copy tree, which lacks T2's files). In the real tree product has two extra T2 test files that I did not run.
- Tree hygiene: `product/` in the tree has no egg-info, build or `__pycache__` (builds happened only in the copy).

## Not done / caveats
- `--count-rule branch` is not implemented (clear exit 3). No branch model was ported.
- No hard wall-clock timeout: the per-cell timeout is the z3 solver timeout; model construction for big netlists is not interrupted. A solver timeout inside minimisation yields `<=n`.
- Input-site model is B2's: one shared site per input bit, not per fanout branch. With constant free inputs, an input flip can make `sig` look like the key (the E1 spec issue); this is a statement about the spec.
- `--init arbitrary` is B2's `free` only; B2's `free_nongoal` (arbitrary non-accepting power-up) is not offered. Per-cycle attacker input is still the TODO (exit 3).
- M1's mask rule is verified on spike V2 only; the sweep says nothing about other netlists. Mask 0x0 is rejected; colliding masks print 0 flips with the generic "no fault needed" text (the config-problem hint in that text may be misleading for them).
- Sweep `boot_ok` row is added only when the design has a 1-bit output named `boot_ok`; other goals need `--sweep-masks` or separate runs. Verilog input is synthesised once per sweep with the plain flow.
- I did not run the research GitHub-Action/Docker items; the test count for T2's files is unknown. Not a substitute for hardware or any security claim.

## Files
Changed: `product/src/faultbound_wt/{_engine,config,runner,cli,reports}.py`, `product/QUICKSTART.md` (section 4b), `product/README.md` (one sentence). New: `product/tests/test_ps4.py`, `product/examples/scope_sweep/scope.toml`, `research/c4/ps4/{PS4_REPORT.md,backup/,data/}`.
