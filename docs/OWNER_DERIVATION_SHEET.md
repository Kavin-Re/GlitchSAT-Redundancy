# Owner derivation sheet: five pencil derivations


Setting for all five: toy designs `rtl/v1.v` and `rtl/v2.v`, key `0xC3`, state register `st` starting at idle `0xF0`, then `0xCC` (compare), then the accept word `0x96` (or the fail word `0x69`). A "flip" is one modelled single-cycle bit flip of one net (gate output or flop Q). Attacker input `sig` is constant and is not the key. 6 cycles. MEASURED means a command below produced it.

## 1. Why one shared wire beats several guards (V1)
- Question: V1 compares `sig` with the key twice (`m1`, `m2`) and accepts only if `ok = m1 & m2`. Why is one flip enough, and what would you have to change so that one flip is not enough?
- Data: `rtl/v1.v` (the line `wire ok = m1 & m2;` and the `case (st)` block).
- Hand steps: (a) with a wrong `sig`, `m1 = m2 = 0`, so `ok = 0` and `st` goes `F0 -> CC -> 69`. (b) Flip the single net `ok` to 1 for one cycle, at the cycle where `st = CC`. (c) The next `st` is `96`, with no other fault. (d) The two compares are upstream of `ok` and never get a vote.
- Expected answer: 1 flip, on net `ok` at cycle 1. Duplicating the check does not help while both copies feed one net that alone drives all 8 result bits. The fix direction is to give each copy its own disjoint output bits (that is V2).
- Check against: `python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6` (MEASURED: ATTACK_FOUND, single point of failure `ok`, drives 8 of 8 bits). Run on a copy of the tree.
- My derivation: ______

## 2. Flips to reach 0x96 from idle, counted by hand (V2, full word)
- Question: what is the cheapest way to make the 8-bit word equal `0x96`? Count the direct route and the comparator route, and take the smaller.
- Data: `rtl/v2.v`: `sel = {m1,m0,m2,m1,m0,m2,m1,m0}` (bit 7 down to bit 0), `word = (sel & 0x96) | (~sel & 0x69)`.
- Hand steps:
  1. Direct route, flip state flops. Idle `0xF0 = 1111 0000` against `0x96 = 1001 0110`: XOR is `0110 0110`, 4 bits differ, so 4 flips. From `0xCC = 1100 1100`: XOR `0101 1010`, again 4 flips.
  2. Comparator route. With a wrong `sig` all `m` are 0, so `word = 0x69`, which is the bitwise complement of `0x96`: all 8 bits are wrong. Copy `m0` owns bits {0,3,6}, `m1` owns {1,4,7}, `m2` owns {2,5}. One flip of a copy's compare output fixes all of that copy's bits at once, so you need one flip per copy: 3 flips.
  3. Take the smaller: 3.
- Expected answer: 3 flips on the stored netlist (the three comparator copies, all at cycle 1). Caveat: this is the full-word goal only; it is not what a consumer reading `boot_ok` sees (question below, and `README.md`).
- Check against: `python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6` (MEASURED: minimum attack cost 3, one internal node in each of three comparator copies, all at cycle 1), and the same with `--k 2` gives NO_ATTACK_UP_TO_BOUND.
- My derivation: ______

## 3. What the mask rule says for a 4-bit consumer on V2
- Question: a consumer checks only bits in a mask. How many flips? Work masks `0x0F` and `0x4E`.
- Data: the owners above ({0,3,6}=m0, {1,4,7}=m1, {2,5}=m2); idle words `F0` and `CC`; `research/c3/m1/M1_REPORT.md` section 3 for the rule: `min flips = min( popcount((s xor 0x96) & mask) for s in {F0, CC},  min over sets S of copies of |S| + popcount(bits not owned by S, within the mask) )`.
- Hand steps for mask `0x0F` (bits 0,1,2,3; owners m0, m1, m2, m0): direct from F0: `0x66 & 0x0F = 0x6`, 2 bits; from CC: `0x5A & 0x0F = 0xA`, 2 bits. Copies: all three gives 3; any two leaves one bit uncovered, so 2+1 = 3; one copy gives 1+2 = 3; none gives 4. Minimum 2.
- Hand steps for mask `0x4E` (bits 1,2,3,6; owners m1, m2, m0, m0): direct F0: `0x66 & 0x4E = 0x46`, 3 bits; CC: `0x5A & 0x4E = 0x4A`, 3 bits. Copies: three gives 3; two leave one bit, 3; one copy gives 1+2 = 3; none gives 4. Minimum 3.
- Expected answers: `0x0F` -> 2, `0x4E` -> 3, and for comparison `0x03` (bits 0 and 1) -> 1 and the full mask `0xFF` -> 3. A 4-bit consumer is typically 1 or 2; only 4 of the 68 four-bit non-colliding masks need 3. V1 is 1 for every mask.
- Check against: `grep -E "^0x(03|0F|4E|FF)," research/c3/m1/m1_all_masks.csv` (column `v2_spike_min_flips` is the 11th: 1, 2, 3, 3; MEASURED by agent M1, solver, all 255 masks, T=6, k<=3; the hand rule matches the solver on all 255 spike masks, and does NOT match the apt-0.33 re-synthesis on 68 masks). Also `python3 -c "import sys; sys.path.insert(0,'research/c3/m1'); from pred import pred; print(pred(0x0F), pred(0x4E))"`.
- My derivation: ______

