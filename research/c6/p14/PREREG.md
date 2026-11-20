# P14 pre-registration: burst events against random flips

License: UNDECIDED. Working title TBD. Written 2026-11-20T05:10:46Z (UTC), BEFORE any P14 run: no burst engine exists yet and no solver or simulator has been run by me on any codebook. Nothing here is a result. A burst is a MODELLED event on a toy netlist (one event = a fixed set of nets changed together in one cycle); it is not a real overclock or voltage glitch and nothing physical is claimed. Textbook coding theory on toy designs; nothing established as new.

## What I had already read (so these are not blind predictions)
- `results/comms/distance_sweep.csv` (P11: random single-flip minima for 19 codebooks) and `research/c6/p11/PREREG.md`.
- `docs/comms/CODING_VIEW.md` (arithmetic 0x69 xor 0xFF = 0x96; "FAIL holds itself").
- `research/c4/b3/b3pack.py`, `research/c5/ledger/data/b3pol.py` (rail event semantics I will reuse), `scripts/glitchsat.py`.
- Reading the generator I noticed that most P11 codebooks, including the stored F0/96 one, use fail word B = ~W. This changed my prediction from the lead's brief (see P2).

## Setup (fixed now)
- Generator: `scripts/comms/distance_sweep.py` (imported read-only): idle I, optional step C, accept W, fail B, grouping 10210210 (copy m0 owns bits {0,3,6} = mask 0x49, m1 {1,4,7} = 0x92, m2 {2,5} = 0x24). Netlists: `synth.sh plain` (yosys 0.33) and the P11 no-ABC structural flow.
- Goal boot_word == W at some cycle < T, T = 6, attacker input sig constant and != 0xC3, known init. Wrong-key runs visit S = {I, C, B}.
- One burst event (cost 1) at one cycle t, at most one event of each kind per cycle:
  - `flops_all`: every state flop Q inverted in cycle t (same single-cycle Q-flip semantics as glitchsat, applied to all 8 flops at once).
  - `flops_group`: the state flops owned by ONE comparator copy inverted (3 possible events per cycle: masks 0x49, 0x92, 0x24).
  - `rail_1to0`: every gate output forced to 0 in cycle t and every flop captures 0 at the end of cycle t (b3pack gates0 + d0, whole design; flop Q itself not touched in cycle t).
  - `rail_0to1`: every gate output forced to 1 and every flop captures 1 (b3pol gates1 + d1).
- Cost = number of events. "none" = no attack with ANY subset of the available events within T = 6 (finite: 6, 18, 6, 6 events), bounded by T, not "safe".
- Random column: minimum single-flip events, flops only and all nets, from P11's CSV; for codebooks not in P11, measured with the same generator functions and product CLI (k_max = min(d(I,W), 6)).
- Engine checks: z3 event engine against a z3-free bit-parallel brute force (all 256 sig values, every event subset up to size 3, and an exhaustive state search); z3 run with and without per-net simplification (`--reduce none`); control: single-flop-flip events in my engine must reproduce P11's min_flops and any-net flips P11's min_all.
- 2x2 thresholds (fixed now): random-robust = flops-only random minimum >= 4 (the stored design's level; all-nets shown beside it). Burst-robust (headline) = no attack with one `flops_all` event. The other burst kinds are reported as extra columns.
- Codebooks (16; name: I, C, W, B). From P11: 69_96_complement (69,-,96,69); C3_3C_complement (C3,-,3C,C3); A5_5A_complement (A5,-,5A,A5); F0_96_stored (F0,CC,96,69); 2B_95 (2B,69,95,6A); 00_1F_F8_E7 (00,F8,1F,E7); A5_A6 (A5,66,A6,59); fam_d2 (95,56,96,69); fam_d4 (99,66,96,69); Bvar_one_copy (69,-,96,DF). New (fail word not the complement of W): F0_96_B3C (F0,CC,96,3C); 2B_95_BEB (2B,69,95,EB); A5_A6_BBE (A5,66,A6,BE); F0_96_BDF (F0,CC,96,DF); 00_FF_C01_B02 (00,01,FF,02); FF_00_CFE_BFD (FF,FE,00,FD).

## Predictions
- P1 (complement pairs 69/96, C3/3C, A5/5A): random flops-only > 6 (P11, already measured); `flops_all` cost 1.
- P2 (rule for `flops_all`): cost is 1 if the complement of W is in S = {I, C, B}, otherwise none. This is sharper than "the all-flop burst cannot reach non-complementary accept words": because B = ~W, I predict cost 1 also for F0_96_stored, 2B_95, A5_A6, fam_d2, fam_d4 (burst after the fail word is latched), and for 00_FF and FF_00 (idle is the complement). Predicted none: 00_1F_F8_E7, F0_96_B3C, 2B_95_BEB, A5_A6_BBE, F0_96_BDF.
- P3 (rule for `flops_group`): cost = smallest number of copy groups whose union mask equals X xor W for some X in S; none if no such union exists. So: 3 wherever P2 says 1, except Bvar_one_copy = 1 (B xor W = 0x49); F0_96_BDF = 1; none for 00_1F_F8_E7, F0_96_B3C, 2B_95_BEB, A5_A6_BBE.
- P4 (rails): `rail_0to1` cost 1 only for W = FF (00_FF_C01_B02), `rail_1to0` cost 1 only for W = 00 (FF_00_CFE_BFD); none on every other codebook.
- P5 (random, new codebooks): flops-only = d_min: F0_96_B3C 4, 2B_95_BEB 6, A5_A6_BBE 2, F0_96_BDF 3, 00_FF and FF_00 > 6 (d_min 7). All-nets <= 3.
- P6 (2x2): random-robust and burst-fragile: the three complement pairs, F0_96_stored, 2B_95, fam_d4, 00_FF, FF_00. Random-robust and burst-robust: 00_1F_F8_E7, F0_96_B3C, 2B_95_BEB. Random-fragile and burst-fragile: A5_A6, fam_d2, Bvar_one_copy. Random-fragile and burst-robust: A5_A6_BBE, F0_96_BDF.
- P7: plain and structural netlists give the same burst costs (the events touch flops or everything, so synthesis sharing should not matter).

## Falsifiers
- Any complement pair with `flops_all` cost != 1 falsifies P1. Any codebook whose `flops_all` cell differs from the P2 list falsifies P2 (a cost of 2 or more would be a surprise worth explaining). Any `flops_group` cell different from P3, any rail cell different from P4, any random cell different from P5, any codebook in a different 2x2 quadrant than P6, any plain/struct disagreement (P7).
- Any disagreement between z3 and brute force, or between reduce modes, or a control mismatch with P11, is an engine failure: results are then not reported as measured.

Failed predictions will be reported at full prominence in P14_REPORT.md.
