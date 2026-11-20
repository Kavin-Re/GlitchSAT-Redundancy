# Redundancy as a code: the coding view of the V0/V1/V2 designs

License: UNDECIDED. Working title TBD. Textbook coding theory measured on toy designs: nothing here is established as new. Faults are modelled single-cycle bit flips in a gate netlist, not physics. Every number has a label and a source (file and CSV row; row numbers count the header as row 1).

## In plain words

When a designer copies a check three times, or stores a state as an 8-bit pattern that is far from every other pattern, they are building an error-detecting code, whether or not they think of it that way. Coding theory then says how many bit errors the code can always notice: its minimum distance minus one. Our measurements show the catch: that promise holds only for errors on the stored bits. As soon as the attacker may also flip the wire that *reads* the code, the number of flips needed falls to the number of separate reading wires, and if all copies are read through one shared wire, it falls to one. A code protects the codeword, not the circuit that decodes it.

## Two codes in each design

1. **The decision bit as a repetition code.** The match result `m = (sig == 0xC3)` is computed by n separate comparators: n=2 in V1, n=3 in V2. That is the repetition code [n, 1, n] (test: `test_repetition_view_of_decision_bit`). V2 never votes; it accepts only if all three copies agree, so it uses the code for detection only, and faking a match needs all three copies flipped: 3 flips, which is the measured V2 cost on the stored netlist. V1 joins its two copies into one net, `ok = m1 & m2`, before anything is stored. That net is a single point where every codeword decodes alike, so one flip suffices.
2. **The state word as a code.** V1 and V2 store the state in 8 flops using {F0, CC, 96, 69}. All five RTL words F0, CC, 96, 69 and the key C3 are codewords of the Reed-Muller code RM(1,3) [8, 4, 4] (FACT, `docs/comms/test_rm13.py`, 16 tests pass, output `research/c6/p13/test_output.txt`). Bit-order convention: bit i of the byte is the value of a Boolean function at the point x = binary(i); then F0 = x2, CC = x1, 96 = x0+x1+x2, 69 = its complement, C3 = 1+x1+x2. The membership also holds when the byte is read MSB-first (the code is invariant under bit reversal; tested). RM(1,3) has weight enumerator 1 + 14z^4 + z^8 (tested). The four state words are a subset, with pairwise distances 4,4,4,4,4 and 8 (96 against 69). We do not claim that the designers chose RM(1,3) on purpose: the words are simply affine functions of three bits.

## Why d bounds the flops-only cost, and why the decoder sets a ceiling

If only the 8 state flops may be flipped, moving the register from a legal word (F0 or CC) to the accept word 96 needs at least d = 4 flips, because every pair of state words differs in at least 4 bits. MEASURED: the flops-only minimum is 4 on V1 and V2, spike and apt-0.33 netlists (`docs/dossier/test_hamming.py`, re-run by P13a, `research/c6/p13/hamming_runs.txt`). With all nets as fault sites the minimum is 1 on V1, 3 on V2 spike, 2 on V2 apt-0.33 (same file; product CLI `research/c6/p13/cli_runs.txt`; z3-free brute force `research/c5/anchor/bf_*.json`). The decoder is the cheaper target: d is the floor only while the reading logic is out of the fault model. A shared reading wire is a ceiling, and the code's distance never gets used.

A narrow consumer is a punctured code. If only some bits are checked, the distance that matters is the distance on those bits: for V2 with consumer mask 0x03, 0x0F, 0x4E the masked distance from {F0, CC} to 96 is 1, 2, 3, and the product CLI measures 1, 2, 3, each time with flop flips only (`research/c6/p13/cli_masks.txt`). On all 255 masks, M1's solver minimum never exceeds the masked distance, and its 27 "colliding" masks are exactly the masks of masked distance 0 (tested against `research/c3/m1/m1_all_masks.csv`).

## Bursts against random flips

A random-error channel rewards distance: 96 and 69 are complements (distance 8), the best possible pair under independent flips. A correlated event behaves differently. One modelled burst that inverts all eight state flops at once maps 69 to 96 exactly (0x69 xor 0xFF = 0x96; ARITHMETIC, tested), and because FAIL holds itself in the RTL, such an event at any later cycle would turn a rejection into an acceptance. So the pair that is strongest against random flips is weakest against one all-flop burst. SIMULATED (P14, `results/comms/burst.csv` rows 2-7): on the three complementary pairs one all-flop burst event reached accept; see "Burst vs random" below. Random, burst and adversarial channels rank the same codes differently.

**Interleaving** is the classic remedy: place copies far apart or in different groups so that one event hits only one copy. V2 interleaves its copies across bit positions (`sel = {m1,m0,m2,m1,m0,m2,m1,m0}`: m0 owns bits {0,3,6}, m1 {1,4,7}, m2 {2,5}). ARITHMETIC (tested): the step CC to 96 changes bits {1,3,4,6}, which lie in only two of the three groups (m0, m1); F0 to 96 touches all three. P01 later measured that it sets the floor that some synthesis flows reach (`docs/report/WHY_TWO_FLIPS.md`); re-encoding the step word restored 3 on 6 of 8 project flows (`research/c6/p01/sweep_rows.csv` rows 2-9 against 10-17).

