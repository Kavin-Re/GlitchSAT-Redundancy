# auto-harden results

Modelled bit flips (one-cycle flips of gate outputs and flop outputs), toy 8-bit designs, constant attacker input, known reset state.
Every "min flips" below is an exhaustive simulation of the named netlist over all wrong inputs. Not a security proof.

Labels: **MEASURED** = simulated here; **RECORDED** = value stored in the repository, shown for comparison; **UNTESTED-HERE** = needs Yosys (cloud/run_cloud.sh).

## 1. Search on the design descriptions (MEASURED on reference gate mappings; Yosys netlists of the fixes UNTESTED-HERE)

"Before" and "after" are the smallest minimum over the three unmerged reference mappings (select-shared, mux-shared, unshared), any number of cycles.
The last column is the same design when identical copies are merged (the `merged` mapping, a model of opt_merge after flatten).

| design | goal (min flips) | best fix found | min flips before | min flips after | cost | after, if copies get merged |
|---|---|---|---|---|---|---|
| v0 | >= 2 | idle code word 0x0 -> 0xF0; armed code word 0x1 -> 0xCC; accept code word 0x2 -> 0x96; reject code word 0x3 -> 0x69; state width (bits) 2 -> 8; boot_word source decoded -> state; voter placement single_and -> owner; compare copies that own bits 1 -> 2; bit ownership (bit 7..0 -> copy) - -> 10101010 | 1 | 2 | +50 gates, +6 flops, depth +2, latency +0 cycles | 1 |
| v0 | >= 3 | idle code word 0x0 -> 0xF0; armed code word 0x1 -> 0xC8; accept code word 0x2 -> 0x96; reject code word 0x3 -> 0x69; state width (bits) 2 -> 8; boot_word source decoded -> state; voter placement single_and -> owner; compare copies that own bits 1 -> 3; bit ownership (bit 7..0 -> copy) - -> 10210210 | 1 | 3 | +61 gates, +6 flops, depth +2, latency +0 cycles | 1 |
| v1 | >= 2 | voter placement single_and -> owner; bit ownership (bit 7..0 -> copy) - -> 10101010 | 1 | 2 | +1 gates, +0 flops, depth +0, latency +0 cycles | 1 |
| v1 | >= 3 | armed code word 0xCC -> 0xC8; voter placement single_and -> owner; compare copies that own bits 2 -> 3; bit ownership (bit 7..0 -> copy) - -> 10210210 | 1 | 3 | +12 gates, +0 flops, depth +0, latency +0 cycles | 1 |
| v2 | >= 3 | armed code word 0xCC -> 0xC8 | 2 | 3 | -1 gates, +0 flops, depth +0, latency +0 cycles | 1 |
| v2 | >= 4 | idle code word 0xF0 -> 0x61; armed code word 0xCC -> 0x49; compare copies that own bits 3 -> 4; bit ownership (bit 7..0 -> copy) 10210210 -> 32103210 | 2 | 4 | +13 gates, +0 flops, depth +0, latency +0 cycles | 1 |
| v2 | >= 5 | not reached (closest: 5 copies, voter owner 21043210, idle/armed/accept/reject 61/49/96/69, 4) | 2 | - | - | - |

Per mapping (before -> after, exact where a number is shown; `> k` = none with k or fewer flips):

| design | goal | select-shared | mux-shared | unshared | flip sets simulated in the search | search time (s) |
|---|---|---|---|---|---|---|
| v0 | >= 2 | 1 -> 2 | 1 -> 2 | 1 -> 2 | 5040 | 9.43 |
| v0 | >= 3 | 1 -> 3 | 1 -> 3 | 1 -> 3 | 13082 | 17.99 |
| v1 | >= 2 | 1 -> 2 | 1 -> 2 | 1 -> 2 | 759 | 1.9 |
| v1 | >= 3 | 1 -> 3 | 1 -> 3 | 1 -> 3 | 12203 | 11.23 |
| v2 | >= 3 | 2 -> 3 | 2 -> 3 | 3 -> 3 | 12203 | 3.78 |
| v2 | >= 4 | 2 -> 4 | 2 -> 4 | 3 -> 4 | 1595633 | 51.28 |
| v2 | >= 5 | 2 -> not reached | 2 -> not reached | 3 -> not reached | 21040508 | 252.18 |

