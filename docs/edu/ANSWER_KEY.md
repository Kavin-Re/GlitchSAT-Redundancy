# Answer key (instructor only)

*Every number below was produced by the command shown, re-run in a copy of the project (`/tmp/work_edu2/p`, Yosys 0.33, z3-solver 5.4.1, shipped faultbound-wt 0.0.1.dev0 installed with `pip install ./product[test]`) on 2026-11-19 (step EDU2); raw output in `research/c4/edu2/verification.log` (earlier run: `research/c4/edu/verification.log`). All commands use the shipped CLI except Exercise 4 rule B (research wrapper `edu_scope.py`). Label for all numbers: MEASURED, modelled single-cycle bit flips, 6 cycles, bounded, not a proof of security. Nothing physical.*

Shorthand as in the worksheet (`REF`, `CFG`, `D`, `T`). Net names and cycle numbers in a minimum attack can differ between runs and solver versions when several minimum attacks exist; **grade the number, not the net name**, except where a name is stated (`ok`, `boot_ok`).

## Exercise 1 (15 points)
Predictions (3): V0 = 1, V1 = 1, V2 = 3 (a common wrong prediction is 2 for V2, or 3 for V1).

| Design | k=1 | k=2 | k=3 | minimum | named in attack |
|---|---|---|---|---|---|
| V0 (18 gates) | ATTACK_FOUND (exit 1) | ATTACK_FOUND | ATTACK_FOUND | **1** | a state flop (e.g. `st[0]@5`; the net name varies with k) |
| V1 (58 gates) | ATTACK_FOUND | ATTACK_FOUND | ATTACK_FOUND | **1** | `ok@1` |
| V2 (68 gates) | NO_ATTACK_UP_TO_BOUND (exit 0) | NO_ATTACK_UP_TO_BOUND (exit 0) | ATTACK_FOUND (exit 1, about 8 s) | **3** | one internal node of each of the three comparator copies, or `word[0]` plus two comparator nodes, all at cycle 1 |

a. `ok` (the AND of the two comparator outputs); its fan-in structure shows it decides all 8 of 8 result bits (tool text: "reaches 8 of 8 bits of `boot_word`"). 4 points for `ok` plus the idea that both copies converge on it.
b. In V2 each comparator copy decides only its own bits (copy m0: bits {0,3,6}, m1: {1,4,7}, m2: {2,5}); no single net decides all 8, so the attacker must corrupt all three copies (or equivalent bits). Accept: "no shared recombination net".
c. Model answer: "goal: output `boot_word` == 0x96 (all bits) at some cycle 0..5 while `sig` != 0xC3; inputs: `sig` free but constant, not a fault site; init: all flops at known `init` values (no reset sequence); fault model: one flip of one net (gate output or flop Q) at one cycle counts as 1, fanout counts 1; bounds: max_flips=2, cycles=6; netlist sha256 289355dc...: no attack found."

## Exercise 2 (15 points)
Predictions (3): 2, 1, 3, 3 (partial credit per entry).

Command (shipped CLI, re-run in the EDU2 copy; the answer is the number of `net@cycle` entries on the `minimum attack:` line):
`faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --consumer-bits MASK`

| Design | mask | min flips | witness (names vary; grade the number) |
|---|---|---|---|
| V2 | 0xFF | **3** | `c0/c1/c2 ..new_n11_@1` (one node in each comparator copy), about 8 s |
| V2 | 0x0F | **2** | `boot_word[2]@0` plus a mux gate at cycle 3 |
| V2 | 0x1B | **1** | `boot_word[1]@0` (a state flop; only a `minimum attack:` line, no `MINIMUM ATTACK COST` line because the cost is 1) |
| V2 | 0x4E | **3** | `boot_word[6]@0`, `boot_word[1]@1`, `boot_word[2]@2` (about 4 s) |
| V1 | 0x0F | **1** | `ok@1` |

