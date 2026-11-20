# Worksheet: "Three guards, one wire"  (100 points + 20 extension points)

*Student name: ____________   Date: ________   Yosys version (`yosys -V`): ____________*

Work in your lab copy of the repository, in the virtualenv from the Lab guide. Every exercise uses the **shipped CLI** `faultbound-wt analyze` except the fanout-counting rule in Exercise 4 (research wrapper, not in the product). Faults are **modelled** single-cycle bit flips; nothing is physical. A result means "within the bound, under this model". Shorthand used below:
```
REF=reference/spike_netlists
CFG=product/src/faultbound_wt/examples/threat.toml     # goal: 8-bit boot_word == 0x96 while sig != 0xC3; 6 cycles
D=docs/edu/starter_designs
T=docs/edu/tools                                        # edu_scope.py: Exercise 4 only; synth_merge.sh: Exercises 3 and 5
mkdir -p edu_work
```
Designs: V0 = naive (one comparator), V1 = two comparators recombined by one AND, V2 = three comparators, each result bit follows one comparator. The consumer wants the 8-bit word `0x96` ("boot accepted"); the attacker holds any `sig` except the key `0xC3`.

"Minimum flips" = the smallest `k` for which `--max-flips k` prints `ATTACK_FOUND`. Exit code 1 means attack found, 0 means none up to the bound, 3 means your input or config is wrong.

---
## Exercise 1: predict, then measure (15 points)
**Predict** (before running; 1 point each, 3 points): minimum flips to reach `0x96` on V0 ____ , V1 ____ , V2 ____ . In one sentence, your reason for V1: ______________________________

**Run** (V2 with `--max-flips 3` takes about 8 seconds):
```
for d in v0 v1 v2; do for k in 1 2 3; do
  faultbound-wt analyze $REF/$d.json --top $d --config $CFG --max-flips $k | head -2; done; done
```
Setup check (not the answer): the verdict lines show 18, 58 and 68 gates for V0, V1, V2.

| Design | verdict at k=1 | k=2 | k=3 | minimum flips | net(s) named in the minimum attack |
|---|---|---|---|---|---|
| V0 | | | | | |
| V1 | | | | | |
| V2 | | | | | |

Questions (12 points):
a. For V1, which net is the single point of failure, and how many of the 8 result bits does it decide? (4)  ______________
b. Why does V2 need more flips than V1, in terms of which wires the copies share? (4)  ______________
c. Write the scope of your V2 answer in one line, using the five fields printed after `scope:` (goal, inputs, init state, fault model, bounds) and the first 8 characters of the netlist hash. (4)  ______________

---
## Exercise 2: what does the consumer read? (15 points)
The consumer of V2 may check only some bits of the result word. `--consumer-bits 0x0F` means "only bits 3..0 must equal those of `0x96`". Bits of the word are made by the three comparator copies as in `rtl/v2.v`. Syntax (H2 change, 2026-11-19): `0x..`, `0b..` or a plain decimal number is a MASK (`15` = bits 0..3); a bit list is written `bits:3,5` or `[3,5]`. A bare `3` is mask 3 (bits 0 and 1), not bit 3. Every command in this worksheet uses `0x` masks.

**Predict** (3 points): for V2, mask `0x0F` needs ____ flips, mask `0x1B` needs ____ , mask `0x4E` needs ____ , mask `0xFF` needs ____ .

