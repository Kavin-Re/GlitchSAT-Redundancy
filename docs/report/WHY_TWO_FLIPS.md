# Why V2 needs 2 flips on one netlist and 3 on another

Toy designs, modelled bit flips, nothing established as new, not a security proof.

## In plain words

V2 first loads a fixed "armed" value 0xCC into its state register, then the result word: 0x96 for the right key, 0x69 otherwise. Result bits are split over three compare copies (m0: bits 0,3,6; m1: 1,4,7; m2: 2,5).

0xCC and the accept word 0x96 differ in bits 1,3,4,6, which belong to only two copies (m1, m0). So the attacker can skip the compare and corrupt the load of 0xCC into a load of 0x96. Synthesis decides how many nets that takes:

- **Stored netlist** (68 gates, one mux per bit): no net moves two of the four bits; that route costs 4, so the three compares stay cheapest. **3.**
- **apt 0.33** (85 gates): ABC put bits {1,4} behind net `new_n58_` and bits {3,6} behind `new_n74_`. Two flips at cycle 0. **2.**
- **conda 0.38, same flow** (83 gates): bits {1,4} share a net (`new_n59`), bits {3,6} do not. **3.**

Changing only the armed constant to 0xA5 (`rtl/v2e.v`; xor 0x96 = bits 0,1,4,5, all three copies) gives 3 on every flow that keeps the copies separate, on both Yosys versions.

## What is supported (MEASURED)

1. **Encoding: supported.** Where the copies stay apart, min flips was never below the number of copies touched by `armed xor 0x96`; on apt plain it equalled it for all 9 constants.
2. **Synthesis structure: supported.** Whether that floor is reached depends on net sharing. With 0xCC, conda 0.38 gives 3,2,3,2,3,2 over the six non-merging flows.
3. **"Yosys version": not supported as worded.** The stored netlist's header reads `Yosys 0.33 (git sha1 2584903a060)`, same as apt; they differ in flow, not version. conda 0.38 is not immune (2 on three flows).

## Rows

Stem rule, goal `boot_word == 0x96`, T=6, k<=3, known init. Eight flows in `--synth-sweep` order; flows 2 and 3 merge the compares (always 1). `u` = unsupported, no verdict.

| Armed | copies | apt 0.33 | conda 0.38+92 | plain sha256 apt / conda |
|---|---|---|---|---|
| CC (v2) | 2 | 2 1 1 2 2 2 2 2 | 3 1 1 2 3 2 3 2 | f3fe9621 / 32b82842 |
| A5 (v2e) | 3 | 3 1 1 3 3 3 3 3 | same | 35624e33 / 53556f01 |
| 4D | 2 | 2 1 1 2 2 u 2 u | 3 1 1 2 3 u 3 u | 8abc2d13 / b3ffbe1b |
| 04 | 1 | 1 1 1 1 1 u 1 u | same | 03e0ce61 / 64b1b256 |
| CC, stored | 2 | 3 (as stored) | - | 289355dc |

Plain-flow hashes are the `research/c6/p01/sweep_rows.csv` values (rows 2, 10, 42, 58 and 74, 82, 114, 130; the integration step's own sweep also gave f3fe962135ab92ca for v2); an earlier version of this table listed the `synth.sh` builds in `research/c6/p01/netlist_sha256.txt` (214a2987 / 152aad31, 005b02a5 / a2aa7119, f8328dd0 / 71f4547e, b96bd545 / 5749a181), which have the same minimum flips but different hashes because the netlist sha256 depends on the Yosys working directory (source paths are embedded in the netlist), corrected by step INT2a, 2026-11-20.

Not shown: 5A, 3C (3 copies; all 3 off the merging flows), BB, 0F (2 copies; 2 or 3), B2 (1 copy; 1 or 2). Full hashes and all 144 rows: `research/c6/p01/netlist_sha256.txt`, `sweep_rows.csv`.

z3-free brute force (`research/c5/anchor/anchor_sim.py NETLIST TOP stem_flip 4 2`; every set of <= 2 flips, T=4): apt v2 3 attacking pairs; apt v2e 0 of 75,467; conda v2 0 of 66,431; conda v2e 0 of 63,547. Agrees with the solver on all 10 netlists.

All 9 designs boot only for key 0xC3 (iverilog, 256 keys).

```
faultbound-wt analyze rtl/v2.v --top v2 --max-flips 3 --cycles 6
faultbound-wt analyze rtl/v2e.v --top v2e --max-flips 3 --cycles 6 --synth-sweep
python3 research/c6/p01/cycle0_delta.py NETLIST TOP ARMEDHEX
```

For conda 0.38, put its yosys first in PATH.

## Suggested README row

"Full 8-bit word, `rtl/v2.v` re-synthesized with apt Yosys 0.33 (85 gates): **2**. Cause: the armed state 0xCC differs from the accept word 0x96 only in bits owned by two of the three compare copies, and this netlist has one shared net per copy. The stored netlist (also Yosys 0.33, different flow) and the conda 0.38 plain flow need 3; three other conda 0.38 flows need 2. Re-encoded (`rtl/v2e.v`): 3 on 6 of 8 flows on both versions, 1 on the two flows that merge the compares. MEASURED, toy model."

## Not done

Only 9 of 253 constants. No netlist images. Stored netlist's recipe not recovered. Docker 0.52 not run.
