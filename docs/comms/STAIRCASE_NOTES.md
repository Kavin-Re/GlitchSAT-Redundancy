# Staircase notes: a boot check read as a code

Numbers MEASURED by `scripts/comms/distance_sweep.py` (product CLI, stem rule, goal `boot_word == W`, T = 6, k <= min(d,6), yosys 0.33); data: `results/comms/distance_sweep.csv`. Modelled flips on a toy design; observed, not a theorem; no physical meaning; nothing established as new.

## In plain words
The boot machine keeps an 8-bit state word. It waits in an idle word I and is accepted only when the word equals the accept word W. An attacker who can flip stored bits must change every bit in which the word it sits on differs from W. That count is the Hamming distance. The words are a code; its distance is the fault budget.

The word is written by a small decoder: three copies of a key comparator, each owning a group of bits. Flip one comparator output and all bits of its group move together. So the decoder sets a ceiling: about one flip per copy that must be fooled.

## What a communications professor sees in the figure (`staircase.png`)
- **Diagonal (flops only).** With only the register bits as fault sites the minimum equals the distance from the nearest non-accept word to W in all 15 codebooks with distance <= 6. Above 6: no attack found up to 6 (a bound, not "safe").
- **The nearest word counts, not the idle word.** Two codebooks have idle at distance 8 but a fail word at distance 3 or 6; the measured value is 3 or 6. The budget is the minimum distance of the whole code.
- **Ceiling (all nets).** With every net a fault site the curve follows the diagonal up to 3 and then stays flat at 3 from distance 3 to 8: three comparator copies, three flips. Complementary pairs (distance 8) gain nothing over distance 3.
- **Grouping = which bits fail together.** Each copy is like a burst-error channel for the bits it owns. If the fail and accept words differ only in bits of one copy, one flip is enough (measured 1); two copies, 2; if one copy owns all eight bits, 1 at any distance. The rule "minimum over copy subsets S of |S| + differing bits not owned by S, or the plain distance if smaller" matched all 19 netlists built without ABC.
- **The synthesiser can lower the ceiling.** With the project flow (ABC) three of the four distance-4 two-step codebooks gave 2 instead of 3; the fourth (CC/96) and all others gave 3. The witnesses use ABC-created shared nodes; cause not analysed further.

## Reading for a designer
Report three numbers: minimum code distance, number of decoder copies that must all be fooled, and the value measured on the actual netlist (it can be lower than both).

## Limits
Toy design, 19 codebooks, full-word consumer, T = 6, k <= 6, stem rule, input nets not fault sites, known power-up state. `>6` is unknown above 6.