## 2. What each transformation buys when applied alone (MEASURED on reference mappings)

### v1: 2 copies, voter single_and, idle/armed/accept/reject F0/CC/96/69

| change (alone) | select-shared | mux-shared | unshared | copies merged | gates | flops | depth |
|---|---|---|---|---|---|---|---|
| as is | 1 | 1 | 1 | 1 | +0 | +0 | +0 |
| voter: one kept AND per state bit | 2 | 2 | 2 | 1 | +17 | +0 | +0 |
| voter: none in front of the register (bit ownership) | 2 | 2 | 2 | 1 | +1 | +0 | +0 |
| one more owning copy | 1 | 1 | 1 | 1 | +12 | +0 | +0 |
| check copy + infection | 1 | 1 | 1 | 1 | +16 | +0 | +1 |
| check copy + sticky alarm flop | 1 | 1 | 1 | 1 | +26 | +1 | +3 |
| infection without a check copy | 1 | 1 | 1 | 1 | +3 | +0 | +0 |
| invalid state -> reject | 1 | 1 | 1 | 1 | +19 | +0 | +2 |

### v2: 3 copies, voter owner 10210210, idle/armed/accept/reject F0/CC/96/69

| change (alone) | select-shared | mux-shared | unshared | copies merged | gates | flops | depth |
|---|---|---|---|---|---|---|---|
| as is | 2 | 2 | 3 | 1 | +0 | +0 | +0 |
| voter: single AND in front of the register | 1 | 1 | 1 | 1 | -1 | +0 | +0 |
| voter: one kept AND per state bit | 3 | 3 | 3 | 1 | +23 | +0 | +0 |
| one more owning copy | 3 | 4 | 4 | 1 | +14 | +0 | +0 |
| check copy + infection | 2 | 2 | 4 | 1 | +20 | +0 | +2 |
| check copy + sticky alarm flop | 2 | 2 | 4 | 1 | +30 | +1 | +4 |
| infection without a check copy | 2 | 2 | 3 | 1 | +7 | +0 | +1 |
| invalid state -> reject | 2 | 2 | 3 | 1 | +19 | +0 | +2 |

## 3. Every armed constant of V2 (MEASURED on reference mappings)

253 possible armed code words (all 8-bit values except idle 0xF0, accept 0x96, reject 0x69), other parameters as rtl/v2.v.
No attack with 2 or fewer flips: select-shared 96, mux-shared 159, unshared 217; on all three: **96**.
Rows: `results/armed_sweep_v2.csv`. 0xA5 (rtl/v2e.v) reaches 3 on mux-shared and unshared and 2 on select-shared; 0x5A and the pick 0xC8 reach 3 on all three.

## 4. The encoding fix on Yosys netlists already in the repository (MEASURED here on stored netlists; plain flow)

Same design, only the armed constant differs. These are real Yosys outputs (`research/c6/p01/netlists/`). "Recorded" is the solver value in `research/c6/p01/sweep_rows.csv`.
Brute force = every pair of (cycle, site) flips over 6 cycles.

| armed | Yosys | gates | min flips, 6 cycles | min flips, all cycles | recorded (solver) | brute force pairs: attacking / all | reference mappings sel / mux / unshared |
|---|---|---|---|---|---|---|---|
| CC | 0.33 (apt) | 85 | 2 | 2 | 2 | 5 / 155403 | 2 / 2 / 3 |
| CC | 0.38+92 (conda) | 83 | 3 | 3 | 3 | 0 / 148785 | 2 / 2 / 3 |
| 04 | 0.33 (apt) | 81 | 1 | 1 | 1 | 530 / 142311 | 1 / 1 / 3 |
| 04 | 0.38+92 (conda) | 82 | 1 | 1 | 1 | 533 / 145530 | 1 / 1 / 3 |
| 4D | 0.33 (apt) | 89 | 2 | 2 | 2 | 5 / 169071 | 2 / 2 / 3 |
| 4D | 0.38+92 (conda) | 88 | 3 | 3 | 3 | 0 / 165600 | 2 / 2 / 3 |
| 5A | 0.33 (apt) | 88 | 3 | 3 | 3 | 0 / 165600 | 3 / 3 / 3 |
| 5A | 0.38+92 (conda) | 88 | 3 | 3 | 3 | 0 / 165600 | 3 / 3 / 3 |
| A5 | 0.33 (apt) | 89 | 3 | 3 | 3 | 0 / 169071 | 2 / 3 / 3 |
| A5 | 0.38+92 (conda) | 81 | 3 | 3 | 3 | 0 / 142311 | 2 / 3 / 3 |

