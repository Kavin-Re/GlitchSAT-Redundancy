# P40 report: Verdict Dial

License: UNDECIDED. Working title TBD. Toy designs; faults are modelled single-tick bit flips; nothing physical; nothing established as new.

## Files written
- `docs/explainers/dial.html`: standalone page, single file, data inline, no external resources, opens from `file://`.
- `docs/explainers/dev/build_dial.py`: reads the sources, writes `dial.json`, inlines it into `dial.html`.
- `docs/explainers/dial.json`: 432 cells (3 designs x 6 readers x 4 builds x 2 pin settings x 3 power-up settings).
- `docs/explainers/dev/check_dial.py`: checker (data and on-screen). `docs/explainers/dev/DIAL_NOTES.md`: stage notes and 3-minute script.
- `research/c6/p40/`: this report, `shoot.py`, `check_dial.log`, `shoot.log`, `shots/` (10 PNG).
No other file was edited. `explainer.html` and `game.html` are untouched (the embed is left to the integration step). `check_game_answers.py` was not extended (not in my scope); `check_dial.py` is separate.

## What the dial shows (all MEASURED, copied from source rows)
| control | options | source |
|---|---|---|
| Who reads | whole word / 4 lights (masks 0x4E, 0x0F, 0x1B, 0x99) / accept flag boot_ok | matrix.jsonl goal; m1_all_masks.csv |
| Build | stored / re-built plain / merging (plain_opt_merge) / V2e (plain) | matrix.jsonl spike, apt033_plain; sweep_rows.csv Yosys 0.33 rows |
| Input pins attackable | no / yes | matrix.jsonl input_sites |
| Power-up | known / any non-opening state / any | matrix.jsonl init known, free_nongoal, free |
| Lock design (extra) | V2 / V1 / V0 | matrix.jsonl design; mask CSV columns |

- 94 cells measured, 338 "not measured". Value counts: 3 in 3 cells, 2 in 4, 1 in 59, 0 in 28.
- Stage path: V2 stored whole word 3 (matrix.jsonl line 241) -> re-built 2 (line 265) -> accept flag 1 (line 277) -> any power-up 0 (line 281). Merging 1 (sweep_rows.csv line 3), V2e 3 (line 10).
- Bound shown under every digit: 6 ticks, search limit 3 flips (N and KMAX parsed from `run_matrix.py`; T=6, k<=3 as stated in M1_REPORT and WHY_TWO_FLIPS).
- Source line (file + row) is always visible under the digit; tap opens key, label, netlist sha256, tool, bound, solver's flips. Netlist sha: from the row for the P01 builds; computed from `reference/spike_netlists/*.json` for the stored build; "not recorded in the source row" for the B2/M1 re-built rows (those netlists lived in /tmp and were not hashed).

## Tests (commands run on the copy in /tmp/work_p40, then again in the tree)
- `python3 docs/explainers/dev/check_dial.py --browser`: 467 checks passed, 0 failed (`check_dial.log`). It re-parses the sources with its own code, compares all 432 cells, then drives headless Chrome at 390 and 1366 px through all 432 combinations and compares the digit on screen, the bound string and the source line; also clicks and arrow keys 3->2->1->0, predict first (digit, reason and source hidden until a guess), F key, count-down animation 2,1,0 with motion allowed, no console errors, no horizontal scroll in any combination.
- `python3 research/c6/p40/shoot.py`: 10 of 10 PASS (`shoot.log`): 390, 1366 and 1920 px, light and dark, default, not measured, predict, big screen; min rendered text 13 px; no button, switch or summary under 44 px; no console output.

## Decisions that differ from the plan (say so rather than hide)
1. Power-up has three options, not two. The matrix separates "any state that would not open by itself" (1) from "any state" (0); merging them would have hidden a measured row.
2. A fifth switch, "Lock design" (V2/V1/V0), was added because the stage plan opens with "Dial on V1 (1)". It is unnumbered and last.
3. The mask buttons do not print their cost. The cost depends on the build, and printing it would defeat predict first; the dial shows it.
4. `results/comms/distance_sweep.csv` was read but is NOT used: none of the four controls maps to its codebook axis. `matrix.jsonl` rows for apt033_opt, conda038_* and the fresh-input rows are not on the dial either (checker confirms constant and fresh input agree in all 180 pairs).
5. Big-screen mode is a layout switch (key F); it does not call the browser full-screen API. Use F11.

## Limits and things not done
- 338 of 432 combinations are "not measured". The merging and V2e builds have one measured cell each (V2, whole word, pins no, known power-up); the 4-light readers only exist for pins no and known power-up. Nothing was run to fill gaps (no solver runs by this step).
- The reason sentences are an step-written lookup keyed by rule, drawn from B2_REPORT, M1_REPORT and WHY_TWO_FLIPS. They are explanations, not measurements. The "inputs" sentence ("every copy reads the same input pins") fits the stored-netlist witnesses (an input pin of one compare); on V1 re-built the solver's 1-flip witness is the `ok` wire, so there the sentence is looser than the witness.
- Yosys 0.38 rows are not on the dial. Tested in headless Chrome only; no Firefox or Safari, no real phone, no screen reader run (roles: native radios, a polite live region).
- Not reviewed by a human; wording is a draft for the author.

## Surprise
In the scope matrix only 10 of 360 cells are above 1, so most switch moves land on 1 or 0; the interesting moves are few and are the ones in the stage path.