## Fault-capacity table

d, detect (d-1) and correct (floor((d-1)/2)) are properties of the code, not of the circuit; none of these circuits corrects. "Code gap" = measured min (flops) minus measured min (all nets). All measured rows: T=6, stem counting, known init, inputs not fault sites, goal `boot_word == 0x96`.

| design | code | n | k | d | detect | correct | measured min (flops) | measured min (all nets) | code gap |
|---|---|---|---|---|---|---|---|---|---|
| reference | RM(1,3) | 8 | 4 | 4 | 3 | 1 | n/a | n/a | n/a |
| V0 | 2-bit binary state {0,1,2,3} | 2 | 2 | 1 | 0 | 0 | 1 (SIMULATED, D1, `docs/dossier/EVIDENCE_INDEX.md` row 21; not re-run) | 1 (MEASURED, `research/c2/b2_scope/B2_REPORT.md`) | 0 |
| V1 | state {F0,CC,96,69} in RM(1,3) | 8 | 2 | 4 | 3 | 1 | 4 (MEASURED, spike and apt-0.33, `hamming_runs.txt`) | 1 (MEASURED, `cli_runs.txt`, B2) | 3 |
| V1 | decision bit, repetition, AND-merged into `ok` | 2 | 1 | 2 | 1 | 0 | n/a | 1 (net `ok`) | ceiling |
| V2 spike | state {F0,CC,96,69} | 8 | 2 | 4 | 3 | 1 | 4 (MEASURED) | 3 (MEASURED, CLI, anchor bf T=3/4 k<=3: 182 triples) | 1 |
| V2 apt-0.33 | same | 8 | 2 | 4 | 3 | 1 | 4 (MEASURED) | 2 (MEASURED, `hamming_runs.txt`, anchor bf T=4 k<=2: 3 pairs) | 2 |
| V2 | decision bit, repetition, detection only | 3 | 1 | 3 | 2 | 0 as used | n/a | 3 spike / 2 apt-0.33 | d minus measured: 0 spike, 1 apt-0.33 |
| V2 consumer 0x0F | state punctured to bits 0..3 | 4 | | 2 (masked, F0/CC to 96) | | | 2 (MEASURED, CLI witness is flops only, `cli_masks.txt`) | 2 (same run) | 0 |
| V2m (per-bit 2-of-3 vote) | repetition decoded with t=1 | 3 | 1 | 3 | | 1 | not measured (P11 swept codebooks, not voters; no flops-only run exists) | 2 (MEASURED, M1 s5, apt-0.33) | not computable |
| V2s (one shared voter) | repetition, one decoder net | 3 | 1 | 3 | | 1 | not measured (as V2m) | 1 (MEASURED, M1 s5) | not computable |
| v2_secded (SECDED corrector before the state) | extended Hamming on the state, t=1 | 8 | | 4 | | 1 | 3 (MEASURED, `results/comms/decoder_variants.csv` row 74) | 2 (row 83) | 1 |
| v2c (check-only syndrome consumer) | same code, detection only | 8 | | 4 | | 0 | 4 (row 110) | 2 (row 119) | 2 |
| 19 accept codebooks (P11) | generated FSMs, 3 copies, Yosys 0.33 plain | 8 | | 1 to 8 | | | = distance in 15 of 15 with d <= 6; ">6" for the 4 with d 7 or 8 (MEASURED, `results/comms/distance_sweep.csv` rows 2-20) | 1 to 3, never above 3 and never above flops-only (19 of 19) | 0 to >3 |
| 69_96 complement (P11) | complementary pair | 8 | | 8 | 7 | 3 | >6 (row 4) | 3 (row 4) | >3 |

V2m reading: a decoder that corrects t=1 lowers the all-nets cost from d=3 to d-t=2, which is what M1 measured; one measured row, not a rule. The v2_secded row shows the same d-t effect on the flops-only column (4 to 3); see "Decoders" below.

## Random-flip channel (waterfall)

SIMULATED: random-flip teaching model, not an attacker model and not a physical error rate (`results/comms/waterfall.csv`, `docs/comms/waterfall.png`, `docs/comms/WATERFALL_NOTES.md`, `research/c6/p12/P12_REPORT.md`). Every wire and flop is wrong with probability p in each cycle, independently; T = 4; one fixed wrong key per design.

