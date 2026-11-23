# OpenTitan counter: a real security block

**What it is.** prim_count from OpenTitan, an open-source security chip. It keeps every count twice, one copy counting up and one counting down, and raises err_o when they disagree.

**Why the protection matters.** Counters limit retries and prove that steps ran. A glitch that changes a count without anyone noticing can skip a limit.

**What it teaches.** A real industrial protection, checked by the same question. The plain counter falls to one glitch; OpenTitan's cross counter needs two (one on the counter, one on the error check).

## Expected results (MEASURED by `python3 scripts/run_examples.py`, stored in expected_results.json)

| command | smallest attack (within the horizon) | any number of cycles | other builds | analysed netlist = RTL in simulation |
|---|---|---|---|---|
| `glitchsat run --task naive` | 1 fault | proved for any number of cycles with 0 faults | - | yes |
| `glitchsat run` | 2 faults | proved for any number of cycles with 1 fault | - | yes |

The fault model is the same in every build: each build is normalised to plain D flip-flops plus gates, and a flip-flop's fault site is its stored value. Without Yosys, the Studio shows the saved full reports in `saved/` (labelled RECORDED).

The cross counter doubles the cost: the attacker must change the count and also silence the error check. Note the answer is bounded (5 cycles); the proof section says whether it also holds for any waiting time.
