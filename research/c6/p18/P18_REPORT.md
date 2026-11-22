# P18 report: error-correcting decoder variants of v2

License: UNDECIDED. Toy designs, modelled single-cycle bit flips, bounded (T=6, k<=4). Nothing established as new; no general claim about ECC.

## Order of work (UTC)
1. 05:20:07 pre-registration written: research/c6/comms/P18_PREREG.md (before RTL synthesis and any solver run).
2. RTL rtl/v2_secded.v, rtl/v2c.v; benches tb/tb_v2_secded.v, tb/tb_v2c.v: FUNC_PASS for both (SIMULATED, iverilog). The benches also printed, before any solver run, that 8 of 280 simultaneous triple flop flips boot a wrong key on v2_secded: this simulation result was known before the solver confirmed 3, but after the pre-registration.
3. One exploratory solver call on v2_secded (all nets, boot_word, --synth-sweep) to learn the JSON format, after steps 1-2.
4. 05:21:34 full run: scripts/comms/decoder_variants.py -> results/comms/decoder_variants.csv (144 rows = 4 designs x 2 goals x 2 site sets x 9 flows), log research/c6/p18/run.log (witnesses). Wall 70 s. No timeout, no 'unknown', no '>k'.

## Predicted vs measured (flow plain, yosys 0.33) - MEASURED, source decoder_variants.csv
| design | goal | sites | predicted | measured | verdict |
|---|---|---|---|---|---|
| v2_secded | boot_word | flops | 3 | 3 | match |
| v2_secded | boot_word | all | 2 (range 1..2) | 2 | match |
| v2c | boot_word | flops | 4 | 4 | match |
| v2c | boot_word | all | 2 (= v2) | 2 (v2: 2) | match |
| v2_secded | boot_ok | flops | 3 | 3 | match |
| v2c | boot_ok | flops | 4 | 4 | match |
| v2, v2e, v2_secded, v2c | boot_ok | all | 1 | 1 | match |
| v2 (reference) | boot_word | flops / all | - | 4 / 2 | agrees with P11 |
| v2e (reference) | boot_word | flops / all | - | 4 / 3 | |

10 of 10 pre-registered cells matched. No falsifier fired. The predictions were easy (d - t arithmetic; goal cones); matching them is weak evidence.

## All 9 flows, goal boot_word==0x96, all nets (MEASURED; not predicted except plain)
flows: plain, plain_opt_merge, flatten_before_abc, abc_fast, abc_no_mux, opt_flow, plain_keep_off, opt_flow_keep_off, struct_no_abc
- v2:        2,1,1,2,2,2,2,2,3
- v2e:       3,1,1,3,3,3,3,3,3
- v2_secded: 2,1,1,2,2,2,2,2,3
- v2c:       2,1,1,2,2,2,2,2,3
Flops only: v2 4, v2e 4, v2c 4, v2_secded 3, in all 9 flows. boot_ok all nets: 1 everywhere.

## Findings
- The SECDED corrector LOWERS the flops-only cost from 4 to 3 (d - t). This contradicts the work plan's suggested prediction ("rises") and matches the pre-registered one.
- NEGATIVE: the task idea "the decoder is shared attack surface, so the all-nets minimum drops" is NOT supported: v2_secded and v2c have the same all-nets minimum as v2 in 9 of 9 flows, although the netlist grows (plain: 85 -> 143 / 100 gates). My prediction "<= 2" holds only because v2 already costs 2.
- NEGATIVE: the check-only consumer v2c changed no minimum in any cell.
- The 1-flip rows (plain_opt_merge, flatten_before_abc; witnesses c0.m, word[0]) are the known merged-compare effect of v2, present with and without a decoder.
- This decoder, this code, this FSM: no general rule about ECC.

## Not done / limits
- Witnesses not attributed (decoder nets vs compare nets), except that the struct_no_abc witness of v2_secded uses fix[2], fix[5] (decoder nets) at the same cost 3 as v2.
- No k>4, no T>6, no other yosys version, no fanout counting rule, no multi-cycle scrub variants, no decoder that traps instead of corrects.
- Sweep 'plain' is the scripts/synth.sh plain flow but its hash differs from synth.sh output (source read as design.v).
- v2_secded design choice: boot_word is the DECODED word. A variant exporting the raw register was not built.