- **Slope = minimum flips (diversity order).** Fitted low-p slopes: V0 0.98, V1 0.88, V2-stored 3.00, V2-apt 2.14, V2e 2.97, against minimum flips 1, 1, 3, 2, 3 (P12 prediction P1, held).
- **Height = multiplicity.** Minimum-size attacking sets at the plotted key: V0 11, V1 1, V2-stored 80 triples, V2-apt 3 pairs, V2e 734 triples (CSV rows 2, 11, 20, 29, 38, column `A_dmin`). At p = 1e-3 the leading term A x p^d is within 1.02 to 1.17 of the Monte Carlo.
- **Higher adversarial cost does not mean lower random false-accept rate: multiplicity matters.** V2e and V2-stored both need 3 flips, but V2e has 734 attacking triples against 80 for the worst wrong key (any-key counts differ: 1065 against 182, column `A_dmin_anykey`), so V2e false-accepts about 9 times more often at low p (6.3e-7 against 6.9e-8 at p = 1e-3, rows 38 and 20). From p = 1.8e-2 V2e is level with or above V2-apt, which needs only 2 flips.
- **Failed prediction (P2).** The exact series truncated at 3 flips is only a lower bound: it lay inside the Monte Carlo 95% interval at 9 of 31 eligible points (never for V2e). A fair test needs K >= 4 or p below 1e-3; neither was run.
- At p = 0.1 the three V2 netlists (0.6% to 0.9%) are within a factor 1.6 of V1 (1.0%) (rows 19, 28, 37, 46): the redundancy advantage is a low-noise property in this model.

## Burst vs random

SIMULATED: modelled burst events on toy netlists, T = 6, Yosys 0.33 (`results/comms/burst.csv`, `docs/comms/BURST_NOTES.md`, `research/c6/p14/P14_REPORT.md`). One modelled burst event = all state flops (or one comparator group) inverted in one cycle; it is not a real overclock or voltage glitch.

- **Complement pairs** 69/96, C3/3C and A5/5A are robust to random flips (flops only: no attack up to 6 flips, ">6") but one all-flop burst gives 1 event to accept (CSV rows 2, 4, 6). A burst confined to one comparator group needs 3 events.
- **The stored code F0/96 also falls to one burst**, because its fail word 0x69 is the complement of accept 0x96 and the circuit rests there (row 8). Changing only the fail word to 0x3C removed every all-flop burst attack within 6 cycles and kept random flops-only at 4 (row 22).
- P14's seven pre-registered predictions held in 32 of 32 rows; the rules are a few lines of XOR arithmetic, so this is a weak test of anything deeper.

| | burst-fragile (one all-flop burst reaches accept) | burst-robust (no all-flop burst attack within T = 6) |
|---|---|---|
| **random-robust** (flops-only minimum >= 4) | 69_96, C3_3C, A5_5A complements, F0_96_stored, 2B_95, fam_d4, 00_FF_C01_B02, FF_00_CFE_BFD | 00_1F_F8_E7, F0_96_B3C, 2B_95_BEB |
| **random-fragile** | A5_A6, fam_d2, Bvar_one_copy | A5_A6_BBE, F0_96_BDF |

## Decoders

MEASURED: product CLI `--synth-sweep`, stem rule, Yosys 0.33, T = 6, k <= 4 (`results/comms/decoder_variants.csv`, `docs/comms/DECODER_NOTES.md`, `research/c6/p18/P18_REPORT.md`; predictions pre-registered in `research/c6/comms/P18_PREREG.md` before any solver run).

- **A SECDED corrector lowers the flops-only cost from 4 to 3** (v2 row 2 against v2_secded row 74): it corrects one bit, so three stored flips plus the decoder's own correction reach 0x96 (d - t).
- **No all-nets change.** Over the 9 synthesis flows the all-nets minimum of v2_secded and of v2c is 2,1,1,2,2,2,2,2,3, the same as v2, although the plain netlist grew from 85 to 143 gates (rows 11 and 83 for plain).
- **The check-only consumer (v2c) changed nothing**: every v2c minimum equals v2's (rows 110-145); the accept flag `boot_ok` stays one net costing 1 flip in all four designs.
- **This decoder, this code, this FSM: no general rule about ECC.**

## What a communications professor should look at

The table's last two columns: the flops-only column sits on the code distance in every measured row, and the all-nets column sits at or below the number of separate decoding paths (1 for V1's shared `ok`, 3 for V2's copies; 2 where re-synthesis shares logic between V2's copies, a P01 question). The interesting object is the gap, which is a property of the decoder, not of the code. Then the punctured-code rows (consumer masks), the complementary pair under a burst, P11's codebook sweep (`docs/comms/STAIRCASE_NOTES.md`), the random-flip waterfall and the decoder rows below. The project's own claim stops at: textbook distance arguments predict the flops-only numbers we measured, and the decoder explains the rest.

## Limits and what we may not claim

- Nothing established as new; this is textbook coding theory measured on toy designs (prior art: SYNFI, FIRMER, `docs/PRIOR_ART.md`).
- No claim that anyone chose RM(1,3) on purpose.
- Modelled flips in a netlist, bounded (T=6, k as stated), not physics; no glitch, voltage or laser claim; a burst here is an arithmetic event, not a measured overclock.
- No bit-error-rate claims for silicon. The waterfall below is a random-flip teaching model (SIMULATED), not an attacker model and not a physical error rate.
- Flops-only minima are 4 on four netlists; that is "matched in 4 of 4", not "always". P11: "matched code distance in 15 of 15 codebooks with distance <= 6", not "always equals".
- No claim that a correcting decoder helps or hurts in general (P18 measured one decoder on one FSM); no claim that complementary codes are weak in general (P14: one burst model on toy netlists).
- The waterfall slopes and multiplicities say nothing about silicon error rates or real attackers.
