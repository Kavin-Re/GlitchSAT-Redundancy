# Lab 4: "The code and its decoder" (45 minutes; timings ESTIMATED, UNPILOTED)


**Model only.** A "flip" is an XOR on one net for one cycle in a gate-level model. No chip, no glitch, no voltage, no bit-error rates. Every solver verdict is "bounded result under this model; not a proof of security".

## Learning outcomes
1. Show by hand that the state words F0, CC, 96, 69 (and the key C3) of `rtl/v1.v`/`rtl/v2.v` are codewords of RM(1,3), and state the bit-order convention used.
2. Compute the minimum distance d of RM(1,3) and of the state code, and predict the flops-only flip cost from d.
3. Measure the cost when the decoder wires are also fault sites, and explain the gap.
4. Explain why the complementary pair 96/69 is best against random flips and worst against one all-flop burst.

## Setup (5 min), in a copy of the repository
```
cp -r <project> ~/lab4 && cd ~/lab4
python3 -m venv .venv && . .venv/bin/activate && pip install ./product pytest
faultbound-wt analyze --help        # check: --consumer-bits, --max-flips, --cycles, --top exist
```
Note for the instructor (checked against `faultbound-wt analyze --help`, version 0.0.1.dev0): **the product CLI has no "flops only" fault-site option.** The flops-only measurement uses the repository script `docs/dossier/test_hamming.py` (it imports `scripts/glitchsat.py`, so run it from the repository copy). The product CLI measures the all-nets cost and the narrow-consumer cost.

## Part A: membership by hand (10 min)
Convention: bit i of a byte (bit 0 = least significant) is the value f(x) at x = (x2, x1, x0) = binary(i). RM(1,3) = all affine functions c + a0 x0 + a1 x1 + a2 x2, i.e. the span of 0xFF, 0x0F, 0x33, 0x55.
1. Write the truth tables of x0, x1, x2 as bytes. (Expected: 0xAA, 0xCC, 0xF0.)
2. Express each of F0, CC, 96, 69, C3 as an XOR of generator rows. (Expected: F0 = FF+0F; CC = FF+33; 69 = 0F+33+55; 96 = FF+0F+33+55; C3 = FF+0F+33.)
3. Reverse the bit order of 96 (MSB-first reading). Is it still a codeword? Why does that hold for every codeword? (Hint: reversing i to 7-i is x -> x + (1,1,1), an affine change of variables.)
4. List the weights of all 16 codewords. (Expected: one of weight 0, fourteen of weight 4, one of weight 8, so d = 4.)
5. Compute the six pairwise distances of {F0, CC, 96, 69}. (Expected: 4, 4, 4, 4, 4 and 8 for 96/69.)

Check with the test: `python3 -m pytest -q -s docs/comms/test_rm13.py` (expect 16 passed; reference output `research/c6/p13/test_output.txt`).

## Part B: predict, then measure (20 min)
Write your predictions in the first column **before** running anything.

| # | design / scope | your prediction | command | measured (reference run, P13a) |
|---|---|---|---|---|
| 1 | V1, only the 8 state flops may flip | ___ (hint: d) | `python3 docs/dossier/test_hamming.py . reference/spike_netlists/v1.json v1 6` (line "state-flop-Q only") | 4 |
| 2 | V2, only the 8 state flops may flip | ___ | `python3 docs/dossier/test_hamming.py . reference/spike_netlists/v2.json v2 6` | 4 |
| 3 | V1, all nets | ___ | `faultbound-wt analyze reference/spike_netlists/v1.json --top v1 --max-flips 3 --cycles 6` | 1 (`ok`@1) |
| 4 | V2, all nets | ___ | `faultbound-wt analyze reference/spike_netlists/v2.json --top v2 --max-flips 3 --cycles 6` | 3 (one node in each comparator copy, cycle 1) |
| 5 | V2, consumer reads bits 0..3 only | ___ (hint: distance from F0 or CC to 96 on those bits) | `faultbound-wt analyze reference/spike_netlists/v2.json --top v2 --max-flips 3 --cycles 6 --consumer-bits 0x0F` | 2 (both flips on state flops) |
| 6 | V2, consumer reads bits 1,2,3,6 | ___ | same with `--consumer-bits 0x4E` | 3 (all on state flops) |

Reference values are MEASURED by step P13a on the stored spike netlists, T=6, stem counting, known init (`research/c6/p13/hamming_runs.txt`, `cli_runs.txt`, `cli_masks.txt`); each run takes under a second except the `test_hamming.py` runs (a few seconds to a minute). Exit code 1 means "attack found"; that is the expected result here, not an error.

Questions: (a) Rows 1 and 2 are the same; rows 3 and 4 differ. What changed between the two scopes? (b) In row 3, what does the single flipped net have in common with "a point where all codewords decode alike"? (c) In rows 5 and 6 the cheapest attack uses only flops, unlike row 4. Why? (Answer: a narrow consumer reads a punctured code with smaller distance, so the flop route becomes cheaper than flipping the comparator copies.)

## Part C: burst against random (10 min)
1. Under independent random flips, which pair of state words is hardest to confuse? (96/69, distance 8.)
2. Compute 0x69 xor 0xFF. What does one event that inverts all eight state flops do to a design sitting in FAIL? (It reaches 96. FAIL holds itself in the RTL, so the event can come at any later cycle.) This is arithmetic only; the circuit-level burst measurement is pending (P14).
3. Interleaving: in V2, `sel = {m1,m0,m2,m1,m0,m2,m1,m0}`. Which copies own the bits that differ between CC and 96 (0x5A)? (Only m0 and m1.) Discuss: what would "place the copies apart" mean for an event that hits one region of the chip? Do not claim an answer about real chips.
4. Discussion: random, burst and adversarial channels rank the same codes differently. Give one example of each from this lab.

## Instructor answer notes
- Correct predictions: rows 1, 2: 4 (= d); row 3: 1; row 4: 3; row 5: 2; row 6: 3. A student who predicts 4 for row 4 has applied the code bound to a scope where it does not hold: the decoder is a fault site.
- Expected failure points: forgetting to run from the repository root (row 1, 2 import error); reading exit code 1 as a crash.
- What students may not conclude: that the designers chose RM(1,3); anything about physical glitch rates; that 4 is a guarantee beyond T=6 and these netlists.
