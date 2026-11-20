# B1 fault-model pack: minimum fault-event cost per model

All faults are MODELLED single-cycle events on Yosys gate netlists, not physical glitches. Every verdict is bounded (T = 6 cycles, cap 3 events, constant free `sig` != 0xC3, goal `boot_word == 0x96` at some cycle, known init state). Solver: z3 via `faultpack.py` (an extension of the `scripts/glitchsat.py` engine; that file is untouched). Entries are minimum cost in events; `>3` means UNSAT for every cost <= 3.

## Models (faultpack.py `MODELS`)
- stem_flip: glitchsat's own model (flip of a gate output or flop Q, all fanout sees it). branch_flip: each fanout pin flipped separately.
- set_only / reset_only: a net forced to 1 / 0 for one cycle. branch_set / branch_reset: same on fanout pins.
- flop_hold: one flop ignores one clock edge. clock_skip_all: ONE glitch holds any subset of flops for one edge.
- group_flops_m2, group_hood_m2: one event flips up to 2 nets of a group (all flops / 1-hop netlist neighbourhood). cone_flip_exact: one event flips ALL gates in the combinational fanout cone of one net. hood_flip_exact: one event flips ALL nets of a 1-hop neighbourhood. Groups come from the netlist graph, not from layout. User-named groups: `--groups-json`.
- input_flip / input_set / input_reset / input_branch_flip: primary-input bits (and the pins they feed) become fault sites.

## Matrix (MEASURED, T=6, cap 3; `matrix_T6.md`, `matrix_T6.json`)
Columns: spike = `reference/spike_netlists/*.json`; apt033 and conda038 = re-synthesis of `rtl/` (`synth_variants.sh`; stored under `netlists/`).
| model | spike v0 | spike v1 | spike v2 | apt033 v0 | apt033 v1 | apt033 v2 | conda038 v0 | conda038 v1 | conda038 v2 |
|---|---|---|---|---|---|---|---|---|---|
| stem_flip (baseline) | 1 | 1 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| set_only | 1 | 1 | 3 | 1 | 1 | 3 | 1 | 1 | 3 |
| reset_only | 1 | 2 | 3 | 1 | 2 | 3 | 1 | 2 | 3 |
| branch_set | 1 | 2 | 3 | 1 | 2 | 3 | 1 | 2 | 3 |
| branch_reset | 1 | 2 | 3 | 1 | 2 | 3 | 1 | 2 | 3 |
| branch_flip | 1 | 2 | not finished | not run | not run | not run | not run | not run | not run |
| flop_hold | >3 | >3 | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| clock_skip_all | >3 | >3 | >3 | >3 | >3 | >3 | >3 | >3 | >3 |
| group_flops_m2 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 1 | 2 |
| group_hood_m2 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 1 | 2 |
| cone_flip_exact | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 |
| hood_flip_exact | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 |
| input_flip / input_set / input_reset | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| input_branch_flip | 1 | 2 | not finished | not run | not run | not run | not run | not run | not run |
(stem_or_branch_flip: not run in this matrix; the solver call hung for the spike V2 branch cells beyond the 60 s z3 timeout, so those cells are unknown, not "no attack".)

## Which models change the V2 verdict (spike netlist, baseline: 3 flips needed, no attack at <= 2)
- Cheaper than baseline: the correlated models (cone_flip_exact, hood_flip_exact: 1 event; group_flops_m2, group_hood_m2: 2 events) and every input-fault model (1 event). So V2 does not survive 1 event under these models. Same direction on the re-synthesized netlists (apt033 already 2 at baseline; apt033 and conda038 reach 1 under input faults).
- Unchanged at 3: set_only, reset_only, branch_set, branch_reset (V1 rises to 2 under reset and branch models because a single stem no longer reaches all fanout).
- No attack at all up to 3: flop_hold and clock_skip_all (a hold alone cannot create the accept word from the reset state in these designs).
- Caveat for the input-fault row: the engine treats `sig` as free and constant, so one flip of a `sig` bit at the sampling cycle makes `sig = 0xC3 xor one bit` appear as the key. That is the time-varying-input spec issue already found by E1; it is a statement about the spec, not a hardware weakness. The cone and hood rows are also a generous model: the cone of a stem near the compare reaches many bits at once by construction.
- V1 and V0 do not change (min 1 under every flip-type model).

## Validation (MEASURED; `validate.py`, log `validate_T4.log`; the json summary was not written because the run was stopped)
Independent checker `modelsim.py` (own JSON reader, no z3, bit-parallel over all 256 `sig` values, exhaustive enumeration of every action set of cost <= 2) vs the solver at T=4 on the spike netlists: 36 (design, model) rows compared, 36 agree, 0 disagree (all 17 models on V0 and V1; on V2 only stem_flip and branch_flip, both min 3, solver witness replayed in the simulator). The V2 rows for the other 15 models were NOT validated (the run was stopped for time). Solver witnesses were replayed in the simulator for every ATTACK row.
pytest: 32 passed in about 60 s, run in /tmp/work_b1 (`PROJ=/home/user/project python3 -m pytest -q test_faultpack.py`).

## Commands
```
cp -r research/c2/b1_faultmodels /tmp/work_b1/ && cd /tmp/work_b1/b1_faultmodels
sh synth_variants.sh /home/user/project netlists          # apt0.33 + conda0.38 netlists (stored copies already present)
python3 validate.py validation_T4.json                   # exhaustive cross-check, T=4 (long on V2)
python3 run_matrix.py --cap 3 --timeout-ms 60000 --models stem_flip,set_only --out m   # matrix; merge_matrix.py merges partial files
python3 faultpack.py ../../../reference/spike_netlists/v2.json --top v2 --model cone_flip_exact --cycles 6 --cap 3
python3 -m pytest -q test_faultpack.py
```

## NOT covered
- Matrix gaps: branch_flip, stem_or_branch_flip, input_branch_flip on V2 (all netlists) and on the re-synthesized V0/V1 columns; not run to completion.
- Exhaustive validation only at T=4, cost <= 2, mostly V0/V1. Matrix is T=6 only; cap 3, so ">3" is not "secure".
- The model semantics (what a "set", "hold", "cone" means) are my modelling choices; none is calibrated to a layout, supply network or clock tree. Fault sites on clk/reset: none. Time-varying `sig` is not modelled beyond the input-fault rows. No physical claim; nothing established as new.
- Stored matrix numbers come from a re-run of interrupted jobs; the earlier agent's partial files were reused for code only.
