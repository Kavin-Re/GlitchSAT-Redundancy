# Secure boot: never run a fake program

**What it is.** The boot check of a small processor: it compares the program's signature (an 8-bit tag here) with the expected one and answers ACCEPT or REJECT.

**Why the protection matters.** If a glitch makes the check say ACCEPT for a wrong signature, the chip runs the attacker's program.

**What it teaches.** How many glitches a real protection (three compares, each owning its own state bits, plus an alarm) forces the attacker to use.

## Expected results (MEASURED by `python3 scripts/run_examples.py`, stored in expected_results.json)

| command | smallest attack (within the horizon) | any number of cycles | other builds | analysed netlist = RTL in simulation |
|---|---|---|---|---|
| `glitchsat run` | 1 fault | proved for any number of cycles with 0 faults | plain: 1, synth: 1 | yes |
| `glitchsat run --task hardened` | 3 faults | not decided in the time limit | plain: 3, synth: 3 | yes |

The fault model is the same in every build: each build is normalised to plain D flip-flops plus gates, and a flip-flop's fault site is its stored value. Without Yosys, the Studio shows the saved full reports in `saved/` (labelled RECORDED).

One compare falls to one glitch. Three compares plus an alarm need three well-timed glitches: the protection raises the cost, it does not make the attack impossible. More glitches at the right moments are much harder to do in a laboratory.