## 4. Why merging identical compare cones drops V2 to 1 flip
- Question: the three compare copies compute the same function `sig == 0xC3` of the same input. What can synthesis do to them, and what does that do to the attack?
- Data: `scripts/synth.sh` (note its header: no `opt_merge` after flatten, so the copies stay separate); `research/c2/e2_variance/raw/matrix.csv` (columns `merge`, `distinct_match_nets`, `min_flips`).
- Hand steps: (a) identical gate structure on identical inputs is the same logic; a pass that merges identical cells (`opt_merge`) keeps one and rewires the readers. (b) After merging, `m0 = m1 = m2` is one net. (c) Then `sel` has all eight bits driven by that one net, exactly the V1 situation: one flip of it for one cycle (at cycle 1) moves the whole result word. (d) So the minimum goes from 2 or 3 down to 1.
- Expected answer: 1 flip. The design RTL is unchanged; only the synthesized netlist differs, which is why a verdict belongs to one netlist hash.
- Check against: in `research/c2/e2_variance/raw/matrix.csv`, V2 rows with `merge = opt_merge` and `flow = plain`, `order = abc_then_flatten`, `abc = default` give `min_flips` 1 and `distinct_match_nets` 1, against 2 or 3 and 3 with `nomerge` (apt 0.33: 2; conda 0.38: 3). To rebuild it yourself in a scratch folder (not the tree): copy `rtl/v2.v`, run `yosys -q -p "read_verilog v2.v; hierarchy -top v2; proc; opt_clean; techmap; opt_clean; abc -g AND,OR,XOR,MUX; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; opt_merge; opt_clean; techmap; opt_clean; write_json v2_merged.json"`, then `python3 scripts/glitchsat.py check v2_merged.json --top v2 --k 1 --cycles 6` (MEASURED by agent FD with apt Yosys 0.33: ATTACK_FOUND at k=1, one AND gate driving 8 of 8 bits). 
- My derivation: ______

## 5. Stem versus fanout counting on a three-gate example
- Question: net `n` is the output of gate `g0` and is read by three gates `g1, g2, g3`. How many faults is "flip `n` for one cycle" under (a) the stem rule, (b) the per-fanout rule? Why can this change a design's minimum?
- Data: draw `g0 -> n -> {g1, g2, g3}`; then the stored rows in `research/c3/rep/rep_results.csv`.
- Hand steps: (a) Stem rule: the disturbance sits at the driver `g0`; every reader sees it; it is 1 fault. (b) Per-fanout rule: charge one fault per reader pin (here 3); equivalent to flipping each branch separately. (c) An attacker who benefits from a stem with fanout 3 pays 1 under (a) and 3 under (b), so a design needing 2 stem-flips can look like it needs 3 or more under (b).
- Expected answer: 1 versus 3. In the data: the apt-0.33 plain V2 netlist (`v2_plain_033_s0`, 85 gates) has minimum 2 under stem = 1 (`rep_unit_cli`) and 3 under fanout counting (`rep_fanout_pins`); its V1 companion goes 1 to 2. Over 32 V2 netlists the stem minimum is 2 on 26 and 3 on 6; under fanout counting it is 3 on all 32.
- Rule of thumb for defending it: stem = 1 is the project headline rule (R22 recommendation, matching one driver-node upset and FIRMER's per-gate counting); fanout counting is a stress test that no source found supports as physical; neither has been shown physical; the replication (REP, 64 of 64 rows) reused one recipe list, so it is one recipe, not independent designs.
- Check against: `grep -E "^v2_plain_033_s0,|^v1_plain_033_s0," research/c3/rep/rep_results.csv` and `research/c3/r22/R22_REPORT.md` sections 3 and 4.
- My derivation: ______

## 6. From the armed word to the accept word in two flips (V2, encoding root cause)
- Question: derive, by hand, the flip count to reach 0x96 from 0xCC at the load and show which copies the flipped bits belong to.
- Data: `rtl/v2.v` (bit groups: m0 bits 0,3,6; m1 bits 1,4,7; m2 bits 2,5); `docs/report/WHY_TWO_FLIPS.md`.
- Hand steps: (leave for the owner)
- Expected answer: (leave for the owner; the agent's check values are in `research/c6/p01/P01_REPORT.md`)
- Check against: `research/c6/p01/sweeps/sweep_apt_v2.json`, `research/c6/p01/sweeps/sweep_apt_v2e.json`.
- My derivation: ______

## After you finish
If you can do any one of these without this page, you are ready for the corresponding review questions.
