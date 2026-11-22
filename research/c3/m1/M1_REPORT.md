# M1 report: decoder width / consumer mask
Step M1, 2026-11-19. Everything here is MEASURED with the commands below unless marked INFERRED. Faults are modelled single-cycle bit flips of gate outputs and flop Q (glitchsat model), T=6 cycles, k<=3, input nets not fault sites, known init state, goal `sig != 0xC3`. Toy designs. Nothing about physical glitches, nothing proved beyond the bound T=6, k<=3. Work copy: `/tmp/work_m1/`; scripts and raw data are copied here. Nothing in the tree was edited.

## 1. Mask patch and its validation
- `gs_mask.py` = copy of `scripts/glitchsat.py` with one change (`diff` is 2 lines): new argument `goal_mask` (default 0xFF); the goal at a cycle is "bits of `boot_word` inside the mask equal 0x96 on those bits". Reconstructed from DA2's patch (`/tmp/work_da2/t1/gs_mask.py` still existed; identical semantics).
- Independent check: `bf.py` (no z3, does not import glitchsat; own JSON parser, own simulator, all 256 `sig` values in parallel, ALL flip sets of size <=2 over ALL (cycle, gate-or-flop) sites, no cone pruning). Run `python3 bf.py v2 4 2 bf_v2_T4_k2.json` (2m44s), then `python3 val.py` runs the z3 solver at T=4 for all 255 masks k<=2. Result: **255 of 255 masks agree** (min flips 0/1/2 or ">2"); distribution 27 at 0, 88 at 1, 96 at 2, 44 ">2". Limits: validation is at T=4, k<=2, V2 spike only (T=6 and k=3 not brute-forced: too many sets for plain Python).
- Mask 0 is excluded. Some masks "collide": F0 or CC (legit states, seen in cycles 0/1) already equal 0x96 on the masked bits, so a consumer on those bits accepts with 0 flips. 27 of 255 masks collide; they are reported as 0 and left out of the statistics below (228 left).

## 2. Matrix: all 255 masks, no sampling
Symmetry classes were NOT needed: every cell was solved exactly. Run time per mask is a few seconds, so I ran every mask for every design, 90 s per-solver-call timeout, **0 unknowns in 1785 cells** (`m_*.jsonl`, status column). Also tested whether "copies touched / composition" alone defines a class: it does not (see 3), so a symmetry reduction by composition would have been wrong; this is a finding of its own.
Command: `python3 mat.py <netlist.json> <top> 6 out.jsonl 90000` per design; table `m1_all_masks.csv` (`python3 ana.py`).
Designs: spike V1, V2 (`reference/spike_netlists`), V0 (spike), apt-0.33 re-synthesis of `rtl/v2.v` and `rtl/v1.v` (`scripts/synth.sh ... plain`), and my variants V2m, V2s (synthesised the same way, rtl in `rtl/`).

Min flips, count of non-colliding masks per popcount (228 masks; e.g. "1:34 2:14" = 34 masks need 1, 14 need 2):

| popcount | V1 spike | V2 spike | V2 apt-0.33 | V2m per-bit vote | V2s shared vote |
|---|---|---|---|---|---|
| 1 | 1:2 | 1:2 | 1:2 | 1:2 | 1:2 |
| 2 | 1:17 | 1:16 2:1 | 1:16 2:1 | 1:16 2:1 | 1:14 |
| 3 | 1:48 | 1:34 2:14 | 1:38 2:10 | 1:35 2:13 | 1:26 |
| 4 | 1:68 | 1:28 2:36 3:4 | 1:38 2:30 | 1:29 2:39 | 1:20 |
| 5 | 1:56 | 1:8 2:34 3:14 | 1:16 2:40 | 1:8 2:48 | 1:7 |
| 6 | 1:28 | 2:11 3:17 | 1:2 2:26 | 2:28 | 1:1 |
| 7 | 1:8 | 3:8 | 2:8 | 2:8 | none |
| 8 (full word) | 1:1 | 3:1 | 2:1 | 2:1 | none |