**Run** (shipped CLI; `--max-flips 3` is the search bound; 0xFF takes about 8 s, 0x4E about 4 s, the others about 1 s):
```
for m in 0xFF 0x0F 0x1B 0x4E; do echo "mask $m"; faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --consumer-bits $m | grep -E 'minimum attack|MINIMUM'| cut -c1-150; done
echo "V1 mask 0x0F"; faultbound-wt analyze $REF/v1.json --top v1 --config $CFG --max-flips 3 --consumer-bits 0x0F | grep -E 'minimum attack|MINIMUM' | cut -c1-150
```
Reading the output: the minimum number of flips is the number of `net@cycle` entries on the `minimum attack:` line (also printed as `MINIMUM ATTACK COST = N flips` when N is 2 or more). If a run prints `NO_ATTACK_UP_TO_BOUND`, write `>3`.
Setup check: all runs print `netlist sha256 289355dc...` (V2) and `84730fa7...` (V1) on the `scope:` line. `--consumer-bits 0xFF` must equal your V2 answer from Exercise 1 (all bits = no mask).

| Design | mask | min flips |
|---|---|---|
| V2 | 0xFF | |
| V2 | 0x0F | |
| V2 | 0x1B | |
| V2 | 0x4E | |
| V1 | 0x0F | |

Questions (12 points):
a. The "accept" consumer in the README reads one flag, not the word. Using the table, is "V2 needs 3 flips" a statement about V2, or about V2 plus one particular consumer? (4)  ______________
b. Mask `0x1B` is cheaper than `0x4E`. Using the comparator-to-bit map `sel = {m1,m0,m2,m1,m0,m2,m1,m0}` (bit 7 first), say which comparator copies each mask touches. (4)  ______________
c. Rewrite the claim "V2 resists 2 flips" so it is not misleading. (4)  ______________

---
## Exercise 3: the same RTL, two synthesis flows (15 points)
Project recipe (`product/scripts/yosys_flow.sh`) versus the same recipe plus one line, `opt_merge` after `flatten` (`$T/synth_merge.sh`). `opt_merge` merges gates that compute the same function of the same inputs.

**Predict** (3 points): after `opt_merge`, will the three comparators of V2 still be three separate gates? ____ Minimum flips for V2 with the project recipe ____ ; after `opt_merge` ____ .

**Run:**
```
product/scripts/yosys_flow.sh rtl/v2.v v2 edu_work/v2_plain.json
$T/synth_merge.sh rtl/v2.v v2 edu_work/v2_merge.json
for f in plain merge; do for k in 1 2; do
  faultbound-wt analyze edu_work/v2_$f.json --top v2 --config $CFG --max-flips $k | head -3; done; done
```
Setup check: with Yosys 0.33 the plain netlist has 85 gates (hash starts `f954078f`), the merged one 63 gates (hash starts `d776226e`). With a different Yosys build your hash and gate counts may differ: write down yours. The stored `$REF/v2.json` has 68 gates (hash `289355dc`): it is a third netlist of the same design.

| Netlist | Yosys | gates | hash (8 chars) | min flips |
|---|---|---|---|---|
| `$REF/v2.json` (stored) | n/a | 68 | 289355dc | (from Ex 1) |
| `edu_work/v2_plain.json` | | | | |
| `edu_work/v2_merge.json` | | | | |

Questions (12 points):
a. Why does the verdict belong to a netlist hash and not to `rtl/v2.v`? (4) ______________
b. In `rtl/v2.v` which attribute keeps the copies apart in the project recipe? What does the extra `opt_merge` line undo? (4) ______________
c. Name one place in a real flow where a tool might perform this kind of merge without you asking. (4) ______________

---
## Exercise 4: stem versus fanout counting (15 points)
Rule A (the headline rule, "stem = 1"): flipping a net is one fault, however many gates read it. Rule B (a stress test, "cost = fanout"): flipping a net with `f` sink pins costs `f` faults. Neither rule has been shown to be physical.

**Tool note.** Rule A is the shipped tool's counting rule (`--count-rule stem`, the default; `--count-rule branch` exits 3, not implemented). Rule B (fanout cost) is **not in the product**: this exercise uses the research wrapper `$T/edu_scope.py` (it imports `research/c3/m1/gs_mask.py` and re-implements the weighting of `research/c3/rep/scripts/rep_measure.py`; not independently reviewed). It is the only exercise that needs it.

