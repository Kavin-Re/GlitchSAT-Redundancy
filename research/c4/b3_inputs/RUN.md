# b3_inputs: netlists needed to regenerate B3's matrix

| netlist | file | origin |
|---|---|---|
| V0, V1, V2 "spike" | `reference/spike_netlists/v{0,1,2}.json` (already in the repo; not copied) | stored spike netlists |
| V0, V1, V2 apt Yosys 0.33 plain flow | `nl/v0_apt033.json`, `nl/v1_apt033.json`, `nl/v2_apt033.json` | copies of `research/c2/b1_faultmodels/netlists/` (v2_apt033 equal to `research/c4/b3/nl/v2_apt033.json`; sha256 03198073...) |
| V5 apt 0.33 | `nl/v5_apt033.json` | copy of `research/c4/b3/nl/v5_apt033.json` (V5 has no spike netlist) |
| B3 committed results | `research/c4/b3/matrix_T6.jsonl` (182 cells) | |

Layout-derived inputs for the same engine are in `research/c4/l2_inputs/` and `research/c4/layout/`.

## Commands (python3 + z3-solver)
```
cd research/c4/b3_inputs
python3 check_b3_matrix.py                         # all 182 cells, T=6, cap 3, z3 timeout 90 s, 4 processes; exit 1 if any differs
python3 check_b3_matrix.py --designs v2,v2_apt033 --models rail_all,rail_cone    # a subset
python3 ../b3/b3pack.py nl/v2_apt033.json --top v2 --model rail_cone --cycles 6 --cap 3 --goal word    # one cell by hand
```
## Measured check (MEASURED, 2026-11-19, fresh copy of reference/ + research/c4/b3 + b3_inputs under /tmp/work_anchor/fresh_b3)
`python3 check_b3_matrix.py`: cells 182, agree 182, DIFFER 0, 35 s wall on 4 cores. (B3's own logged solve time for the matrix was 334 s serial.)
