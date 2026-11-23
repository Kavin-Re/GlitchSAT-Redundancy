# Hello lock: the smallest lock

**What it is.** A door lock on a chip: it opens when someone types the secret code A5. In the protected version, three separate checks must all agree.

**Why the protection matters.** If one wire decides 'open', one glitch on that wire opens the door without the code.

**What it teaches.** Redundancy only helps when the copies are really separate: one glitch beats one check, but not three.

## Expected results (MEASURED by `python3 scripts/run_examples.py`, stored in expected_results.json)

| command | smallest attack (within the horizon) | any number of cycles | other builds | analysed netlist = RTL in simulation |
|---|---|---|---|---|
| `glitchsat run` | 1 fault | proved for any number of cycles with 0 faults | - | yes |
| `glitchsat run glitchsat_hardened.yaml` | 3 faults | proved for any number of cycles with 2 faults | plain: 3, synth: 1, synth-keep: 3 | yes |

The fault model is the same in every build: each build is normalised to plain D flip-flops plus gates, and a flip-flop's fault site is its stored value. Without Yosys, the Studio shows the saved full reports in `saved/` (labelled RECORDED).

Compare the two runs. The weak lock opens with a single glitch on its one 'open' flip-flop. The protected lock needs three glitches, one per copy, as long as the copies stay separate. Look at 'Did the protection survive the build?': the optimising build (synth) merges the three copies into one, and the lock is weak again. The fix is named under 'What to do': keep the copies in separate modules and stop the tool from merging them, then check the final netlist again.
