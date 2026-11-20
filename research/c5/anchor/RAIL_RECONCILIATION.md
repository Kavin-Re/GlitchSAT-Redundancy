# Why B3 and L2/LAYOUT agree on rail dips

## The apparent conflict
- B3 (`research/c4/b3/B3_REPORT.md`): V2/V5 under `rail_all`, `rail_half`, `rail_unions`, `rail_cone`: ">3", no attack found with up to 3 events at T=6.
- L2/LAYOUT (`research/c4/l2/L2_REPORT.md`, `research/c4/layout/LAYOUT_REPORT.md`): a die-wide `rail_all` event costs 1 event in all 5 placements.

## Same word, two event definitions (this is the whole answer)
| | what ONE event does | V2 cost (word goal) | where it is measured |
|---|---|---|---|
| all-or-nothing (AoN) | every gate/flop-D in the domain falls to 0 together (rail-wide, row, rail pair, strap, disc) | `rail_all` > 3 (B3, LAYOUT, all 5 L2 placements); discs: 2 to 3 events at r <= 5 um, none for 1 event | B3 matrix; LAYOUT sec. 4; L2 sweep |
| selectable (SUB; B3 `dip_subset`) | the one event may choose WHICH cells in the domain fall | 1 event; smallest chosen set = 3 cells, one per compare copy | B3 `minsubset.py`; LAYOUT minsets; L2 `fam_*.jsonl` (`rail_all` SUB 1/1 everywhere) |
| geometric radius | cells within r of a point fall (AoN) or the event picks among them (SUB) | AoN needs 2 events at r about 2 to 5 um (one disc covers two copies); SUB 1 event from r about 3 um (base) or 10 to >15 um (spread) | LAYOUT/L2 sweep |

So "rail_all survives" (B3) and "rail_all costs 1" (L2) are both right: B3's `rail_all` is AoN, L2's table line is the SUB column of the same family. The word "rail_all" names the DOMAIN (whole die), not the event. Why AoN fails: the dip forces every gate to 0, including the vote/output logic and flop D pins the attacker needs high, so the word cannot come out as 0x96. Why SUB works: choosing exactly one compare net in each of the 3 copies at one cycle needs no collateral.

## Independent anchor (this folder, z3-free)
- AoN: brute force over all `rail_all`/`rail_half`/`rail_unions`/`rail_cone` events at T=4, k<=2 on V2 (spike and apt 0.33): no attacking event set, equal to z3 (ANCHOR_REPORT sec. 1b).
- SUB: enumerating EVERY set of up to 3 sites forced to 0 by ONE event (292,904 events, T=4, V2 spike): 0 sets of size 1 or 2 work, 22 sets of size 3 work (`bf_dipsubset_v2spike_T4_M3.json`). B3 reported minimum 3 gates; agreed.

## What is physically supported
SPICE basis (`research/c2/el1_spice`, SIMULATED, one small rail): all high gates on a dipping rail droop together, i.e. the AoN reading. Whether a real dip can be selective at the 3-cell level, or what separates a nand2 from a neighbour, is not in any data here (no extraction, no IR-drop). Selectivity is the open assumption; spreading the copies (L2) raises the reach a selective dip needs from about 3 um to 10 to more than 15 um but does not change a die-wide selective event (cost 1).

## Single honest statement for the front door (<= 60 words)
"Under the modelled rail dip, V2 needs more than 3 events if a dip hits every gate in its domain together, but 1 event if the dip can choose which cells fall (three cells, one per copy). The SPICE basis supports only the first reading; selectivity is unproven. Bounded: 6 cycles, 3 events, toy design, no extraction."
