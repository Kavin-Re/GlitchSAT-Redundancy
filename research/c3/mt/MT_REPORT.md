# MT report: do the test suites catch a broken solver?
All numbers MEASURED on a COPY (/tmp/work_mt/lite, built from /tmp/work_mt/proj; nothing run in the tree). Machine was heavily loaded by other steps, so the run was **cut off by the 40-minute cap: 86 of 158 mutant runs completed (72 not run)**. Not-run mutants are listed as NOT RUN, not counted.

## Commands
- Copy: `tar cf - --exclude=work --exclude=dl ... . | tar xf -` into /tmp/work_mt/proj; a light tree /tmp/work_mt/lite (tests scripts rtl reference ci results product Makefile) used for mutants.
- venv: `python3 -m venv /tmp/work_mt/venv; pip install ./proj/product[test] coverage`.
- Suites (clean baseline, MEASURED): `pytest -q tests` = 30 passed (33 s); `cd product; PYTHONPATH=src pytest -q tests` = 27 passed (27 s).
- Harness: `research/c3/mt/mutate.py` (98 one-line mutants defined; scope E = same text mutated in scripts/glitchsat.py AND product/.../_engine.py, G = glitchsat CLI only, P = product runner/cli/config/engine-only). Each mutant gets its own copy, `pytest -q -x`, `timeout 120`. Mutants run on suite 'root' (tests/) when glitchsat.py is mutated, on suite 'product' (product/tests) when the product files are mutated. Log: run.log, results_partial.json.
- Survivor check against new tests: `research/c3/mt/kill_check.py` (log kill_new.log).

## Mutation score (completed runs only)
| suite | run | killed | survived | timeout | score killed/run |
|---|---|---|---|---|---|
| tests/ vs glitchsat.py | 43 | 29 | 14 | 0 | 67 % |
| product/tests vs product src | 43 | 28 | 15 | 0 | 65 % |
Of the survivors, I judge (by reading, NOT proven) 8 distinct mutants equivalent-suspect (performance/pruning only: simp_off, simp_always, min_nopop_brk, temporal_off1, dist_noinc, dist_goal_none partly) -> adjusted score if those are removed is about 78 % (root) / 76 % (product). Not-run mutants (72 runs incl. all product-only runner/cli/config ones and the glitchsat CLI ones) are unmeasured: the score is for the engine-core subset that happened to finish first, not for the whole list.

## Survivors (before new tests), what would kill them
| mutant (id) | suites surviving | line text changed | verdict / killing test |
|---|---|---|---|
| flip_or: `Xor(v,F)` -> `Or(v,F)` | both | build(): fault injection | KILLED by new oracle test (needs an attack that requires 1->0 flip) |
| no_flop_sites: drop flops from allsites | root | build(): `allsites=` | KILLED by new `test_flop_only_attack_found` (existing root tests never need a flop-only attack) |
| xor_to_or: XOR gate encoded as OR | both | get() | KILLED by new oracle test |
| last_cycle_only: goal only at last cycle (`hits[-1]`) | both | solve/build `s.add(Or(*hits))` | KILLED by new oracle test (needs attack that hits earlier) |
| min_off / min_bound2: minimisation off / wrong bound | product (min_off), product (min_bound2) | solve() loop | KILLED by new oracle test (asserts reported size == brute-force minimum, and k=min-1 is unsat) |
| init_default1: undefined flop init defaults to 1 | both | Netlist.__init__ | KILLED by new oracle test (random nets have flops with no init attr) |
| honest_nofix: honest_boots without fixed_in=key | root | honest_boots() | NOT killed: needs a netlist where the honest key does not boot but some other input does; product suite catches it, root suite does not. Test: hand-built net, assert honest_key_boots_fault_free is False |
| temporal_off2 (`<= N-2`), coi_nolast (`t>0`), dist_goal_none | both | build() reduction | NOT killed: need a netlist whose ONLY attack uses a combinational site at the last cycle or at cycle 0, and compare reduce=full vs none. My random nets always allow an alternative cycle. Not written (out of time). Real gap in both suites |
| inport_drv_off (input-port-driven-by-gate check disabled) | product | Netlist.__init__ | NOT killed: product tests lack this hostile case (root test_hardening has it) |
| temporal_off1 (`<= N`), dist_noinc, min_nopop_brk, simp_off, simp_always | both | | equivalent-suspect: only change how many sites/terms are modelled, verdict identical by construction; not killable by black-box verdict tests |

## New tests (research/c3/mt/new_tests/test_mt_oracle.py, NOT in the tree)
Independent brute-force simulator (own code) + 30 seeded random netlists with flops (oracle min = 1 or 2) x reduce in {none, full}, asserts verdict, minimal size, witness replays, input != key, and k=min-1 unsat; plus `test_flop_only_attack_found`.
Run: `MT_ROOT=<tree> pytest research/c3/mt/new_tests` (root engine) or `MT_ENGINE=product PYTHONPATH=product/src pytest ...`. Clean copy: 61 passed in ~1.3 s for each engine (MEASURED; count after final edit: see below).
Killed by the new tests (MEASURED, kill_new.log): flip_or (both), no_flop_sites (root), xor_to_or (both), last_cycle_only (both), min_off (product), min_bound2 (product), init_default1 (both) = 7 distinct mutants, 12 of the 29 surviving runs. The other 17 survivor runs remain alive: 5 distinct are equivalent-suspect, 4 are real gaps (honest_nofix root, temporal_off2, coi_nolast, dist_goal_none) and inport_drv_off (product).
The oracle test runs in ~1 s, so it is cheap to adopt as a mutation-killing test.

## Coverage (MEASURED, `coverage run --branch --source=... -m pytest`, copy)
- product (`cd product; PYTHONPATH=src coverage run --branch --source=src/faultbound_wt -m pytest tests`): _engine.py 303/320 stmts = 94.7 % line (93 % with branches), runner.py 124/139 = 89 %, cli.py 77/80 = 96 %, config.py 61/67 = 91 %, reports.py 55/60 = 92 %; total 91 % (incl. branches).
- root (`coverage run --branch --source=scripts -m pytest tests`): scripts/glitchsat.py 304/364 stmts = 83.5 % line (82 % incl. branches). CAVEAT: the CLI is exercised via `subprocess` (`python -I glitchsat.py`), which this coverage run does not measure, so lines 437-462 (main) and some error paths show as missed although tests run them; true coverage is higher. scripts/reproduce.py, mutate.py 0 % (not unit tested).
- Uncovered in product engine: lines 50,52,74,86,90,95,99,106,110,131,137,171,202,204,216,218,251 (error branches of Netlist loading).

## Not done / limits
- 72 of 158 mutant runs not executed (time cap + load): product-only runner/cli/config mutants and glitchsat CLI mutants are mostly unmeasured. Re-run `mutate.py` with `--only ids` to finish.
- Equivalence judgements are by reading, not by a solver.
- A 120 s timeout was never hit (0 TIMEOUT), but under the load observed a clean suite needed up to ~60 s per run.
