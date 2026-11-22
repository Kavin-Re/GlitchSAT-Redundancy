# E2: synthesis-variance matrix for V0, V1, V2

Licence: UNDECIDED. Working title TBD.
Every number below is MEASURED unless marked otherwise; the command is `python3 scripts/matrix.py out` followed by `python3 scripts/report_tables.py out` (run in /tmp/work_e2; scripts in `scripts/`, raw data in `raw/`).

## What was run
- Designs: `rtl/v0.v`, `v1.v`, `v2.v` (copied to /tmp/work_e2; the originals and `scripts/glitchsat.py` were not touched).
- Yosys builds: apt 0.33 (`/usr/bin/yosys`), conda `formal` 0.38+92 (git 84116c9a3), conda `eda` 0.38+92 (same git sha, separate build). Envs not modified.
- Factors (full factorial, 864 configurations = 3 builds x 3 designs x 96 per design):
  - flow: `plain` (proc; techmap) | `opt` (`synth -top; dffunmap`), as in `scripts/synth.sh`
  - order: `abc_then_flatten` (map each module, then flatten: what `synth.sh` does) | `flatten_then_abc` (flatten first, so ABC sees all three compare copies at once)
  - ABC: `abc -g AND,OR,XOR,MUX` (default) | `-fast` | `-g AND,OR,XOR` (no MUX) | `-g AND,OR` | `-dff` | no abc
  - merge: no `opt_merge` | `opt_merge` after flatten (before abc in flatten_then_abc)
  - keep: RTL `(* keep *)` attributes as written | stripped (`(* keep_hierarchy *)` retained)
