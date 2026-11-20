# Poster text (one page)
Working title TBD.

## Picture: how one shared wire can beat three guards

**Where do the copies meet?**

*Model only: a small model checked on a computer. Nothing physical, no real product.*

**The picture (drawn, not computed, not a result).** A lock has three guards. All three answers go down one shared wire. A flip is a glitch that turns one 0 into 1, or one 1 into 0, for one clock tick. Flip that wire and, in the drawing, the door opens: one flip beats all three.

**Why you might care.** Any device that protects a decision with several guards can be fooled if the guards share one wire. Here is how to check.

**With separate wires.** In the picture it takes 3 flips. MEASURED on a small design: 3 flips for the 8-light result word.

**In the designs we tested (one recipe family; measured).** Of 32 rebuilds of one design (one recipe, not 32 independent designs), 26 needed 2 flips and 6 needed 3. Count a wire once per place it feeds and all 32 needed 3. We found no check of which counting matches real hardware.

**Ask a supplier.** Where do the copies meet? How do you count a fault? What is checked at the end: the finished wiring, and which outputs? These are prompts, not a pass/fail standard.

**Limits.** Caveat for every number: result word only; the separate accept flag falls to 1 flip. A power dip makes outputs fall (1 to 0); a push the other way (0 to 1) on the three copies breaks even the guarded designs with one event in our model (a modelled domain in the wiring hierarchy, not a physical rail; no physical test was done); which is realistic depends on the attack. Known start, inputs not attacked, up to 3 flips. No tracking. Licence undecided.

**Try it:** game.html, about 2 minutes, offline.
