# Real standard cells (SkyWater sky130)

**What it is.** The hello lock after it was turned into real SkyWater sky130 logic cells, the way a chip factory receives it. No Verilog source is needed: only the cell netlist and the cell library.

**Why the protection matters.** The chip that is made is the cell netlist, not the source code. Protections must survive into it.

**What it teaches.** GlitchSAT reads what each cell does from the library file, checks every cell by its truth table, and asks the same question on the real cells.

## Expected results (MEASURED by `python3 scripts/run_examples.py`, stored in expected_results.json)

| command | smallest attack (within the horizon) | any number of cycles | other builds | analysed netlist = RTL in simulation |
|---|---|---|---|---|
| `glitchsat run` | 1 fault | proved for any number of cycles with 0 faults | - | yes |
| `glitchsat run --task hardened` | no attack with up to 2 faults | proved for any number of cycles with 2 faults | - | yes |

The fault model is the same in every build: each build is normalised to plain D flip-flops plus gates, and a flip-flop's fault site is its stored value. Without Yosys, the Studio shows the saved full reports in `saved/` (labelled RECORDED).

Same answers as for the Verilog version, now on factory cells: the protected lock's three checks survived into this sky130 netlist because it was mapped one module at a time. A flow that flattens before optimising (LibreLane's default, like the hello lock's `synth` build) can merge the three copies, so always check the netlist that is really made. These netlists also use the isolation cell lpflow_inputiso1p as a plain OR gate; real flows list lpflow cells as don't-use. Needs the sky130 library on this computer (scripts/fetch_libs.sh).