- Each configuration synthesised 3 times (2592 synthesis runs, 0 failures).
- Verdict engine: copy of `glitchsat.py` (z3), goal `boot_word == 0x96` with attacker input `sig` held constant and != key, 6 cycles, flips = single-cycle flips of any gate output or flop Q (the engine's model). One minimising solve per unique netlist at k<=3 gives the minimum number of flips; "min <= k" is the verdict for k=1,2,3, ">3" would mean none found (never occurred). Cross-check with the documented CLI (`glitchsat.py check ... --k 1|2|3 --cycles 6`) on the baseline V2 for apt and conda: raw/cli_v2.txt, agrees (apt: k=1 none, k=2 attack, min 2; conda: k=1,2 none, k=3 attack, min 3).
- Netlists the engine cannot read (cells such as $_NAND_, $_ANDNOT_ from the `opt` flow with no final abc) are marked ENGINE_UNSUPPORTED (72 of 864 configs, all `opt` flow with no ABC): no verdict, not "safe".

## 1. Determinism
MEASURED: all 864 configurations gave byte-identical netlists across 3 repeated runs (raw SHA-256 identical, and identical after dropping the `creator` field). Synthesis is deterministic per build; the variance is between builds and options, not between runs. (`raw/tables.txt`, `raw/synth_all.json`.)

## 2. Baseline (the `synth.sh` plain flow) per build  (MEASURED; SHA-256 of the netlist file, first 12 hex)
| design | build | gates (flops) | min flips (6 cycles) | sha256 |
|---|---|---|---|---|
| V0 | apt 0.33 | 25 (2) | 1 | 15432bfd3837 |
| V0 | conda formal 0.38 | 23 (2, 1 MUX) | 1 | d8b45e231229 |
| V0 | conda eda 0.38 | 23 (2, 1 MUX) | 1 | 746d2b2f96e0 |
| V1 | apt | 72 (8) | 1 | 5839583d189d |
| V1 | formal | 70 (8) | 1 | b329e4e7b2ad |
| V1 | eda | 70 (8) | 1 | 382cfa33610c |
| V2 | apt | 85 (8) | 2 | 0454bf4a8b04 |
| V2 | formal | 83 (8, 1 MUX) | 3 | 4ca175d0a3fb |
| V2 | eda | 83 (8, 1 MUX) | 3 | 72fd54da6554 |
Same gate counts for formal and eda, but different file hashes (names/ids differ, and the creator string). Full matrix with gate histograms, flops, hashes: `raw/matrix.csv` (864 rows).

## 3. Results over the whole matrix (MEASURED, `raw/tables.txt`, `raw/v2_v1_compact.txt`)
Minimum flips, count of solved configurations (ENGINE_UNSUPPORTED excluded):
| design | min 1 | min 2 | min 3 |
|---|---|---|---|
| V0 | 264 | 0 | 0 |
| V1 | 233 | 31 | 0 |
| V2 | 180 | 60 | 24 |
So V0 never exceeds 1 and V1 never exceeds 2. V2's verdict ranges over 1, 2 and 3 flips. The ordering V0 <= V1 <= V2 held in every comparable configuration I looked at, but I did not run an automated check of it per row (UNVERIFIED as a universal statement).

V2 by build (min1/min2/min3): apt 60/24/4, formal 60/18/10, eda 60/18/10. The formal and eda builds gave identical verdicts in all 288 matched configurations (same git sha).

### Which choices move V2
(counts over all builds; configs where min 3 happens)
- **min 3 (compare copies stay independent)** occurs only in `plain` flow, `abc_then_flatten`, no `opt_merge`, and: the default / no-MUX / AND,OR ABC scripts on conda 0.38 (not apt 0.33, which gives 2), or no ABC at all (141-gate unoptimised netlist; all three builds). It does not occur with `opt` flow, `-fast`, `-dff`, `opt_merge` or `flatten_then_abc` (except no-ABC).
- **min 2:** apt 0.33 baseline and its default/noMUX/AND_OR variants; `-fast` on all three builds (plain and opt, both orders); `opt` flow with `abc_then_flatten`, no merge, on all builds.
- **min 1 (V2 falls to one flip):** any `opt_merge` after flatten (the three copies collapse to one match net: 1 distinct `sig==0xC3` net instead of 3); `flatten_then_abc` with default ABC; `abc -dff`; `opt` flow with flatten first; no-ABC with merge.
- `keep` attribute: on/off changed the netlist in all 432 pairs (gate counts, e.g. conda baseline 83 vs 79 gates) but did not change any V2 or V1 verdict in a matched pair.
- The 0.33 vs 0.38 difference is confined to the baseline-type configurations: 7 matched groups differ in min flips (6 V2, all `plain / abc_then_flatten / default|noMUX|AND_OR / no merge`, apt 2 vs conda 3; 1 V1: `opt / abc_then_flatten / default / no merge / keep stripped`, apt 2 vs conda 1). Everywhere else the two builds agree on the verdict (though the netlists differ in 288 of 288 matched groups when compared as files).

### V1
V1's verdict is 1 flip in 233 of 264 solved configurations (shared decision net `ok`) and 2 in 31: 24 are `abc -fast` (all builds, both flows/orders, no merge or merge) and 7 are `opt` flow + `abc_then_flatten` + no merge + `(* keep *)` stripped + a non-fast ABC script (apt: default, noMUX, AND_OR; conda: noMUX, AND_OR). So V1's 'breaks with 1 flip' is also not build-invariant when `keep` is stripped under the optimising flow. I did not analyse why; unexplained.

## 4. Why (what the tool merges) - partly MEASURED, partly interpretation
- MEASURED structural check (`matrix.csv` columns `distinct_match_nets`, `shared_gates_between_match_cones`): in the baseline all three compare copies are three distinct nets with 0 shared gates (V2 has 3 match nets, 0 shared). After `opt_merge`, or after flattening before ABC, the number of distinct nets that compute `sig == 0xC3` drops to 1 or 2 and the cones share gates. The redundancy is then not in the netlist, and one flip on the merged net decides every result bit: min 1. This is plain common-subexpression elimination: identical logic over the same input is, to the tool, one gate.
- The `(* keep_hierarchy *)` on `cmp8` is what keeps the copies apart in the baseline: ABC runs per module before flatten. The flow depends on that ordering; `scripts/synth.sh` encodes it ("no opt_merge after flatten").
- Between apt 0.33 and conda 0.38 the three compare cones are disjoint in both. The difference is outside the compare copies: the inspected minimum attacks differ (`raw` run of `scripts/inspect_faults.py`): apt: two flips in cycle 0 (an AND with fanout 3 reaching 3 state-D bits plus an OR reaching 2) give boot_word = 0x96; conda needs three (an AND, a `$procmux` OR, and a flop Q flip at cycle 1). The 85- vs 83-gate difference is ABC/techmap mapping of the next-state logic (one MUX on conda). I did NOT locate the exact tool change responsible; "build" is a correlate, not an identified cause. In this model one flip of a net with fanout is one fault, so a stem flip that touches several result bits is cheap; the other step's weighted-cost analysis (DA_CYCLE1) says that is the largest driver of 2 vs 3.
- `abc -fast`, `-dff` and the optimising `synth` flow restructure the next-state logic and/or the FSM encoding, giving other minima; reasons not analysed.

## 5. What this means for wording
1. A verdict ("V2 needs 3 flips" / "V2 resists 2") is a property of one netlist (a file hash) under one fault model, not of the Verilog. The same Verilog and the same script give 1, 2 or 3 depending on the build and flags; synthesis is deterministic, so a stored netlist plus its SHA-256 is reproducible and a re-synthesis is reproducible only on the same build.
2. State the claim as: "On the stored spike netlist (sha ...), no attack with <=2 single-cycle flips for goal boot_word within 6 cycles; re-synthesising rtl/v2.v with apt Yosys 0.33 `synth.sh plain` gives an 85-gate netlist with a 2-flip attack; conda 0.38 gives 83 gates and min 3; in this 864-configuration grid V2's minimum was 1 in 180, 2 in 60, 3 in 24 of 264 solved". Never "V2 resists 2 faults" without the netlist.
3. Say "redundancy that survives synthesis" and name the guard (hierarchy kept through ABC, no post-flatten opt_merge); say that a build with default optimisation merges the copies and V2 then breaks with 1 flip.
4. The V0 <= V1 <= V2 ordering and "V0 breaks with 1" were robust in this grid; absolute V2 numbers were not.
5. "Min flips" counts one net flip as one fault regardless of fanout; the 2 vs 3 difference interacts with that counting rule.

## 6. Limits (what I did not do)
- 6 cycles, goal boot_word=0x96, flips only, attacker input constant (not free per cycle), toy designs. No unbounded proof on any re-synthesised netlist. No k>=4.
- Minimum per netlist taken from one minimising z3 solve at k<=3 per unique netlist (447 solves; identical netlists shared by hash). CLI cross-check done only on the baseline V2 for apt and conda-formal, not per row. Solver ran with default z3 seed; no seed sweep (an older partial script supports `--seeds`).
- Only Yosys + ABC as built; no other synthesis tools or ABC versions; formal and eda builds share one git sha so they are not independent builds. A newer Yosys (the earlier partial run mentioned an env `ynew`) was not used and does not exist here.
- 72 ENGINE_UNSUPPORTED configurations have no verdict.
- Yosys script is passed as a script file (the `-p` form splits on commas in `abc -g AND,OR`); otherwise identical commands to `synth.sh`.

## Files
- `scripts/matrix.py` (driver), `scripts/report_tables.py`, `scripts/analyze.py` (engine call + structural check), `scripts/inspect_faults.py`; earlier partial scripts (`variants.sh`, `run_*.sh`, `summarize.py`) kept unchanged, superseded.
- `raw/matrix.csv`, `raw/matrix.json` (864 rows), `raw/synth_all.json` (2592 runs with SHA-256), `raw/solve_by_canon_sha.json`, `raw/tables.txt`, `raw/v2_v1_compact.txt`, `raw/cli_v2.txt`, `raw/matrix.log`.
- `baseline_netlists/` the 9 baseline netlists and one example Yosys script.