Hashes printed: V2 `289355dc...`, V1 `84730fa7...`. `--consumer-bits 0xFF` = 3 equals the Exercise 1 answer. These agree with `research/c3/m1/m1_all_masks.csv` (V2 spike column: 0x0F 2, 0x1B 1, 0x4E 3, 0xFF 3; V1 0x0F 1) and with the earlier research-wrapper numbers. Verification: `research/c4/edu2/verification.log`.
CORRECTION (EDU2): the previous key quoted witnesses from the research wrapper (ids 30,77,84 / 13,14 / 13 with fanout 4 / 13,14,18). The shipped CLI names different nets (above). No minimum cost changed.
a. About V2 **plus** the consumer. A consumer reading all 8 bits gets 3; one reading mask 0x1B gets 1; the accept flag gets 1 (Exercise 6). 4 points for "both".
b. With `sel = {m1,m0,m2,m1,m0,m2,m1,m0}` (bit 7 down to 0): bit0=m0, bit1=m1, bit2=m2, bit3=m0, bit4=m1, bit5=m2, bit6=m0, bit7=m1. Mask 0x1B = bits {0,1,3,4}: owned by m0, m1, m0, m1: two copies are touched (but note the measured 1-flip witness is a state flop, i.e. a direct route through the idle-state bits, M1 section 3, not a comparator-copy attack). Mask 0x4E = bits {1,2,3,6}: m1, m2, m0, m0: all three copies, and the measured cost is 3. Accept "0x1B touches only two copies, 0x4E touches all three" for full marks; the state-flop point is a bonus (`research/c3/m1/M1_REPORT.md`).
c. e.g. "On the stored netlist (sha 289355dc), no attack with at most 2 single-cycle flips of gate outputs or flop Q within 6 cycles, for a consumer that checks all 8 bits of `boot_word`, with `sig` constant and not a fault site and a known start state." Must contain the consumer width and the bound.

## Exercise 3 (15 points)
Predictions (3): after `opt_merge` the three comparators merge into one (not separate). Project recipe 2 flips; after `opt_merge` 1 flip. (Stored netlist: 3.)

| Netlist | Yosys | gates | hash | min flips |
|---|---|---|---|---|
| `$REF/v2.json` | n/a | 68 | 289355dc... | 3 |
| `edu_work/v2_plain.json` | 0.33 | **85** | f954078f... (full sha256 in the log) | **2** (k=1: NO_ATTACK, exit 0; k=2: ATTACK_FOUND, exit 1) |
| `edu_work/v2_merge.json` | 0.33 | **63** | d776226e... | **1** (k=1: ATTACK_FOUND at `$flatten\c0...@1`) |

