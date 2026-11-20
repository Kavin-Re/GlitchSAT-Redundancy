# Burst errors against random errors: the complementary code's blind spot

License: UNDECIDED. Working title TBD. Every number below is SIMULATED: modelled events on toy netlists, bounded to 6 clock cycles, from `results/comms/burst.csv` (script `scripts/comms/burst_sweep.py`). Textbook coding theory measured on toy designs; nothing established as new.

## In plain words

Engineers who send data over noisy channels separate two kinds of trouble. **Random errors** hit bits one at a time, independently, like raindrops. **Burst errors** hit many bits in one go, like a scratch across a disc. A code that is excellent against one can be poor against the other.

Our boot circuit stores its state as an 8-bit word. Against random flips the best choice looks obvious: make "rejected" and "accepted" exact opposites, such as 0x69 and 0x96. All eight bits differ; in our model six random flips of the state flops were not enough (the search stopped at six).

Now picture one disturbance that inverts **every** state flop in the same clock cycle. The opposite of 0x69 is 0x96, so that single event turns "rejected" into "accepted". We measured this on all three complementary pairs we tried: one modelled burst event each.

The design as stored (idle 0xF0, accept 0x96) also fell to one burst, because its *fail* word is 0x69 and the circuit rests there. With the fail word changed to 0x3C (not the opposite), no all-flop burst within six cycles reached accept, and random flips still needed four.

**Interleaving** is the classic remedy: spread a codeword's bits so that one burst touches only a few. In a circuit that means placing copies apart, so one event reaches one group only. In our model a burst limited to one comparator copy's flops needed three events (one per group) on the complementary pairs. But a fail word that differs from accept only inside one group fell to one group burst.

**For designers:** choose codes by the channel you fear. Distance guards against independent flips. Against a common-mode event, check that no word the circuit can rest in is the bitwise opposite of accept, and that no single group's bits bridge the two. Avoid all-zeros and all-ones accept words: one modelled "everything to 1" event reached accept 0xFF, and "everything to 0" reached 0x00.

A modelled burst is an arithmetic event (a fixed set of bits changed together). It is not a real overclock or voltage glitch; these results say nothing about real hardware.

## The table (SIMULATED; T = 6; plain yosys-0.33 netlists; the no-ABC structural netlists gave the same burst cells)

| | burst-fragile (one all-flop burst reaches accept) | burst-robust (no all-flop burst attack within T) |
|---|---|---|
| **random-robust** | 69_96_complement, C3_3C_complement, A5_5A_complement, F0_96_stored, 2B_95, fam_d4, 00_FF_C01_B02, FF_00_CFE_BFD | 00_1F_F8_E7, F0_96_B3C, 2B_95_BEB |
| **random-fragile** | A5_A6, fam_d2, Bvar_one_copy | A5_A6_BBE, F0_96_BDF |

| codebook (idle, step, accept, fail) | random: flops / all nets | all flops | one group | rail 1->0 | rail 0->1 | quadrant |
|---|---|---|---|---|---|---|
| 69_96_complement (69, -, 96, 69) | >6 / 3 | 1 | 3 | none | none | random-robust / burst-fragile |
| C3_3C_complement (C3, -, 3C, C3) | >6 / 3 | 1 | 3 | none | none | random-robust / burst-fragile |
| A5_5A_complement (A5, -, 5A, A5) | >6 / 3 | 1 | 3 | none | none | random-robust / burst-fragile |
| F0_96_stored (F0, CC, 96, 69) | 4 / 2 | 1 | 3 | none | none | random-robust / burst-fragile |
| 2B_95 (2B, 69, 95, 6A) | 6 / 3 | 1 | 3 | none | none | random-robust / burst-fragile |
| 00_1F_F8_E7 (00, F8, 1F, E7) | 5 / 3 | none | none | none | none | random-robust / burst-robust |
| A5_A6 (A5, 66, A6, 59) | 2 / 2 | 1 | 3 | none | none | random-fragile / burst-fragile |
| fam_d2 (95, 56, 96, 69) | 2 / 2 | 1 | 3 | none | none | random-fragile / burst-fragile |
| fam_d4 (99, 66, 96, 69) | 4 / 2 | 1 | 3 | none | none | random-robust / burst-fragile |
| Bvar_one_copy (69, -, 96, DF) | 3 / 1 | 1 | 1 | none | none | random-fragile / burst-fragile |
| F0_96_B3C (F0, CC, 96, 3C) | 4 / 3 | none | none | none | none | random-robust / burst-robust |
| 2B_95_BEB (2B, 69, 95, EB) | 6 / 3 | none | none | none | none | random-robust / burst-robust |
| A5_A6_BBE (A5, 66, A6, BE) | 2 / 2 | none | none | none | none | random-fragile / burst-robust |
| F0_96_BDF (F0, CC, 96, DF) | 3 / 1 | none | 1 | none | none | random-fragile / burst-robust |
| 00_FF_C01_B02 (00, 01, FF, 02) | >6 / 3 | 1 | 3 | none | 1 | random-robust / burst-fragile |
| FF_00_CFE_BFD (FF, FE, 00, FD) | >6 / 1 | 1 | 3 | 1 | none | random-robust / burst-fragile |

Columns: random = minimum single-flip events (flops only / all nets; P11's CSV, or the same generator and product CLI for new rows). Burst cells = minimum events of that kind; "none" = no attack with any subset of that kind's events within 6 cycles (bounded; not a guarantee). Random-robust means flops-only random minimum of 4 or more; burst-robust means one all-flop burst does not reach accept (both thresholds fixed in `research/c6/p14/PREREG.md` before the run).

## Event definitions and checks

- `all flops`: every state flop Q inverted in one cycle. `one group`: the flops owned by one comparator copy (masks 0x49, 0x92, 0x24) inverted. `rail 1->0` / `rail 0->1`: every gate output forced to 0 / 1 in one cycle and every flop captures 0 / 1 (the event definitions of `research/c4/b3/b3pack.py` and `research/c5/ledger/data/b3pol.py`, applied to the whole design).
- The z3 event engine agreed with a z3-free brute force (all 256 input values; every event subset up to size 3; an exhaustive state search over all subsets) on every row, with and without term simplification (`--reduce none`), and its single-flip controls reproduced the product CLI's random-flip numbers on 31 of 32 rows (columns `bf_agree`, `reduce_none_agree`, `control_agree`). The exception is 2B_95_BEB on the structural netlist: the any-net control timed out ("unknown", 120 s), so that row is flagged `ENGINE_CHECK_FAILED: control mismatch` in the CSV; its burst cells still passed the brute-force and reduce checks. A separate re-run of that control with a longer limit returned 3, equal to the CLI (`research/c6/p14/recheck_control.log`); the CSV row was left as produced.
- Predictions against measurements: `research/c6/p14/P14_REPORT.md`.

## Limits

Toy design, 16 codebooks, one synthesis tool version, 6 cycles. The attacker input is held constant. Burst reach (all flops, one group, whole design) is an assumption of the model, not derived from any layout or measurement. "none" and ">6" are bounded search results. Not a security claim about any real chip.
