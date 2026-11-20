# Solver Replay Theatre: 3-minute stage script

License: Apache-2.0. GlitchSAT. For the owner to edit and time aloud.

Page: `docs/wow/theatre.html` (offline, one file). Keys: Space or Right = next step, Left = back, R = reset, P = play.
Booth loop: open `theatre.html?kiosk=1`. Every number on screen comes from `docs/wow/witness.json`
(MEASURED solver output and SIMULATED gate-level replay on the stored netlists; command: `python3 scripts/export_witness.py`).

Say "flip" (one wire inverted for one clock tick, in the model). Do not say "glitch a chip". Nothing here touched hardware.

| Time | Show | Say (plain words) |
|---|---|---|
| 0:00 | Step 1 on screen | "This is a toy lock. It checks an 8-bit key. Left: the check is done twice. Right: it is done three times. What you will see is a replay of the solver's witness in a gate-level simulation, not a real chip." |
| 0:20 | Step 1, point at the strips | "No flips yet. Right key: the boot word goes to 0x96, which means open, at tick 2. Wrong key: it goes to 0x69, shut. Both locks do their job." |
| 0:40 | Press Space: step 2 | "Now we ask the solver: what is the smallest number of flips that opens the lock with a wrong key? For the left lock it answers: one. The wire is called `ok`, the tick is 1." |
| 0:55 | Point at the red wire, then the lower strip | "Both checks said no. But both feed this one wire. We replay the solver's answer in the simulator: the red block is the flip, and one tick later the boot word reads open. Two checks on one wire behave like one check." |
| 1:20 | Press Space: step 3, right side, green box | "Right lock, three copies. The solver looked at all 456 places a flip could go, 76 wires times 6 ticks. Result: no 1- or 2-flip attack found within 6 ticks. That is a bounded statement about this one stored netlist, nothing more." |
| 1:45 | Scroll to the red box and strips on the right | "With three flips it does find one: one wire per copy, all at tick 1. Replayed: the lock opens. So separating the wires raised the cost from one flip to three." |
| 2:10 | Press Space: step 4 | "One caveat. The lock also has a one-bit accept flag. If the next stage reads only that flag, the solver needs one flip again: the flag wire itself, at tick 3. Look: the boot word stays shut, the flag reads open for one tick. The reader is a wire too." |
| 2:35 | Press Space: step 5 | "What we did NOT show: no hardware; nothing beyond 6 ticks and 3 flips; one stored netlist per design, and a fresh build of the same V2 source needs only 2 flips; one fault model. The diagrams are simplified drawings; the strips are the recorded simulation." |
| 2:55 | Leave step 5 up | "Every frame names its source file, its netlist checksum and the command. You can re-run it." |

Fallbacks
- If the keyboard fails: the Step button and the buttons 1 to 5 do the same.
- If asked "is V2 then fine?": answer "No attack with 1 or 2 flips was found within 6 ticks on this stored netlist. That is all the page says."
- If asked "are the waveforms real?": "They are parsed from the VCD file the simulator wrote during the replay. The small schematics are hand-drawn."
- If asked about the different wire names in other project tables: the solver returns one smallest witness; another run or version can name different wires with the same count (the stored `results/reproduce_summary.json` row lists three different V2 wires; see research/c6/p21/P21_REPORT.md).

Numbers used above and where they come from (all in `docs/wow/witness.json`):
- V1 one flip, `ok`, tick 1: MEASURED, `python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6`.
- V2 none found with at most 1 and at most 2 flips, 456 sites: MEASURED, same command with `v2`, `--k 1` and `--k 2`.
- V2 three flips: MEASURED, `--k 3`. V2 accept flag one flip: MEASURED, `--k 1 --goal-out boot_ok --goal-value 1`.
- "Opens at tick 2 / tick 3": SIMULATED, gate-level replay with `scripts/replay.py` (iverilog), re-checked by `docs/wow/check_theatre.py`.
- "A fresh build of V2 needs only 2 flips": MEASURED, `results/reproduce_summary.json` row (v2, rtl/plain); not replayed in the theatre.