(Rows 7/8 for V2s are empty because those masks all collide.) V0 and V1 are 1 flip for every non-colliding mask (V0 spike, V1 spike, V1 apt-0.33); V0 is in the CSV. Figure: `m1_flips_vs_mask.png` (mean and best-protected mask per width, 5 designs).
Headline readings (spike V2): only 44 of 228 masks give 3 (all of them need all three comparator copies' bits); 88 of 228 give 1, the same as V1. A consumer that checks 4 or fewer bits gets 3 flips in 4 of 68 non-colliding cases.

## 3. Rule that explains V2 exactly (255 of 255 masks)
Groups of result bits by comparator copy, from `sel={m1,m0,m2,m1,m0,m2,m1,m0}`: copy m0 owns bits {0,3,6}, m1 {1,4,7}, m2 {2,5}. An attacker flips the comparator output of a copy (1 flip, moves all of that copy's result bits at once) and/or individual result bits (1 flip each), or reads the idle/compare state (F0, CC) with bit flips:
`min flips = min( min over s in {F0,CC} of popcount((s xor 0x96) & mask),  min over subsets S of copies of |S| + popcount(~bits(S) & mask) )`.
`pred.py` implements it; it matches the solver on **all 255 V2-spike masks (0 mismatches)**. In words: a decoder that needs bits from one copy only is beaten by flipping that copy's shared result (1 flip); needing bits from two copies costs at most 2; the 3 flips appear only when the consumer needs bits owned by all three copies AND the direct-bit/state route is not cheaper (4 or more bits that differ from the idle states). Composition counts (bits per copy) alone do not decide it: 34 of 47 compositions have mixed outcomes, because the bit values (which bits of 0x96 are 1) matter via the state route. The rule does NOT hold for the re-synthesised netlist (68 mismatches): ABC creates shared nodes there, so apt-0.33 V2 gives 2 for the full word, as B2 found, and also 1 for 2 six-bit masks.
Witness (solver, full word): V2 spike = the same internal node of each of the three comparator copies flipped at cycle 1 (3 flips).

## 4. What this means for the claim
- "V2 needs 3 flips" is a statement about a consumer that decodes all 8 bits (or at least bits from all three copies, 4+ bits). The honest figure of merit is "flips needed against what the consumer actually checks", reported as a pair (design, mask). For V1 it is 1 for every mask; for V2 it is 1 to 3, with 1 for 39% (88/228) of consumers on the spike netlist and 3 only for 19% (44/228).
- Consistent with CT-1 (boot_ok = 1 flip) and B2: all three are the same effect seen from different sides (decoder width).
- Suggested table for the front page: full-word consumer 3 (spike) / 2 (apt-0.33); 4-bit consumer 1 to 3, typically 1 to 2; single-net `boot_ok` 1.

## 5. Design fix tested: V2m (and a negative control V2s)
- Idea: no single comparator copy decides any bit; each result bit takes a 2-of-3 majority of the three copies, with its own voter gate group (`keep_hierarchy`). RTL `rtl/v2m.v`. Negative control `rtl/v2s.v`: one voter shared by all eight bits.
- Result (apt-0.33 plain synthesis, all 255 masks, MEASURED): V2m full word = **2** (witness: two of the three comparator copies' internal nodes flipped at cycle 1), and every mask of 6 or more bits is exactly 2; masks of 1 to 5 bits look like V2 (mostly 1 or 2). V2s = 1 for every non-colliding mask (the shared voter output is a single point).
- So voting did NOT raise the best case: it lowered the full-word figure from 3 (spike V2) to 2, because the attacker now needs only 2 of 3 copies, but it removed the dependence on which bits are checked (width 6 or more is always 2, V2 apt-0.33 can drop to 1). Compared with V2 apt-0.33 (full word 2), V2m is equal in full word and slightly better in 6-bit masks (2 for all 28 vs 26 of 28). Votes only help in combination with a hardened voter or a consumer that does not trust one net.
- Fix direction (INFERRED, not built): (a) the consumer must decode all result bits (width 8; it then gets the full-word number, 2 to 3); (b) majority across 3 copies resists 1 flip in the comparator layer only; the voter outputs and the state register stay single-flip sites for narrow masks, so narrow consumers stay at 1 whatever the voting; (c) the bit-level floor is the Hamming distance from idle state to accept word on the checked bits, so make that distance large (an accept code far from F0/CC on all bits that are checked).

## 6. Not done / caveats
- Brute-force validation only T=4, k<=2, V2 spike; solver matrix at T=6, k<=3 (">3" never occurred; max value 3).
- Equivalence-class reduction was dropped (full enumeration was cheap); the "class" claim in the task (copy composition) is refuted as a sufficient invariant.
- apt-0.33 re-synthesis only for V1, V2 (not V0); conda 0.38 not run. V2m/V2s synthesised once (apt 0.33 plain).
- Collision masks (27) are fault-free acceptances at cycle 0/1 and say the consumer cannot tell idle from boot; reported as 0.
- Input nets not fault sites, power-up state known, sig constant over the run (as in the project baseline); B2 shows that under other scopes V2 is already 1.
- Faults are modelled bit flips in a toy netlist; this is not a statement about hardware.

## Files (this folder)
`M1_REPORT.md`, `m1_all_masks.csv`, `m1_flips_vs_mask.png`, `m_*.jsonl` (raw cells), `gs_mask.py`, `bf.py`, `val.py`, `mat.py`, `pred.py`, `ana.py`, `fig.py`, `wit.py`, `bf_v2_T4_k2.json`, `val_solver_T4.json`, `all.json`, `rtl/v2m.v`, `rtl/v2s.v`.