Expected hashes and gate counts are for **Yosys 0.33** only. A student with another Yosys may get different counts (the project saw 83 gates and a minimum of 3 on a conda Yosys 0.38 build, and the same 83 gates with no 2-flip attack on Debian's Yosys 0.52 in Docker (H5); not a version effect: Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, not the underlying weakness. (`docs/report/WHY_TWO_FLIPS.md`); `research/c2/e2_variance/E2_REPORT.md`; not reproducible here because only 0.33 was installed). Accept any answer consistent with the student's own recorded version and hash. The relation "plain > merge" in minimum flips must hold (E2 reports minimum 1 for its `opt_merge`-after-flatten configurations).
a. The solver reads the netlist; synthesis chooses the netlist; the same RTL gives different netlists (68, 85, 63 gates here) and different minimum flips (3, 2, 1). Full marks: mentions that the tool prints the hash and the Yosys build.
b. `(* keep_hierarchy *)` on `cmp8` makes ABC optimise each copy separately before flatten; `opt_merge` after flatten sees three identical gates on the same input and keeps one (common-subexpression elimination), so one flip on the merged net decides every result bit.
c. Any of: a full `synth` / `opt` step, `abc` with `-dff` or without hierarchy preserved, a P&R or resizing step, a retiming or duplicate-register removal pass (these last ones are plausible but UNVERIFIED here). (E2 found `opt_merge`, `flatten` before ABC, `abc -dff` collapse V2 to 1 flip in its 864-configuration grid. Whether a particular commercial flow does so is UNVERIFIED here.)

## Exercise 4 (15 points)
Rule B is `edu_scope.py` only (not in the product; say so to students). Rule A cross-check with the shipped CLI (`--max-flips 2` on `v2_plain.json`): 2 flips, `$abc$275$new_n58_@0, $abc$275$new_n74_@0`, equal to the wrapper.

| Netlist | rule | min_cost | fanout cost of flipped nets |
|---|---|---|---|
| v2_plain | A (unit) | **2** | 3 and 2 (a flip of a net that feeds 3 sink pins and one that feeds 2) |
| v2_plain | B (fanout) | **3** | 1, 1, 1 (three flips of single-fanout nets) |
| v2_merge | B (fanout) | **1** | 1 |

(Also measured: stored V2: 3 under both rules; `v2_merge` rule A = 1, from Exercise 3.)
a. Prediction: higher or equal (full marks for either "higher" with reasoning; measured: higher, 3 versus 2). Explanation: the cheap 2-flip attack uses two nets with fanout 3 and 2, i.e. cost 5 under rule B; B must pick a different attack of three single-fanout flips, so its minimum is 3. The stem rule rewards hitting a wide net.
b. The merged net is the single point of failure and has fanout 1 (cost 1 under either rule) so both rules agree on 1.
c. Any two of: different Yosys build or flow (68 / 85 / 63 gates), different consumer width (mask), different counting rule (stem vs fanout), different scope (goal `boot_ok`, inputs as fault sites, start state), different bound. Both statements are "right" for their own scope.

## Exercise 5 (25 points)
1. `mini_v1.json`: ATTACK_FOUND, exit 1, hash `b3b890da...`, 39 gates, attack on `ok@1` (3 points).
2. Valid design (8 points): `faultbound-wt` does not exit 3 on the edited `.v`.
3. Reference solution (not given to students): `$D/mini_v2.v` with the module renamed `mini1`. Measured as `mini_v2`: 45 gates, hash `dc7cee25...`; k=1 exit 0 (NO_ATTACK_UP_TO_BOUND), k=2 exit 1 (minimum **2**, e.g. `boot_word[2]@1` plus a comparator-side net at cycle 4). Typical student ideas and their measured/expected fates:
   - Three copies with per-bit assignment (= `mini_v2`): passes at k=1, min 2.
   - Add a third copy but still recombine with one AND/OR/majority gate: a single point remains: min 1 (the combined net).
   - Add `(* keep *)` attributes only: no structural change; min 1.
   Grading for the 6 points: consistent record of gates, hash, exits and minimum. Award the pass automatically if exit at k=1 is 0.
4. `mini_v2` after `synth_merge.sh`: 33 gates, hash `b07856cf...`, k=1 ATTACK_FOUND (`c0.m@1`), i.e. **it does not survive** `opt_merge`. Expect most good designs not to survive; full marks for an honest "yes/no" with the recorded exit code. The two-sentence text: look for (i) the single remaining wire (the voter/comparator shared net), (ii) scope = bound 1 flip, 6 cycles, goal `boot_word == 9`, `sig` != 5, hash.

## Exercise 6 (15 points)
Prediction (3): 1.
a. `boot_ok@1` on the stored V2 (1 flip, ATTACK_FOUND, exit 1); `boot_ok` is a single AND-style net derived from the whole state register and one flip on it makes the flag 1, regardless of the word's protection. The data word is not the decision: the asset must be defined first. For `mini_v2` the flag attack is also 1 flip (`boot_ok@0`).
b. Because the honest input must reach the goal in the fault-free design; if `sig = 7` cannot make `boot_word == 9`, any "attack" or "no attack" is about a meaningless setup. Exit 3 with `error: CONFIGURATION PROBLEM: the honest input does not reach the goal`.
c. Any two of: inputs that change per cycle; power-up/unknown state; other fault types (stuck-at, multi-bit, clock/voltage); more flips or more cycles than the bound; other netlists of the same RTL; physical feasibility; larger designs; the consumer or counting rule not modelled.

## Exercise 7 (extension, 10 points): width curve
Prediction (2): accept any monotone guess; the measured curve for V2 is not a copy count. V1 (MEASURED, below): 0,1,1,1,1,1,1,1, flat at 1 because every bit hangs on `ok`; award the points for a reasoned guess.
Command: `faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --sweep-widths` (netlist `289355dc...`, 18 s, exit 1).

| n | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| V2 stored, min flips | **0** | **1** | **1** | **2** | **2** | **3** | **3** | **3** |
| mini_v2 (`mini.toml`, `mini2`, hash `dc7cee25...`) | **0** | **1** | **2** | **2** | | | | - |

(MEASURED; V2 row equals the PS5 report and `m1_all_masks.csv` for masks 0x01..0xFF. V1 stored (`--max-flips 3 --sweep-widths`, hash `84730fa7...`): 0,1,1,1,1,1,1,1. The `--sweep-out` CSV has one row per n.)
a. 0 flips: the consumer reads only bit 0, whose accept value is 0, and the idle (fault-free) state already looks like acceptance on that bit (M1 calls these collisions). Not a fault-tolerance result; it says the consumer is too narrow to discriminate. 3 points.
b. Touched copies by n: n=1: m0; n=2: m0,m1; n=3..: all three, but the measured cost at n=3 is 1 (the idle-state route through a state bit, as for 0x1B), at n=4 it is 2 although all three copies are touched. Any n in {3,4,5} with the right reasoning is full marks. The hypothesis is only a rough guide.
c. The n=8 column (all bits); it says nothing about n=2..7, or the accept flag.

## Exercise 8 (extension, 10 points): scope sweep
Command: `faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --scope-sweep --sweep-masks 0x0F --cell-timeout-ms 120000` (13.5 s, exit 1), MEASURED:

| V2 row | none, known | all, known | none, arbitrary | all, arbitrary |
|---|---|---|---|---|
| boot_word == 0x96 | **3** | **1** | **0** | **0** |
| boot_word bits 0xF | **2** | **1** | **0** | **0** |
| boot_ok == 1 | **1** | **1** | **0** | **0** |
| mini_v2: boot_word == 9 | **2** | **1** | **0** | **0** |
| mini_v2: boot_ok == 1 | **1** | **1** | **0** | **0** |

(mini_v2 command: `faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini.toml --max-flips 3 --scope-sweep`, 3.4 s, exit 1.) V2 agrees with the PS4 report (word 3/1/0/0, bits 0xF 2/1/0/0, boot_ok 1/1/0/0).
a. Model answer: the table is not a score of the design; it is a map of how the claim moves with the scope. Cost falls (weakly) as the attacker gets more: a narrower consumer, a fault site on the input, a free start state. The number to quote is one cell with the scope next to it (for example "V2, all 8 bits, inputs not fault sites, known start state: 3 flips, k<=3, 6 cycles, hash 289355dc"). Not meant: that the design "needs" the row-minimum, or that the 0 cells are good or bad faults. Accept any answer that names (i) cells differ by scope, (ii) one cell is quoted with scope, bound and hash, (iii) 0 is a different statement.
b. With an arbitrary power-up state the flops may start in a state that already shows the goal value, so zero flips are needed; that says "no reset sequence is modelled", not that the design is weak against faults (the report says so). Neither good nor bad: not a fault result. (`--init free_nongoal` is the stricter variant, not used here.)
c. `in-sites=all, init=known`: a flip of one input net (seen by all its fanout) already changes the honest `sig` into the key, so 1 flip. (PS4: `c0.a[1]@1`, an input net.) Stem rule counts the shared input net once.

## Scoring summary
Ex1 15, Ex2 15, Ex3 15, Ex4 15, Ex5 25, Ex6 15 = 100; extension Ex7 10 + Ex8 10 = 20 more (120 if used; or treat them as bonus on top of 100). See the marking scheme in `INSTRUCTOR_NOTES.md`.

## Tool output reference (stored `$REF/v2.json`, bundled threat.toml, MEASURED)
`--max-flips 1`: NO_ATTACK_UP_TO_BOUND 0.3 s. `--max-flips 2`: NO_ATTACK_UP_TO_BOUND 1.9 s. `--max-flips 3`: ATTACK_FOUND 8.0 s (EDU2 re-run; the earlier run took 11.9 s), "MINIMUM ATTACK COST = 3 flips ... on 3 distinct net(s) in 1 distinct cycle(s)". Times are from one run on a small cloud VM (ESTIMATED for other machines).