**Run** (on the apt-style netlist from Exercise 3):
```
python3 $T/edu_scope.py edu_work/v2_plain.json v2 --rule unit
python3 $T/edu_scope.py edu_work/v2_plain.json v2 --rule fanout
python3 $T/edu_scope.py edu_work/v2_merge.json v2 --rule fanout
```
Cross-check of rule A with the shipped CLI (should print 2 flips): `faultbound-wt analyze edu_work/v2_plain.json --top v2 --config $CFG --max-flips 2 | grep -E 'minimum attack'`.
Each `edu_scope.py` run prints `min_cost`, the flips, and a line "flip net ids and their fanout cost". The numbers are net ids inside the solver, not names; the fanout cost is what you need.

| Netlist | rule | min_cost | fanout cost of each flipped net |
|---|---|---|---|
| v2_plain | A (unit) | | |
| v2_plain | B (fanout) | | |
| v2_merge | B (fanout) | | |

Questions (15 points, 5 each, including the prediction):
a. **Predict first:** for `v2_plain`, will rule B give a higher, lower or equal minimum than rule A? ____ Then explain the measured difference using the "fanout cost" line of the rule A attack. ______________
b. For `v2_merge`, rules A and B agree. Why does the merged netlist give the same number under both? ______________
c. A colleague says "V2 needs 3 flips" and another says "V2 needs 2". List two different reasons in this lab that could both be right. ______________

---
## Exercise 5: design a variant and test it (25 points)
`$D/mini_v1.v` is a 4-bit version of V1 (key `4'h5`): two comparators and one shared AND `ok`. Threat config: `$D/mini.toml` (goal `boot_word == 9` while `sig != 5`, 6 cycles). The aim: edit a copy so that **one** flip no longer suffices.

1. Measure the starting point (3 points):
```
faultbound-wt analyze $D/mini_v1.json --top mini1 --config $D/mini.toml --max-flips 1 ; echo "exit $?"
```
Setup check: the exit status printed is 1; the netlist hash starts `b3b890da`; minimum attack names `ok`.

2. Copy `mini_v1.v` to `edu_work/mine.v` (keep the module name `mini1`). Edit it. You may add copies, change how the result bits are formed, or anything else that keeps the honest path working. Do not edit the config. (8 points for a valid design: the tool must not exit 3.)
3. Test with the project recipe (the tool calls Yosys itself on a `.v` file):
```
faultbound-wt analyze edu_work/mine.v --top mini1 --config $D/mini.toml --max-flips 1 ; echo "exit $?"
faultbound-wt analyze edu_work/mine.v --top mini1 --config $D/mini.toml --max-flips 2 ; echo "exit $?"
```
Record: gates ____ , hash prefix ____ , exit at k=1 ____ (0 = no attack with 1 flip), exit at k=2 ____ , minimum flips ____ , nets of the minimum attack ____ . (6 points)
4. Re-test your design after an extra `opt_merge`:
```
$T/synth_merge.sh edu_work/mine.v mini1 edu_work/mine_merge.json
faultbound-wt analyze edu_work/mine_merge.json --top mini1 --config $D/mini.toml --max-flips 1 ; echo "exit $?"
```
Does your design survive? ____ (4 points) Write two sentences: what you changed, which single wire you think is the next weakest, and the scope of your claim (bound, goal, hash). (4 points) ______________

Autograder-style line: a design "passes" when step 3 at `--max-flips 1` exits 0. A pass is not "secure": it is "no attack with 1 flip within 6 cycles on this netlist".

---
## Exercise 6: which asset, and is the setup honest? (15 points)
**Predict** (3 points): if the goal is the single accept flag `boot_ok == 1` instead of the whole word, V2 needs ____ flips.