Simulator equals the recorded solver value on 10 of 10 netlists. The select-shared mapping is not above the Yosys netlist on 10 of 10.
So the manual fix 0xCC -> 0xA5 is confirmed here on the stored apt 0.33 netlist: **2 -> 3**; 0xCC -> 0x5A likewise 2 -> 3. The search pick 0xC8 has no stored Yosys netlist: UNTESTED-HERE.

## 5. Fixes applied directly to stored netlists (MEASURED here, no re-synthesis)

| netlist | what it is | goal | lint | fix | min flips before | min flips after | cost | goal reached |
|---|---|---|---|---|---|---|---|---|
| `validation/nl/v2.json` | V2 synthesised flatten-first (copies merged by abc) | >= 2 | merged, 16 single points | Remove single points (separate the shared copy logic) | 1 | 2 | +20 gates, depth +0 | yes |
| `research/c2/reviews/ct/tests/v2_inbuf.json` | V2 with a shared input buffer stage | >= 3 | merged, 8 single points | Remove single points (separate the shared copy logic) | 1 | 3 | +16 gates, depth +0 | yes |
| `reference/spike_netlists/v2.json` | stored V2, consumer checks only bits 0x8D | >= 3 | separate, 0 single points | Consumer checks every owned bit | 1 | 3 | +4 compared bits in the consumer (ASSUMED) | yes |
| `reference/spike_netlists/v2.json` | stored V2, consumer checks only the low nibble | >= 3 | separate, 0 single points | Consumer checks every owned bit | 2 | 3 | +4 compared bits in the consumer (ASSUMED) | yes |
| `research/c2/e2_variance/baseline_netlists/apt0.33_v2.json` | apt 0.33 V2: no shared copy logic, nothing to remove | >= 3 | separate, 0 single points | none applicable | 2 | 2 | - | no |

The lint is `merge_lint.py` from the attack-surface work, called with the V2 bit ownership 0,3,6 / 1,4,7 / 2,5. The un-merged netlists are in `results/netlists/` (JSON readable by scripts/glitchsat.py, and structural Verilog).

## 6. Why the separation constraints (RECORDED: the 264 solved V2 configurations of research/c2/e2_variance)

| subset of the 264 solved V2 configurations | min 1 / min 2 / min 3 |
|---|---|
| all | 180 / 60 / 24 |
| opt_merge after flatten | 120 / 12 / 0 |
| flatten before abc | 102 / 24 / 6 |
| abc per module then flatten, no opt_merge (the flow the guard script enforces) | 12 / 36 / 18 |

48 of the 60 configurations that still have three distinct match nets need 2 or more flips; 153 of the 180 one-flip configurations have fewer than three.
The guard added by harden (keep on every cell of a kept module before flatten) is meant to make the opt_merge rows behave like the last row. That is read from the Yosys 0.33 source of opt_merge (two cells that both carry keep are not merged); it is UNTESTED-HERE and is the first thing cloud/run_cloud.sh measures. It cannot help the flatten-before-abc rows: abc rebuilds the logic.

## Reproduce

```
GLITCHSAT_ROOT=<repository root> python3 results/make_results.py     # this file, results.json, studio/suggest_fix.json
sh cloud/run_cloud.sh                                                # Ubuntu 24.04: Yosys 0.33 re-synthesis check
```

Run time of this file: 372.7 s (numpy only).