**Run:**
```
faultbound-wt analyze $REF/v2.json --top v2 --config $D/v2_bootok.toml --max-flips 1 | head -3
faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini_bootok.toml --max-flips 1 | head -3
sed 's/legitimate_value = 5/legitimate_value = 7/' $D/mini.toml > edu_work/bad.toml
faultbound-wt analyze $D/mini_v2.json --top mini2 --config edu_work/bad.toml --max-flips 1 ; echo "exit $?"
```
Setup check: the third command prints a message beginning `error: CONFIGURATION PROBLEM` and exit 3.

Questions (12 points):
a. Name the net of the minimum attack on the accept flag in the first command, and say in one line why protecting the 8 data bits did not protect the decision. (4) ______________
b. Why does the tool refuse the `legitimate_value = 7` configuration instead of answering? (4) ______________
c. Name two things a "no attack up to the bound" answer does **not** tell you about a real chip. (4) ______________

---

## Exercise 7 (extension, 10 points): flips versus consumer width
`--sweep-widths` asks, for n = 1..W, how many flips are needed if the consumer reads only the lowest n bits of the goal output (mask `0x1`, `0x3`, `0x7`, ... ), in one fixed scope (`--input-sites none`, `--init known` unless you change them).

**Predict** (2 points): sketch the curve for V2 (n = 1..8) as 8 numbers: ______________ ; and for V1 you expect: ______________

**Run:**
```
faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --sweep-widths --sweep-out edu_work/widths_v2.csv
faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini.toml --max-flips 3 --sweep-widths
faultbound-wt analyze $REF/v1.json --top v1 --config $CFG --max-flips 3 --sweep-widths    # optional
```
(about 18 s and 2 s). The table prints `n | mask | min flips | time`. A value of `>3` would mean no attack up to 3.

| n | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| V2 stored, min flips | | | | | | | | |
| V1 stored (optional, 2 s) | | | | | | | | |
| mini_v2 (n = 1..4 only) | | | | | | | | - |

Questions (8 points):
a. n = 1 prints 0 flips. Bit 0 of `0x96` is 0. What does "0 flips" mean here, and is it a result about fault tolerance? (3) ______________
b. Test the hypothesis "cost = number of comparator copies the mask touches" with the map from Exercise 2 b. Give one n where it fails. (3) ______________
c. A designer says "V2 needs 3 flips". Which row of your table is that, and which rows does it not cover? (2) ______________

---
## Exercise 8 (extension, 10 points): the scope sweep
`--scope-sweep` runs a whole matrix goal x input-sites x init and prints one table of minimum flips (`>k` none up to k, `unknown` solver timeout, which is **not** "no attack").

**Run** (about 14 s on V2):
```
faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --scope-sweep --sweep-masks 0x0F --cell-timeout-ms 120000 --sweep-out edu_work/sweep_v2.csv
faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini.toml --max-flips 3 --scope-sweep
```
Columns are the four scopes `in-sites=none|all` x `init=known|arbitrary`. `in-sites=all` makes every input bit a fault site; `init=arbitrary` lets every flop power up in any state.

| V2 row | none, known | all, known | none, arbitrary | all, arbitrary |
|---|---|---|---|---|
| boot_word == 0x96 | | | | |
| boot_word bits 0xF | | | | |
| boot_ok == 1 | | | | |
| mini_v2: boot_word == 9 | | | | |
| mini_v2: boot_ok == 1 | | | | |

Questions (8 points; 2 points of the Ex 8 total are for the table):
a. Discussion: the same netlist has cells from 0 to 3. What does the table as a whole mean, and what does it not mean? Which single cell would you quote in a report, and what must you write next to it? (4) ______________
b. Why is every `init=arbitrary` cell 0 for every goal? Is the 0 a good or a bad sign for the design? (2) ______________
c. Which column is the most favourable to the attacker among those that are still a *fault* result (not a no-reset artefact)? Say why one flip is enough there. (2) ______________

---
**Self-check before handing in:** every number has its command; every verdict has its netlist hash prefix; nowhere do you write "secure", "safe" or "proved".
